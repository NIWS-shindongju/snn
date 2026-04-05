"""HybridRouter: SNN-first classifier with CNN fallback for low-confidence tiles.

Reduces inference cost by routing only uncertain tiles (confidence < threshold)
through the heavier CNN fallback.
"""

import logging
import time
from dataclasses import dataclass, field

import torch
import torch.nn as nn

from spikeeo.core.snn_backbone import SNNBackbone

logger = logging.getLogger(__name__)


@dataclass
class CostReport:
    """Summary of inference routing statistics.

    Attributes:
        total_tiles: Total tiles processed.
        snn_tiles: Tiles handled by SNN only.
        cnn_tiles: Tiles re-classified by CNN fallback.
        snn_pct: Percentage handled by SNN.
        cnn_pct: Percentage routed to CNN.
        cost_saving_pct: Estimated cost saving vs. all-CNN baseline.
        snn_latency_ms: Cumulative SNN inference time (ms).
        cnn_latency_ms: Cumulative CNN inference time (ms).
        cnn_cost_multiplier: CNN cost per tile relative to SNN (default 5x).
    """

    total_tiles: int = 0
    snn_tiles: int = 0
    cnn_tiles: int = 0
    snn_pct: float = 0.0
    cnn_pct: float = 0.0
    cost_saving_pct: float = 0.0
    snn_latency_ms: float = 0.0
    cnn_latency_ms: float = 0.0
    cnn_cost_multiplier: float = 5.0

    def __str__(self) -> str:
        return (
            f"SNN {self.snn_pct:.0f}%, CNN {self.cnn_pct:.0f}%, "
            f"cost saving {self.cost_saving_pct:.0f}%"
        )


class HybridRouter(nn.Module):
    """SNN-first inference router with CNN fallback for uncertain tiles.

    Workflow:
        1. Run all tiles through SNNBackbone.
        2. Identify tiles where max softmax probability < confidence_threshold.
        3. Re-classify those tiles with the CNN fallback.
        4. Merge results and track routing statistics.

    Args:
        snn: Pre-initialised SNNBackbone instance.
        cnn: Optional CNN fallback (auto-creates CNNFallback if None).
        confidence_threshold: Minimum SNN confidence to skip CNN re-scoring.
        cnn_cost_multiplier: Relative cost of CNN inference vs. SNN (default 5x).
    """

    def __init__(
        self,
        snn: SNNBackbone,
        cnn: nn.Module | None = None,
        confidence_threshold: float = 0.75,
        cnn_cost_multiplier: float = 5.0,
    ) -> None:
        super().__init__()
        self.snn = snn

        if cnn is None:
            from spikeeo.core.cnn_fallback import CNNFallback
            cnn = CNNFallback(num_bands=snn.num_bands, num_classes=snn.num_classes)
        self.cnn = cnn

        self.confidence_threshold = confidence_threshold
        self.cnn_cost_multiplier = cnn_cost_multiplier

        # Running cost statistics
        self._total_tiles: int = 0
        self._snn_tiles: int = 0
        self._cnn_tiles: int = 0
        self._snn_latency_ms: float = 0.0
        self._cnn_latency_ms: float = 0.0

        logger.info(
            "HybridRouter initialised | threshold=%.2f cnn_cost=%.1fx",
            confidence_threshold,
            cnn_cost_multiplier,
        )

    @torch.no_grad()
    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Classify a batch of tiles with SNN+CNN hybrid routing.

        Args:
            x: Input tensor (B, num_bands, H, W).

        Returns:
            Tuple of (class_ids (B,), confidences (B,)).
        """
        batch_size = x.size(0)
        self._total_tiles += batch_size

        # SNN inference
        t0 = time.perf_counter()
        snn_class_ids, snn_confidences = self.snn.predict(x)
        self._snn_latency_ms += (time.perf_counter() - t0) * 1000.0

        # Route low-confidence tiles to CNN
        low_conf_mask: torch.Tensor = snn_confidences < self.confidence_threshold
        num_low = int(low_conf_mask.sum().item())

        final_class_ids = snn_class_ids.clone()
        final_confidences = snn_confidences.clone()

        self._snn_tiles += batch_size - num_low
        self._cnn_tiles += num_low

        if num_low > 0:
            x_low = x[low_conf_mask]
            t1 = time.perf_counter()
            self.cnn.eval()
            cnn_logits = self.cnn(x_low)
            self._cnn_latency_ms += (time.perf_counter() - t1) * 1000.0

            cnn_probs = torch.softmax(cnn_logits, dim=-1)
            cnn_conf, cnn_cls = cnn_probs.max(dim=-1)

            final_class_ids[low_conf_mask] = cnn_cls
            final_confidences[low_conf_mask] = cnn_conf

            logger.debug(
                "CNN fallback: %d/%d tiles (%.1f%%)",
                num_low, batch_size, num_low / batch_size * 100,
            )

        return final_class_ids, final_confidences

    def get_cost_report(self) -> CostReport:
        """Return cumulative routing cost statistics.

        Returns:
            CostReport with SNN/CNN routing split and cost savings.
        """
        total = self._total_tiles or 1
        snn_pct = self._snn_tiles / total * 100
        cnn_pct = self._cnn_tiles / total * 100

        # cost_saving = 1 - actual_cost / full_cnn_cost
        # actual_cost  = snn_tiles * 1  + cnn_tiles * cnn_cost_multiplier
        # full_cnn_cost = total * cnn_cost_multiplier
        actual_cost = self._snn_tiles * 1 + self._cnn_tiles * self.cnn_cost_multiplier
        full_cnn_cost = total * self.cnn_cost_multiplier
        cost_saving_pct = max(0.0, (1.0 - actual_cost / full_cnn_cost) * 100)

        return CostReport(
            total_tiles=self._total_tiles,
            snn_tiles=self._snn_tiles,
            cnn_tiles=self._cnn_tiles,
            snn_pct=snn_pct,
            cnn_pct=cnn_pct,
            cost_saving_pct=cost_saving_pct,
            snn_latency_ms=self._snn_latency_ms,
            cnn_latency_ms=self._cnn_latency_ms,
            cnn_cost_multiplier=self.cnn_cost_multiplier,
        )

    def reset_cost_tracking(self) -> None:
        """Reset all cumulative routing counters."""
        self._total_tiles = 0
        self._snn_tiles = 0
        self._cnn_tiles = 0
        self._snn_latency_ms = 0.0
        self._cnn_latency_ms = 0.0

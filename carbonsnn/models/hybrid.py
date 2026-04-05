"""HybridClassifier: SNN → low-confidence regions re-classified by ResNet-18 CNN.

Reduces inference cost by routing only uncertain tiles (confidence < threshold)
through the heavier CNN fallback.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import torch
import torch.nn as nn
import torchvision.models as tv_models

from carbonsnn.models.forest_snn import ForestSNN

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Cost Tracking
# ──────────────────────────────────────────────────────────

@dataclass
class CostReport:
    """Summary of inference routing statistics.

    Attributes:
        total_tiles: Total number of tiles processed.
        snn_tiles: Tiles classified by SNN only.
        cnn_tiles: Tiles re-classified by CNN fallback.
        snn_pct: Percentage handled by SNN.
        cnn_pct: Percentage routed to CNN.
        cost_saving_pct: Estimated relative cost saving vs. full CNN.
        snn_latency_ms: Cumulative SNN inference time (ms).
        cnn_latency_ms: Cumulative CNN inference time (ms).
    """

    total_tiles: int = 0
    snn_tiles: int = 0
    cnn_tiles: int = 0
    snn_pct: float = 0.0
    cnn_pct: float = 0.0
    cost_saving_pct: float = 0.0
    snn_latency_ms: float = 0.0
    cnn_latency_ms: float = 0.0

    def __str__(self) -> str:
        return (
            f"SNN {self.snn_pct:.0f}%, CNN {self.cnn_pct:.0f}%, "
            f"cost saving {self.cost_saving_pct:.0f}%"
        )


class _ResNet18Head(nn.Module):
    """Lightweight CNN fallback based on ResNet-18.

    Accepts 10-channel input by replacing the first conv layer.

    Args:
        num_classes: Number of output classes.
        pretrained: Whether to load ImageNet weights for RGB channels.
    """

    def __init__(self, num_classes: int = 2, pretrained: bool = False) -> None:
        super().__init__()
        weights = tv_models.ResNet18_Weights.DEFAULT if pretrained else None
        base = tv_models.resnet18(weights=weights)
        # Replace first conv to accept 10 input bands
        base.conv1 = nn.Conv2d(10, 64, kernel_size=7, stride=2, padding=3, bias=False)
        # Replace classifier head
        base.fc = nn.Linear(512, num_classes)
        self.model = base

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Tile tensor (B, 10, H, W).

        Returns:
            Class logits (B, num_classes).
        """
        return self.model(x)


# ──────────────────────────────────────────────────────────
# Hybrid Classifier
# ──────────────────────────────────────────────────────────

class HybridClassifier(nn.Module):
    """SNN-first classifier with CNN fallback for low-confidence tiles.

    Workflow:
        1. Run all tiles through ForestSNN.
        2. Identify tiles where max softmax probability < confidence_threshold.
        3. Re-classify those tiles with ResNet-18 CNN.
        4. Merge results; track routing statistics.

    Args:
        snn_model: Pre-initialised ForestSNN instance.
        num_classes: Number of output classes (must match SNN).
        confidence_threshold: Minimum SNN confidence to skip CNN re-scoring.
        pretrained_cnn: Load ImageNet weights for CNN.
    """

    def __init__(
        self,
        snn_model: ForestSNN | None = None,
        num_classes: int = 2,
        confidence_threshold: float = 0.75,
        pretrained_cnn: bool = False,
    ) -> None:
        super().__init__()
        self.snn = snn_model or ForestSNN()
        self.cnn = _ResNet18Head(num_classes=num_classes, pretrained=pretrained_cnn)
        self.confidence_threshold = confidence_threshold
        self._num_classes = num_classes

        # Running cost statistics
        self._total_tiles: int = 0
        self._snn_tiles: int = 0
        self._cnn_tiles: int = 0
        self._snn_latency_ms: float = 0.0
        self._cnn_latency_ms: float = 0.0

        logger.info(
            "HybridClassifier initialised | threshold=%.2f classes=%d",
            confidence_threshold,
            num_classes,
        )

    @torch.no_grad()
    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Classify a batch of tiles.

        Args:
            x: Input tensor (B, 10, H, W).

        Returns:
            Tuple of (class_ids (B,), confidences (B,)).
        """
        batch_size = x.size(0)
        self._total_tiles += batch_size

        # ── SNN inference ────────────────────────────────────
        t0 = time.perf_counter()
        snn_class_ids, snn_confidences = self.snn.predict(x)
        self._snn_latency_ms += (time.perf_counter() - t0) * 1000.0

        # ── Route low-confidence tiles to CNN ─────────────────
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
                "CNN fallback invoked for %d/%d tiles (%.1f%%)",
                num_low,
                batch_size,
                num_low / batch_size * 100,
            )

        return final_class_ids, final_confidences

    def get_cost_report(self) -> CostReport:
        """Return cumulative routing cost statistics.

        Returns:
            CostReport with SNN/CNN split and estimated cost saving.
        """
        total = self._total_tiles or 1  # avoid div-by-zero
        snn_pct = self._snn_tiles / total * 100
        cnn_pct = self._cnn_tiles / total * 100
        # Assume CNN is ~5× more expensive per tile
        cnn_relative_cost = 5.0
        cost_saving_pct = (1.0 - (self._snn_tiles / total + self._cnn_tiles / total * cnn_relative_cost / 5.0)) * 100
        # Simpler formula: saving vs. 100% CNN
        cost_saving_pct = max(0.0, (1.0 - (cnn_pct / 100 + snn_pct / 100 / cnn_relative_cost)) * 100)

        report = CostReport(
            total_tiles=self._total_tiles,
            snn_tiles=self._snn_tiles,
            cnn_tiles=self._cnn_tiles,
            snn_pct=snn_pct,
            cnn_pct=cnn_pct,
            cost_saving_pct=cost_saving_pct,
            snn_latency_ms=self._snn_latency_ms,
            cnn_latency_ms=self._cnn_latency_ms,
        )
        logger.info("HybridClassifier cost report: %s", report)
        return report

    def reset_cost_tracking(self) -> None:
        """Reset all cumulative cost counters."""
        self._total_tiles = 0
        self._snn_tiles = 0
        self._cnn_tiles = 0
        self._snn_latency_ms = 0.0
        self._cnn_latency_ms = 0.0

"""Change detection between two Sentinel-2 acquisitions.

Two detectors:
- RuleBasedChangeDetector: threshold dNDVI / dNBR with minimum area filter.
- SiameseChangeDetectorSNN: learned 5-class change type classifier.
"""

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import snntorch as snn
import torch
import torch.nn as nn
from snntorch import surrogate

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Change type labels
# ──────────────────────────────────────────────────────────

CHANGE_CLASSES: list[str] = [
    "No Change",            # 0
    "Deforestation",        # 1
    "Forest Degradation",   # 2
    "Regrowth",             # 3
    "Land Use Change",      # 4
]

# ──────────────────────────────────────────────────────────
# Rule-Based Detector
# ──────────────────────────────────────────────────────────

@dataclass
class ChangePixels:
    """Results from rule-based change detection.

    Attributes:
        change_mask: Boolean array (H, W) — True where change detected.
        dndvi: dNDVI array (H, W).
        dnbr: dNBR array (H, W).
        deforestation_mask: Sub-mask for likely deforestation pixels.
        pixel_count: Number of changed pixels.
        area_ha: Estimated area in hectares (assuming 10 m resolution).
        is_above_threshold: True if area ≥ min_area_ha.
    """

    change_mask: np.ndarray
    dndvi: np.ndarray
    dnbr: np.ndarray
    deforestation_mask: np.ndarray
    pixel_count: int
    area_ha: float
    is_above_threshold: bool


class RuleBasedChangeDetector:
    """Threshold-based deforestation/change detector using spectral indices.

    Detects change by comparing dNDVI and dNBR between two acquisitions.
    Applies a minimum area filter to remove noise.

    Args:
        ndvi_threshold: Negative dNDVI exceeding this indicates vegetation loss.
        nbr_threshold: Negative dNBR exceeding this indicates burn/clearing.
        min_area_ha: Minimum contiguous change area (ha) to flag as alert.
        pixel_size_m: Ground sampling distance in metres (default 10 m).
    """

    def __init__(
        self,
        ndvi_threshold: float = 0.15,
        nbr_threshold: float = 0.10,
        min_area_ha: float = 0.5,
        pixel_size_m: float = 10.0,
    ) -> None:
        self.ndvi_threshold = ndvi_threshold
        self.nbr_threshold = nbr_threshold
        self.min_area_ha = min_area_ha
        self._pixels_per_ha = (100.0 / pixel_size_m) ** 2  # pixels in 1 ha

    def detect(
        self,
        ndvi_before: np.ndarray,
        ndvi_after: np.ndarray,
        nbr_before: np.ndarray,
        nbr_after: np.ndarray,
    ) -> ChangePixels:
        """Detect vegetation loss pixels.

        Args:
            ndvi_before: NDVI array at t0 (H, W).
            ndvi_after: NDVI array at t1 (H, W).
            nbr_before: NBR array at t0 (H, W).
            nbr_after: NBR array at t1 (H, W).

        Returns:
            ChangePixels dataclass with detection results.
        """
        dndvi: np.ndarray = ndvi_before - ndvi_after   # positive = loss
        dnbr: np.ndarray = nbr_before - nbr_after

        deforestation_mask: np.ndarray = (dndvi > self.ndvi_threshold) | (dnbr > self.nbr_threshold)
        change_mask = deforestation_mask.copy()

        pixel_count = int(np.sum(deforestation_mask))
        area_ha = pixel_count / self._pixels_per_ha

        logger.debug(
            "RuleBasedChangeDetector: pixels=%d area_ha=%.2f threshold=%.2f ha",
            pixel_count,
            area_ha,
            self.min_area_ha,
        )

        return ChangePixels(
            change_mask=change_mask,
            dndvi=dndvi,
            dnbr=dnbr,
            deforestation_mask=deforestation_mask,
            pixel_count=pixel_count,
            area_ha=area_ha,
            is_above_threshold=area_ha >= self.min_area_ha,
        )


# ──────────────────────────────────────────────────────────
# Siamese SNN Change Detector
# ──────────────────────────────────────────────────────────

class _SpectralEncoder(nn.Module):
    """Shared spectral encoder branch for Siamese SNN."""

    def __init__(self, beta: float, spike_grad: Any) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(10, 64, 3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.pool1 = nn.MaxPool2d(2, 2)
        self.lif1 = snn.Leaky(beta=beta, spike_grad=spike_grad, init_hidden=True)

        self.conv2 = nn.Conv2d(64, 128, 3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(128)
        self.pool2 = nn.AdaptiveAvgPool2d(1)
        self.lif2 = snn.Leaky(beta=beta, spike_grad=spike_grad, init_hidden=True)

    def reset_hidden(self) -> None:
        """Reset LIF hidden states."""
        self.lif1.reset_hidden()
        self.lif2.reset_hidden()

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Encode a single tile.

        Args:
            x: Tile (B, 10, H, W).

        Returns:
            Tuple of (spikes (B, 128), membrane).
        """
        z = self.pool1(self.bn1(self.conv1(x)))
        s1, _ = self.lif1(z)
        z = self.pool2(self.bn2(self.conv2(s1))).flatten(1)
        s2, mem2 = self.lif2(z)
        return s2, mem2


class SiameseChangeDetectorSNN(nn.Module):
    """Learned 5-class change detector using a Siamese SNN architecture.

    Two branches share weights to encode t0 and t1 tiles.
    Their feature difference is fed into a classification head.

    Args:
        num_steps: SNN time steps.
        beta: LIF membrane decay rate.
        spike_grad: Surrogate gradient function.
    """

    def __init__(
        self,
        num_steps: int = 15,
        beta: float = 0.9,
        spike_grad: Any = surrogate.fast_sigmoid(slope=25),
    ) -> None:
        super().__init__()
        self.num_steps = num_steps
        self.num_classes = len(CHANGE_CLASSES)

        self.encoder = _SpectralEncoder(beta=beta, spike_grad=spike_grad)

        self.classifier = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(64, self.num_classes),
        )

        logger.info(
            "SiameseChangeDetectorSNN initialised | classes=%d num_steps=%d",
            self.num_classes,
            num_steps,
        )

    def forward(
        self, x0: torch.Tensor, x1: torch.Tensor
    ) -> torch.Tensor:
        """Compute change class logits for a tile pair.

        Args:
            x0: Tile at t0, shape (B, 10, H, W).
            x1: Tile at t1, shape (B, 10, H, W).

        Returns:
            Logits of shape (B, 5).
        """
        self.encoder.reset_hidden()
        spike_sum = torch.zeros(x0.size(0), 128, device=x0.device)

        for _ in range(self.num_steps):
            s0, _ = self.encoder(x0)
            self.encoder.reset_hidden()
            s1, _ = self.encoder(x1)
            self.encoder.reset_hidden()
            spike_sum += torch.abs(s0 - s1)   # difference feature

        return self.classifier(spike_sum / self.num_steps)

    @torch.no_grad()
    def predict(
        self, x0: torch.Tensor, x1: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Predict change type.

        Args:
            x0: Before tile (B, 10, H, W).
            x1: After tile (B, 10, H, W).

        Returns:
            Tuple of (change_class_ids (B,), confidences (B,)).
        """
        self.eval()
        logits = self.forward(x0, x1)
        probs = torch.softmax(logits, dim=-1)
        conf, cls = probs.max(dim=-1)
        return cls, conf

    @staticmethod
    def dummy_inputs(
        batch_size: int = 2, tile_size: int = 64
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Return random dummy input pair for smoke-testing."""
        x = torch.rand(batch_size, 10, tile_size, tile_size)
        return x, x + torch.rand_like(x) * 0.1

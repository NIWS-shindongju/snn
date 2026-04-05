"""ChangeDetectionTask: Multi-temporal change detection.

Wraps both rule-based (spectral indices) and Siamese SNN-based
change detection between two satellite image acquisitions.
"""

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import snntorch as snn
from snntorch import surrogate

logger = logging.getLogger(__name__)

CHANGE_CLASSES: list[str] = [
    "No Change",
    "Deforestation",
    "Forest Degradation",
    "Regrowth",
    "Land Use Change",
]


@dataclass
class ChangePixels:
    """Results from rule-based change detection."""

    change_mask: np.ndarray
    dndvi: np.ndarray
    dnbr: np.ndarray
    deforestation_mask: np.ndarray
    pixel_count: int
    area_ha: float
    is_above_threshold: bool


class RuleBasedChangeDetector:
    """Threshold-based change detector using spectral indices.

    Args:
        ndvi_threshold: Negative dNDVI threshold for vegetation loss.
        nbr_threshold: Negative dNBR threshold for burn/clearing.
        min_area_ha: Minimum contiguous change area (ha) to flag.
        pixel_size_m: Ground sampling distance in metres.
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
        self._pixels_per_ha = (100.0 / pixel_size_m) ** 2

    def detect(
        self,
        ndvi_before: np.ndarray,
        ndvi_after: np.ndarray,
        nbr_before: np.ndarray,
        nbr_after: np.ndarray,
    ) -> ChangePixels:
        """Detect vegetation loss pixels.

        Args:
            ndvi_before: NDVI at t0 (H, W).
            ndvi_after: NDVI at t1 (H, W).
            nbr_before: NBR at t0 (H, W).
            nbr_after: NBR at t1 (H, W).

        Returns:
            ChangePixels dataclass with detection results.
        """
        dndvi = ndvi_before - ndvi_after
        dnbr = nbr_before - nbr_after
        deforestation_mask = (dndvi > self.ndvi_threshold) | (dnbr > self.nbr_threshold)
        pixel_count = int(np.sum(deforestation_mask))
        area_ha = pixel_count / self._pixels_per_ha

        return ChangePixels(
            change_mask=deforestation_mask.copy(),
            dndvi=dndvi,
            dnbr=dnbr,
            deforestation_mask=deforestation_mask,
            pixel_count=pixel_count,
            area_ha=area_ha,
            is_above_threshold=area_ha >= self.min_area_ha,
        )


class _SpectralEncoder(nn.Module):
    """Shared spectral encoder for Siamese SNN."""

    def __init__(self, beta: float, spike_grad: Any) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(10, 64, 3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.pool1 = nn.MaxPool2d(2, 2)
        self.lif1 = snn.Leaky(beta=beta, spike_grad=spike_grad)

        self.conv2 = nn.Conv2d(64, 128, 3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(128)
        self.pool2 = nn.AdaptiveAvgPool2d(1)
        self.lif2 = snn.Leaky(beta=beta, spike_grad=spike_grad)

    def forward(
        self,
        x: torch.Tensor,
        mem1: torch.Tensor,
        mem2: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Encode a tile.

        Args:
            x: Tile (B, 10, H, W).
            mem1: Membrane state for lif1.
            mem2: Membrane state for lif2.

        Returns:
            Tuple of (spikes (B, 128), mem1, mem2).
        """
        z = self.pool1(self.bn1(self.conv1(x)))
        s1, mem1 = self.lif1(z, mem1)
        z = self.pool2(self.bn2(self.conv2(s1))).flatten(1)
        s2, mem2 = self.lif2(z, mem2)
        return s2, mem1, mem2


class SiameseChangeDetectorSNN(nn.Module):
    """Learned 5-class change detector using a Siamese SNN.

    Args:
        num_steps: SNN time steps.
        beta: LIF decay rate.
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

    def forward(self, x0: torch.Tensor, x1: torch.Tensor) -> torch.Tensor:
        """Compute change class logits for a tile pair.

        Args:
            x0: Tile at t0 (B, 10, H, W).
            x1: Tile at t1 (B, 10, H, W).

        Returns:
            Logits of shape (B, 5).
        """
        spike_sum = torch.zeros(x0.size(0), 128, device=x0.device)
        for _ in range(self.num_steps):
            mem1_a = self.encoder.lif1.init_leaky()
            mem2_a = self.encoder.lif2.init_leaky()
            mem1_b = self.encoder.lif1.init_leaky()
            mem2_b = self.encoder.lif2.init_leaky()
            s0, _, _ = self.encoder(x0, mem1_a, mem2_a)
            s1, _, _ = self.encoder(x1, mem1_b, mem2_b)
            spike_sum += torch.abs(s0 - s1)
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


class ChangeDetectionTask:
    """Change detection task wrapper.

    Supports both rule-based (spectral index) and SNN-based detectors.
    """

    def __init__(
        self,
        ndvi_threshold: float = 0.15,
        nbr_threshold: float = 0.10,
        min_area_ha: float = 0.5,
    ) -> None:
        self.rule_detector = RuleBasedChangeDetector(
            ndvi_threshold=ndvi_threshold,
            nbr_threshold=nbr_threshold,
            min_area_ha=min_area_ha,
        )
        self._siamese: SiameseChangeDetectorSNN | None = None

    def run(
        self,
        backbone: Any,
        tiles: list[np.ndarray],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Run change detection using SNN comparison.

        Args:
            backbone: SNNBackbone (used for feature comparison).
            tiles: Tiles from the 'before' image (C, H, W) each.
            metadata: Must contain 'tiles_after' key with 'after' tiles.

        Returns:
            Dict with change_map, change_stats, geojson.
        """
        tiles_after = metadata.get("tiles_after", [])
        if not tiles or not tiles_after:
            return {"change_map": [], "change_stats": {"change_area_ha": 0.0}}

        n = min(len(tiles), len(tiles_after))
        batch_before = torch.tensor(np.stack(tiles[:n], axis=0), dtype=torch.float32)
        batch_after = torch.tensor(np.stack(tiles_after[:n], axis=0), dtype=torch.float32)

        backbone.eval()
        with torch.no_grad():
            cls_before, conf_before = backbone.predict(batch_before)
            cls_after, conf_after = backbone.predict(batch_after)

        change_mask = (cls_before != cls_after).cpu().numpy()
        changed_tiles = int(change_mask.sum())
        change_area_ha = changed_tiles * 0.01  # approx 10m pixel = 0.01 ha per tile pixel

        result = {
            "change_map": change_mask.tolist(),
            "change_stats": {
                "changed_tiles": changed_tiles,
                "total_tiles": n,
                "change_pct": float(changed_tiles / max(n, 1) * 100),
                "change_area_ha": round(change_area_ha, 4),
            },
        }
        result = self.postprocess(result)
        logger.info("ChangeDetectionTask: %d changed tiles (%.1f%%)", changed_tiles, changed_tiles / max(n, 1) * 100)
        return result

    def postprocess(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Add GeoJSON representation of changed areas.

        Args:
            raw: Raw change detection output.

        Returns:
            Result with geojson.
        """
        change_map = raw.get("change_map", [])
        features = [
            {
                "type": "Feature",
                "geometry": None,
                "properties": {"tile_index": i, "changed": True},
            }
            for i, changed in enumerate(change_map)
            if changed
        ]
        raw["geojson"] = {"type": "FeatureCollection", "features": features}
        return raw

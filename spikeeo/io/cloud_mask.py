"""Sentinel-2 cloud masking using the Scene Classification Layer (SCL).

The SCL band assigns each pixel one of 11 categories.
This module identifies cloud/shadow/snow pixels and builds a binary mask.
"""

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

SCL_LABELS: dict[int, str] = {
    0: "No Data",
    1: "Saturated / Defective",
    2: "Dark Area Pixels",
    3: "Cloud Shadows",
    4: "Vegetation",
    5: "Bare Soils",
    6: "Water",
    7: "Clouds Low Probability",
    8: "Clouds Medium Probability",
    9: "Clouds High Probability",
    10: "Thin Cirrus",
    11: "Snow / Ice",
}

DEFAULT_CLOUD_CLASSES: frozenset[int] = frozenset({1, 3, 7, 8, 9, 10, 11})


@dataclass
class CloudMaskResult:
    """Output from CloudMasker.

    Attributes:
        mask: Boolean array (H, W) — True where pixel is cloudy/shadowed/snow.
        cloud_percentage: Percentage of masked pixels.
        is_usable: True if cloud_percentage <= max_cloud_cover threshold.
        scl_array: Original SCL integer array (H, W).
    """

    mask: np.ndarray
    cloud_percentage: float
    is_usable: bool
    scl_array: np.ndarray


class CloudMasker:
    """Generate cloud/shadow masks from Sentinel-2 SCL band.

    Args:
        max_cloud_cover: Maximum acceptable cloud percentage (0-100).
        cloud_classes: SCL values considered as cloud/shadow/snow.
    """

    def __init__(
        self,
        max_cloud_cover: float = 20.0,
        cloud_classes: frozenset[int] | None = None,
    ) -> None:
        self.max_cloud_cover = max_cloud_cover
        self.cloud_classes = cloud_classes or DEFAULT_CLOUD_CLASSES

    def mask(self, scl: np.ndarray) -> CloudMaskResult:
        """Compute a cloud mask from an SCL array.

        Args:
            scl: Integer array (H, W) with SCL class values.

        Returns:
            CloudMaskResult with binary mask and statistics.

        Raises:
            ValueError: If scl is not 2-D.
        """
        if scl.ndim != 2:
            raise ValueError(f"SCL array must be 2-D, got shape {scl.shape}")

        cloud_mask = np.isin(scl, list(self.cloud_classes))
        cloud_pct = cloud_mask.sum() / scl.size * 100.0

        return CloudMaskResult(
            mask=cloud_mask,
            cloud_percentage=cloud_pct,
            is_usable=cloud_pct <= self.max_cloud_cover,
            scl_array=scl,
        )

    def is_usable(self, scl: np.ndarray) -> bool:
        """Check whether a scene meets the cloud threshold.

        Args:
            scl: SCL integer array (H, W).

        Returns:
            True if cloud percentage <= max_cloud_cover.
        """
        return self.mask(scl).is_usable

    def apply_mask(
        self,
        image: np.ndarray,
        scl: np.ndarray,
        fill_value: float = float("nan"),
    ) -> np.ndarray:
        """Apply cloud mask to a multi-band image.

        Args:
            image: Float array (C, H, W).
            scl: SCL integer array (H, W).
            fill_value: Value to set for masked pixels.

        Returns:
            Masked image array (C, H, W) as float32.

        Raises:
            ValueError: If image and SCL spatial dims differ.
        """
        if image.shape[-2:] != scl.shape:
            raise ValueError(
                f"Image spatial size {image.shape[-2:]} != SCL size {scl.shape}"
            )
        result = self.mask(scl)
        masked = image.astype(np.float32).copy()
        masked[:, result.mask] = fill_value
        return masked

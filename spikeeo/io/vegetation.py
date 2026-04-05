"""Vegetation index calculators for satellite imagery.

All indices operate on float64 arrays. NaN pixels are propagated without errors.
"""

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

ALL_BANDS: list[str] = ["B02", "B03", "B04", "B08", "B05", "B06", "B07", "B8A", "B11", "B12"]


@dataclass
class VegetationIndices:
    """Container for computed vegetation indices.

    Attributes:
        ndvi: Normalised Difference Vegetation Index (-1 to 1).
        evi: Enhanced Vegetation Index.
        nbr: Normalised Burn Ratio (-1 to 1).
        ndmi: Normalised Difference Moisture Index (-1 to 1).
        lai: Leaf Area Index estimate.
    """

    ndvi: np.ndarray
    evi: np.ndarray
    nbr: np.ndarray
    ndmi: np.ndarray
    lai: np.ndarray


class VegetationIndexCalculator:
    """Compute common remote-sensing vegetation indices.

    Args:
        epsilon: Small constant for numerical stability in division.
    """

    def __init__(self, epsilon: float = 1e-10) -> None:
        self.epsilon = epsilon

    def _safe_div(self, num: np.ndarray, denom: np.ndarray) -> np.ndarray:
        """Element-wise division returning NaN where |denom| < epsilon."""
        with np.errstate(invalid="ignore", divide="ignore"):
            result = np.where(np.abs(denom) < self.epsilon, np.nan, num / denom)
        return result.astype(np.float64)

    def ndvi(self, nir: np.ndarray, red: np.ndarray) -> np.ndarray:
        """Compute NDVI = (NIR - Red) / (NIR + Red).

        Args:
            nir: NIR band (B08), shape (H, W).
            red: Red band (B04), shape (H, W).

        Returns:
            NDVI array (H, W) in [-1, 1].
        """
        return self._safe_div(nir.astype(np.float64) - red.astype(np.float64),
                               nir.astype(np.float64) + red.astype(np.float64))

    def evi(self, nir: np.ndarray, red: np.ndarray, blue: np.ndarray,
            g: float = 2.5, c1: float = 6.0, c2: float = 7.5, l_const: float = 1.0) -> np.ndarray:
        """Compute EVI = G * (NIR - Red) / (NIR + C1*Red - C2*Blue + L).

        Args:
            nir: NIR band (B08).
            red: Red band (B04).
            blue: Blue band (B02).
            g: Gain factor.
            c1: Aerosol resistance coefficient 1.
            c2: Aerosol resistance coefficient 2.
            l_const: Soil adjustment factor.

        Returns:
            EVI array (H, W).
        """
        n, r, b = nir.astype(np.float64), red.astype(np.float64), blue.astype(np.float64)
        return g * self._safe_div(n - r, n + c1 * r - c2 * b + l_const)

    def nbr(self, nir: np.ndarray, swir2: np.ndarray) -> np.ndarray:
        """Compute NBR = (NIR - SWIR2) / (NIR + SWIR2).

        Args:
            nir: NIR band (B08).
            swir2: SWIR2 band (B12).

        Returns:
            NBR array (H, W) in [-1, 1].
        """
        return self._safe_div(nir.astype(np.float64) - swir2.astype(np.float64),
                               nir.astype(np.float64) + swir2.astype(np.float64))

    def ndmi(self, nir: np.ndarray, swir1: np.ndarray) -> np.ndarray:
        """Compute NDMI = (NIR - SWIR1) / (NIR + SWIR1).

        Args:
            nir: NIR band (B08).
            swir1: SWIR1 band (B11).

        Returns:
            NDMI array (H, W) in [-1, 1].
        """
        return self._safe_div(nir.astype(np.float64) - swir1.astype(np.float64),
                               nir.astype(np.float64) + swir1.astype(np.float64))

    def lai_estimate(self, ndvi_arr: np.ndarray) -> np.ndarray:
        """Estimate Leaf Area Index from NDVI (Baret 1991 model).

        LAI ~= -ln((0.69 - NDVI) / 0.59) / 0.91, clipped to [0, 8].

        Args:
            ndvi_arr: NDVI array (H, W).

        Returns:
            LAI array (H, W) in [0, 8].
        """
        v = ndvi_arr.astype(np.float64)
        with np.errstate(invalid="ignore"):
            inner = np.clip((0.69 - v) / 0.59, 1e-10, None)
            lai = -np.log(inner) / 0.91
        return np.clip(lai, 0.0, 8.0)

    def compute_all(
        self, bands: np.ndarray, band_order: list[str] | None = None
    ) -> VegetationIndices:
        """Compute all indices from a stacked band array.

        Args:
            bands: Array (C, H, W) with stacked bands.
            band_order: List of band names (defaults to Sentinel-2 ALL_BANDS).

        Returns:
            VegetationIndices dataclass.
        """
        order = band_order or ALL_BANDS
        idx = {name: i for i, name in enumerate(order)}

        blue = bands[idx["B02"]].astype(np.float64)
        red = bands[idx["B04"]].astype(np.float64)
        nir = bands[idx["B08"]].astype(np.float64)
        swir1 = bands[idx["B11"]].astype(np.float64)
        swir2 = bands[idx["B12"]].astype(np.float64)

        ndvi_arr = self.ndvi(nir, red)
        return VegetationIndices(
            ndvi=ndvi_arr,
            evi=self.evi(nir, red, blue),
            nbr=self.nbr(nir, swir2),
            ndmi=self.ndmi(nir, swir1),
            lai=self.lai_estimate(ndvi_arr),
        )

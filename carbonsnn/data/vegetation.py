"""Vegetation index calculators for Sentinel-2 imagery.

All indices operate on float64 arrays to preserve precision.
NaN pixels (e.g. clouds) are propagated without raising errors.
"""

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Result dataclass
# ──────────────────────────────────────────────────────────

@dataclass
class VegetationIndices:
    """Container for computed vegetation indices.

    Attributes:
        ndvi: Normalised Difference Vegetation Index (-1 to 1).
        evi: Enhanced Vegetation Index.
        nbr: Normalised Burn Ratio (-1 to 1).
        ndmi: Normalised Difference Moisture Index (-1 to 1).
        lai: Leaf Area Index estimate (m² leaf / m² ground).
    """

    ndvi: np.ndarray
    evi: np.ndarray
    nbr: np.ndarray
    ndmi: np.ndarray
    lai: np.ndarray


# ──────────────────────────────────────────────────────────
# Calculator
# ──────────────────────────────────────────────────────────

class VegetationIndexCalculator:
    """Compute common remote-sensing vegetation indices.

    All computations are done in float64 with safe division to avoid
    division-by-zero errors; NaN values are preserved.

    Args:
        epsilon: Small constant added to denominators for numerical stability.
    """

    def __init__(self, epsilon: float = 1e-10) -> None:
        self.epsilon = epsilon

    def _safe_div(self, num: np.ndarray, denom: np.ndarray) -> np.ndarray:
        """Element-wise division that returns NaN where denom ≈ 0.

        Args:
            num: Numerator array.
            denom: Denominator array.

        Returns:
            Result array with NaN where |denom| < epsilon.
        """
        with np.errstate(invalid="ignore", divide="ignore"):
            result = np.where(np.abs(denom) < self.epsilon, np.nan, num / denom)
        return result.astype(np.float64)

    def ndvi(self, nir: np.ndarray, red: np.ndarray) -> np.ndarray:
        """Compute NDVI = (NIR - Red) / (NIR + Red).

        Args:
            nir: Near-infrared band (B08), shape (H, W), raw or normalised.
            red: Red band (B04), shape (H, W).

        Returns:
            NDVI array (H, W) in [-1, 1].
        """
        nir = nir.astype(np.float64)
        red = red.astype(np.float64)
        result = self._safe_div(nir - red, nir + red)
        logger.debug("NDVI: mean=%.3f std=%.3f", float(np.nanmean(result)), float(np.nanstd(result)))
        return result

    def evi(
        self,
        nir: np.ndarray,
        red: np.ndarray,
        blue: np.ndarray,
        g: float = 2.5,
        c1: float = 6.0,
        c2: float = 7.5,
        l_const: float = 1.0,
    ) -> np.ndarray:
        """Compute EVI = G * (NIR - Red) / (NIR + C1*Red - C2*Blue + L).

        Args:
            nir: NIR band (B08).
            red: Red band (B04).
            blue: Blue band (B02).
            g: Gain factor.
            c1: Coefficient 1 (aerosol resistance).
            c2: Coefficient 2 (aerosol resistance).
            l_const: Soil adjustment factor.

        Returns:
            EVI array (H, W).
        """
        nir = nir.astype(np.float64)
        red = red.astype(np.float64)
        blue = blue.astype(np.float64)
        denom = nir + c1 * red - c2 * blue + l_const
        result = g * self._safe_div(nir - red, denom)
        logger.debug("EVI: mean=%.3f", float(np.nanmean(result)))
        return result

    def nbr(self, nir: np.ndarray, swir2: np.ndarray) -> np.ndarray:
        """Compute NBR = (NIR - SWIR2) / (NIR + SWIR2).

        Used to detect burned areas and forest disturbance.

        Args:
            nir: NIR band (B08).
            swir2: Short-wave infrared 2 (B12).

        Returns:
            NBR array (H, W) in [-1, 1].
        """
        nir = nir.astype(np.float64)
        swir2 = swir2.astype(np.float64)
        result = self._safe_div(nir - swir2, nir + swir2)
        logger.debug("NBR: mean=%.3f", float(np.nanmean(result)))
        return result

    def ndmi(self, nir: np.ndarray, swir1: np.ndarray) -> np.ndarray:
        """Compute NDMI = (NIR - SWIR1) / (NIR + SWIR1).

        Sensitive to vegetation water content.

        Args:
            nir: NIR band (B08).
            swir1: Short-wave infrared 1 (B11).

        Returns:
            NDMI array (H, W) in [-1, 1].
        """
        nir = nir.astype(np.float64)
        swir1 = swir1.astype(np.float64)
        result = self._safe_div(nir - swir1, nir + swir1)
        logger.debug("NDMI: mean=%.3f", float(np.nanmean(result)))
        return result

    def lai_estimate(self, ndvi: np.ndarray) -> np.ndarray:
        """Estimate Leaf Area Index from NDVI using the Baret (1991) model.

        LAI ≈ -ln((0.69 - NDVI) / 0.59) / 0.91  (clipped to [0, 8]).

        Args:
            ndvi: NDVI array (H, W).

        Returns:
            LAI estimate array (H, W), clamped to [0, 8].
        """
        ndvi = ndvi.astype(np.float64)
        with np.errstate(invalid="ignore"):
            inner = np.clip((0.69 - ndvi) / 0.59, 1e-10, None)
            lai = -np.log(inner) / 0.91
        lai = np.clip(lai, 0.0, 8.0)
        logger.debug("LAI estimate: mean=%.3f max=%.3f", float(np.nanmean(lai)), float(np.nanmax(lai)))
        return lai

    def compute_all(
        self,
        bands: np.ndarray,
        band_order: list[str] | None = None,
    ) -> VegetationIndices:
        """Compute all indices from a stacked band array.

        Args:
            bands: Array (C, H, W) with band stacks in the order defined by
                band_order (defaults to BAND_10M + BAND_20M).
            band_order: List of band names matching the channel axis.

        Returns:
            VegetationIndices dataclass.
        """
        from carbonsnn.data.preprocessor import ALL_BANDS

        order = band_order or ALL_BANDS
        idx: dict[str, int] = {name: i for i, name in enumerate(order)}

        blue = bands[idx["B02"]].astype(np.float64)
        red = bands[idx["B04"]].astype(np.float64)
        nir = bands[idx["B08"]].astype(np.float64)
        swir1 = bands[idx["B11"]].astype(np.float64)
        swir2 = bands[idx["B12"]].astype(np.float64)

        ndvi_arr = self.ndvi(nir, red)
        evi_arr = self.evi(nir, red, blue)
        nbr_arr = self.nbr(nir, swir2)
        ndmi_arr = self.ndmi(nir, swir1)
        lai_arr = self.lai_estimate(ndvi_arr)

        logger.info("Computed all vegetation indices")
        return VegetationIndices(
            ndvi=ndvi_arr,
            evi=evi_arr,
            nbr=nbr_arr,
            ndmi=ndmi_arr,
            lai=lai_arr,
        )

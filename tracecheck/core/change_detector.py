"""EUDR change detector — pure Python/NumPy rule-based engine.

For MVP demo: reads mock or real GeoTIFF data and applies dNDVI/dNBR rules.
No SNN or PyTorch required for MVP rule-based mode.

Production upgrade path:
  - spikeeo.tasks.change_detection.RuleBasedChangeDetector (requires torch)
  - Swap _run() implementation when spikeeo deps are available
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ChangeResult:
    """Per-parcel change detection result."""

    parcel_id: str
    ndvi_before: float
    ndvi_after: float
    delta_ndvi: float
    nbr_before: float
    nbr_after: float
    delta_nbr: float
    changed_area_ha: float
    cloud_fraction: float
    confidence: float  # 0.0 (uncertain) – 1.0 (very certain)
    before_scene_date: str | None = None
    after_scene_date: str | None = None
    data_source: str = "Copernicus Sentinel-2"
    error: str | None = None


def _safe_ndvi(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """Compute NDVI with zero-division guard."""
    denom = nir + red
    with np.errstate(invalid="ignore", divide="ignore"):
        ndvi = np.where(denom > 0, (nir - red) / denom, np.nan)
    return ndvi.astype(np.float32)


def _safe_nbr(nir: np.ndarray, swir2: np.ndarray) -> np.ndarray:
    """Compute NBR (Normalized Burn Ratio) with zero-division guard."""
    denom = nir + swir2
    with np.errstate(invalid="ignore", divide="ignore"):
        nbr = np.where(denom > 0, (nir - swir2) / denom, np.nan)
    return nbr.astype(np.float32)


class EUDRChangeDetector:
    """Rule-based change detector for EUDR parcel screening.

    Accepts pre-downloaded Sentinel-2 GeoTIFF paths (or mock synthetic arrays)
    and returns spectral change metrics per parcel.

    Band order assumed (matches spikeeo BAND_ORDER):
      [0] B02 (Blue 490nm)
      [1] B03 (Green 560nm)
      [2] B04 (Red 665nm)    ← used for NDVI
      [3] B08 (NIR 842nm)    ← used for NDVI / NBR
      [4] B05 (Red Edge 1)
      [5] B06 (Red Edge 2)
      [6] B07 (Red Edge 3)
      [7] B8A (NIR narrow)
      [8] B11 (SWIR 1)
      [9] B12 (SWIR 2)       ← used for NBR
    """

    # Band indices (0-based, 10-band Sentinel-2 L2A stack)
    _RED = 2   # B04
    _NIR = 3   # B08
    _SWIR2 = 9  # B12

    def __init__(
        self,
        ndvi_threshold: float = 0.10,
        nbr_threshold: float = 0.10,
        min_area_ha: float = 0.3,
        pixel_size_m: float = 10.0,
    ) -> None:
        self.ndvi_threshold = ndvi_threshold
        self.nbr_threshold = nbr_threshold
        self.min_area_ha = min_area_ha
        self.pixel_size_m = pixel_size_m
        self._pixel_area_ha = (pixel_size_m ** 2) / 10_000.0
        logger.info("EUDRChangeDetector initialised (rule-based, no SNN/torch required)")

    def detect(
        self,
        parcel_id: str,
        before_tif: Path,
        after_tif: Path,
        geojson_str: str,
        before_scene_date: str | None = None,
        after_scene_date: str | None = None,
    ) -> ChangeResult:
        """Run change detection for one parcel.

        Args:
            parcel_id: DB parcel UUID (for logging).
            before_tif: Path to pre-cutoff Sentinel-2 GeoTIFF (or mock .npy).
            after_tif: Path to post-cutoff Sentinel-2 GeoTIFF (or mock .npy).
            geojson_str: GeoJSON Feature string for the parcel polygon/point.
            before_scene_date: Acquisition date string of the before image.
            after_scene_date: Acquisition date string of the after image.

        Returns:
            ChangeResult dataclass.
        """
        try:
            return self._run(
                parcel_id, before_tif, after_tif, geojson_str,
                before_scene_date, after_scene_date,
            )
        except Exception as exc:
            logger.warning("Change detection failed for parcel %s: %s", parcel_id, exc)
            return ChangeResult(
                parcel_id=parcel_id,
                ndvi_before=float("nan"),
                ndvi_after=float("nan"),
                delta_ndvi=float("nan"),
                nbr_before=float("nan"),
                nbr_after=float("nan"),
                delta_nbr=float("nan"),
                changed_area_ha=0.0,
                cloud_fraction=1.0,
                confidence=0.0,
                before_scene_date=before_scene_date,
                after_scene_date=after_scene_date,
                error=str(exc),
            )

    def _run(
        self,
        parcel_id: str,
        before_tif: Path,
        after_tif: Path,
        geojson_str: str,
        before_scene_date: str | None,
        after_scene_date: str | None,
    ) -> ChangeResult:
        # Load band arrays (from GeoTIFF or .npy mock)
        bands_before = self._load_array(before_tif)
        bands_after = self._load_array(after_tif)

        # Compute vegetation indices
        ndvi_b_arr = _safe_ndvi(bands_before[self._RED], bands_before[self._NIR])
        ndvi_a_arr = _safe_ndvi(bands_after[self._RED], bands_after[self._NIR])
        nbr_b_arr = _safe_nbr(bands_before[self._NIR], bands_before[self._SWIR2])
        nbr_a_arr = _safe_nbr(bands_after[self._NIR], bands_after[self._SWIR2])

        # Cloud fraction estimate (low NIR = cloud/shadow)
        cloud_fraction = self._estimate_cloud_fraction(bands_before, bands_after)

        # Mean values over parcel
        ndvi_b = float(np.nanmean(ndvi_b_arr))
        ndvi_a = float(np.nanmean(ndvi_a_arr))
        nbr_b = float(np.nanmean(nbr_b_arr))
        nbr_a = float(np.nanmean(nbr_a_arr))

        delta_ndvi = ndvi_b - ndvi_a
        delta_nbr = nbr_b - nbr_a

        # Changed area: pixels where dNDVI exceeds threshold
        dndvi_map = ndvi_b_arr - ndvi_a_arr
        changed_pixels = np.sum((dndvi_map > self.ndvi_threshold) & ~np.isnan(dndvi_map))
        changed_area_ha = float(changed_pixels) * self._pixel_area_ha

        # Confidence: penalise for cloud cover
        confidence = round(float(np.clip(1.0 - cloud_fraction, 0.0, 1.0)), 3)

        logger.debug(
            "parcel=%s dNDVI=%.3f dNBR=%.3f area_ha=%.2f cloud=%.0f%%",
            parcel_id[:8], delta_ndvi, delta_nbr,
            changed_area_ha, cloud_fraction * 100,
        )

        return ChangeResult(
            parcel_id=parcel_id,
            ndvi_before=round(ndvi_b, 4),
            ndvi_after=round(ndvi_a, 4),
            delta_ndvi=round(delta_ndvi, 4),
            nbr_before=round(nbr_b, 4),
            nbr_after=round(nbr_a, 4),
            delta_nbr=round(delta_nbr, 4),
            changed_area_ha=round(changed_area_ha, 4),
            cloud_fraction=round(cloud_fraction, 3),
            confidence=confidence,
            before_scene_date=before_scene_date,
            after_scene_date=after_scene_date,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _load_array(self, path: Path) -> np.ndarray:
        """Load a (10, H, W) float32 band array.

        Supports:
        - .npy files (mock synthetic data from SentinelFetcher mock mode)
        - GeoTIFF files (real Copernicus data via rasterio)
        """
        path = Path(path)
        if path.suffix == ".npy":
            arr = np.load(str(path)).astype(np.float32)
            if arr.ndim == 2:
                arr = arr[np.newaxis, :, :]  # (1, H, W) edge case
            return arr

        # Real GeoTIFF via rasterio
        try:
            import rasterio
            with rasterio.open(str(path)) as src:
                arr = src.read().astype(np.float32)  # (bands, H, W)
                # Sentinel-2 DN 0-10000 → [0, 1]
                arr = np.where(arr == 0, np.nan, arr / 10_000.0)
            return arr
        except ImportError:
            raise RuntimeError(
                "rasterio is required for GeoTIFF loading. "
                "Install it with: pip install rasterio"
            )

    def _estimate_cloud_fraction(
        self, bands_before: np.ndarray, bands_after: np.ndarray
    ) -> float:
        """Estimate cloud fraction as fraction of very-low NIR pixels."""
        fracs = []
        for bands in [bands_before, bands_after]:
            if bands.shape[0] > self._NIR:
                nir = bands[self._NIR]
                valid = ~np.isnan(nir)
                if valid.any():
                    cloud_like = (nir < 0.05) & valid
                    fracs.append(float(np.sum(cloud_like) / np.sum(valid)))
        return max(fracs) if fracs else 0.5

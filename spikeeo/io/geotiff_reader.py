"""GeoTIFF reader and multi-band stacking utilities.

Reads single or multi-band GeoTIFF files, resamples 20-m bands to 10-m,
and stacks them into a single (C, H, W) array with CRS and transform metadata.
"""

import logging
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.warp import reproject

logger = logging.getLogger(__name__)

# Sentinel-2 band definitions
BAND_10M: list[str] = ["B02", "B03", "B04", "B08"]
BAND_20M: list[str] = ["B05", "B06", "B07", "B8A", "B11", "B12"]
ALL_BANDS: list[str] = BAND_10M + BAND_20M


def read_geotiff(path: str | Path) -> tuple[np.ndarray, Any, Affine]:
    """Read a GeoTIFF file and return bands with georeferencing metadata.

    Args:
        path: Path to the GeoTIFF file.

    Returns:
        Tuple of (bands (C, H, W) float32, crs, transform).

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    fpath = Path(path)
    if not fpath.exists():
        raise FileNotFoundError(f"GeoTIFF not found: {fpath}")

    with rasterio.open(fpath) as src:
        bands = src.read().astype(np.float32)
        crs = src.crs
        transform = src.transform

    logger.info("Read GeoTIFF: %s shape=%s crs=%s", fpath.name, bands.shape, crs)
    return bands, crs, transform


def stack_bands(
    band_paths: dict[str, str | Path],
    band_order: list[str] | None = None,
    resample_to_first: bool = True,
) -> tuple[np.ndarray, Any, Affine]:
    """Read and stack multiple single-band GeoTIFF files.

    Args:
        band_paths: Mapping of band name to file path.
        band_order: Ordered list of band names to stack. If None,
            defaults to ALL_BANDS (Sentinel-2 10-band order).
        resample_to_first: If True, resample all bands to the
            resolution and grid of the first band in band_order.

    Returns:
        Tuple of (stacked_array (C, H, W) float32, crs, transform).

    Raises:
        KeyError: If a required band is missing from band_paths.
    """
    order = band_order or ALL_BANDS
    missing = [b for b in order if b not in band_paths]
    if missing:
        raise KeyError(f"Missing band paths: {missing}")

    # Read reference band
    ref_name = order[0]
    with rasterio.open(band_paths[ref_name]) as ref:
        ref_shape = (ref.height, ref.width)
        ref_crs = ref.crs
        ref_transform = ref.transform

    bands: list[np.ndarray] = []
    for band_name in order:
        with rasterio.open(band_paths[band_name]) as src:
            arr = src.read(1).astype(np.float32)
            if resample_to_first and arr.shape != ref_shape:
                dst = np.zeros(ref_shape, dtype=np.float32)
                dst_transform = Affine(
                    ref_transform.a / 2, ref_transform.b, ref_transform.c,
                    ref_transform.d, ref_transform.e / 2, ref_transform.f,
                )
                reproject(
                    source=arr,
                    destination=dst,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=dst_transform,
                    dst_crs=ref_crs,
                    resampling=Resampling.bilinear,
                )
                arr = dst
        bands.append(arr)

    stacked = np.stack(bands, axis=0)
    logger.info("Stacked %d bands, shape=%s", len(bands), stacked.shape)
    return stacked, ref_crs, ref_transform

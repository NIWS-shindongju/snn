"""Satellite image preprocessing utilities.

Provides normalisation, tiling, untiling, resampling and 10-band
stacking using rasterio. CRS metadata is preserved throughout.
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

# ──────────────────────────────────────────────────────────
# Sentinel-2 Band Definitions
# ──────────────────────────────────────────────────────────

# 10-m resolution bands (B2, B3, B4, B8)  → indices 0-3
# 20-m resolution bands (B5, B6, B7, B8A, B11, B12) → indices 4-9
BAND_10M: list[str] = ["B02", "B03", "B04", "B08"]
BAND_20M: list[str] = ["B05", "B06", "B07", "B8A", "B11", "B12"]
ALL_BANDS: list[str] = BAND_10M + BAND_20M


class ImagePreprocessor:
    """Preprocess Sentinel-2 tiles for model inference.

    All operations preserve CRS and geotransform metadata where possible.

    Args:
        tile_size: Spatial extent of output tiles (pixels, H = W).
        overlap: Pixel overlap between adjacent tiles.
        band_min: Per-band minimum reflectance for normalisation.
        band_max: Per-band maximum reflectance for normalisation.
        target_resolution_m: Target ground sampling distance in metres.
    """

    def __init__(
        self,
        tile_size: int = 64,
        overlap: int = 8,
        band_min: float = 0.0,
        band_max: float = 10000.0,
        target_resolution_m: float = 10.0,
    ) -> None:
        self.tile_size = tile_size
        self.overlap = overlap
        self.band_min = band_min
        self.band_max = band_max
        self.target_resolution_m = target_resolution_m
        logger.debug(
            "ImagePreprocessor: tile_size=%d overlap=%d res=%.1fm",
            tile_size,
            overlap,
            target_resolution_m,
        )

    # ── Normalisation ─────────────────────────────────────────

    def normalize(self, image: np.ndarray) -> np.ndarray:
        """Clip and min-max normalise to [0, 1].

        Args:
            image: Float/int array (C, H, W) with raw reflectance values.

        Returns:
            Float32 array normalised to [0, 1].
        """
        clipped = np.clip(image.astype(np.float32), self.band_min, self.band_max)
        normed = (clipped - self.band_min) / (self.band_max - self.band_min + 1e-8)
        return normed.astype(np.float32)

    # ── Tiling ────────────────────────────────────────────────

    def tile(self, image: np.ndarray) -> tuple[list[np.ndarray], list[tuple[int, int]]]:
        """Split an image into overlapping square tiles.

        Args:
            image: Array (C, H, W).

        Returns:
            Tuple of (tiles, positions) where positions are (row, col)
            top-left pixel offsets for each tile.
        """
        _, h, w = image.shape
        stride = self.tile_size - self.overlap
        tiles: list[np.ndarray] = []
        positions: list[tuple[int, int]] = []

        for row in range(0, h - self.tile_size + 1, stride):
            for col in range(0, w - self.tile_size + 1, stride):
                tile = image[:, row : row + self.tile_size, col : col + self.tile_size]
                tiles.append(tile)
                positions.append((row, col))

        logger.debug("Tiled %s image into %d tiles (stride=%d)", image.shape, len(tiles), stride)
        return tiles, positions

    def untile(
        self,
        tiles: list[np.ndarray],
        positions: list[tuple[int, int]],
        original_shape: tuple[int, int],
    ) -> np.ndarray:
        """Reconstruct an image from overlapping tile predictions.

        Overlapping regions are averaged.

        Args:
            tiles: List of arrays each (C, tile_size, tile_size).
            positions: Corresponding (row, col) top-left offsets.
            original_shape: (H, W) of the original image.

        Returns:
            Reconstructed float32 array (C, H, W).
        """
        if not tiles:
            raise ValueError("tiles list is empty")

        channels = tiles[0].shape[0]
        h, w = original_shape
        accum = np.zeros((channels, h, w), dtype=np.float32)
        count = np.zeros((h, w), dtype=np.float32)

        for tile, (r, c) in zip(tiles, positions, strict=True):
            accum[:, r : r + self.tile_size, c : c + self.tile_size] += tile
            count[r : r + self.tile_size, c : c + self.tile_size] += 1.0

        count = np.maximum(count, 1.0)
        result = accum / count[np.newaxis, ...]
        logger.debug("Untiled %d tiles back to shape %s", len(tiles), (channels, h, w))
        return result

    # ── Resampling ────────────────────────────────────────────

    def resample_20m_to_10m(
        self,
        band_20m: np.ndarray,
        src_transform: Affine,
        src_crs: Any,
        target_shape: tuple[int, int],
    ) -> np.ndarray:
        """Upsample a 20-m band to 10-m resolution.

        Args:
            band_20m: 2-D array (H, W) at 20 m.
            src_transform: Rasterio Affine transform at 20 m.
            src_crs: Source CRS.
            target_shape: Output (H, W) at 10 m.

        Returns:
            Resampled 2-D float32 array.
        """
        dst = np.zeros(target_shape, dtype=np.float32)
        dst_transform = Affine(
            src_transform.a / 2, src_transform.b, src_transform.c,
            src_transform.d, src_transform.e / 2, src_transform.f,
        )
        reproject(
            source=band_20m.astype(np.float32),
            destination=dst,
            src_transform=src_transform,
            src_crs=src_crs,
            dst_transform=dst_transform,
            dst_crs=src_crs,
            resampling=Resampling.bilinear,
        )
        return dst

    # ── Band Stacking ─────────────────────────────────────────

    def stack_10_bands(self, band_paths: dict[str, Path | str]) -> tuple[np.ndarray, Any, Affine]:
        """Read and stack the 10 Sentinel-2 model-input bands.

        Reads 10-m bands directly; resamples 20-m bands to 10-m grid.

        Args:
            band_paths: Mapping of band name (e.g. 'B02') to GeoTIFF path.

        Returns:
            Tuple of (stacked_array (10, H, W), crs, transform).

        Raises:
            KeyError: If any of ALL_BANDS is missing from band_paths.
        """
        missing = [b for b in ALL_BANDS if b not in band_paths]
        if missing:
            raise KeyError(f"Missing band paths: {missing}")

        # Read reference 10-m band to get grid dimensions
        with rasterio.open(band_paths["B02"]) as ref:
            ref_shape = (ref.height, ref.width)
            ref_crs = ref.crs
            ref_transform = ref.transform

        bands: list[np.ndarray] = []

        for band_name in ALL_BANDS:
            path = Path(band_paths[band_name])
            with rasterio.open(path) as src:
                arr = src.read(1).astype(np.float32)
                if arr.shape != ref_shape:
                    # Resample 20-m to 10-m
                    arr = self.resample_20m_to_10m(arr, src.transform, src.crs, ref_shape)
            bands.append(arr)

        stacked = np.stack(bands, axis=0)  # (10, H, W)
        logger.info("Stacked 10 bands, shape=%s crs=%s", stacked.shape, ref_crs)
        return stacked, ref_crs, ref_transform

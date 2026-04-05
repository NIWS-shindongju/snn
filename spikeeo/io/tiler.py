"""Tiler: Tile and untile satellite imagery arrays.

Splits large images into overlapping square tiles for model inference
and reconstructs predictions back into the original spatial extent.
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)


class Tiler:
    """Split and reconstruct satellite imagery tiles.

    Args:
        tile_size: Spatial extent of each tile (H = W = tile_size pixels).
        overlap: Pixel overlap between adjacent tiles.
        band_min: Minimum reflectance value for normalisation.
        band_max: Maximum reflectance value for normalisation.
    """

    def __init__(
        self,
        tile_size: int = 64,
        overlap: int = 8,
        band_min: float = 0.0,
        band_max: float = 10000.0,
    ) -> None:
        self.tile_size = tile_size
        self.overlap = overlap
        self.band_min = band_min
        self.band_max = band_max
        logger.debug("Tiler: tile_size=%d overlap=%d", tile_size, overlap)

    def normalize(self, image: np.ndarray) -> np.ndarray:
        """Clip and min-max normalise to [0, 1].

        Args:
            image: Float/int array (C, H, W).

        Returns:
            Float32 array in [0, 1].
        """
        clipped = np.clip(image.astype(np.float32), self.band_min, self.band_max)
        return ((clipped - self.band_min) / (self.band_max - self.band_min + 1e-8)).astype(np.float32)

    def tile(
        self, image: np.ndarray, normalize: bool = True
    ) -> tuple[list[np.ndarray], list[tuple[int, int]]]:
        """Split an image into overlapping square tiles.

        Args:
            image: Array (C, H, W).
            normalize: If True, normalise values to [0, 1].

        Returns:
            Tuple of (tiles, positions) where positions are (row, col)
            top-left pixel offsets for each tile.
        """
        if normalize:
            image = self.normalize(image)

        _, h, w = image.shape
        stride = self.tile_size - self.overlap
        tiles: list[np.ndarray] = []
        positions: list[tuple[int, int]] = []

        for row in range(0, h - self.tile_size + 1, stride):
            for col in range(0, w - self.tile_size + 1, stride):
                tile = image[:, row : row + self.tile_size, col : col + self.tile_size]
                tiles.append(tile)
                positions.append((row, col))

        if not tiles:
            # Image smaller than tile_size: pad and return single tile
            pad_h = max(0, self.tile_size - h)
            pad_w = max(0, self.tile_size - w)
            padded = np.pad(image, ((0, 0), (0, pad_h), (0, pad_w)), mode="reflect")
            tiles = [padded[:, : self.tile_size, : self.tile_size]]
            positions = [(0, 0)]

        logger.debug("Tiled %s into %d tiles (stride=%d)", image.shape, len(tiles), stride)
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
            tiles: List of arrays (C, tile_size, tile_size).
            positions: Corresponding (row, col) top-left offsets.
            original_shape: (H, W) of the original image.

        Returns:
            Reconstructed float32 array (C, H, W).

        Raises:
            ValueError: If tiles list is empty.
        """
        if not tiles:
            raise ValueError("tiles list is empty")

        channels = tiles[0].shape[0]
        h, w = original_shape
        accum = np.zeros((channels, h, w), dtype=np.float32)
        count = np.zeros((h, w), dtype=np.float32)

        for tile, (r, c) in zip(tiles, positions, strict=True):
            r_end = min(r + self.tile_size, h)
            c_end = min(c + self.tile_size, w)
            th = r_end - r
            tw = c_end - c
            accum[:, r:r_end, c:c_end] += tile[:, :th, :tw]
            count[r:r_end, c:c_end] += 1.0

        count = np.maximum(count, 1.0)
        return accum / count[np.newaxis, ...]

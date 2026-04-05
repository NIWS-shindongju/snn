"""CostCalculator: Cloud GPU cost estimation for SNN vs CNN inference.

Estimates dollar cost of processing satellite imagery with SNN vs CNN
based on area, resolution, GPU pricing, and SNN speedup.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class CostCalculator:
    """Estimate cloud GPU costs for SNN vs CNN satellite image analysis.

    Args:
        gpu_cost_per_hour: Hourly GPU cost in USD (default: A100 ~$3/hr).
        snn_speedup: Relative SNN speedup over CNN (default 5x).
        tile_size_m: Tile resolution in metres (default 10 m = Sentinel-2).
        tile_pixels: Tile side length in pixels (default 64).
    """

    def __init__(
        self,
        gpu_cost_per_hour: float = 3.0,
        snn_speedup: float = 5.0,
        tile_size_m: float = 10.0,
        tile_pixels: int = 64,
    ) -> None:
        self.gpu_cost_per_hour = gpu_cost_per_hour
        self.snn_speedup = snn_speedup
        self.tile_size_m = tile_size_m
        self.tile_pixels = tile_pixels

        # Tile area in km²
        tile_side_m = tile_pixels * tile_size_m
        self._tile_area_km2 = (tile_side_m / 1000.0) ** 2

    def estimate(
        self,
        total_km2: float,
        resolution_m: float = 10.0,
        gpu_cost_per_hour: float | None = None,
        snn_speedup: float | None = None,
        tiles_per_second_cnn: float = 100.0,
    ) -> dict[str, Any]:
        """Estimate processing cost for a given area.

        Args:
            total_km2: Total area to process (km²).
            resolution_m: Image resolution (m/pixel).
            gpu_cost_per_hour: Override hourly GPU cost.
            snn_speedup: Override SNN speedup factor.
            tiles_per_second_cnn: CNN throughput (tiles/second on 1 GPU).

        Returns:
            Dict with cnn_cost_usd, snn_cost_usd, saving_usd,
            saving_pct, tiles_processed, cnn_hours, snn_hours.
        """
        cost_per_hr = gpu_cost_per_hour or self.gpu_cost_per_hour
        speedup = snn_speedup or self.snn_speedup

        # Recalculate tile area for custom resolution
        tile_side_m = self.tile_pixels * resolution_m
        tile_area_km2 = (tile_side_m / 1000.0) ** 2
        tiles = max(1, int(total_km2 / tile_area_km2))

        cnn_hours = tiles / (tiles_per_second_cnn * 3600.0)
        snn_hours = cnn_hours / speedup
        cnn_cost = cnn_hours * cost_per_hr
        snn_cost = snn_hours * cost_per_hr
        saving = cnn_cost - snn_cost
        saving_pct = saving / max(cnn_cost, 1e-6) * 100

        result = {
            "cnn_cost_usd": round(cnn_cost, 4),
            "snn_cost_usd": round(snn_cost, 4),
            "saving_usd": round(saving, 4),
            "saving_pct": round(saving_pct, 1),
            "tiles_processed": tiles,
            "cnn_hours": round(cnn_hours, 4),
            "snn_hours": round(snn_hours, 4),
            "speedup": speedup,
        }
        logger.info(
            "Cost estimate: %.0f km2, %d tiles, CNN=$%.2f SNN=$%.2f saving=%.1f%%",
            total_km2, tiles, cnn_cost, snn_cost, saving_pct,
        )
        return result

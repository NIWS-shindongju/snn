"""Carbon MRV pipeline: land cover classification + carbon stock estimation.

Demonstrates using SpikeEO Engine for IPCC Tier-2 carbon MRV workflows.

Usage:
    python -m examples.carbon_mrv.pipeline --input scene.tif --output ./out/ --mode analyze
"""

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

C_TO_CO2: float = 3.667


@dataclass
class CarbonStockResult:
    """Carbon stock estimate for a classified scene."""
    total_carbon_mg: float
    area_ha: float
    carbon_density_mg_ha: float
    uncertainty_low: float
    uncertainty_high: float
    class_breakdown: dict[str, dict[str, float]]
    climate_zone: str
    co2_equivalent_mg: float


def detect_climate_zone(latitude: float) -> str:
    """Infer IPCC climate zone from latitude.

    Args:
        latitude: Scene centroid latitude.

    Returns:
        'tropical', 'temperate', or 'boreal'.
    """
    abs_lat = abs(latitude)
    if abs_lat <= 23.5:
        return "tropical"
    if abs_lat <= 60.0:
        return "temperate"
    return "boreal"


def estimate_carbon_stock(
    class_ids: list[int],
    latitude: float = 0.0,
    pixel_size_m: float = 10.0,
    uncertainty_pct: float = 0.20,
) -> CarbonStockResult:
    """Estimate carbon stock from a list of classified tile IDs.

    Args:
        class_ids: List of land cover class indices (0-10).
        latitude: Scene centroid latitude.
        pixel_size_m: Ground sampling distance (m).
        uncertainty_pct: Fractional uncertainty.

    Returns:
        CarbonStockResult with total and per-class statistics.
    """
    from examples.carbon_mrv.config import CarbonLandCoverConfig
    config = CarbonLandCoverConfig()
    climate_zone = detect_climate_zone(latitude)
    ha_per_tile = (pixel_size_m * 64 / 100.0) ** 2 / 10000.0  # approx

    total_carbon = 0.0
    breakdown: dict[str, dict[str, float]] = {}

    for cls_idx, cls_name in enumerate(config.class_names):
        count = sum(1 for c in class_ids if c == cls_idx)
        area_ha = count * ha_per_tile
        agb = config.carbon_density_agb[cls_idx] * area_ha
        bgb = config.carbon_density_bgb[cls_idx] * area_ha
        total_carbon += agb + bgb
        breakdown[cls_name] = {
            "area_ha": round(area_ha, 4),
            "total_carbon_mg_c": round(agb + bgb, 4),
        }

    total_area = len(class_ids) * ha_per_tile

    return CarbonStockResult(
        total_carbon_mg=round(total_carbon, 4),
        area_ha=round(total_area, 4),
        carbon_density_mg_ha=round(total_carbon / max(total_area, 1e-6), 4),
        uncertainty_low=round(total_carbon * (1 - uncertainty_pct), 4),
        uncertainty_high=round(total_carbon * (1 + uncertainty_pct), 4),
        class_breakdown=breakdown,
        climate_zone=climate_zone,
        co2_equivalent_mg=round(total_carbon * C_TO_CO2, 4),
    )


def run_analyze(input_path: str, output_dir: str, latitude: float = 0.0) -> dict[str, Any]:
    """Run full carbon analysis on a GeoTIFF.

    Args:
        input_path: Path to input GeoTIFF.
        output_dir: Directory for output files.
        latitude: Scene latitude for climate zone detection.

    Returns:
        Combined inference + carbon stock result dict.
    """
    import spikeeo

    engine = spikeeo.Engine(task="classification", num_classes=11, num_bands=10)
    result = engine.run(input_path, output_dir=output_dir, output_format="geojson")

    class_ids = result.get("class_ids", [])
    carbon = estimate_carbon_stock(class_ids, latitude=latitude)

    out = {
        "inference": result,
        "carbon_stock": {
            "total_carbon_mg": carbon.total_carbon_mg,
            "co2_equivalent_mg": carbon.co2_equivalent_mg,
            "area_ha": carbon.area_ha,
            "carbon_density_mg_ha": carbon.carbon_density_mg_ha,
            "climate_zone": carbon.climate_zone,
            "uncertainty_low": carbon.uncertainty_low,
            "uncertainty_high": carbon.uncertainty_high,
            "class_breakdown": carbon.class_breakdown,
        },
    }

    out_path = Path(output_dir) / "carbon_mrv_result.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        json.dump(out, fh, indent=2, default=str)
    logger.info("Carbon MRV result written to %s", out_path)
    return out


def main() -> None:
    """CLI entry point for the Carbon MRV pipeline."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="CarbonSNN MRV Pipeline")
    parser.add_argument("--input", required=True, help="Input GeoTIFF path")
    parser.add_argument("--output", default="./out/", help="Output directory")
    parser.add_argument("--mode", choices=["analyze", "change"], default="analyze")
    parser.add_argument("--latitude", type=float, default=0.0, help="Scene latitude")
    args = parser.parse_args()

    if args.mode == "analyze":
        result = run_analyze(args.input, args.output, latitude=args.latitude)
        logger.info("Carbon stock: %.2f Mg C (CO2e: %.2f Mg)", result["carbon_stock"]["total_carbon_mg"], result["carbon_stock"]["co2_equivalent_mg"])
    else:
        logger.info("Change detection mode requires --before and --after arguments")


if __name__ == "__main__":
    main()

"""Retail counting pipeline: count vehicles in parking lot satellite imagery.

Demonstrates using SpikeEO Engine for object detection tasks.

Usage:
    python -m examples.retail_counting.pipeline --input parking_lot.tif --output ./out/
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def run_vehicle_count(input_path: str, output_dir: str) -> dict[str, Any]:
    """Count vehicles in a satellite image.

    Args:
        input_path: Path to input GeoTIFF (high-resolution aerial/satellite).
        output_dir: Directory for output files.

    Returns:
        Dict with vehicle_count, centroids, and geojson.
    """
    import spikeeo

    engine = spikeeo.Engine(
        task="detection",
        num_classes=2,   # 0=background, 1=vehicle
        num_bands=10,
        confidence_threshold=0.7,
    )
    result = engine.run(input_path, output_dir=output_dir, output_format="geojson")

    summary = {
        "vehicle_count": result.get("object_count", 0),
        "centroids": result.get("centroids", []),
        "geojson": result.get("geojson"),
        "metadata": result.get("metadata", {}),
    }

    out_path = Path(output_dir) / "vehicle_count.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        json.dump(summary, fh, indent=2, default=str)

    logger.info("Vehicle count: %d vehicles detected", summary["vehicle_count"])
    return summary


def demo_with_synthetic_data() -> dict[str, Any]:
    """Run a demo with synthetic (random) tile data.

    Returns:
        Demo result dict.
    """
    import numpy as np
    import tempfile
    import rasterio
    from rasterio.transform import from_bounds

    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
        bands = np.random.rand(10, 128, 128).astype(np.float32) * 3000
        profile = {
            "driver": "GTiff",
            "dtype": "float32",
            "width": 128,
            "height": 128,
            "count": 10,
            "crs": "EPSG:4326",
            "transform": from_bounds(-0.01, -0.01, 0.01, 0.01, 128, 128),
        }
        with rasterio.open(tmp.name, "w", **profile) as dst:
            dst.write(bands)
        tif_path = tmp.name

    import spikeeo
    engine = spikeeo.Engine(task="detection", num_classes=2)
    result = engine.run(tif_path)
    Path(tif_path).unlink(missing_ok=True)
    return {
        "vehicle_count": result.get("object_count", 0),
        "centroids": result.get("centroids", []),
        "demo": True,
    }


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Retail Vehicle Counting Demo")
    parser.add_argument("--input", default=None, help="Input GeoTIFF path (omit for demo mode)")
    parser.add_argument("--output", default="./out/", help="Output directory")
    args = parser.parse_args()

    if args.input:
        result = run_vehicle_count(args.input, args.output)
    else:
        logger.info("No input provided, running in demo mode with synthetic data...")
        result = demo_with_synthetic_data()

    logger.info("Result: %d vehicles detected", result.get("vehicle_count", 0))


if __name__ == "__main__":
    main()

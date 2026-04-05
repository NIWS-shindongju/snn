"""Deforestation alert pipeline: weekly change detection and alert generation.

Compares two Sentinel-2 acquisitions and generates deforestation alerts
as GeoJSON polygons. Demonstrates SpikeEO Engine change_detection task.

Usage:
    python -m examples.deforestation_alert.pipeline --before before.tif --after after.tif
"""

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DeforestationAlert:
    """A single deforestation event alert.

    Attributes:
        detected_date: Date the alert was generated.
        change_area_ha: Estimated deforested area (ha).
        severity: 'low' | 'medium' | 'high'.
        change_pct: Percentage of scene that changed.
        geojson: GeoJSON FeatureCollection of changed areas.
    """

    detected_date: str
    change_area_ha: float
    severity: str
    change_pct: float
    geojson: dict[str, Any]

    @staticmethod
    def severity_from_area(area_ha: float) -> str:
        """Classify severity from area.

        Args:
            area_ha: Area in hectares.

        Returns:
            'low' (<1 ha), 'medium' (1-10 ha), 'high' (>10 ha).
        """
        if area_ha < 1.0:
            return "low"
        if area_ha < 10.0:
            return "medium"
        return "high"


def run_change_detection(
    before_path: str,
    after_path: str,
    output_dir: str,
    min_area_ha: float = 0.5,
) -> DeforestationAlert | None:
    """Detect deforestation between two satellite acquisitions.

    Args:
        before_path: Path to before-state GeoTIFF.
        after_path: Path to after-state GeoTIFF.
        output_dir: Output directory.
        min_area_ha: Minimum area threshold for alerts.

    Returns:
        DeforestationAlert if significant change detected, else None.
    """
    import spikeeo

    engine = spikeeo.Engine(task="change_detection", num_bands=10)
    result = engine.run_change(before_path, after_path, output_dir=output_dir)

    stats = result.get("change_stats", {})
    change_area = stats.get("change_area_ha", 0.0)

    if change_area < min_area_ha:
        logger.info("No significant deforestation detected (%.2f ha < %.2f ha threshold)", change_area, min_area_ha)
        return None

    alert = DeforestationAlert(
        detected_date=date.today().isoformat(),
        change_area_ha=round(change_area, 4),
        severity=DeforestationAlert.severity_from_area(change_area),
        change_pct=stats.get("change_pct", 0.0),
        geojson=result.get("geojson", {"type": "FeatureCollection", "features": []}),
    )

    out_path = Path(output_dir) / "deforestation_alert.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        json.dump(asdict(alert), fh, indent=2, default=str)

    logger.info(
        "Deforestation alert: area=%.2f ha severity=%s",
        alert.change_area_ha, alert.severity,
    )
    return alert


def demo_with_synthetic_data() -> dict[str, Any]:
    """Run demo with synthetic before/after images.

    Returns:
        Alert summary dict.
    """
    import numpy as np
    import tempfile
    import rasterio
    from rasterio.transform import from_bounds

    def make_tif(suffix: str, noise_scale: float = 1.0) -> str:
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
            bands = (np.random.rand(10, 128, 128) * 3000 * noise_scale).astype(np.float32)
            profile = {
                "driver": "GTiff", "dtype": "float32",
                "width": 128, "height": 128, "count": 10,
                "crs": "EPSG:4326",
                "transform": from_bounds(-0.01, -0.01, 0.01, 0.01, 128, 128),
            }
            with rasterio.open(tmp.name, "w", **profile) as dst:
                dst.write(bands)
            return tmp.name

    before_path = make_tif("before")
    after_path = make_tif("after", noise_scale=0.5)  # Different to simulate change

    import spikeeo
    engine = spikeeo.Engine(task="change_detection")
    result = engine.run_change(before_path, after_path)

    Path(before_path).unlink(missing_ok=True)
    Path(after_path).unlink(missing_ok=True)

    stats = result.get("change_stats", {})
    return {
        "change_area_ha": stats.get("change_area_ha", 0.0),
        "change_pct": stats.get("change_pct", 0.0),
        "severity": DeforestationAlert.severity_from_area(stats.get("change_area_ha", 0.0)),
        "demo": True,
    }


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Deforestation Alert Pipeline")
    parser.add_argument("--before", default=None, help="Before GeoTIFF path")
    parser.add_argument("--after", default=None, help="After GeoTIFF path")
    parser.add_argument("--output", default="./out/", help="Output directory")
    parser.add_argument("--min-area", type=float, default=0.5)
    args = parser.parse_args()

    if args.before and args.after:
        alert = run_change_detection(args.before, args.after, args.output, args.min_area)
        if alert:
            logger.info("Alert raised: %.2f ha %s", alert.change_area_ha, alert.severity)
        else:
            logger.info("No significant deforestation detected")
    else:
        logger.info("Running demo mode with synthetic data...")
        result = demo_with_synthetic_data()
        logger.info("Demo result: %s", result)


if __name__ == "__main__":
    main()

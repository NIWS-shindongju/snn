"""Verra VCS-compatible MRV report generator.

Produces structured JSON and GeoJSON reports following the
Verified Carbon Standard (VCS) methodology framework.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from carbonsnn.analysis.carbon_stock import CarbonStockResult

logger = logging.getLogger(__name__)


class MRVReportGenerator:
    """Generate MRV reports compatible with Verra VCS methodologies.

    Args:
        methodology_version: VCS methodology reference string.
        organisation: Reporting organisation name.
        validator: Third-party validator name (optional).
    """

    METHODOLOGY_MAP: dict[str, str] = {
        "REDD+": "VM0015",
        "Afforestation": "VM0047",
        "IFM": "VM0010",
    }

    def __init__(
        self,
        methodology_version: str = "VM0015 v1.3",
        organisation: str = "CarbonSNN",
        validator: str | None = None,
    ) -> None:
        self.methodology_version = methodology_version
        self.organisation = organisation
        self.validator = validator

    def generate_json(
        self,
        project_id: str,
        project_name: str,
        country: str,
        reference_period_start: datetime,
        reference_period_end: datetime,
        monitoring_period_start: datetime,
        monitoring_period_end: datetime,
        carbon_stock: CarbonStockResult,
        deforestation_area_ha: float = 0.0,
        carbon_lost_mg: float = 0.0,
        co2_equivalent_mg: float = 0.0,
        additional_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate a Verra VCS-compatible MRV JSON report.

        Args:
            project_id: Unique project identifier.
            project_name: Human-readable project name.
            country: ISO-3166 country code or name.
            reference_period_start: Start of the reference/baseline period.
            reference_period_end: End of the reference period.
            monitoring_period_start: Start of the monitoring period.
            monitoring_period_end: End of the monitoring period.
            carbon_stock: Carbon stock estimation results.
            deforestation_area_ha: Total detected deforestation area.
            carbon_lost_mg: Carbon lost due to deforestation (Mg C).
            co2_equivalent_mg: CO2-equivalent emissions (Mg CO2e).
            additional_metadata: Optional extra key-value pairs.

        Returns:
            JSON-serialisable dictionary following VCS structure.
        """
        report_id = f"MRV-{project_id[:8].upper()}-{uuid.uuid4().hex[:6].upper()}"
        generated_at = datetime.now(timezone.utc).isoformat()

        report: dict[str, Any] = {
            "report_id": report_id,
            "schema_version": "carbonsnn_mrv_v1.0",
            "generated_at": generated_at,
            "generator": {
                "tool": "CarbonSNN",
                "version": "0.1.0",
                "methodology": self.methodology_version,
            },
            "project": {
                "id": project_id,
                "name": project_name,
                "country": country,
                "organisation": self.organisation,
                "validator": self.validator,
            },
            "periods": {
                "reference": {
                    "start": reference_period_start.isoformat(),
                    "end": reference_period_end.isoformat(),
                },
                "monitoring": {
                    "start": monitoring_period_start.isoformat(),
                    "end": monitoring_period_end.isoformat(),
                    "duration_days": (monitoring_period_end - monitoring_period_start).days,
                },
            },
            "methodology": {
                "standard": "Verra VCS",
                "reference": self.methodology_version,
                "approach": "Activity-data × Emission Factor (Tier 2)",
                "carbon_pools": ["AGB", "BGB"],
                "excluded_pools": ["Dead Wood", "Litter", "Soil Organic Carbon"],
                "uncertainty_method": "IPCC Tier 2 (±20%)",
            },
            "area": {
                "total_ha": carbon_stock.area_ha,
                "deforested_ha": round(deforestation_area_ha, 4),
                "class_breakdown_ha": {
                    cls: data["area_ha"]
                    for cls, data in carbon_stock.class_breakdown.items()
                },
            },
            "carbon_stocks": {
                "reference_period": {
                    "total_mg_c": carbon_stock.total_carbon_mg,
                    "agb_mg_c": carbon_stock.total_agb_mg,
                    "bgb_mg_c": carbon_stock.total_bgb_mg,
                    "density_mg_c_per_ha": carbon_stock.carbon_density_mg_ha,
                },
            },
            "emissions": {
                "carbon_lost_mg_c": round(carbon_lost_mg, 4),
                "co2_equivalent_mg": round(co2_equivalent_mg, 4),
                "uncertainty": {
                    "low_mg_co2e": round(co2_equivalent_mg * 0.80, 4),
                    "high_mg_co2e": round(co2_equivalent_mg * 1.20, 4),
                    "confidence_interval": "90%",
                },
            },
            "uncertainty": {
                "carbon_stock_low": carbon_stock.uncertainty_low,
                "carbon_stock_high": carbon_stock.uncertainty_high,
                "method": "IPCC Tier 2 default ±20%",
                "climate_zone": carbon_stock.climate_zone,
            },
            "data_sources": {
                "satellite": "Sentinel-2 L2A (Copernicus Data Space)",
                "land_cover_model": "CarbonSNN 11-class SNN classifier",
                "carbon_factors": "IPCC 2006 Guidelines, Vol. 4 (updated 2019)",
                "change_detection": "dNDVI + dNBR rule-based + Siamese SNN",
            },
            "quality_flags": {
                "cloud_screening": True,
                "minimum_area_threshold_ha": 0.5,
                "minimum_confidence": 0.75,
            },
        }

        if additional_metadata:
            report["additional_metadata"] = additional_metadata

        logger.info("Generated MRV report: %s for project %s", report_id, project_id)
        return report

    def generate_geojson(
        self,
        project_id: str,
        project_name: str,
        bbox: list[float],
        deforestation_polygons: list[dict[str, Any]] | None = None,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate a GeoJSON FeatureCollection for MRV spatial output.

        Args:
            project_id: Project identifier.
            project_name: Project display name.
            bbox: Project bounding box [W, S, E, N].
            deforestation_polygons: Optional list of polygon geometries.
            properties: Optional extra properties for the boundary feature.

        Returns:
            GeoJSON FeatureCollection dictionary.
        """
        west, south, east, north = bbox
        features: list[dict[str, Any]] = []

        # Project boundary
        boundary_feature: dict[str, Any] = {
            "type": "Feature",
            "properties": {
                "feature_type": "project_boundary",
                "project_id": project_id,
                "project_name": project_name,
                **(properties or {}),
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [west, south],
                    [east, south],
                    [east, north],
                    [west, north],
                    [west, south],
                ]],
            },
        }
        features.append(boundary_feature)

        # Deforestation event polygons
        for i, poly in enumerate(deforestation_polygons or []):
            features.append({
                "type": "Feature",
                "properties": {
                    "feature_type": "deforestation_event",
                    "event_index": i,
                    "project_id": project_id,
                },
                "geometry": poly,
            })

        geojson: dict[str, Any] = {
            "type": "FeatureCollection",
            "name": f"MRV_{project_name}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "features": features,
        }

        logger.info(
            "Generated GeoJSON for project %s: %d features",
            project_id,
            len(features),
        )
        return geojson

    def save(
        self,
        report: dict[str, Any],
        path: str | Path,
        indent: int = 2,
    ) -> None:
        """Write a report dictionary to a JSON file.

        Args:
            report: Report dictionary (from generate_json or generate_geojson).
            path: Destination file path.
            indent: JSON indentation spaces.
        """
        save_path = Path(path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with save_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=indent, ensure_ascii=False, default=str)
        logger.info("Saved report to %s", save_path)

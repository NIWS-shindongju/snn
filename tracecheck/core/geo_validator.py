"""GeoJSON and CSV coordinate validator for EUDR parcel upload.

Validates:
- CSV files with lat/lon columns
- GeoJSON Feature or FeatureCollection files
- Coordinate range, polygon validity, area estimation
"""

from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import dataclass, field
from typing import Any

import shapely.wkt  # noqa: F401  (ensure shapely is available)
from shapely.geometry import Point, Polygon, shape
from shapely.validation import explain_validity

logger = logging.getLogger(__name__)

# Column name aliases for CSV auto-detection
_LAT_ALIASES = {"lat", "latitude", "y", "lat_dd", "latitude_dd"}
_LON_ALIASES = {"lon", "lng", "longitude", "x", "lon_dd", "longitude_dd", "long"}
_SUPPLIER_ALIASES = {"supplier", "supplier_name", "farm", "vendor", "producer"}
_REF_ALIASES = {"ref", "parcel_ref", "parcel_id", "plot_id", "plot_ref", "id", "code"}

# Approximate country bounding boxes (ISO2 -> (minx, miny, maxx, maxy))
# Covers EUDR high-risk origin countries for coffee / cocoa / palm oil
_COUNTRY_BBOX: dict[str, tuple[float, float, float, float]] = {
    "BR": (-73.99, -33.75, -28.85, 5.27),
    "CO": (-81.73, -4.23, -66.87, 12.58),
    "VN": (102.14, 8.56, 109.47, 23.39),
    "ID": (95.01, -10.94, 141.02, 5.91),
    "MY": (99.64, 0.85, 119.28, 7.36),
    "GH": (-3.26, 4.74, 1.20, 11.17),
    "CI": (-8.60, 4.34, -2.49, 10.74),
    "CM": (8.50, 1.65, 16.19, 12.36),
    "NG": (2.69, 4.27, 14.68, 13.89),
    "PH": (116.93, 4.59, 126.61, 21.12),
    "ET": (33.00, 3.40, 47.99, 14.89),
    "HN": (-89.35, 13.00, -83.15, 16.52),
    "GT": (-92.24, 13.74, -88.22, 17.82),
    "MX": (-118.36, 14.53, -86.71, 32.72),
    "PE": (-81.33, -18.35, -68.65, -0.04),
    "TZ": (29.34, -11.75, 40.44, -0.99),
    "UG": (29.57, -1.48, 35.00, 4.23),
    "PG": (140.84, -11.66, 155.97, -1.35),
}


@dataclass
class ParsedParcel:
    """A single validated parcel ready for DB insertion."""

    project_id: str
    geometry_type: str  # 'point' | 'polygon'
    geojson: str
    supplier_name: str | None = None
    parcel_ref: str | None = None
    bbox_minx: float | None = None
    bbox_miny: float | None = None
    bbox_maxx: float | None = None
    bbox_maxy: float | None = None
    area_ha: float | None = None
    country: str | None = None


@dataclass
class ValidationResult:
    """Aggregated result of a parcel upload validation pass."""

    valid: list[ParsedParcel] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    @property
    def valid_count(self) -> int:
        return len(self.valid)

    @property
    def invalid_count(self) -> int:
        return len(self.errors)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _detect_country(lon: float, lat: float) -> str | None:
    """Return ISO2 country code if point falls in a known bounding box."""
    for iso2, (minx, miny, maxx, maxy) in _COUNTRY_BBOX.items():
        if minx <= lon <= maxx and miny <= lat <= maxy:
            return iso2
    return None


def _estimate_area_ha(polygon: Polygon) -> float:
    """Rough area estimate in hectares using degree-to-meter conversion."""
    # 1 degree lat ≈ 111,320 m; 1 degree lon ≈ 111,320 * cos(lat) m
    import math

    centroid_lat = polygon.centroid.y
    scale_x = 111_320.0 * math.cos(math.radians(centroid_lat))
    scale_y = 111_320.0
    area_m2 = polygon.area * scale_x * scale_y
    return round(area_m2 / 10_000.0, 4)


def _point_to_geojson(lat: float, lon: float) -> str:
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {},
    }
    return json.dumps(feature)


def _polygon_to_geojson(polygon: Polygon) -> str:
    coords = list(polygon.exterior.coords)
    feature = {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [[[c[0], c[1]] for c in coords]]},
        "properties": {},
    }
    return json.dumps(feature)


# ─────────────────────────────────────────────────────────────────────────────
# CSV parser
# ─────────────────────────────────────────────────────────────────────────────

def validate_csv(content: bytes, project_id: str) -> ValidationResult:
    """Parse and validate a CSV upload.

    Expected columns (case-insensitive): lat, lon [, supplier_name, parcel_ref]
    """
    result = ValidationResult()
    text = content.decode("utf-8-sig", errors="replace")  # handle BOM
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        result.errors.append({"row": 0, "error": "CSV file is empty or has no header"})
        return result

    # Normalise column names
    header_map: dict[str, str] = {h.strip().lower(): h for h in reader.fieldnames if h}

    lat_col = next((header_map[a] for a in _LAT_ALIASES if a in header_map), None)
    lon_col = next((header_map[a] for a in _LON_ALIASES if a in header_map), None)
    supplier_col = next((header_map[a] for a in _SUPPLIER_ALIASES if a in header_map), None)
    ref_col = next((header_map[a] for a in _REF_ALIASES if a in header_map), None)

    if not lat_col or not lon_col:
        result.errors.append({
            "row": 0,
            "error": (
                f"Could not detect lat/lon columns. Found: {list(header_map.keys())}. "
                "Expected one of: lat/latitude/y and lon/longitude/x"
            ),
        })
        return result

    for row_num, row in enumerate(reader, start=2):
        try:
            lat = float(row[lat_col])
            lon = float(row[lon_col])
        except (ValueError, KeyError) as exc:
            result.errors.append({"row": row_num, "error": f"Invalid coordinates: {exc}"})
            continue

        if not (-90 <= lat <= 90):
            result.errors.append({"row": row_num, "error": f"Latitude {lat} out of range [-90, 90]"})
            continue
        if not (-180 <= lon <= 180):
            result.errors.append({"row": row_num, "error": f"Longitude {lon} out of range [-180, 180]"})
            continue

        country = _detect_country(lon, lat)
        supplier = row.get(supplier_col, "").strip() if supplier_col else None
        parcel_ref = row.get(ref_col, "").strip() if ref_col else None

        result.valid.append(ParsedParcel(
            project_id=project_id,
            geometry_type="point",
            geojson=_point_to_geojson(lat, lon),
            supplier_name=supplier or None,
            parcel_ref=parcel_ref or None,
            bbox_minx=lon,
            bbox_miny=lat,
            bbox_maxx=lon,
            bbox_maxy=lat,
            area_ha=None,
            country=country,
        ))

    logger.info(
        "CSV validation: %d valid, %d errors", result.valid_count, result.invalid_count
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# GeoJSON parser
# ─────────────────────────────────────────────────────────────────────────────

def validate_geojson(content: bytes, project_id: str) -> ValidationResult:
    """Parse and validate a GeoJSON upload (Feature or FeatureCollection)."""
    result = ValidationResult()

    try:
        data = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        result.errors.append({"row": 0, "error": f"Invalid JSON: {exc}"})
        return result

    geo_type = data.get("type", "")

    if geo_type == "Feature":
        features = [data]
    elif geo_type == "FeatureCollection":
        features = data.get("features", [])
    else:
        result.errors.append({
            "row": 0,
            "error": f"Expected Feature or FeatureCollection, got '{geo_type}'",
        })
        return result

    for idx, feature in enumerate(features, start=1):
        _validate_geojson_feature(feature, idx, project_id, result)

    logger.info(
        "GeoJSON validation: %d valid, %d errors", result.valid_count, result.invalid_count
    )
    return result


def _validate_geojson_feature(
    feature: dict[str, Any],
    idx: int,
    project_id: str,
    result: ValidationResult,
) -> None:
    """Validate a single GeoJSON Feature and append to result."""
    props = feature.get("properties") or {}
    geometry = feature.get("geometry")

    if not geometry:
        result.errors.append({"row": idx, "error": "Feature has no geometry"})
        return

    geom_type = geometry.get("type", "")
    coords = geometry.get("coordinates")

    supplier = str(props.get("supplier_name", props.get("supplier", "")) or "").strip() or None
    parcel_ref = str(props.get("parcel_ref", props.get("id", "")) or "").strip() or None

    try:
        shapely_geom = shape(geometry)
    except Exception as exc:
        result.errors.append({"row": idx, "error": f"Cannot parse geometry: {exc}"})
        return

    if not shapely_geom.is_valid:
        result.errors.append({
            "row": idx,
            "error": f"Invalid geometry: {explain_validity(shapely_geom)}",
        })
        return

    if geom_type == "Point":
        lon, lat = coords[0], coords[1]
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            result.errors.append({"row": idx, "error": f"Coordinates out of range: lon={lon}, lat={lat}"})
            return
        country = _detect_country(lon, lat)
        result.valid.append(ParsedParcel(
            project_id=project_id,
            geometry_type="point",
            geojson=json.dumps(feature),
            supplier_name=supplier,
            parcel_ref=parcel_ref,
            bbox_minx=lon,
            bbox_miny=lat,
            bbox_maxx=lon,
            bbox_maxy=lat,
            area_ha=None,
            country=country,
        ))

    elif geom_type in ("Polygon", "MultiPolygon"):
        bounds = shapely_geom.bounds  # (minx, miny, maxx, maxy)
        centroid = shapely_geom.centroid
        country = _detect_country(centroid.x, centroid.y)

        if geom_type == "Polygon":
            area_ha = _estimate_area_ha(shapely_geom)  # type: ignore[arg-type]
        else:
            area_ha = sum(_estimate_area_ha(p) for p in shapely_geom.geoms)  # type: ignore[attr-defined]

        result.valid.append(ParsedParcel(
            project_id=project_id,
            geometry_type="polygon",
            geojson=json.dumps(feature),
            supplier_name=supplier,
            parcel_ref=parcel_ref,
            bbox_minx=bounds[0],
            bbox_miny=bounds[1],
            bbox_maxx=bounds[2],
            bbox_maxy=bounds[3],
            area_ha=area_ha,
            country=country,
        ))
    else:
        result.errors.append({
            "row": idx,
            "error": f"Unsupported geometry type: {geom_type}. Supported: Point, Polygon, MultiPolygon",
        })


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def validate_upload(content: bytes, filename: str, project_id: str) -> ValidationResult:
    """Auto-detect file type and validate parcels.

    Args:
        content: Raw file bytes.
        filename: Original filename (used for type detection).
        project_id: Target project UUID.

    Returns:
        ValidationResult with valid parcels and error list.
    """
    fn = filename.lower()
    if fn.endswith(".csv"):
        return validate_csv(content, project_id)
    if fn.endswith((".geojson", ".json")):
        return validate_geojson(content, project_id)

    # Try to auto-detect JSON vs CSV
    stripped = content.lstrip()
    if stripped.startswith(b"{") or stripped.startswith(b"["):
        return validate_geojson(content, project_id)
    return validate_csv(content, project_id)

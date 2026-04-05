"""Output writers for inference results.

Supports GeoJSON, COG (Cloud-Optimized GeoTIFF), JSON, and CSV output formats.
"""

import csv
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def write_geojson(data: dict[str, Any], path: str | Path) -> None:
    """Write a GeoJSON FeatureCollection to disk.

    Args:
        data: GeoJSON dictionary.
        path: Output file path (.geojson or .json).
    """
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=_json_default)
    logger.info("GeoJSON written: %s (%d features)", out_path, len(data.get("features", [])))


def write_json(data: dict[str, Any], path: str | Path) -> None:
    """Write any JSON-serialisable dictionary to disk.

    Args:
        data: Data dictionary.
        path: Output file path (.json).
    """
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=_json_default)
    logger.info("JSON written: %s", out_path)


def write_csv(data: dict[str, Any], path: str | Path) -> None:
    """Write inference result statistics as CSV.

    Args:
        data: Result dictionary (class_ids, confidences, etc.).
        path: Output file path (.csv).
    """
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    class_ids = data.get("class_ids", [])
    confidences = data.get("confidences", [])
    n = max(len(class_ids), len(confidences))

    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["tile_index", "class_id", "confidence"])
        writer.writeheader()
        for i in range(n):
            writer.writerow({
                "tile_index": i,
                "class_id": class_ids[i] if i < len(class_ids) else "",
                "confidence": round(confidences[i], 4) if i < len(confidences) else "",
            })
    logger.info("CSV written: %s (%d rows)", out_path, n)


def write_cog(
    array: np.ndarray,
    path: str | Path,
    crs: Any = None,
    transform: Any = None,
) -> None:
    """Write a numpy array as a Cloud-Optimized GeoTIFF.

    Args:
        array: Array to write, shape (C, H, W) or (H, W).
        path: Output .tif file path.
        crs: Rasterio CRS object (optional).
        transform: Rasterio Affine transform (optional).
    """
    try:
        import rasterio
        from rasterio.transform import from_bounds
    except ImportError:
        logger.warning("rasterio not available — COG output skipped")
        return

    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if array.ndim == 2:
        array = array[np.newaxis, ...]

    c, h, w = array.shape
    profile = {
        "driver": "GTiff",
        "dtype": str(array.dtype),
        "width": w,
        "height": h,
        "count": c,
    }
    if crs is not None:
        profile["crs"] = crs
    if transform is not None:
        profile["transform"] = transform

    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(array)
    logger.info("COG written: %s shape=%s", out_path, array.shape)


def _json_default(obj: Any) -> Any:
    """JSON serialisation fallback for numpy types."""
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")

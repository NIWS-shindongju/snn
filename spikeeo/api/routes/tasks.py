"""Task listing API route."""

import logging

from fastapi import APIRouter, Request

from spikeeo.api.schemas import TaskInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["Tasks"])

_TASK_REGISTRY: list[TaskInfo] = [
    TaskInfo(
        name="classification",
        description="N-class land cover classification. Returns class_map and confidence_map.",
        output_keys=["class_ids", "confidences", "class_areas", "geojson"],
    ),
    TaskInfo(
        name="detection",
        description="Object counting (vehicles, buildings). Returns centroids and count.",
        output_keys=["detections", "object_count", "centroids", "geojson"],
    ),
    TaskInfo(
        name="change_detection",
        description="Multi-temporal change detection between two images.",
        output_keys=["change_map", "change_stats", "geojson"],
    ),
    TaskInfo(
        name="segmentation",
        description="Pixel-wise semantic segmentation.",
        output_keys=["segment_map", "class_areas", "geojson"],
    ),
    TaskInfo(
        name="anomaly",
        description="Anomaly detection for fire, spill, and deforestation events.",
        output_keys=["anomaly_scores", "anomaly_mask", "anomaly_count", "geojson"],
    ),
]


@router.get("", response_model=list[TaskInfo])
async def list_tasks(request: Request) -> list[TaskInfo]:
    """Return the list of supported inference tasks.

    Args:
        request: FastAPI request.

    Returns:
        List of TaskInfo objects.
    """
    return _TASK_REGISTRY


@router.get("/models", tags=["Tasks"])
async def list_models(request: Request) -> dict:
    """Return information about available model configurations.

    Args:
        request: FastAPI request.

    Returns:
        Dict with model configuration options.
    """
    return {
        "backbone_depths": ["light", "standard", "deep"],
        "supported_tasks": [t.name for t in _TASK_REGISTRY],
        "default_num_bands": 10,
        "default_tile_size": 64,
        "default_num_steps": 15,
    }

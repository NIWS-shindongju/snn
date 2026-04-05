"""Inference API routes.

Endpoints for uploading GeoTIFF files and running SNN inference.
"""

import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse

from spikeeo.api.schemas import InferenceRequest, InferenceResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inference", tags=["Inference"])


@router.post("", response_model=InferenceResponse)
async def run_inference(
    request: Request,
    file: UploadFile = File(..., description="GeoTIFF file to analyse"),
    task: str = "classification",
    num_classes: int = 2,
    num_bands: int = 10,
    confidence_threshold: float = 0.75,
    use_hybrid: bool = True,
) -> InferenceResponse:
    """Upload a GeoTIFF and run SNN inference.

    Args:
        request: FastAPI request.
        file: Uploaded GeoTIFF file.
        task: Inference task type.
        num_classes: Number of output classes.
        num_bands: Number of input spectral bands.
        confidence_threshold: SNN confidence threshold.
        use_hybrid: Whether to use SNN+CNN hybrid routing.

    Returns:
        InferenceResponse with classification results.
    """
    import spikeeo

    if not file.filename or not file.filename.lower().endswith((".tif", ".tiff")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File must be a GeoTIFF (.tif or .tiff)",
        )

    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        engine = spikeeo.Engine(
            task=task,
            num_classes=num_classes,
            num_bands=num_bands,
            confidence_threshold=confidence_threshold,
            use_hybrid=use_hybrid,
        )
        result = engine.run(tmp_path)
    except Exception as exc:
        logger.exception("Inference failed for %s", file.filename)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    class_ids = result.get("class_ids", [])
    class_dist: dict[str, int] = {}
    for cid in class_ids:
        k = str(cid)
        class_dist[k] = class_dist.get(k, 0) + 1

    return InferenceResponse(
        task=task,
        num_tiles=result.get("metadata", {}).get("num_tiles", 0),
        class_distribution=class_dist,
        geojson=result.get("geojson"),
        cost_report=result.get("cost_report"),
        metadata=result.get("metadata", {}),
    )


@router.post("/batch", tags=["Inference"])
async def run_batch_inference(
    request: Request,
    files: list[UploadFile] = File(...),
    task: str = "classification",
    num_classes: int = 2,
    num_bands: int = 10,
) -> dict[str, Any]:
    """Run batch inference on multiple GeoTIFF files.

    Args:
        request: FastAPI request.
        files: List of uploaded GeoTIFF files.
        task: Inference task type.
        num_classes: Number of output classes.
        num_bands: Number of input bands.

    Returns:
        Dict with results list and summary statistics.
    """
    import spikeeo

    engine = spikeeo.Engine(task=task, num_classes=num_classes, num_bands=num_bands)
    results = []
    tmp_paths = []

    for f in files:
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
            tmp.write(await f.read())
            tmp_paths.append(tmp.name)

    try:
        for i, tmp_path in enumerate(tmp_paths):
            try:
                r = engine.run(tmp_path)
                results.append({"filename": files[i].filename, "success": True, **r})
            except Exception as exc:
                results.append({"filename": files[i].filename, "success": False, "error": str(exc)})
    finally:
        for p in tmp_paths:
            Path(p).unlink(missing_ok=True)

    return {"results": results, "total": len(results), "succeeded": sum(1 for r in results if r.get("success"))}


@router.post("/change-detection", tags=["Inference"])
async def run_change_detection(
    request: Request,
    before: UploadFile = File(..., description="Before GeoTIFF"),
    after: UploadFile = File(..., description="After GeoTIFF"),
) -> dict[str, Any]:
    """Detect changes between two GeoTIFF acquisitions.

    Args:
        request: FastAPI request.
        before: Before-state GeoTIFF.
        after: After-state GeoTIFF.

    Returns:
        Change detection result with statistics and GeoJSON.
    """
    import spikeeo

    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as b_tmp:
        b_tmp.write(await before.read())
        before_path = b_tmp.name

    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as a_tmp:
        a_tmp.write(await after.read())
        after_path = a_tmp.name

    try:
        engine = spikeeo.Engine(task="change_detection")
        result = engine.run_change(before_path, after_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        Path(before_path).unlink(missing_ok=True)
        Path(after_path).unlink(missing_ok=True)

    return result

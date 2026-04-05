"""Analysis request, result retrieval and GeoTIFF download endpoints."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import FileResponse

from carbonsnn.api.deps import CurrentUserDep, DbDep, PageDep
from carbonsnn.api.schemas import AnalysisRequest, AnalysisResponse, AnalysisResultDetail
from carbonsnn.db import crud

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyses", tags=["Analysis"])


# ──────────────────────────────────────────────────────────
# Background analysis task
# ──────────────────────────────────────────────────────────

async def _run_analysis(analysis_id: str, project_id: str) -> None:
    """Background task: run deforestation + carbon analysis.

    This function simulates the full pipeline. In production it would:
    1. Download Sentinel-2 images
    2. Preprocess bands
    3. Run ForestSNN / CarbonSNN inference
    4. Compute carbon stocks
    5. Persist results

    Args:
        analysis_id: Analysis UUID to update.
        project_id: Parent project UUID.
    """
    import asyncio
    import random

    from carbonsnn.db.session import AsyncSessionLocal

    await asyncio.sleep(2)  # Simulate processing time

    async with AsyncSessionLocal() as db:
        try:
            deforestation_ha = round(random.uniform(0.5, 50.0), 4)
            carbon_lost = round(deforestation_ha * 200.0 * 1.26, 4)
            co2_eq = round(carbon_lost * 3.667, 4)

            await crud.update_analysis(
                db,
                analysis_id,
                status="completed",
                area_ha=round(random.uniform(100.0, 5000.0), 4),
                deforestation_ha=deforestation_ha,
                carbon_stock_mg=round(random.uniform(10000.0, 500000.0), 4),
                co2_equivalent_mg=co2_eq,
                result_json=json.dumps({
                    "analysis_id": analysis_id,
                    "deforestation_ha": deforestation_ha,
                    "carbon_lost_mg": carbon_lost,
                    "co2_equivalent_mg": co2_eq,
                }),
                completed_at=datetime.now(timezone.utc),
            )
            await db.commit()
            logger.info("Analysis %s completed", analysis_id)
        except Exception as exc:
            await crud.update_analysis(
                db, analysis_id, status="failed", error_message=str(exc)
            )
            await db.commit()
            logger.error("Analysis %s failed: %s", analysis_id, exc)


# ──────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────

@router.post("/", response_model=AnalysisResponse, status_code=status.HTTP_202_ACCEPTED)
async def request_analysis(
    body: AnalysisRequest,
    user: CurrentUserDep,
    db: DbDep,
    background_tasks: BackgroundTasks,
) -> AnalysisResponse:
    """Submit a new deforestation analysis request.

    The analysis is processed asynchronously. Poll the result endpoint
    until status='completed'.

    Args:
        body: Analysis request parameters.
        user: Authenticated user.
        db: Database session.
        background_tasks: FastAPI background task runner.

    Returns:
        Pending analysis record.
    """
    project = await crud.get_project(db, body.project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    analysis = await crud.create_analysis(
        db=db,
        project_id=body.project_id,
        sensing_date_before=body.sensing_date_before,
        sensing_date_after=body.sensing_date_after,
    )
    await db.flush()

    background_tasks.add_task(_run_analysis, analysis.id, body.project_id)
    logger.info("Analysis %s queued for project %s", analysis.id, body.project_id)
    return AnalysisResponse.model_validate(analysis)


@router.get("/{analysis_id}", response_model=AnalysisResultDetail)
async def get_analysis(
    analysis_id: str,
    user: CurrentUserDep,
    db: DbDep,
) -> AnalysisResultDetail:
    """Retrieve analysis result by ID.

    Args:
        analysis_id: Analysis UUID.
        user: Authenticated user.
        db: Database session.

    Returns:
        Detailed analysis record including JSON result.
    """
    analysis = await crud.get_analysis(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")

    # Verify ownership via project
    project = await crud.get_project(db, analysis.project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return AnalysisResultDetail.model_validate(analysis)


@router.get("/project/{project_id}", response_model=list[AnalysisResponse])
async def list_analyses(
    project_id: str,
    user: CurrentUserDep,
    db: DbDep,
    page: PageDep,
) -> list[AnalysisResponse]:
    """List analyses for a specific project.

    Args:
        project_id: Project UUID.
        user: Authenticated user.
        db: Database session.
        page: Pagination.

    Returns:
        List of analysis records ordered newest first.
    """
    project = await crud.get_project(db, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    analyses = await crud.list_analyses(db, project_id=project_id, skip=page.skip, limit=page.limit)
    return [AnalysisResponse.model_validate(a) for a in analyses]


@router.get("/{analysis_id}/download")
async def download_geotiff(
    analysis_id: str,
    user: CurrentUserDep,
    db: DbDep,
) -> FileResponse:
    """Download the GeoTIFF result file for a completed analysis.

    Args:
        analysis_id: Analysis UUID.
        user: Authenticated user.
        db: Database session.

    Returns:
        GeoTIFF file download response.

    Raises:
        HTTPException 404: If analysis or file not found.
        HTTPException 409: If analysis not yet completed.
    """
    analysis = await crud.get_analysis(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")

    project = await crud.get_project(db, analysis.project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if analysis.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Analysis not completed (status={analysis.status})",
        )

    if not analysis.geotiff_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GeoTIFF not available")

    geotiff_path = Path(analysis.geotiff_path)
    if not geotiff_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GeoTIFF file missing")

    return FileResponse(
        path=str(geotiff_path),
        media_type="image/tiff",
        filename=f"analysis_{analysis_id}.tif",
    )

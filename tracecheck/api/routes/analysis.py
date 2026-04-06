"""Analysis job endpoints: trigger, status, results."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from tracecheck.api.auth import get_current_user
from tracecheck.api.schemas import (
    JobOut,
    ParcelResultOut,
    ResultsSummary,
)
from tracecheck.db import crud
from tracecheck.db.models import User
from tracecheck.db.session import AsyncSessionLocal, get_db

router = APIRouter(tags=["analysis"])


@router.post(
    "/projects/{project_id}/analyze",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_analysis(
    project_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobOut:
    """Start an EUDR analysis job for all parcels in a project.

    Returns immediately with job_id — poll GET /api/jobs/{job_id} for status.
    """
    project = await crud.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    total = await crud.count_parcels(db, project_id)
    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Project has no parcels. Upload parcels first.",
        )

    job = await crud.create_job(db, project_id, current_user.id, total_parcels=total)
    await db.commit()

    # Launch pipeline in background (new DB session to avoid sharing)
    background_tasks.add_task(_run_pipeline_bg, job.id)

    return JobOut.model_validate(job)


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobOut:
    """Get job status and progress."""
    job = await crud.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    # Verify ownership via project
    project = await crud.get_project(db, job.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return JobOut.model_validate(job)


@router.get("/jobs/{job_id}/results", response_model=list[ParcelResultOut])
async def get_results(
    job_id: str,
    risk_level: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ParcelResultOut]:
    """Get per-parcel results for a job.

    Optionally filter by risk_level: low | review | high
    """
    job = await crud.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    project = await crud.get_project(db, job.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    results = await crud.list_results(db, job_id)

    if risk_level:
        results = [r for r in results if r.risk_level == risk_level]

    out = []
    for r in results:
        item = ParcelResultOut.model_validate(r)
        if r.parcel:
            item.parcel_ref = r.parcel.parcel_ref
            item.supplier_name = r.parcel.supplier_name
        out.append(item)
    return out


@router.get("/jobs/{job_id}/results/summary", response_model=ResultsSummary)
async def get_results_summary(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResultsSummary:
    """Get risk level summary counts for a job."""
    job = await crud.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    project = await crud.get_project(db, job.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    summary = await crud.get_results_summary(db, job_id)
    total = summary["total"]

    def pct(n: int) -> float:
        return round(n / total * 100, 1) if total > 0 else 0.0

    return ResultsSummary(
        job_id=job_id,
        status=job.status,
        total=total,
        low=summary["low"],
        review=summary["review"],
        high=summary["high"],
        low_pct=pct(summary["low"]),
        review_pct=pct(summary["review"]),
        high_pct=pct(summary["high"]),
    )


@router.get("/projects/{project_id}/jobs", response_model=list[JobOut])
async def list_jobs(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[JobOut]:
    """List all analysis jobs for a project."""
    project = await crud.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    jobs = await crud.list_jobs(db, project_id)
    return [JobOut.model_validate(j) for j in jobs]


# ─────────────────────────────────────────────────────────────────────────────
# Background task helper
# ─────────────────────────────────────────────────────────────────────────────

async def _run_pipeline_bg(job_id: str) -> None:
    """Run pipeline in background with a fresh DB session."""
    from tracecheck.pipeline.eudr_pipeline import run_eudr_analysis

    async with AsyncSessionLocal() as db:
        try:
            await run_eudr_analysis(job_id, db)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("Pipeline error job=%s: %s", job_id, exc)
            try:
                from tracecheck.db.crud import update_job_status
                await update_job_status(db, job_id, "failed", error_message=str(exc))
                await db.commit()
            except Exception:
                pass

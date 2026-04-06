"""Analysis job endpoints: trigger, status, results.

v2: uses job_runs / plot_assessments tables.
Old paths (analysis_jobs / parcel_results) kept as aliases.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from tracecheck.api.auth import get_current_user
from tracecheck.api.schemas import (
    AssessmentsSummary,
    JobRunOut,
    PlotAssessmentOut,
)
from tracecheck.db import crud
from tracecheck.db.models import User
from tracecheck.db.session import AsyncSessionLocal, get_db

router = APIRouter(tags=["analysis"])


# ─────────────────────────────────────────────────────────────────────────────
# Trigger analysis
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/projects/{project_id}/analyze",
    response_model=JobRunOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_analysis(
    project_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobRunOut:
    """Start an EUDR analysis job for all plots in a project.

    Returns immediately with job_run_id — poll GET /api/jobs/{id} for status.
    """
    project = await crud.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    total = await crud.count_plots(db, project_id)
    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Project has no plots. Upload plots first.",
        )

    job = await crud.create_job_run(
        db,
        project_id=project_id,
        triggered_by=current_user.id,
        total_plots=total,
    )
    await crud.log_action(
        db, project_id=project_id, user_id=current_user.id,
        action="job.started",
        detail={"job_run_id": job.id, "total_plots": total},
    )
    await db.commit()

    background_tasks.add_task(_run_pipeline_bg, job.id)
    return JobRunOut.model_validate(job)


# ─────────────────────────────────────────────────────────────────────────────
# Job status
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/jobs/{job_id}", response_model=JobRunOut)
async def get_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobRunOut:
    """Get job run status and progress."""
    job = await crud.get_job_run(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    project = await crud.get_project(db, job.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return JobRunOut.model_validate(job)


# ─────────────────────────────────────────────────────────────────────────────
# Per-plot results
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/jobs/{job_id}/results", response_model=list[PlotAssessmentOut])
async def get_results(
    job_id: str,
    risk_level: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlotAssessmentOut]:
    """Get per-plot assessment results for a job.

    Optionally filter by risk_level: low | review | high
    """
    job = await crud.get_job_run(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    project = await crud.get_project(db, job.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    assessments = await crud.list_assessments(db, job_id, risk_level=risk_level)

    out = []
    for a in assessments:
        item = PlotAssessmentOut.model_validate(a)
        if a.plot:
            item.plot_ref = a.plot.plot_ref
            item.supplier_name = a.plot.supplier_name
        out.append(item)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Results summary
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/jobs/{job_id}/results/summary", response_model=AssessmentsSummary)
async def get_results_summary(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AssessmentsSummary:
    """Get risk-level summary counts for a job."""
    job = await crud.get_job_run(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    project = await crud.get_project(db, job.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    summary = await crud.get_assessments_summary(db, job_id)
    total = summary["total"]

    def pct(n: int) -> float:
        return round(n / total * 100, 1) if total > 0 else 0.0

    return AssessmentsSummary(
        job_run_id=job_id,
        status=job.status,
        total=total,
        low=summary["low"],
        review=summary["review"],
        high=summary["high"],
        low_pct=pct(summary["low"]),
        review_pct=pct(summary["review"]),
        high_pct=pct(summary["high"]),
    )


# ─────────────────────────────────────────────────────────────────────────────
# List job runs for a project
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/jobs", response_model=list[JobRunOut])
async def list_jobs(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[JobRunOut]:
    """List all analysis job runs for a project."""
    project = await crud.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    jobs = await crud.list_job_runs(db, project_id)
    return [JobRunOut.model_validate(j) for j in jobs]


# ─────────────────────────────────────────────────────────────────────────────
# Audit history for a project
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/history")
async def get_project_history(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return audit log for a project (latest 100 entries)."""
    project = await crud.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    logs = await crud.list_audit_logs(db, project_id)
    return [
        {
            "id": log.id,
            "action": log.action,
            "detail": log.detail,
            "occurred_at": log.occurred_at.isoformat(),
        }
        for log in logs
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Background task helper
# ─────────────────────────────────────────────────────────────────────────────

async def _run_pipeline_bg(job_id: str) -> None:
    """Run EUDR pipeline in background with a fresh DB session."""
    from tracecheck.pipeline.eudr_pipeline import run_eudr_analysis

    async with AsyncSessionLocal() as db:
        try:
            await run_eudr_analysis(job_id, db)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("Pipeline error job=%s: %s", job_id, exc)
            try:
                from tracecheck.db.crud import update_job_run_status
                await update_job_run_status(db, job_id, "failed", error_message=str(exc))
                await db.commit()
            except Exception:
                pass

"""TraceCheck CRUD helpers — v2 SaaS schema.

All operations use async SQLAlchemy sessions.
Table names: users, projects, plots, job_runs, plot_assessments,
             evidence_exports, audit_logs
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tracecheck.db.models import (
    AuditLog,
    EvidenceExport,
    JobRun,
    Plot,
    PlotAssessment,
    Project,
    User,
)

logger = logging.getLogger(__name__)


# ─── users ────────────────────────────────────────────────────────────────────

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    email: str,
    hashed_password: str,
    org_name: Optional[str] = None,
) -> User:
    user = User(email=email, hashed_password=hashed_password, org_name=org_name)
    db.add(user)
    await db.flush()
    return user


# ─── projects ─────────────────────────────────────────────────────────────────

async def list_projects(db: AsyncSession, owner_id: str) -> list[Project]:
    result = await db.execute(
        select(Project)
        .where(Project.owner_id == owner_id)
        .order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


async def get_project(
    db: AsyncSession, project_id: str, owner_id: Optional[str] = None
) -> Optional[Project]:
    q = select(Project).where(Project.id == project_id)
    if owner_id:
        q = q.where(Project.owner_id == owner_id)
    result = await db.execute(q)
    return result.scalar_one_or_none()


async def create_project(
    db: AsyncSession,
    owner_id: str,
    name: str,
    commodity: str = "coffee",
    origin_country: Optional[str] = None,
    cutoff_date: str = "2020-12-31",
    description: Optional[str] = None,
) -> Project:
    project = Project(
        owner_id=owner_id,
        name=name,
        commodity=commodity,
        origin_country=origin_country,
        cutoff_date=cutoff_date,
        description=description,
    )
    db.add(project)
    await db.flush()
    return project


async def delete_project(db: AsyncSession, project_id: str) -> bool:
    project = await get_project(db, project_id)
    if not project:
        return False
    await db.delete(project)
    await db.flush()
    return True


async def count_plots(db: AsyncSession, project_id: str) -> int:
    result = await db.execute(
        select(func.count()).select_from(Plot).where(Plot.project_id == project_id)
    )
    return result.scalar() or 0


# ─── plots ────────────────────────────────────────────────────────────────────

async def list_plots(db: AsyncSession, project_id: str) -> list[Plot]:
    result = await db.execute(
        select(Plot).where(Plot.project_id == project_id).order_by(Plot.uploaded_at)
    )
    return list(result.scalars().all())


async def get_plot(db: AsyncSession, plot_id: str) -> Optional[Plot]:
    result = await db.execute(select(Plot).where(Plot.id == plot_id))
    return result.scalar_one_or_none()


async def create_plots_bulk(
    db: AsyncSession,
    project_id: str,
    plots_data: list[dict[str, Any]],
) -> list[Plot]:
    """Bulk-insert plot records. Returns list of created Plot objects."""
    plots = []
    for d in plots_data:
        plot = Plot(project_id=project_id, **d)
        db.add(plot)
        plots.append(plot)
    await db.flush()
    return plots


async def delete_plot(db: AsyncSession, plot_id: str) -> bool:
    plot = await get_plot(db, plot_id)
    if not plot:
        return False
    await db.delete(plot)
    await db.flush()
    return True


# ─── job_runs ─────────────────────────────────────────────────────────────────

async def create_job_run(
    db: AsyncSession,
    project_id: str,
    triggered_by: str,
    total_plots: int = 0,
    data_mode: str = "mock",
) -> JobRun:
    job = JobRun(
        project_id=project_id,
        triggered_by=triggered_by,
        total_plots=total_plots,
        data_mode=data_mode,
    )
    db.add(job)
    await db.flush()
    return job


async def get_job_run(
    db: AsyncSession, job_id: str, load_assessments: bool = False
) -> Optional[JobRun]:
    q = select(JobRun).where(JobRun.id == job_id)
    if load_assessments:
        q = q.options(
            selectinload(JobRun.plot_assessments).selectinload(PlotAssessment.plot)
        )
    result = await db.execute(q)
    return result.scalar_one_or_none()


async def list_job_runs(db: AsyncSession, project_id: str) -> list[JobRun]:
    result = await db.execute(
        select(JobRun)
        .where(JobRun.project_id == project_id)
        .order_by(JobRun.created_at.desc())
    )
    return list(result.scalars().all())


async def update_job_run_status(
    db: AsyncSession,
    job_id: str,
    status: str,
    processed_plots: Optional[int] = None,
    error_message: Optional[str] = None,
) -> None:
    job = await get_job_run(db, job_id)
    if not job:
        return
    job.status = status
    if processed_plots is not None:
        job.processed_plots = processed_plots
    if error_message is not None:
        job.error_message = error_message
    if status == "running" and job.started_at is None:
        job.started_at = datetime.now(timezone.utc)
    if status in ("done", "failed"):
        job.completed_at = datetime.now(timezone.utc)
    await db.flush()


# ─── plot_assessments ─────────────────────────────────────────────────────────

async def save_plot_assessment(
    db: AsyncSession,
    job_run_id: str,
    plot_id: str,
    risk_level: str,
    metrics: dict[str, Any],
) -> PlotAssessment:
    pa = PlotAssessment(
        job_run_id=job_run_id,
        plot_id=plot_id,
        risk_level=risk_level,
        **metrics,
    )
    db.add(pa)
    await db.flush()
    return pa


async def list_assessments(
    db: AsyncSession, job_run_id: str, risk_level: Optional[str] = None
) -> list[PlotAssessment]:
    q = (
        select(PlotAssessment)
        .where(PlotAssessment.job_run_id == job_run_id)
        .options(selectinload(PlotAssessment.plot))
        .order_by(PlotAssessment.assessed_at)
    )
    if risk_level:
        q = q.where(PlotAssessment.risk_level == risk_level)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_assessments_summary(
    db: AsyncSession, job_run_id: str
) -> dict[str, int]:
    result = await db.execute(
        select(PlotAssessment.risk_level, func.count().label("cnt"))
        .where(PlotAssessment.job_run_id == job_run_id)
        .group_by(PlotAssessment.risk_level)
    )
    rows = result.all()
    counts = {"low": 0, "review": 0, "high": 0}
    for row in rows:
        if row.risk_level in counts:
            counts[row.risk_level] = row.cnt
    counts["total"] = sum(counts.values())
    return counts


# ─── evidence_exports ─────────────────────────────────────────────────────────

async def create_evidence_export(
    db: AsyncSession,
    job_run_id: str,
    created_by: str,
    fmt: str,
    file_path: Optional[str] = None,
    file_size: Optional[int] = None,
    summary_snapshot: Optional[Any] = None,
) -> EvidenceExport:
    export = EvidenceExport(
        job_run_id=job_run_id,
        created_by=created_by,
        format=fmt,
        file_path=file_path,
        file_size_bytes=file_size,
        summary_snapshot=summary_snapshot,
    )
    db.add(export)
    await db.flush()
    return export


async def get_evidence_export(
    db: AsyncSession, export_id: str
) -> Optional[EvidenceExport]:
    result = await db.execute(
        select(EvidenceExport).where(EvidenceExport.id == export_id)
    )
    return result.scalar_one_or_none()


async def list_evidence_exports(
    db: AsyncSession, job_run_id: str
) -> list[EvidenceExport]:
    result = await db.execute(
        select(EvidenceExport)
        .where(EvidenceExport.job_run_id == job_run_id)
        .order_by(EvidenceExport.generated_at.desc())
    )
    return list(result.scalars().all())


# ─── audit_logs ───────────────────────────────────────────────────────────────

async def log_action(
    db: AsyncSession,
    project_id: str,
    user_id: str,
    action: str,
    detail: Optional[Any] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    entry = AuditLog(
        project_id=project_id,
        user_id=user_id,
        action=action,
        detail=detail,
        ip_address=ip_address,
    )
    db.add(entry)
    await db.flush()
    return entry


async def list_audit_logs(
    db: AsyncSession, project_id: str, limit: int = 100
) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.project_id == project_id)
        .order_by(AuditLog.occurred_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())

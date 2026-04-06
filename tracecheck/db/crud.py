"""Async CRUD helpers for TraceCheck ORM models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tracecheck.db.models import (
    AnalysisJob,
    Parcel,
    ParcelResult,
    Project,
    Report,
    User,
)


# ─────────────────────────────────────────────────────────────────────────────
# User
# ─────────────────────────────────────────────────────────────────────────────

async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession, email: str, hashed_password: str, org_name: str | None = None
) -> User:
    user = User(email=email, hashed_password=hashed_password, org_name=org_name)
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


# ─────────────────────────────────────────────────────────────────────────────
# Project
# ─────────────────────────────────────────────────────────────────────────────

async def list_projects(db: AsyncSession, owner_id: str) -> list[Project]:
    result = await db.execute(
        select(Project)
        .where(Project.owner_id == owner_id)
        .order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


async def get_project(db: AsyncSession, project_id: str, owner_id: str) -> Project | None:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == owner_id)
    )
    return result.scalar_one_or_none()


async def create_project(
    db: AsyncSession,
    owner_id: str,
    name: str,
    commodity: str,
    description: str | None = None,
    origin_country: str | None = None,
    cutoff_date: str = "2020-12-31",
) -> Project:
    project = Project(
        owner_id=owner_id,
        name=name,
        commodity=commodity,
        description=description,
        origin_country=origin_country,
        cutoff_date=cutoff_date,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, project_id: str, owner_id: str) -> bool:
    project = await get_project(db, project_id, owner_id)
    if not project:
        return False
    await db.delete(project)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Parcel
# ─────────────────────────────────────────────────────────────────────────────

async def list_parcels(db: AsyncSession, project_id: str) -> list[Parcel]:
    result = await db.execute(
        select(Parcel)
        .where(Parcel.project_id == project_id)
        .order_by(Parcel.uploaded_at.asc())
    )
    return list(result.scalars().all())


async def get_parcel(db: AsyncSession, parcel_id: str) -> Parcel | None:
    result = await db.execute(select(Parcel).where(Parcel.id == parcel_id))
    return result.scalar_one_or_none()


async def create_parcels_bulk(db: AsyncSession, parcels: list[dict[str, Any]]) -> list[Parcel]:
    """Bulk insert validated parcels."""
    orm_parcels = [Parcel(**p) for p in parcels]
    db.add_all(orm_parcels)
    await db.flush()
    for p in orm_parcels:
        await db.refresh(p)
    return orm_parcels


async def delete_parcel(db: AsyncSession, parcel_id: str) -> bool:
    parcel = await get_parcel(db, parcel_id)
    if not parcel:
        return False
    await db.delete(parcel)
    return True


async def count_parcels(db: AsyncSession, project_id: str) -> int:
    result = await db.execute(
        select(func.count()).where(Parcel.project_id == project_id)
    )
    return result.scalar_one()


# ─────────────────────────────────────────────────────────────────────────────
# AnalysisJob
# ─────────────────────────────────────────────────────────────────────────────

async def create_job(
    db: AsyncSession, project_id: str, triggered_by: str, total_parcels: int
) -> AnalysisJob:
    job = AnalysisJob(
        project_id=project_id,
        triggered_by=triggered_by,
        total_parcels=total_parcels,
        status="pending",
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return job


async def get_job(db: AsyncSession, job_id: str) -> AnalysisJob | None:
    result = await db.execute(
        select(AnalysisJob)
        .where(AnalysisJob.id == job_id)
        .options(selectinload(AnalysisJob.results).selectinload(ParcelResult.parcel))
    )
    return result.scalar_one_or_none()


async def list_jobs(db: AsyncSession, project_id: str) -> list[AnalysisJob]:
    result = await db.execute(
        select(AnalysisJob)
        .where(AnalysisJob.project_id == project_id)
        .order_by(AnalysisJob.created_at.desc())
    )
    return list(result.scalars().all())


async def update_job_status(
    db: AsyncSession,
    job_id: str,
    status: str,
    error_message: str | None = None,
    processed_parcels: int | None = None,
) -> None:
    job = await db.get(AnalysisJob, job_id)
    if not job:
        return
    job.status = status
    if error_message is not None:
        job.error_message = error_message
    if processed_parcels is not None:
        job.processed_parcels = processed_parcels
    if status == "running" and job.started_at is None:
        job.started_at = datetime.now(timezone.utc)
    if status in ("done", "failed"):
        job.completed_at = datetime.now(timezone.utc)
    await db.flush()


# ─────────────────────────────────────────────────────────────────────────────
# ParcelResult
# ─────────────────────────────────────────────────────────────────────────────

async def save_parcel_result(db: AsyncSession, data: dict[str, Any]) -> ParcelResult:
    result_obj = ParcelResult(**data)
    db.add(result_obj)
    await db.flush()
    await db.refresh(result_obj)
    return result_obj


async def list_results(db: AsyncSession, job_id: str) -> list[ParcelResult]:
    result = await db.execute(
        select(ParcelResult)
        .where(ParcelResult.job_id == job_id)
        .options(selectinload(ParcelResult.parcel))
        .order_by(ParcelResult.analyzed_at.asc())
    )
    return list(result.scalars().all())


async def get_results_summary(db: AsyncSession, job_id: str) -> dict[str, int]:
    """Return count of each risk level for a job."""
    result = await db.execute(
        select(ParcelResult.risk_level, func.count().label("cnt"))
        .where(ParcelResult.job_id == job_id)
        .group_by(ParcelResult.risk_level)
    )
    rows = result.all()
    summary = {"low": 0, "review": 0, "high": 0, "total": 0}
    for row in rows:
        level = row.risk_level
        if level in summary:
            summary[level] = row.cnt
        summary["total"] += row.cnt
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────────────────────

async def create_report(
    db: AsyncSession, job_id: str, fmt: str, file_path: str, file_size: int
) -> Report:
    report = Report(job_id=job_id, format=fmt, file_path=file_path, file_size_bytes=file_size)
    db.add(report)
    await db.flush()
    await db.refresh(report)
    return report


async def get_report(db: AsyncSession, report_id: str) -> Report | None:
    result = await db.execute(select(Report).where(Report.id == report_id))
    return result.scalar_one_or_none()


async def list_reports(db: AsyncSession, job_id: str) -> list[Report]:
    result = await db.execute(
        select(Report).where(Report.job_id == job_id).order_by(Report.generated_at.desc())
    )
    return list(result.scalars().all())

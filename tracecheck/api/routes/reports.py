"""Report generation and download endpoints."""

from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from tracecheck.api.auth import get_current_user
from tracecheck.api.schemas import ReportOut, ReportRequest
from tracecheck.config import settings
from tracecheck.core.report_generator import generate_json_report, generate_pdf_report, generate_csv_report
from tracecheck.db import crud
from tracecheck.db.models import User
from tracecheck.db.session import get_db

router = APIRouter(tags=["reports"])


@router.post(
    "/jobs/{job_id}/reports",
    response_model=ReportOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_report(
    job_id: str,
    body: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportOut:
    """Generate an evidence report for a completed analysis job."""
    job = await crud.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    project = await crud.get_project(db, job.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    if job.status != "done":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Job is not complete (status={job.status}). Wait for analysis to finish.",
        )

    results = await crud.list_results(db, job_id)
    summary = await crud.get_results_summary(db, job_id)

    # Ensure report dir exists
    report_dir = Path(settings.data_dir) / "reports" / job_id
    report_dir.mkdir(parents=True, exist_ok=True)

    fmt = body.format
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"tracecheck_report_{job_id[:8]}_{timestamp}.{fmt}"
    file_path = report_dir / filename

    if fmt == "json":
        generate_json_report(job, project, current_user, results, summary, file_path)
    elif fmt == "pdf":
        generate_pdf_report(job, project, current_user, results, summary, file_path)
    elif fmt == "csv":
        generate_csv_report(results, file_path)

    file_size = file_path.stat().st_size

    report = await crud.create_report(
        db, job_id=job_id, fmt=fmt, file_path=str(file_path), file_size=file_size
    )
    return ReportOut.model_validate(report)


@router.get("/reports/{report_id}/download")
async def download_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download a generated report file."""
    report = await crud.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    # Verify ownership
    job = await crud.get_job(db, report.job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    project = await crud.get_project(db, job.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    file_path = Path(report.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found on server",
        )

    media_types = {"json": "application/json", "pdf": "application/pdf", "csv": "text/csv"}
    return FileResponse(
        path=str(file_path),
        media_type=media_types.get(report.format, "application/octet-stream"),
        filename=file_path.name,
    )


@router.get("/jobs/{job_id}/reports", response_model=list[ReportOut])
async def list_reports(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ReportOut]:
    """List all generated reports for a job."""
    job = await crud.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    project = await crud.get_project(db, job.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    reports = await crud.list_reports(db, job_id)
    return [ReportOut.model_validate(r) for r in reports]

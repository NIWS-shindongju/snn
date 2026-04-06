"""Evidence export generation and download endpoints.

v2: uses evidence_exports table (was: reports).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from tracecheck.api.auth import get_current_user
from tracecheck.api.schemas import EvidenceExportOut, ExportRequest
from tracecheck.config import settings
from tracecheck.core.report_generator import (
    generate_csv_report,
    generate_json_report,
    generate_pdf_report,
)
from tracecheck.db import crud
from tracecheck.db.models import User
from tracecheck.db.session import get_db

router = APIRouter(tags=["reports"])


@router.post(
    "/jobs/{job_id}/reports",
    response_model=EvidenceExportOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_evidence_export(
    job_id: str,
    body: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvidenceExportOut:
    """Generate an evidence export (PDF/JSON/CSV) for a completed analysis job."""
    job = await crud.get_job_run(db, job_id)
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

    assessments = await crud.list_assessments(db, job_id)
    summary = await crud.get_assessments_summary(db, job_id)

    # Ensure report directory exists
    report_dir = Path(settings.data_dir) / "reports" / job_id
    report_dir.mkdir(parents=True, exist_ok=True)

    fmt = body.format
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"tracecheck_report_{job_id[:8]}_{timestamp}.{fmt}"
    file_path = report_dir / filename

    if fmt == "json":
        generate_json_report(job, project, current_user, assessments, summary, file_path)
    elif fmt == "pdf":
        generate_pdf_report(job, project, current_user, assessments, summary, file_path)
    elif fmt == "csv":
        generate_csv_report(assessments, file_path)

    file_size = file_path.stat().st_size if file_path.exists() else None

    export = await crud.create_evidence_export(
        db,
        job_run_id=job_id,
        created_by=current_user.id,
        fmt=fmt,
        file_path=str(file_path),
        file_size=file_size,
        summary_snapshot=summary,
    )
    await crud.log_action(
        db, project_id=project.id, user_id=current_user.id,
        action="export.created",
        detail={"export_id": export.id, "format": fmt, "file_size": file_size},
    )
    await db.commit()
    return EvidenceExportOut.model_validate(export)


@router.get("/reports/{report_id}/download")
async def download_export(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download a generated evidence export file."""
    export = await crud.get_evidence_export(db, report_id)
    if not export:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")

    # Verify ownership
    job = await crud.get_job_run(db, export.job_run_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    project = await crud.get_project(db, job.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    if not export.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Export file path not stored"
        )
    file_path = Path(export.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Export file not found on server"
        )

    media_types = {
        "json": "application/json",
        "pdf": "application/pdf",
        "csv": "text/csv",
    }
    return FileResponse(
        path=str(file_path),
        media_type=media_types.get(export.format, "application/octet-stream"),
        filename=file_path.name,
    )


@router.get("/jobs/{job_id}/reports", response_model=list[EvidenceExportOut])
async def list_exports(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[EvidenceExportOut]:
    """List all evidence exports for a job."""
    job = await crud.get_job_run(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    project = await crud.get_project(db, job.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    exports = await crud.list_evidence_exports(db, job_id)
    return [EvidenceExportOut.model_validate(e) for e in exports]

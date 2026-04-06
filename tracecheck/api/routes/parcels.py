"""Plot upload, validation, and CRUD endpoints.

Terminology change from v1 → v2:
  parcel  →  plot
  /parcels/  →  /plots/
Old paths kept as aliases for backwards compatibility.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from tracecheck.api.auth import get_current_user
from tracecheck.api.schemas import PlotOut, UploadSummary, ValidationPreview
from tracecheck.core.geo_validator import validate_upload
from tracecheck.db import crud
from tracecheck.db.models import User
from tracecheck.db.session import get_db

router = APIRouter(tags=["plots"])

_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
_MAX_PLOTS = 5_000


# ─────────────────────────────────────────────────────────────────────────────
# Validate (preview without saving)
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/projects/{project_id}/plots/validate",
    response_model=ValidationPreview,
)
async def validate_plots_preview(
    project_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ValidationPreview:
    """Validate uploaded file WITHOUT saving to DB.

    Returns a preview of valid/invalid rows. Use before final upload.
    """
    await _check_project_ownership(db, project_id, current_user.id)
    content = await _read_limited(file)
    vr = validate_upload(content, file.filename or "upload.csv", project_id)

    preview = []
    for p in vr.valid[:20]:
        geojson = json.loads(p.geojson)
        preview.append({
            "plot_ref": p.parcel_ref,
            "supplier_name": p.supplier_name,
            "geometry_type": p.geometry_type,
            "country": p.country,
            "area_ha": p.area_ha,
            "coordinates": geojson.get("geometry", {}).get("coordinates"),
        })

    return ValidationPreview(
        valid_count=vr.valid_count,
        invalid_count=vr.invalid_count,
        errors=vr.errors[:100],
        preview=preview,
    )


# v1 compat alias
@router.post(
    "/projects/{project_id}/parcels/validate",
    response_model=ValidationPreview,
    include_in_schema=False,
)
async def validate_parcels_preview_compat(
    project_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ValidationPreview:
    return await validate_plots_preview(project_id, file, current_user, db)


# ─────────────────────────────────────────────────────────────────────────────
# Upload (save to DB)
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/projects/{project_id}/plots/upload",
    response_model=UploadSummary,
    status_code=status.HTTP_201_CREATED,
)
async def upload_plots(
    project_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadSummary:
    """Upload CSV or GeoJSON containing supplier plots.

    Saves valid plots to DB. Returns created/skipped counts and errors.
    """
    await _check_project_ownership(db, project_id, current_user.id)
    content = await _read_limited(file)
    vr = validate_upload(content, file.filename or "upload.csv", project_id)

    if not vr.valid:
        return UploadSummary(
            created_count=0,
            skipped_count=vr.invalid_count,
            errors=vr.errors[:100],
        )

    if vr.valid_count > _MAX_PLOTS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Upload contains {vr.valid_count} plots, max is {_MAX_PLOTS}",
        )

    plot_dicts: list[dict[str, Any]] = [
        {
            "geometry_type": p.geometry_type,
            "geojson": p.geojson,
            "supplier_name": p.supplier_name,
            "plot_ref": p.parcel_ref,   # geo_validator still uses parcel_ref field
            "bbox_minx": p.bbox_minx,
            "bbox_miny": p.bbox_miny,
            "bbox_maxx": p.bbox_maxx,
            "bbox_maxy": p.bbox_maxy,
            "area_ha": p.area_ha,
            "country": p.country,
        }
        for p in vr.valid
    ]

    saved = await crud.create_plots_bulk(db, project_id, plot_dicts)

    await crud.log_action(
        db, project_id=project_id, user_id=current_user.id,
        action="plots.upload",
        detail={"created": len(saved), "skipped": vr.invalid_count, "filename": file.filename},
    )
    await db.commit()

    return UploadSummary(
        created_count=len(saved),
        skipped_count=vr.invalid_count,
        errors=vr.errors[:100],
        plot_ids=[p.id for p in saved],
    )


# v1 compat alias
@router.post(
    "/projects/{project_id}/parcels/upload",
    response_model=UploadSummary,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def upload_parcels_compat(
    project_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadSummary:
    return await upload_plots(project_id, file, current_user, db)


# ─────────────────────────────────────────────────────────────────────────────
# List plots
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/plots", response_model=list[PlotOut])
async def list_plots(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlotOut]:
    """List all plots for a project."""
    await _check_project_ownership(db, project_id, current_user.id)
    plots = await crud.list_plots(db, project_id)
    return [PlotOut.model_validate(p) for p in plots]


# v1 compat alias
@router.get(
    "/projects/{project_id}/parcels",
    response_model=list[PlotOut],
    include_in_schema=False,
)
async def list_parcels_compat(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlotOut]:
    return await list_plots(project_id, current_user, db)


# ─────────────────────────────────────────────────────────────────────────────
# Delete plot
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/plots/{plot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plot(
    plot_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a single plot."""
    deleted = await crud.delete_plot(db, plot_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plot not found")


# v1 compat
@router.delete(
    "/parcels/{plot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
)
async def delete_parcel_compat(
    plot_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    return await delete_plot(plot_id, current_user, db)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _check_project_ownership(
    db: AsyncSession, project_id: str, user_id: str
) -> None:
    project = await crud.get_project(db, project_id, user_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")


async def _read_limited(file: UploadFile) -> bytes:
    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {_MAX_FILE_SIZE // 1024 // 1024} MB",
        )
    return content

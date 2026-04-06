"""Parcel upload, validation, and CRUD endpoints."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from tracecheck.api.auth import get_current_user
from tracecheck.api.schemas import ParcelOut, UploadSummary, ValidationPreview
from tracecheck.core.geo_validator import validate_upload
from tracecheck.db import crud
from tracecheck.db.models import User
from tracecheck.db.session import get_db

router = APIRouter(tags=["parcels"])

_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
_MAX_PARCELS = 5_000


@router.post(
    "/projects/{project_id}/parcels/validate",
    response_model=ValidationPreview,
)
async def validate_parcels_preview(
    project_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ValidationPreview:
    """Validate uploaded file WITHOUT saving to DB.

    Returns a preview of valid/invalid rows. Use this before final upload.
    """
    await _check_project_ownership(db, project_id, current_user.id)
    content = await _read_limited(file)
    vr = validate_upload(content, file.filename or "upload.csv", project_id)

    preview = []
    for p in vr.valid[:20]:  # show first 20 valid parcels as preview
        geojson = json.loads(p.geojson)
        preview.append({
            "parcel_ref": p.parcel_ref,
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


@router.post(
    "/projects/{project_id}/parcels/upload",
    response_model=UploadSummary,
    status_code=status.HTTP_201_CREATED,
)
async def upload_parcels(
    project_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadSummary:
    """Upload CSV or GeoJSON file containing supplier parcels.

    Saves valid parcels to DB. Returns count of valid/invalid and any errors.
    """
    await _check_project_ownership(db, project_id, current_user.id)
    content = await _read_limited(file)
    vr = validate_upload(content, file.filename or "upload.csv", project_id)

    if not vr.valid:
        return UploadSummary(
            valid_count=0,
            invalid_count=vr.invalid_count,
            errors=vr.errors[:100],
        )

    if vr.valid_count > _MAX_PARCELS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Upload contains {vr.valid_count} parcels, max is {_MAX_PARCELS}",
        )

    parcel_dicts: list[dict[str, Any]] = [
        {
            "project_id": p.project_id,
            "geometry_type": p.geometry_type,
            "geojson": p.geojson,
            "supplier_name": p.supplier_name,
            "parcel_ref": p.parcel_ref,
            "bbox_minx": p.bbox_minx,
            "bbox_miny": p.bbox_miny,
            "bbox_maxx": p.bbox_maxx,
            "bbox_maxy": p.bbox_maxy,
            "area_ha": p.area_ha,
            "country": p.country,
        }
        for p in vr.valid
    ]

    saved = await crud.create_parcels_bulk(db, parcel_dicts)

    return UploadSummary(
        valid_count=vr.valid_count,
        invalid_count=vr.invalid_count,
        errors=vr.errors[:100],
        parcel_ids=[p.id for p in saved],
    )


@router.get("/projects/{project_id}/parcels", response_model=list[ParcelOut])
async def list_parcels(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ParcelOut]:
    """List all parcels for a project."""
    await _check_project_ownership(db, project_id, current_user.id)
    parcels = await crud.list_parcels(db, project_id)
    return [ParcelOut.model_validate(p) for p in parcels]


@router.delete("/parcels/{parcel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_parcel(
    parcel_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a single parcel."""
    deleted = await crud.delete_parcel(db, parcel_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")


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

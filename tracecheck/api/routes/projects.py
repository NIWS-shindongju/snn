"""Project CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from tracecheck.api.auth import get_current_user
from tracecheck.api.schemas import ProjectCreate, ProjectOut
from tracecheck.db import crud
from tracecheck.db.models import User
from tracecheck.db.session import get_db

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectOut]:
    """List all projects owned by the current user."""
    projects = await crud.list_projects(db, current_user.id)
    result = []
    for p in projects:
        count = await crud.count_parcels(db, p.id)
        out = ProjectOut.model_validate(p)
        out.parcel_count = count
        result.append(out)
    return result


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    """Create a new EUDR compliance project."""
    project = await crud.create_project(
        db,
        owner_id=current_user.id,
        name=body.name,
        commodity=body.commodity,
        description=body.description,
        origin_country=body.origin_country,
        cutoff_date=body.cutoff_date,
    )
    out = ProjectOut.model_validate(project)
    out.parcel_count = 0
    return out


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    """Get a single project by ID."""
    project = await crud.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    count = await crud.count_parcels(db, project_id)
    out = ProjectOut.model_validate(project)
    out.parcel_count = count
    return out


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a project and all associated parcels and jobs."""
    deleted = await crud.delete_project(db, project_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

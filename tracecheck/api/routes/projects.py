"""Project management endpoints."""

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
@router.get("/", response_model=list[ProjectOut], include_in_schema=False)
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectOut]:
    """List all projects for the authenticated user."""
    projects = await crud.list_projects(db, current_user.id)
    out = []
    for p in projects:
        plot_count = await crud.count_plots(db, p.id)
        item = ProjectOut.model_validate(p)
        item.plot_count = plot_count
        out.append(item)
    return out


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ProjectOut, status_code=status.HTTP_201_CREATED, include_in_schema=False)
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
        origin_country=body.origin_country,
        cutoff_date=body.cutoff_date,
        description=body.description,
    )
    await crud.log_action(
        db, project_id=project.id, user_id=current_user.id,
        action="project.created",
        detail={"name": body.name, "commodity": body.commodity},
    )
    await db.commit()
    item = ProjectOut.model_validate(project)
    item.plot_count = 0
    return item


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    """Get a single project with plot count."""
    project = await crud.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    plot_count = await crud.count_plots(db, project_id)
    item = ProjectOut.model_validate(project)
    item.plot_count = plot_count
    return item


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a project and all related data."""
    project = await crud.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    await crud.delete_project(db, project_id)
    await db.commit()

"""Project CRUD endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from carbonsnn.api.deps import CurrentUserDep, DbDep, PageDep
from carbonsnn.api.schemas import ProjectCreate, ProjectResponse, ProjectUpdate
from carbonsnn.db import crud

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    user: CurrentUserDep,
    db: DbDep,
) -> ProjectResponse:
    """Create a new monitoring project.

    Args:
        body: Project creation payload.
        user: Authenticated user.
        db: Database session.

    Returns:
        Created project record.
    """
    project = await crud.create_project(
        db=db,
        owner_id=user.id,
        name=body.name,
        country=body.country,
        bbox=body.bbox.to_list(),
        description=body.description,
    )
    logger.info("Project created: %s by user %s", project.id, user.id)
    return ProjectResponse.model_validate(project)


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    user: CurrentUserDep,
    db: DbDep,
    page: PageDep,
) -> list[ProjectResponse]:
    """List all projects owned by the authenticated user.

    Args:
        user: Authenticated user.
        db: Database session.
        page: Pagination parameters.

    Returns:
        List of project records.
    """
    projects = await crud.list_projects(db, owner_id=user.id, skip=page.skip, limit=page.limit)
    return [ProjectResponse.model_validate(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    user: CurrentUserDep,
    db: DbDep,
) -> ProjectResponse:
    """Retrieve a single project by ID.

    Args:
        project_id: Project UUID.
        user: Authenticated user.
        db: Database session.

    Returns:
        Project record.

    Raises:
        HTTPException 404: If project not found or not owned by user.
    """
    project = await crud.get_project(db, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    user: CurrentUserDep,
    db: DbDep,
) -> ProjectResponse:
    """Update project metadata.

    Args:
        project_id: Project UUID.
        body: Fields to update.
        user: Authenticated user.
        db: Database session.

    Returns:
        Updated project record.
    """
    project = await crud.get_project(db, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    updates = body.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(project, key, value)
    await db.flush()
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    user: CurrentUserDep,
    db: DbDep,
) -> None:
    """Delete a project and all associated data.

    Args:
        project_id: Project UUID.
        user: Authenticated user.
        db: Database session.

    Raises:
        HTTPException 404: If project not found or not owned by user.
    """
    project = await crud.get_project(db, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    await crud.delete_project(db, project_id)
    logger.info("Project deleted: %s by user %s", project_id, user.id)

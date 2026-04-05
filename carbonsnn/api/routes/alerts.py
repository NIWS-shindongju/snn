"""Deforestation alert endpoints."""

import logging

from fastapi import APIRouter, HTTPException, status

from carbonsnn.api.deps import CurrentUserDep, DbDep, PageDep
from carbonsnn.api.schemas import AlertResponse
from carbonsnn.db import crud

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("/", response_model=list[AlertResponse])
async def list_all_alerts(
    user: CurrentUserDep,
    db: DbDep,
    page: PageDep,
    unacknowledged_only: bool = False,
) -> list[AlertResponse]:
    """List all deforestation alerts across all user projects.

    Args:
        user: Authenticated user.
        db: Database session.
        page: Pagination.
        unacknowledged_only: If True, only return unacknowledged alerts.

    Returns:
        List of alert records ordered newest first.
    """
    # Get all user's project IDs
    projects = await crud.list_projects(db, owner_id=user.id, limit=1000)
    project_ids = {p.id for p in projects}

    if not project_ids:
        return []

    alerts = await crud.list_alerts(
        db,
        unacknowledged_only=unacknowledged_only,
        skip=page.skip,
        limit=page.limit,
    )
    # Filter to only user's projects
    filtered = [a for a in alerts if a.project_id in project_ids]
    return [AlertResponse.model_validate(a) for a in filtered]


@router.get("/project/{project_id}", response_model=list[AlertResponse])
async def list_project_alerts(
    project_id: str,
    user: CurrentUserDep,
    db: DbDep,
    page: PageDep,
    unacknowledged_only: bool = False,
) -> list[AlertResponse]:
    """List deforestation alerts for a specific project.

    Args:
        project_id: Project UUID.
        user: Authenticated user.
        db: Database session.
        page: Pagination.
        unacknowledged_only: Filter to unacknowledged alerts only.

    Returns:
        List of alert records.
    """
    project = await crud.get_project(db, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    alerts = await crud.list_alerts(
        db,
        project_id=project_id,
        skip=page.skip,
        limit=page.limit,
        unacknowledged_only=unacknowledged_only,
    )
    return [AlertResponse.model_validate(a) for a in alerts]


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: str,
    user: CurrentUserDep,
    db: DbDep,
) -> AlertResponse:
    """Retrieve a single alert by ID.

    Args:
        alert_id: Alert UUID.
        user: Authenticated user.
        db: Database session.

    Returns:
        Alert record.
    """
    from carbonsnn.db.models import Alert

    alert = await db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    project = await crud.get_project(db, alert.project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return AlertResponse.model_validate(alert)


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: str,
    user: CurrentUserDep,
    db: DbDep,
) -> AlertResponse:
    """Acknowledge a deforestation alert.

    Args:
        alert_id: Alert UUID.
        user: Authenticated user.
        db: Database session.

    Returns:
        Updated alert record.
    """
    from carbonsnn.db.models import Alert

    alert = await db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    project = await crud.get_project(db, alert.project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    updated = await crud.acknowledge_alert(db, alert_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Update failed")
    return AlertResponse.model_validate(updated)

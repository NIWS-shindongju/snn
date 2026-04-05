"""CRUD operations for all ORM models.

All functions accept an AsyncSession and return typed ORM instances.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from carbonsnn.db.models import APIKey, Alert, Analysis, Project, User, Webhook

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────

def _hash_key(raw_key: str) -> str:
    """SHA-256 hash a raw API key for secure storage."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


# ──────────────────────────────────────────────────────────
# User CRUD
# ──────────────────────────────────────────────────────────

async def create_user(
    db: AsyncSession,
    email: str,
    hashed_password: str,
    is_superuser: bool = False,
) -> User:
    """Create and persist a new User record.

    Args:
        db: Database session.
        email: Unique email address.
        hashed_password: Bcrypt-hashed password string.
        is_superuser: Grant admin privileges.

    Returns:
        Newly created User instance.
    """
    user = User(email=email, hashed_password=hashed_password, is_superuser=is_superuser)
    db.add(user)
    await db.flush()
    logger.info("Created user: %s", email)
    return user


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Fetch a User by email address.

    Args:
        db: Database session.
        email: Email to look up.

    Returns:
        User instance or None.
    """
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """Fetch a User by UUID.

    Args:
        db: Database session.
        user_id: UUID string.

    Returns:
        User instance or None.
    """
    return await db.get(User, user_id)


# ──────────────────────────────────────────────────────────
# API Key CRUD
# ──────────────────────────────────────────────────────────

async def create_api_key(
    db: AsyncSession,
    user_id: str,
    name: str,
) -> tuple[str, APIKey]:
    """Generate and persist a new API key.

    Args:
        db: Database session.
        user_id: Owning user UUID.
        name: Human-readable key label.

    Returns:
        Tuple of (raw_key, APIKey instance).
        The raw key is only returned once and never stored in plain text.
    """
    raw_key = f"csk_{secrets.token_urlsafe(32)}"
    api_key = APIKey(
        key_hash=_hash_key(raw_key),
        name=name,
        user_id=user_id,
    )
    db.add(api_key)
    await db.flush()
    logger.info("Created API key '%s' for user %s", name, user_id)
    return raw_key, api_key


async def get_api_key_by_raw(db: AsyncSession, raw_key: str) -> APIKey | None:
    """Retrieve an active API key record by the raw (unhashed) key value.

    Args:
        db: Database session.
        raw_key: Raw API key string (e.g. from X-API-Key header).

    Returns:
        Active APIKey instance or None.
    """
    key_hash = _hash_key(raw_key)
    result = await db.execute(
        select(APIKey).where(APIKey.key_hash == key_hash, APIKey.is_active == True)  # noqa: E712
    )
    return result.scalar_one_or_none()


async def record_api_usage(
    db: AsyncSession,
    api_key_id: str,
    endpoint: str,
    method: str,
    status_code: int,
    latency_ms: float = 0.0,
) -> None:
    """Log an API call for auditing and billing.

    Args:
        db: Database session.
        api_key_id: API key UUID.
        endpoint: Request path.
        method: HTTP method.
        status_code: HTTP response status.
        latency_ms: Processing latency in milliseconds.
    """
    from carbonsnn.db.models import APIUsage

    usage = APIUsage(
        api_key_id=api_key_id,
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        latency_ms=latency_ms,
    )
    db.add(usage)
    await db.flush()


# ──────────────────────────────────────────────────────────
# Project CRUD
# ──────────────────────────────────────────────────────────

async def create_project(
    db: AsyncSession,
    owner_id: str,
    name: str,
    country: str,
    bbox: list[float],
    description: str | None = None,
) -> Project:
    """Create a new monitoring project.

    Args:
        db: Database session.
        owner_id: User UUID.
        name: Project display name.
        country: Country name or code.
        bbox: [west, south, east, north].
        description: Optional description.

    Returns:
        Newly created Project instance.
    """
    west, south, east, north = bbox
    project = Project(
        owner_id=owner_id,
        name=name,
        country=country,
        description=description,
        bbox_west=west,
        bbox_south=south,
        bbox_east=east,
        bbox_north=north,
        latitude=(south + north) / 2,
        longitude=(west + east) / 2,
    )
    db.add(project)
    await db.flush()
    logger.info("Created project '%s' (id=%s)", name, project.id)
    return project


async def list_projects(
    db: AsyncSession, owner_id: str, skip: int = 0, limit: int = 100
) -> list[Project]:
    """List projects owned by a user.

    Args:
        db: Database session.
        owner_id: Owning user UUID.
        skip: Pagination offset.
        limit: Maximum results.

    Returns:
        List of Project instances.
    """
    result = await db.execute(
        select(Project).where(Project.owner_id == owner_id).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


async def get_project(db: AsyncSession, project_id: str) -> Project | None:
    """Fetch a single project by UUID."""
    return await db.get(Project, project_id)


async def delete_project(db: AsyncSession, project_id: str) -> bool:
    """Delete a project and its cascade records."""
    project = await db.get(Project, project_id)
    if not project:
        return False
    await db.delete(project)
    logger.info("Deleted project %s", project_id)
    return True


async def list_active_projects(db: AsyncSession) -> list[Project]:
    """Return all active projects (for scheduler)."""
    result = await db.execute(select(Project).where(Project.is_active == True))  # noqa: E712
    return list(result.scalars().all())


# ──────────────────────────────────────────────────────────
# Analysis CRUD
# ──────────────────────────────────────────────────────────

async def create_analysis(
    db: AsyncSession,
    project_id: str,
    sensing_date_before: datetime | None = None,
    sensing_date_after: datetime | None = None,
) -> Analysis:
    """Create a pending analysis record.

    Args:
        db: Database session.
        project_id: Parent project UUID.
        sensing_date_before: Optional t0 date.
        sensing_date_after: Optional t1 date.

    Returns:
        Newly created Analysis instance with status='pending'.
    """
    analysis = Analysis(
        project_id=project_id,
        sensing_date_before=sensing_date_before,
        sensing_date_after=sensing_date_after,
        status="pending",
    )
    db.add(analysis)
    await db.flush()
    return analysis


async def update_analysis(
    db: AsyncSession,
    analysis_id: str,
    **kwargs: Any,
) -> Analysis | None:
    """Update analysis fields by ID.

    Args:
        db: Database session.
        analysis_id: Analysis UUID.
        **kwargs: Fields to update.

    Returns:
        Updated Analysis or None.
    """
    analysis = await db.get(Analysis, analysis_id)
    if not analysis:
        return None
    for key, value in kwargs.items():
        setattr(analysis, key, value)
    await db.flush()
    return analysis


async def get_analysis(db: AsyncSession, analysis_id: str) -> Analysis | None:
    """Fetch analysis by UUID."""
    return await db.get(Analysis, analysis_id)


async def list_analyses(
    db: AsyncSession, project_id: str, skip: int = 0, limit: int = 50
) -> list[Analysis]:
    """List analyses for a project ordered newest first."""
    result = await db.execute(
        select(Analysis)
        .where(Analysis.project_id == project_id)
        .order_by(Analysis.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


# ──────────────────────────────────────────────────────────
# Alert CRUD
# ──────────────────────────────────────────────────────────

async def create_alert(
    db: AsyncSession,
    project_id: str,
    area_ha: float,
    severity: str,
    centroid_lon: float,
    centroid_lat: float,
    geojson: str | None = None,
) -> Alert:
    """Persist a new deforestation alert.

    Args:
        db: Database session.
        project_id: Parent project UUID.
        area_ha: Deforested area.
        severity: 'low' | 'medium' | 'high'.
        centroid_lon: Longitude of event centre.
        centroid_lat: Latitude of event centre.
        geojson: GeoJSON polygon string.

    Returns:
        Newly created Alert instance.
    """
    alert = Alert(
        project_id=project_id,
        area_ha=area_ha,
        severity=severity,
        centroid_lon=centroid_lon,
        centroid_lat=centroid_lat,
        geojson=geojson,
    )
    db.add(alert)
    await db.flush()
    logger.info("Created alert for project %s: %.2f ha %s", project_id, area_ha, severity)
    return alert


async def list_alerts(
    db: AsyncSession,
    project_id: str | None = None,
    skip: int = 0,
    limit: int = 100,
    unacknowledged_only: bool = False,
) -> list[Alert]:
    """List alerts, optionally filtered by project and acknowledgement status."""
    q = select(Alert).order_by(Alert.created_at.desc())
    if project_id:
        q = q.where(Alert.project_id == project_id)
    if unacknowledged_only:
        q = q.where(Alert.is_acknowledged == False)  # noqa: E712
    q = q.offset(skip).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


async def acknowledge_alert(db: AsyncSession, alert_id: str) -> Alert | None:
    """Mark an alert as acknowledged."""
    alert = await db.get(Alert, alert_id)
    if not alert:
        return None
    alert.is_acknowledged = True
    alert.acknowledged_at = datetime.now(timezone.utc)
    await db.flush()
    return alert


# ──────────────────────────────────────────────────────────
# Webhook CRUD
# ──────────────────────────────────────────────────────────

async def create_webhook(
    db: AsyncSession,
    project_id: str,
    url: str,
    secret: str,
    events: str = "alert.created",
) -> Webhook:
    """Register a new webhook endpoint.

    Args:
        db: Database session.
        project_id: Parent project UUID.
        url: Target URL.
        secret: HMAC signing secret.
        events: Comma-separated event types.

    Returns:
        Newly created Webhook instance.
    """
    webhook = Webhook(project_id=project_id, url=url, secret=secret, events=events)
    db.add(webhook)
    await db.flush()
    return webhook


async def list_webhooks(db: AsyncSession, project_id: str) -> list[Webhook]:
    """List active webhooks for a project."""
    result = await db.execute(
        select(Webhook).where(
            Webhook.project_id == project_id, Webhook.is_active == True  # noqa: E712
        )
    )
    return list(result.scalars().all())


async def delete_webhook(db: AsyncSession, webhook_id: str) -> bool:
    """Delete a webhook by UUID."""
    webhook = await db.get(Webhook, webhook_id)
    if not webhook:
        return False
    await db.delete(webhook)
    return True

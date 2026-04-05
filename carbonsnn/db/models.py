"""SQLAlchemy ORM models for CarbonSNN.

All models inherit from a common Base and use UUID primary keys.
Compatible with SQLite (default) and PostgreSQL.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ──────────────────────────────────────────────────────────
# Base
# ──────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


# ──────────────────────────────────────────────────────────
# User
# ──────────────────────────────────────────────────────────

class User(Base):
    """Registered user account.

    Attributes:
        id: UUID primary key.
        email: Unique email address.
        hashed_password: Bcrypt-hashed password.
        is_active: Account active flag.
        is_superuser: Admin privileges.
        created_at: Account creation timestamp.
        api_keys: Related APIKey records.
        projects: Owned projects.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    projects: Mapped[list["Project"]] = relationship("Project", back_populates="owner", cascade="all, delete-orphan")
    api_keys: Mapped[list["APIKey"]] = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")


# ──────────────────────────────────────────────────────────
# APIKey
# ──────────────────────────────────────────────────────────

class APIKey(Base):
    """API key for authenticating API requests.

    Attributes:
        id: UUID primary key.
        key_hash: SHA-256 hash of the raw key.
        name: Human-readable label.
        user_id: Owning user UUID.
        is_active: Key active flag.
        created_at: Creation timestamp.
        last_used_at: Last successful authentication.
        expires_at: Optional expiry timestamp.
    """

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="api_keys")
    usages: Mapped[list["APIUsage"]] = relationship("APIUsage", back_populates="api_key")


# ──────────────────────────────────────────────────────────
# Project
# ──────────────────────────────────────────────────────────

class Project(Base):
    """Forest monitoring project (area of interest).

    Attributes:
        id: UUID primary key.
        name: Display name.
        description: Optional project description.
        country: ISO-3166 country code or name.
        bbox_west/south/east/north: Bounding box in EPSG:4326.
        latitude: Scene centroid latitude (for climate zone).
        longitude: Scene centroid longitude.
        is_active: Whether weekly scans are enabled.
        owner_id: Owning user UUID.
        created_at: Creation timestamp.
    """

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    bbox_west: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_south: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_east: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_north: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, default=0.0)
    longitude: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    owner: Mapped["User"] = relationship("User", back_populates="projects")
    analyses: Mapped[list["Analysis"]] = relationship("Analysis", back_populates="project", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="project", cascade="all, delete-orphan")
    webhooks: Mapped[list["Webhook"]] = relationship("Webhook", back_populates="project", cascade="all, delete-orphan")


# ──────────────────────────────────────────────────────────
# Analysis
# ──────────────────────────────────────────────────────────

class Analysis(Base):
    """A single deforestation / carbon analysis run.

    Attributes:
        id: UUID primary key.
        project_id: Parent project UUID.
        status: 'pending' | 'running' | 'completed' | 'failed'.
        sensing_date_before: Acquisition date of t0 image.
        sensing_date_after: Acquisition date of t1 image.
        area_ha: Analysed area.
        deforestation_ha: Detected deforestation area.
        carbon_stock_mg: Estimated carbon stock (Mg C).
        co2_equivalent_mg: CO2-equivalent emissions (Mg CO2e).
        result_json: Full analysis result as JSON string.
        geotiff_path: Optional path to result GeoTIFF.
        error_message: Error description if status='failed'.
        created_at: Request timestamp.
        completed_at: Completion timestamp.
    """

    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    sensing_date_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sensing_date_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    area_ha: Mapped[float] = mapped_column(Float, default=0.0)
    deforestation_ha: Mapped[float] = mapped_column(Float, default=0.0)
    carbon_stock_mg: Mapped[float] = mapped_column(Float, default=0.0)
    co2_equivalent_mg: Mapped[float] = mapped_column(Float, default=0.0)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    geotiff_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="analyses")


# ──────────────────────────────────────────────────────────
# Alert
# ──────────────────────────────────────────────────────────

class Alert(Base):
    """Deforestation alert generated from change detection.

    Attributes:
        id: UUID primary key.
        project_id: Parent project UUID.
        detected_date: Date the alert was raised.
        area_ha: Detected deforestation area.
        severity: 'low' | 'medium' | 'high'.
        centroid_lon: Alert centroid longitude.
        centroid_lat: Alert centroid latitude.
        geojson: GeoJSON polygon as text.
        is_acknowledged: Whether the user has acknowledged the alert.
        acknowledged_at: Acknowledgement timestamp.
        created_at: Alert creation timestamp.
    """

    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    detected_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    area_ha: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    centroid_lon: Mapped[float] = mapped_column(Float, default=0.0)
    centroid_lat: Mapped[float] = mapped_column(Float, default=0.0)
    geojson: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    project: Mapped["Project"] = relationship("Project", back_populates="alerts")


# ──────────────────────────────────────────────────────────
# Webhook
# ──────────────────────────────────────────────────────────

class Webhook(Base):
    """Outbound webhook for deforestation alert notifications.

    Attributes:
        id: UUID primary key.
        project_id: Parent project UUID.
        url: Target HTTPS URL.
        secret: HMAC signing secret.
        events: Comma-separated event types (e.g. 'alert.created').
        is_active: Whether the webhook is enabled.
        failure_count: Consecutive delivery failures.
        last_triggered_at: Last successful delivery timestamp.
        created_at: Creation timestamp.
    """

    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    secret: Mapped[str] = mapped_column(String(100), nullable=False)
    events: Mapped[str] = mapped_column(String(200), default="alert.created")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    project: Mapped["Project"] = relationship("Project", back_populates="webhooks")


# ──────────────────────────────────────────────────────────
# APIUsage
# ──────────────────────────────────────────────────────────

class APIUsage(Base):
    """Log of API key usage for billing/monitoring.

    Attributes:
        id: UUID primary key.
        api_key_id: Associated API key UUID.
        endpoint: Request path (e.g. '/api/v1/projects').
        method: HTTP method.
        status_code: HTTP response status.
        latency_ms: Request processing time.
        timestamp: When the request was made.
    """

    __tablename__ = "api_usage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    api_key_id: Mapped[str] = mapped_column(String(36), ForeignKey("api_keys.id"), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    api_key: Mapped["APIKey"] = relationship("APIKey", back_populates="usages")

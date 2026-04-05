"""SQLAlchemy ORM models for SpikeEO.

Simplified model set: User, APIKey, InferenceJob, APIUsage.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


class User(Base):
    """Registered user account.

    Attributes:
        id: UUID primary key.
        email: Unique email address.
        hashed_password: Bcrypt-hashed password.
        is_active: Account active flag.
        is_superuser: Admin privileges.
        created_at: Account creation timestamp.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    api_keys: Mapped[list["APIKey"]] = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    jobs: Mapped[list["InferenceJob"]] = relationship("InferenceJob", back_populates="owner", cascade="all, delete-orphan")


class APIKey(Base):
    """API key for authenticating requests.

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


class InferenceJob(Base):
    """Record of a single inference request.

    Attributes:
        id: UUID primary key.
        owner_id: Owning user UUID.
        task: Inference task type.
        status: 'pending' | 'running' | 'completed' | 'failed'.
        input_filename: Original uploaded filename.
        num_tiles: Number of tiles processed.
        result_json: Full result as JSON string.
        error_message: Error if failed.
        created_at: Request timestamp.
        completed_at: Completion timestamp.
    """

    __tablename__ = "inference_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    task: Mapped[str] = mapped_column(String(50), nullable=False, default="classification")
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    input_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    num_tiles: Mapped[int] = mapped_column(Integer, default=0)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped["User"] = relationship("User", back_populates="jobs")


class APIUsage(Base):
    """Log of API key usage for billing/monitoring.

    Attributes:
        id: UUID primary key.
        api_key_id: Associated API key UUID.
        endpoint: Request path.
        method: HTTP method.
        status_code: HTTP response status.
        latency_ms: Request latency.
        timestamp: Request timestamp.
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

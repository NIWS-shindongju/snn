"""SQLAlchemy ORM models for TraceCheck EUDR SaaS."""

from __future__ import annotations

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


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# User
# ─────────────────────────────────────────────────────────────────────────────

class User(Base):
    """Registered user / organisation account."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    org_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    projects: Mapped[list["Project"]] = relationship(
        "Project", back_populates="owner", cascade="all, delete-orphan"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Project
# ─────────────────────────────────────────────────────────────────────────────

class Project(Base):
    """An EUDR compliance project (one supplier batch or crop origin)."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # EUDR-regulated commodity: coffee | cocoa | palm_oil | soy | cattle | wood | rubber
    commodity: Mapped[str] = mapped_column(String(50), nullable=False, default="coffee")
    # ISO 3166-1 alpha-2 country code of origin
    origin_country: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # EUDR forest reference cutoff date (default 2020-12-31)
    cutoff_date: Mapped[str] = mapped_column(String(20), nullable=False, default="2020-12-31")

    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    owner: Mapped["User"] = relationship("User", back_populates="projects")
    parcels: Mapped[list["Parcel"]] = relationship(
        "Parcel", back_populates="project", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["AnalysisJob"]] = relationship(
        "AnalysisJob", back_populates="project", cascade="all, delete-orphan"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Parcel
# ─────────────────────────────────────────────────────────────────────────────

class Parcel(Base):
    """A single agricultural plot / GPS coordinate from a supplier."""

    __tablename__ = "parcels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True
    )

    # Supplier reference
    supplier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parcel_ref: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Geometry: 'point' | 'polygon'
    geometry_type: Mapped[str] = mapped_column(String(20), nullable=False, default="point")
    # GeoJSON Feature string
    geojson: Mapped[str] = mapped_column(Text, nullable=False)
    # Bounding box cache: minx, miny, maxx, maxy
    bbox_minx: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_miny: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_maxx: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_maxy: Mapped[float | None] = mapped_column(Float, nullable=True)
    area_ha: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Origin country (ISO2)
    country: Mapped[str | None] = mapped_column(String(10), nullable=True)

    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    project: Mapped["Project"] = relationship("Project", back_populates="parcels")
    results: Mapped[list["ParcelResult"]] = relationship(
        "ParcelResult", back_populates="parcel", cascade="all, delete-orphan"
    )


# ─────────────────────────────────────────────────────────────────────────────
# AnalysisJob
# ─────────────────────────────────────────────────────────────────────────────

class AnalysisJob(Base):
    """A batch analysis run for all parcels in a project."""

    __tablename__ = "analysis_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True
    )
    triggered_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    # pending | running | done | failed
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    total_parcels: Mapped[int] = mapped_column(Integer, default=0)
    processed_parcels: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    project: Mapped["Project"] = relationship("Project", back_populates="jobs")
    results: Mapped[list["ParcelResult"]] = relationship(
        "ParcelResult", back_populates="job", cascade="all, delete-orphan"
    )
    reports: Mapped[list["Report"]] = relationship(
        "Report", back_populates="job", cascade="all, delete-orphan"
    )


# ─────────────────────────────────────────────────────────────────────────────
# ParcelResult
# ─────────────────────────────────────────────────────────────────────────────

class ParcelResult(Base):
    """Per-parcel analysis result from a single job."""

    __tablename__ = "parcel_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_jobs.id"), nullable=False, index=True
    )
    parcel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("parcels.id"), nullable=False, index=True
    )

    # Risk level: low | review | high
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="review")

    # Raw spectral metrics
    ndvi_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    ndvi_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_ndvi: Mapped[float | None] = mapped_column(Float, nullable=True)
    nbr_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    nbr_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_nbr: Mapped[float | None] = mapped_column(Float, nullable=True)
    changed_area_ha: Mapped[float | None] = mapped_column(Float, nullable=True)
    cloud_fraction: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Human-readable reason for flagging
    flag_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Satellite data used
    before_scene_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    after_scene_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    data_source: Mapped[str] = mapped_column(
        String(100), default="Copernicus Sentinel-2", nullable=False
    )

    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    job: Mapped["AnalysisJob"] = relationship("AnalysisJob", back_populates="results")
    parcel: Mapped["Parcel"] = relationship("Parcel", back_populates="results")


# ─────────────────────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────────────────────

class Report(Base):
    """Generated evidence report (PDF / JSON / CSV)."""

    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_jobs.id"), nullable=False, index=True
    )

    # pdf | json | csv
    format: Mapped[str] = mapped_column(String(10), nullable=False, default="json")
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    job: Mapped["AnalysisJob"] = relationship("AnalysisJob", back_populates="reports")

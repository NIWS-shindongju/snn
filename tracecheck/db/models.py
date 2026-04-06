"""TraceCheck — EUDR SaaS ORM models.

Table hierarchy:
  users
  └─ projects
     ├─ plots
     ├─ job_runs
     │  ├─ plot_assessments  (one per plot per job)
     │  └─ evidence_exports  (PDF/JSON/CSV per job)
     └─ audit_logs           (all user actions in project)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey,
    Integer, String, Text, JSON,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)

def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


# ─── users ────────────────────────────────────────────────────────────────────

class User(Base):
    """Registered organisation account."""
    __tablename__ = "users"

    id:               Mapped[str]           = mapped_column(String(36), primary_key=True, default=_uuid)
    email:            Mapped[str]           = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password:  Mapped[str]           = mapped_column(String(255), nullable=False)
    org_name:         Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active:        Mapped[bool]          = mapped_column(Boolean, default=True)
    created_at:       Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=_now)
    updated_at:       Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    projects: Mapped[list["Project"]] = relationship(
        "Project", back_populates="owner", cascade="all, delete-orphan"
    )


# ─── projects ─────────────────────────────────────────────────────────────────

class Project(Base):
    """
    One EUDR compliance project = one batch of supplier plots
    for a single commodity + origin combination.
    """
    __tablename__ = "projects"

    id:             Mapped[str]           = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id:       Mapped[str]           = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    name:           Mapped[str]           = mapped_column(String(255), nullable=False)
    description:    Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # EUDR commodity (coffee|cocoa|palm_oil|soy|cattle|wood|rubber)
    commodity:      Mapped[str]           = mapped_column(String(50), nullable=False, default="coffee")
    # ISO 3166-1 alpha-2 origin country
    origin_country: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    # Forest reference cutoff date (EUDR default: 2020-12-31)
    cutoff_date:    Mapped[str]           = mapped_column(String(20), nullable=False, default="2020-12-31")

    # active | archived
    status:         Mapped[str]           = mapped_column(String(20), default="active")
    created_at:     Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=_now)
    updated_at:     Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    owner:           Mapped["User"]              = relationship("User", back_populates="projects")
    plots:           Mapped[list["Plot"]]        = relationship("Plot",          back_populates="project", cascade="all, delete-orphan")
    job_runs:        Mapped[list["JobRun"]]      = relationship("JobRun",        back_populates="project", cascade="all, delete-orphan")
    audit_logs:      Mapped[list["AuditLog"]]    = relationship("AuditLog",      back_populates="project", cascade="all, delete-orphan")


# ─── plots ────────────────────────────────────────────────────────────────────

class Plot(Base):
    """
    A single supplier agricultural plot.
    Geometry stored as GeoJSON Feature string.
    """
    __tablename__ = "plots"

    id:            Mapped[str]           = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id:    Mapped[str]           = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)

    # Supplier traceability fields
    supplier_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    plot_ref:      Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Geometry
    geometry_type: Mapped[str]           = mapped_column(String(20), nullable=False, default="point")
    geojson:       Mapped[str]           = mapped_column(Text, nullable=False)       # GeoJSON Feature

    # Bounding box cache (derived from geojson, for quick spatial queries)
    bbox_minx:     Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_miny:     Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_maxx:     Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_maxy:     Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    area_ha:       Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Reverse-geocoded country
    country:       Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Validation status: pending | valid | invalid
    validation_status: Mapped[str]       = mapped_column(String(20), default="valid")
    validation_error:  Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    uploaded_at:   Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=_now)

    project:      Mapped["Project"]              = relationship("Project", back_populates="plots")
    assessments:  Mapped[list["PlotAssessment"]] = relationship("PlotAssessment", back_populates="plot", cascade="all, delete-orphan")


# ─── job_runs ─────────────────────────────────────────────────────────────────

class JobRun(Base):
    """
    A single execution of the risk-assessment pipeline
    covering all plots in a project at a point in time.
    """
    __tablename__ = "job_runs"

    id:               Mapped[str]           = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id:       Mapped[str]           = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    triggered_by:     Mapped[str]           = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    # pending | running | done | failed
    status:           Mapped[str]           = mapped_column(String(20), default="pending")
    total_plots:      Mapped[int]           = mapped_column(Integer, default=0)
    processed_plots:  Mapped[int]           = mapped_column(Integer, default=0)
    error_message:    Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Sentinel-2 fetch mode: mock | real
    data_mode:        Mapped[str]           = mapped_column(String(20), default="mock")

    started_at:       Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at:     Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at:       Mapped[datetime]           = mapped_column(DateTime(timezone=True), default=_now)

    project:          Mapped["Project"]                  = relationship("Project", back_populates="job_runs")
    plot_assessments: Mapped[list["PlotAssessment"]]     = relationship("PlotAssessment", back_populates="job_run", cascade="all, delete-orphan")
    evidence_exports: Mapped[list["EvidenceExport"]]     = relationship("EvidenceExport", back_populates="job_run", cascade="all, delete-orphan")


# ─── plot_assessments ─────────────────────────────────────────────────────────

class PlotAssessment(Base):
    """
    Risk assessment result for one plot from one job run.
    Contains all raw spectral metrics and the derived risk level.
    """
    __tablename__ = "plot_assessments"

    id:         Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("job_runs.id"), nullable=False, index=True)
    plot_id:    Mapped[str] = mapped_column(String(36), ForeignKey("plots.id"),    nullable=False, index=True)

    # Risk classification: low | review | high
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="review")

    # Spectral change metrics
    ndvi_before:      Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ndvi_after:       Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delta_ndvi:       Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    nbr_before:       Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    nbr_after:        Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delta_nbr:        Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    changed_area_ha:  Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cloud_fraction:   Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence:       Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Human-readable flag reason (why REVIEW or HIGH)
    flag_reason:      Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    # Satellite scenes used
    before_scene_date: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    after_scene_date:  Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    data_source:       Mapped[str]           = mapped_column(String(100), default="Copernicus Sentinel-2")

    # Human reviewer override (for false-positive / false-negative mitigation)
    # none | confirmed | dismissed
    reviewer_decision: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    reviewer_note:     Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by:       Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    reviewed_at:       Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    job_run: Mapped["JobRun"] = relationship("JobRun", back_populates="plot_assessments")
    plot:    Mapped["Plot"]   = relationship("Plot",   back_populates="assessments")


# ─── evidence_exports ─────────────────────────────────────────────────────────

class EvidenceExport(Base):
    """
    A generated evidence package (PDF / JSON / CSV) for a completed job run.
    Represents the audit-ready artefact submitted to regulators or stored
    as due-diligence proof.
    """
    __tablename__ = "evidence_exports"

    id:         Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("job_runs.id"), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    # pdf | json | csv
    format:          Mapped[str]           = mapped_column(String(10), nullable=False)
    file_path:       Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Snapshot of summary at export time (for audit trail completeness)
    summary_snapshot: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)

    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    job_run: Mapped["JobRun"] = relationship("JobRun", back_populates="evidence_exports")


# ─── audit_logs ───────────────────────────────────────────────────────────────

class AuditLog(Base):
    """
    Immutable log of every significant user action within a project.
    Supports regulatory audit trail requirements.
    """
    __tablename__ = "audit_logs"

    id:         Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    user_id:    Mapped[str] = mapped_column(String(36), ForeignKey("users.id"),    nullable=False)

    # e.g. "plots.upload", "job.started", "job.completed", "export.created", "assessment.reviewed"
    action:     Mapped[str]           = mapped_column(String(100), nullable=False)
    detail:     Mapped[Optional[str]] = mapped_column(JSON, nullable=True)   # arbitrary extra context

    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    occurred_at: Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=_now, index=True)

    project: Mapped["Project"] = relationship("Project", back_populates="audit_logs")

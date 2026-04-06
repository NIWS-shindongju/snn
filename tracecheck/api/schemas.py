"""Pydantic request/response schemas for TraceCheck API — v2 SaaS schema."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    org_name: Optional[str] = None


class LoginRequest(BaseModel):
    username: str  # OAuth2PasswordRequestForm compatible field name = email
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    org_name: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Project
# ─────────────────────────────────────────────────────────────────────────────

VALID_COMMODITIES = {
    "coffee", "cocoa", "palm_oil", "soy", "cattle", "wood", "rubber", "other"
}


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    commodity: str = Field(default="coffee")
    description: Optional[str] = None
    origin_country: Optional[str] = Field(None, max_length=10)
    cutoff_date: str = Field(default="2020-12-31")

    @field_validator("commodity")
    @classmethod
    def validate_commodity(cls, v: str) -> str:
        if v not in VALID_COMMODITIES:
            raise ValueError(f"commodity must be one of {sorted(VALID_COMMODITIES)}")
        return v


class ProjectOut(BaseModel):
    id: str
    name: str
    commodity: str
    description: Optional[str]
    origin_country: Optional[str]
    cutoff_date: str
    status: str
    created_at: datetime
    plot_count: int = 0  # injected by route handler

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Plot  (formerly "Parcel")
# ─────────────────────────────────────────────────────────────────────────────

class PlotOut(BaseModel):
    id: str
    project_id: str
    supplier_name: Optional[str]
    plot_ref: Optional[str]
    geometry_type: str
    geojson: str
    area_ha: Optional[float]
    country: Optional[str]
    validation_status: str
    validation_error: Optional[str]
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class UploadSummary(BaseModel):
    created_count: int
    skipped_count: int
    errors: list[dict[str, Any]] = []
    plot_ids: list[str] = []


class ValidationPreview(BaseModel):
    valid_count: int
    invalid_count: int
    errors: list[dict[str, Any]] = []
    preview: list[dict[str, Any]] = []


# ─────────────────────────────────────────────────────────────────────────────
# Job Run  (formerly "AnalysisJob")
# ─────────────────────────────────────────────────────────────────────────────

class JobRunOut(BaseModel):
    id: str
    project_id: str
    status: str
    total_plots: int
    processed_plots: int
    data_mode: str
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Plot Assessment  (formerly "ParcelResult")
# ─────────────────────────────────────────────────────────────────────────────

class PlotAssessmentOut(BaseModel):
    id: str
    job_run_id: str
    plot_id: str
    # Enriched from Plot relationship:
    plot_ref: Optional[str] = None
    supplier_name: Optional[str] = None
    # Risk classification
    risk_level: str
    # Spectral metrics
    ndvi_before: Optional[float]
    ndvi_after: Optional[float]
    delta_ndvi: Optional[float]
    nbr_before: Optional[float]
    nbr_after: Optional[float]
    delta_nbr: Optional[float]
    changed_area_ha: Optional[float]
    cloud_fraction: Optional[float]
    confidence: Optional[float]
    flag_reason: Optional[str]
    # Scene info
    before_scene_date: Optional[str]
    after_scene_date: Optional[str]
    data_source: str
    # Reviewer override
    reviewer_decision: Optional[str]
    reviewer_note: Optional[str]
    assessed_at: datetime

    model_config = {"from_attributes": True}


class AssessmentsSummary(BaseModel):
    job_run_id: str
    status: str
    total: int
    low: int
    review: int
    high: int
    low_pct: float
    review_pct: float
    high_pct: float


# ─────────────────────────────────────────────────────────────────────────────
# Evidence Export  (formerly "Report")
# ─────────────────────────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    format: str = Field(default="json")

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        if v not in {"json", "pdf", "csv"}:
            raise ValueError("format must be json, pdf, or csv")
        return v


class EvidenceExportOut(BaseModel):
    id: str
    job_run_id: str
    format: str
    file_size_bytes: Optional[int]
    summary_snapshot: Optional[Any]
    generated_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Audit Log
# ─────────────────────────────────────────────────────────────────────────────

class AuditLogOut(BaseModel):
    id: str
    project_id: str
    user_id: str
    action: str
    detail: Optional[Any]
    ip_address: Optional[str]
    occurred_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Backwards-compat aliases (for code still using old names)
# ─────────────────────────────────────────────────────────────────────────────
ParcelOut = PlotOut
JobOut = JobRunOut
ParcelResultOut = PlotAssessmentOut
ResultsSummary = AssessmentsSummary
ReportOut = EvidenceExportOut
ReportRequest = ExportRequest

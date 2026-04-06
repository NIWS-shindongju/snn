"""Pydantic request/response schemas for TraceCheck API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    org_name: str | None = None


class LoginRequest(BaseModel):
    username: str  # OAuth2PasswordRequestForm compatible field name = email
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    org_name: str | None
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
    description: str | None = None
    origin_country: str | None = Field(None, max_length=10)
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
    description: str | None
    origin_country: str | None
    cutoff_date: str
    status: str
    created_at: datetime
    parcel_count: int = 0

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Parcel
# ─────────────────────────────────────────────────────────────────────────────

class ParcelOut(BaseModel):
    id: str
    project_id: str
    supplier_name: str | None
    parcel_ref: str | None
    geometry_type: str
    geojson: str
    area_ha: float | None
    country: str | None
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class UploadSummary(BaseModel):
    valid_count: int
    invalid_count: int
    errors: list[dict[str, Any]] = []
    parcel_ids: list[str] = []


class ValidationPreview(BaseModel):
    valid_count: int
    invalid_count: int
    errors: list[dict[str, Any]] = []
    preview: list[dict[str, Any]] = []


# ─────────────────────────────────────────────────────────────────────────────
# Analysis Job
# ─────────────────────────────────────────────────────────────────────────────

class JobOut(BaseModel):
    id: str
    project_id: str
    status: str
    total_parcels: int
    processed_parcels: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ParcelResultOut(BaseModel):
    id: str
    job_id: str
    parcel_id: str
    parcel_ref: str | None = None
    supplier_name: str | None = None
    risk_level: str
    delta_ndvi: float | None
    changed_area_ha: float | None
    cloud_fraction: float | None
    confidence: float | None
    flag_reason: str | None
    before_scene_date: str | None
    after_scene_date: str | None
    data_source: str
    analyzed_at: datetime

    model_config = {"from_attributes": True}


class ResultsSummary(BaseModel):
    job_id: str
    status: str
    total: int
    low: int
    review: int
    high: int
    low_pct: float
    review_pct: float
    high_pct: float


# ─────────────────────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────────────────────

class ReportRequest(BaseModel):
    format: str = Field(default="json")

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        if v not in {"json", "pdf", "csv"}:
            raise ValueError("format must be json, pdf, or csv")
        return v


class ReportOut(BaseModel):
    id: str
    job_id: str
    format: str
    file_size_bytes: int | None
    generated_at: datetime

    model_config = {"from_attributes": True}

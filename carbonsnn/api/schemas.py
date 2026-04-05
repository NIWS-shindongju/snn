"""Pydantic request/response schemas for the CarbonSNN API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator


# ──────────────────────────────────────────────────────────
# Shared / Base
# ──────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """API health check response."""

    status: str = "ok"
    version: str
    timestamp: datetime


# ──────────────────────────────────────────────────────────
# User & Auth
# ──────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    """Request body for user registration."""

    email: str = Field(..., description="Unique email address")
    password: str = Field(..., min_length=8, description="Password (min 8 chars)")


class UserResponse(BaseModel):
    """User record in API responses."""

    id: str
    email: str
    is_active: bool
    is_superuser: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class APIKeyCreate(BaseModel):
    """Request body for API key creation."""

    name: str = Field(..., max_length=100, description="Human-readable key label")


class APIKeyResponse(BaseModel):
    """API key metadata returned after creation."""

    id: str
    name: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None = None
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}


class APIKeyCreateResponse(APIKeyResponse):
    """Extended response on key creation — includes the raw key (once only)."""

    raw_key: str = Field(..., description="Raw API key — store securely, shown only once")


# ──────────────────────────────────────────────────────────
# Projects
# ──────────────────────────────────────────────────────────

class BoundingBox(BaseModel):
    """Geographic bounding box in EPSG:4326."""

    west: float = Field(..., ge=-180.0, le=180.0)
    south: float = Field(..., ge=-90.0, le=90.0)
    east: float = Field(..., ge=-180.0, le=180.0)
    north: float = Field(..., ge=-90.0, le=90.0)

    @field_validator("east")
    @classmethod
    def east_gt_west(cls, v: float, info: Any) -> float:
        """Validate that east > west."""
        if "west" in info.data and v <= info.data["west"]:
            raise ValueError("east must be greater than west")
        return v

    @field_validator("north")
    @classmethod
    def north_gt_south(cls, v: float, info: Any) -> float:
        """Validate that north > south."""
        if "south" in info.data and v <= info.data["south"]:
            raise ValueError("north must be greater than south")
        return v

    def to_list(self) -> list[float]:
        """Return [west, south, east, north]."""
        return [self.west, self.south, self.east, self.north]


class ProjectCreate(BaseModel):
    """Request body for project creation."""

    name: str = Field(..., max_length=200)
    country: str = Field(..., max_length=100)
    bbox: BoundingBox
    description: str | None = Field(None, max_length=2000)


class ProjectUpdate(BaseModel):
    """Request body for project updates (all fields optional)."""

    name: str | None = Field(None, max_length=200)
    description: str | None = None
    is_active: bool | None = None


class ProjectResponse(BaseModel):
    """Project record in API responses."""

    id: str
    name: str
    country: str
    description: str | None
    bbox_west: float
    bbox_south: float
    bbox_east: float
    bbox_north: float
    is_active: bool
    owner_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────────────────
# Analysis
# ──────────────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    """Request body to trigger an analysis run."""

    project_id: str
    sensing_date_before: datetime | None = None
    sensing_date_after: datetime | None = None
    start_date: str | None = Field(None, description="ISO-8601 start date for image search")
    end_date: str | None = Field(None, description="ISO-8601 end date for image search")


class AnalysisResponse(BaseModel):
    """Analysis record in API responses."""

    id: str
    project_id: str
    status: str
    sensing_date_before: datetime | None
    sensing_date_after: datetime | None
    area_ha: float
    deforestation_ha: float
    carbon_stock_mg: float
    co2_equivalent_mg: float
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class AnalysisResultDetail(AnalysisResponse):
    """Detailed analysis response including full JSON result."""

    result_json: str | None = None


# ──────────────────────────────────────────────────────────
# Alerts
# ──────────────────────────────────────────────────────────

class AlertResponse(BaseModel):
    """Deforestation alert in API responses."""

    id: str
    project_id: str
    detected_date: datetime
    area_ha: float
    severity: str
    centroid_lon: float
    centroid_lat: float
    geojson: str | None
    is_acknowledged: bool
    acknowledged_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertAcknowledgeRequest(BaseModel):
    """Request body for acknowledging an alert."""

    alert_id: str


# ──────────────────────────────────────────────────────────
# Webhooks
# ──────────────────────────────────────────────────────────

class WebhookCreate(BaseModel):
    """Request body for webhook registration."""

    url: str = Field(..., description="Target HTTPS URL")
    secret: str = Field(..., min_length=16, description="HMAC signing secret (min 16 chars)")
    events: str = Field(
        default="alert.created",
        description="Comma-separated event types (e.g. 'alert.created,alert.updated')",
    )

    @field_validator("url")
    @classmethod
    def url_must_be_https(cls, v: str) -> str:
        """Require HTTPS for webhook URLs."""
        if not (v.startswith("https://") or v.startswith("http://localhost")):
            raise ValueError("Webhook URL must use HTTPS")
        return v


class WebhookResponse(BaseModel):
    """Webhook record in API responses."""

    id: str
    project_id: str
    url: str
    events: str
    is_active: bool
    failure_count: int
    last_triggered_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────────────────
# Pagination
# ──────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    """Generic paginated list envelope."""

    total: int
    skip: int
    limit: int
    items: list[Any]


# ──────────────────────────────────────────────────────────
# Error
# ──────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Standard API error response."""

    detail: str
    code: str | None = None

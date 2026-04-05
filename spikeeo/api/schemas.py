"""Pydantic request/response schemas for the SpikeEO API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """API health check response."""
    status: str = "ok"
    version: str
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Standard API error response."""
    detail: str
    code: str | None = None


class InferenceRequest(BaseModel):
    """Request body for inference endpoint (when using pre-uploaded data)."""
    task: str = Field(default="classification", description="Inference task type")
    num_classes: int = Field(default=2, ge=2, le=1000)
    num_bands: int = Field(default=10, ge=1, le=20)
    confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    use_hybrid: bool = Field(default=True)


class InferenceResponse(BaseModel):
    """Response from inference endpoint."""
    task: str
    num_tiles: int
    class_distribution: dict[str, int]
    geojson: dict[str, Any] | None = None
    cost_report: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChangeDetectionRequest(BaseModel):
    """Request for change detection (file paths already on server)."""
    before_path: str
    after_path: str


class ChangeDetectionResponse(BaseModel):
    """Response from change detection."""
    changed_tiles: int
    total_tiles: int
    change_pct: float
    change_area_ha: float
    geojson: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkRequest(BaseModel):
    """Request to run a benchmark."""
    test_data_dir: str
    cnn_model: str = "resnet18"
    num_classes: int = 2
    num_bands: int = 10


class BenchmarkResponse(BaseModel):
    """Response from benchmark endpoint."""
    snn_accuracy: float
    cnn_accuracy: float
    accuracy_gap: float
    snn_inference_time_ms: float
    cnn_inference_time_ms: float
    speedup_ratio: float
    energy_saving_ratio: float
    cost_saving_estimate_pct: float


class TaskInfo(BaseModel):
    """Information about a supported inference task."""
    name: str
    description: str
    output_keys: list[str]


class UserCreate(BaseModel):
    """Request body for user registration."""
    email: str
    password: str = Field(..., min_length=8)


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
    name: str = Field(..., max_length=100)


class APIKeyResponse(BaseModel):
    """API key metadata."""
    id: str
    name: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None = None
    model_config = {"from_attributes": True}


class APIKeyCreateResponse(APIKeyResponse):
    """Extended response on creation — includes raw key (shown once)."""
    raw_key: str

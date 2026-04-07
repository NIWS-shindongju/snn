"""TraceCheck application configuration.

All settings are read from environment variables prefixed with TRACECHECK_.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_prefix="TRACECHECK_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///./tracecheck.db",
        description="SQLAlchemy async DB URL",
    )

    # ── Auth / Security ───────────────────────────────────────────────────────
    secret_key: str = Field(
        default="dev-only-change-in-production-" + "x" * 20,
        description="JWT signing secret key (set TRACECHECK_SECRET_KEY in production)",
    )
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(
        default=60 * 24,  # 24 hours
        description="JWT access token expiry in minutes",
    )

    # ── Copernicus / Sentinel-2 ───────────────────────────────────────────────
    copernicus_client_id: str = Field(default="", description="Copernicus Data Space client ID")
    copernicus_client_secret: str = Field(
        default="", description="Copernicus Data Space client secret"
    )

    # ── Analysis thresholds ───────────────────────────────────────────────────
    ndvi_threshold: float = Field(
        default=0.10,
        description="dNDVI drop threshold for REVIEW flag (absolute)",
    )
    ndvi_high_threshold: float = Field(
        default=0.15,
        description="dNDVI drop threshold for HIGH risk",
    )
    min_changed_area_ha: float = Field(
        default=0.3,
        description="Minimum changed area (ha) to flag REVIEW",
    )
    max_cloud_fraction: float = Field(
        default=0.5,
        description="Cloud fraction above which result is forced to REVIEW",
    )

    # ── EUDR ─────────────────────────────────────────────────────────────────
    eudr_cutoff_date: str = Field(
        default="2020-12-31",
        description="EUDR forest reference cutoff date",
    )

    # ── Storage ───────────────────────────────────────────────────────────────
    data_dir: str = Field(
        default="./data",
        description="Local data directory for Sentinel-2 tiles and reports",
    )

    # ── App ───────────────────────────────────────────────────────────────────
    debug: bool = Field(default=False, description="Enable debug mode")
    app_name: str = Field(default="TraceCheck", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173", "http://localhost:8000"],
        description="Allowed CORS origins (set TRACECHECK_CORS_ORIGINS for production)",
    )

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    rate_limit_per_minute: int = Field(
        default=60,
        description="Global rate limit per IP per minute",
    )
    rate_limit_auth: int = Field(
        default=10,
        description="Auth endpoint rate limit per IP per minute",
    )

    # ── TRACES NT ─────────────────────────────────────────────────────────────
    traces_nt_client_id: str = Field(default="", description="EU TRACES NT client ID")
    traces_nt_client_secret: str = Field(default="", description="EU TRACES NT client secret")
    traces_nt_environment: str = Field(default="test", description="TRACES environment (test|production)")


settings = Settings()

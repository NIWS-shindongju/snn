"""Application configuration via Pydantic Settings.

All values can be overridden via environment variables or a .env file.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Global application settings.

    Attributes:
        app_name: Human-readable service name.
        app_env: Deployment environment.
        app_debug: Enable debug mode.
        app_secret_key: Secret key for signing tokens.
        app_host: API server bind address.
        app_port: API server port.
        database_url: SQLAlchemy async database URL.
        redis_url: Redis connection URL.
        celery_broker_url: Celery broker URL.
        celery_result_backend: Celery result backend URL.
        copernicus_client_id: Copernicus Data Space OAuth2 client ID.
        copernicus_client_secret: Copernicus Data Space OAuth2 client secret.
        copernicus_token_url: OAuth2 token endpoint.
        copernicus_search_url: OData search endpoint.
        copernicus_download_url: Download endpoint.
        data_dir: Root directory for raw satellite data.
        models_dir: Directory for trained model weights.
        tiles_dir: Directory for preprocessed image tiles.
        results_dir: Directory for analysis results.
        cache_dir: Directory for HTTP response caching.
        rate_limit_per_minute: API rate limit.
        rate_limit_burst: API rate limit burst allowance.
        webhook_timeout_seconds: Timeout for outbound webhook calls.
        webhook_retry_attempts: Number of webhook delivery retries.
        forest_snn_num_steps: Time steps for ForestSNN.
        carbon_snn_num_steps: Time steps for CarbonSNN.
        confidence_threshold: Minimum SNN confidence before CNN fallback.
        min_deforestation_area_ha: Minimum alert area in hectares.
        ipcc_tropical_agb_density: Tropical forest AGB (Mg C/ha).
        ipcc_temperate_agb_density: Temperate forest AGB (Mg C/ha).
        ipcc_boreal_agb_density: Boreal forest AGB (Mg C/ha).
        ipcc_root_shoot_ratio: IPCC root-to-shoot ratio.
        streamlit_port: Streamlit dashboard port.
        api_base_url: Base URL for internal API calls.
        log_level: Python logging level string.
        log_format: Log output format (json/text).
        log_file: Optional log file path.
        weekly_scan_cron: Cron expression for weekly scan.
        scheduler_timezone: Timezone string for scheduler.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "CarbonSNN"
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = False
    app_secret_key: str = "change-me-to-a-random-64-char-string"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Database
    database_url: str = "sqlite+aiosqlite:///./carbonsnn.db"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Copernicus / Sentinel-2
    copernicus_client_id: str = ""
    copernicus_client_secret: str = ""
    copernicus_token_url: str = (
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    )
    copernicus_search_url: str = "https://catalogue.dataspace.copernicus.eu/odata/v1"
    copernicus_download_url: str = "https://download.dataspace.copernicus.eu/odata/v1"

    # Storage paths
    data_dir: Path = Field(default=Path("./data"))
    models_dir: Path = Field(default=Path("./models/weights"))
    tiles_dir: Path = Field(default=Path("./data/tiles"))
    results_dir: Path = Field(default=Path("./data/results"))
    cache_dir: Path = Field(default=Path("./data/cache"))

    # Rate limiting
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 100

    # Webhooks
    webhook_timeout_seconds: int = 30
    webhook_retry_attempts: int = 3

    # Model hyperparameters
    forest_snn_num_steps: int = 15
    carbon_snn_num_steps: int = 25
    confidence_threshold: float = 0.75
    min_deforestation_area_ha: float = 0.5

    # IPCC carbon density (Mg C/ha)
    ipcc_tropical_agb_density: float = 200.0
    ipcc_temperate_agb_density: float = 120.0
    ipcc_boreal_agb_density: float = 80.0
    ipcc_root_shoot_ratio: float = 0.26

    # Dashboard
    streamlit_port: int = 8501
    api_base_url: str = "http://localhost:8000"

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "text"] = "text"
    log_file: str | None = None

    # Scheduler
    weekly_scan_cron: str = "0 6 * * 1"
    scheduler_timezone: str = "UTC"

    @field_validator("data_dir", "models_dir", "tiles_dir", "results_dir", "cache_dir", mode="after")
    @classmethod
    def create_directories(cls, v: Path) -> Path:
        """Ensure storage directories exist."""
        v.mkdir(parents=True, exist_ok=True)
        return v

    def configure_logging(self) -> None:
        """Apply log level and format to root logger."""
        level = getattr(logging, self.log_level, logging.INFO)
        handlers: list[logging.Handler] = [logging.StreamHandler()]
        if self.log_file:
            Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(self.log_file))
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
            handlers=handlers,
        )
        logger.info("Logging configured: level=%s format=%s", self.log_level, self.log_format)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    settings = Settings()
    settings.configure_logging()
    return settings

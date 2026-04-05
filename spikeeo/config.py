"""Application configuration via Pydantic Settings.

All values can be overridden via environment variables (prefix: SPIKEEO_) or a .env file.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Global application settings for SpikeEO.

    Attributes:
        app_name: Human-readable service name.
        app_env: Deployment environment.
        app_debug: Enable debug mode.
        app_secret_key: Secret key for signing tokens.
        app_host: API server bind address.
        app_port: API server port.
        database_url: SQLAlchemy async database URL.
        data_dir: Root directory for raw satellite data.
        models_dir: Directory for trained model weights.
        pretrained_dir: Directory for pretrained weights bundled with the SDK.
        tiles_dir: Directory for preprocessed image tiles.
        results_dir: Directory for inference results.
        cache_dir: Directory for HTTP response caching.
        rate_limit_per_minute: API rate limit.
        rate_limit_burst: API rate limit burst allowance.
        default_task: Default inference task type.
        default_num_classes: Default number of output classes.
        default_num_bands: Default number of input spectral bands.
        default_depth: Default SNNBackbone depth.
        default_num_steps: Default SNN time steps.
        confidence_threshold: Minimum SNN confidence before CNN fallback.
        max_upload_size_mb: Maximum file upload size.
        log_level: Python logging level string.
        log_format: Log output format.
        log_file: Optional log file path.
    """

    model_config = SettingsConfigDict(
        env_prefix="SPIKEEO_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "SpikeEO"
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = False
    app_secret_key: str = "change-me-to-a-random-64-char-string"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Database
    database_url: str = "sqlite+aiosqlite:///./spikeeo.db"

    # Storage paths
    data_dir: Path = Field(default=Path("./data"))
    models_dir: Path = Field(default=Path("./models/weights"))
    pretrained_dir: Path = Field(default=Path("./pretrained"))
    tiles_dir: Path = Field(default=Path("./data/tiles"))
    results_dir: Path = Field(default=Path("./data/results"))
    cache_dir: Path = Field(default=Path("./data/cache"))

    # Rate limiting
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 100

    # Model defaults
    default_task: str = "classification"
    default_num_classes: int = 2
    default_num_bands: int = 10
    default_depth: str = "standard"
    default_num_steps: int = 15
    confidence_threshold: float = 0.75
    max_upload_size_mb: int = 500

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "text"] = "text"
    log_file: str | None = None

    @field_validator("data_dir", "models_dir", "pretrained_dir", "tiles_dir", "results_dir", "cache_dir", mode="after")
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
        logger.info("Logging configured: level=%s", self.log_level)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    settings = Settings()
    settings.configure_logging()
    return settings

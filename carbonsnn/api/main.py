"""FastAPI application entry point.

Configures middleware, rate limiting, CORS, and includes all route modules.
"""

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from carbonsnn.api.routes import alerts, analysis, projects, webhooks
from carbonsnn.api.schemas import ErrorResponse, HealthResponse
from carbonsnn.config import get_settings
from carbonsnn.db.session import init_db

logger = logging.getLogger(__name__)

settings = get_settings()

# ──────────────────────────────────────────────────────────
# Rate Limiter
# ──────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)


# ──────────────────────────────────────────────────────────
# Lifespan
# ──────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup / shutdown lifecycle."""
    logger.info("CarbonSNN API starting up…")
    await init_db()
    logger.info("Database initialised")
    yield
    logger.info("CarbonSNN API shutting down")


# ──────────────────────────────────────────────────────────
# Application
# ──────────────────────────────────────────────────────────

app = FastAPI(
    title="CarbonSNN API",
    description=(
        "Satellite-based deforestation detection and carbon MRV SaaS "
        "powered by Spiking Neural Networks."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_debug else ["https://your-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate limiting ────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── Request timing middleware ─────────────────────────────────
@app.middleware("http")
async def add_process_time_header(request: Request, call_next: Any) -> Response:
    """Attach X-Process-Time header to every response."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
    return response


# ── Global exception handler ──────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a structured error response for unhandled exceptions."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(detail="Internal server error", code="INTERNAL_ERROR").model_dump(),
    )


# ──────────────────────────────────────────────────────────
# Routers
# ──────────────────────────────────────────────────────────

API_PREFIX = "/api/v1"

app.include_router(projects.router, prefix=API_PREFIX)
app.include_router(analysis.router, prefix=API_PREFIX)
app.include_router(alerts.router, prefix=API_PREFIX)
app.include_router(webhooks.router, prefix=API_PREFIX)


# ──────────────────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def health(request: Request) -> HealthResponse:
    """Return API health status.

    Args:
        request: FastAPI request object (required by rate limiter).

    Returns:
        HealthResponse with status and timestamp.
    """
    return HealthResponse(
        status="ok",
        version="0.1.0",
        timestamp=datetime.now(timezone.utc),
    )


@app.get("/", include_in_schema=False)
async def root() -> dict:
    """Redirect hint for the API root."""
    return {"message": "CarbonSNN API — see /docs for full documentation"}


# ──────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────

def start() -> None:
    """Start the API server via uvicorn (used by project script)."""
    import uvicorn

    uvicorn.run(
        "carbonsnn.api.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
        log_level=settings.log_level.lower(),
    )

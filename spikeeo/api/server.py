"""SpikeEO FastAPI server entry point.

Configures middleware, rate limiting, CORS, and registers all route modules.
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

from spikeeo.api.routes import inference as inference_router
from spikeeo.api.routes import benchmark as benchmark_router
from spikeeo.api.routes import tasks as tasks_router
from spikeeo.api.schemas import ErrorResponse, HealthResponse
from spikeeo.config import get_settings
from spikeeo.db.session import init_db

logger = logging.getLogger(__name__)
settings = get_settings()

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup / shutdown lifecycle."""
    logger.info("SpikeEO API starting up...")
    await init_db()
    logger.info("Database initialised")
    yield
    logger.info("SpikeEO API shutting down")


app = FastAPI(
    title="SpikeEO",
    description=(
        "Energy-efficient satellite image analysis engine "
        "powered by Spiking Neural Networks."
    ),
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_debug else ["https://your-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

API_PREFIX = "/api/v1"
app.include_router(inference_router.router, prefix=API_PREFIX)
app.include_router(benchmark_router.router, prefix=API_PREFIX)
app.include_router(tasks_router.router, prefix=API_PREFIX)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next: Any) -> Response:
    """Attach X-Process-Time-Ms header to every response."""
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = f"{(time.perf_counter() - start) * 1000:.2f}"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return structured error response for unhandled exceptions."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(detail="Internal server error", code="INTERNAL_ERROR").model_dump(),
    )


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
        version="0.2.0",
        timestamp=datetime.now(timezone.utc),
    )


@app.get("/", include_in_schema=False)
async def root() -> dict:
    """API root hint."""
    return {"message": "SpikeEO API -- see /docs for documentation"}


def start() -> None:
    """Start the API server via uvicorn."""
    import uvicorn
    uvicorn.run(
        "spikeeo.api.server:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
        log_level=settings.log_level.lower(),
    )

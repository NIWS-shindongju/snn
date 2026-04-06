"""TraceCheck FastAPI application entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from tracecheck.config import settings
from tracecheck.db.session import init_db

# ── Routers ───────────────────────────────────────────────────────────────────
from tracecheck.api.routes.auth import router as auth_router
from tracecheck.api.routes.projects import router as projects_router
from tracecheck.api.routes.parcels import router as parcels_router
from tracecheck.api.routes.analysis import router as analysis_router
from tracecheck.api.routes.reports import router as reports_router

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="TraceCheck API",
        description=(
            "EUDR Supply Chain Pre-screening SaaS — "
            "Satellite-based deforestation risk assessment for due diligence workflows. "
            "Powered by SpikeEO change detection engine.\n\n"
            "⚠️ **DISCLAIMER**: This tool provides pre-screening support only and does NOT "
            "constitute a legal compliance determination under EUDR or any other regulation."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Startup ───────────────────────────────────────────────────────────────
    @app.on_event("startup")
    async def startup() -> None:
        await init_db()
        logger.info("TraceCheck API started — DB initialised")

    # ── Health ────────────────────────────────────────────────────────────────
    @app.get("/health", tags=["system"])
    async def health() -> dict:
        return {
            "status": "ok",
            "service": "TraceCheck API",
            "version": "0.1.0",
        }

    # ── API routers ───────────────────────────────────────────────────────────
    prefix = "/api"
    app.include_router(auth_router, prefix=prefix)
    app.include_router(projects_router, prefix=prefix)
    app.include_router(parcels_router, prefix=prefix)
    app.include_router(analysis_router, prefix=prefix)
    app.include_router(reports_router, prefix=prefix)

    # ── Static frontend files ─────────────────────────────────────────────────
    frontend_dir = Path(__file__).parent.parent / "frontend"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
        logger.info("Serving frontend from %s", frontend_dir)

    return app


app = create_app()


def start() -> None:
    """Entry point for uvicorn."""
    import uvicorn

    uvicorn.run(
        "tracecheck.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )


if __name__ == "__main__":
    start()

"""TraceCheck FastAPI application entry point — v1 API."""

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
from tracecheck.api.routes.organizations import router as orgs_router
from tracecheck.api.routes.webhooks import router as webhooks_router
from tracecheck.api.routes.admin import router as admin_router

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
            "**EUDR Supply Chain Pre-screening SaaS** — "
            "Satellite-based deforestation risk assessment for due diligence workflows. "
            "Powered by SpikeEO Spiking Neural Network change detection engine.\n\n"
            "## Features\n"
            "- 🌿 **EUDR / CBAM / CSRD** multi-framework compliance pre-screening\n"
            "- 🛰️ Copernicus Sentinel-2 satellite change detection\n"
            "- 📊 PDF / JSON / CSV evidence export packages\n"
            "- 🏢 Multi-tenant with RBAC (admin / analyst / viewer)\n"
            "- 🔔 Webhook alerts for high-risk plot detection\n"
            "- 🔑 Partner / white-label API key support\n\n"
            "⚠️ **DISCLAIMER**: This tool provides pre-screening support only and does NOT "
            "constitute a legal compliance determination under EUDR or any other regulation."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=[
            {"name": "auth",          "description": "Authentication — register, login, JWT"},
            {"name": "organizations", "description": "Organisation management & RBAC"},
            {"name": "projects",      "description": "EUDR compliance project management"},
            {"name": "plots",         "description": "Supplier plot upload & validation"},
            {"name": "analysis",      "description": "Analysis job runs & results"},
            {"name": "reports",       "description": "Evidence export generation & download"},
            {"name": "webhooks",      "description": "Webhook alert subscriptions"},
            {"name": "admin",         "description": "Platform admin (superuser only)"},
            {"name": "system",        "description": "Health & system info"},
        ],
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
        logger.info("TraceCheck API v1.0.0 started — DB initialised")

    # ── Health ────────────────────────────────────────────────────────────────
    @app.get("/health", tags=["system"])
    async def health() -> dict:
        return {
            "status": "ok",
            "service": "TraceCheck API",
            "version": "1.0.0",
            "features": {
                "eudr_screening": True,
                "multi_tenant": True,
                "rbac": True,
                "webhook_alerts": True,
                "partner_api": True,
                "frameworks": ["eudr", "cbam", "csrd"],
            },
        }

    @app.get("/", tags=["system"], include_in_schema=False)
    async def root() -> dict:
        return {"service": "TraceCheck API", "version": "1.0.0", "docs": "/docs"}

    # ── API v1 routers ────────────────────────────────────────────────────────
    V1 = "/api/v1"

    app.include_router(auth_router,     prefix=V1)
    app.include_router(orgs_router,     prefix=V1)
    app.include_router(projects_router, prefix=V1)
    app.include_router(parcels_router,  prefix=V1)
    app.include_router(analysis_router, prefix=V1)
    app.include_router(reports_router,  prefix=V1)
    app.include_router(webhooks_router, prefix=V1)
    app.include_router(admin_router,    prefix=V1)

    # ── Legacy /api/ (no version) aliases — backwards compat ─────────────────
    app.include_router(auth_router,     prefix="/api",   include_in_schema=False)
    app.include_router(projects_router, prefix="/api",   include_in_schema=False)
    app.include_router(parcels_router,  prefix="/api",   include_in_schema=False)
    app.include_router(analysis_router, prefix="/api",   include_in_schema=False)
    app.include_router(reports_router,  prefix="/api",   include_in_schema=False)

    # ── Static frontend files ─────────────────────────────────────────────────
    frontend_dir = Path(__file__).parent.parent.parent / "frontend"
    if frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="frontend_static")
        logger.info("Serving static frontend from %s", frontend_dir)

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

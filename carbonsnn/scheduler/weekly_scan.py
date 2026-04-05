"""Celery beat scheduler: weekly deforestation scan for all active projects.

Runs every Monday at 06:00 UTC. For each active project:
1. Searches for recent Sentinel-2 image pairs
2. Runs deforestation change detection
3. Creates Alert records
4. Dispatches registered webhooks
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from celery import Celery
from celery.schedules import crontab

from carbonsnn.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ──────────────────────────────────────────────────────────
# Celery App
# ──────────────────────────────────────────────────────────

celery_app = Celery(
    "carbonsnn",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.scheduler_timezone,
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

# ── Celery Beat schedule ──────────────────────────────────────
celery_app.conf.beat_schedule = {
    "weekly-deforestation-scan": {
        "task": "carbonsnn.scheduler.weekly_scan.run_weekly_scan",
        "schedule": crontab(hour=6, minute=0, day_of_week=1),  # Monday 06:00 UTC
        "options": {"expires": 3600},
    },
}


# ──────────────────────────────────────────────────────────
# Helper: run async code in sync Celery task
# ──────────────────────────────────────────────────────────

def _run_async(coro: "Any") -> "Any":
    """Run an async coroutine from a synchronous Celery task."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ──────────────────────────────────────────────────────────
# Tasks
# ──────────────────────────────────────────────────────────

@celery_app.task(
    name="carbonsnn.scheduler.weekly_scan.run_weekly_scan",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def run_weekly_scan(self: "Any") -> dict:
    """Celery task: scan all active projects for deforestation.

    Returns:
        Summary dict with counts of scanned projects, alerts, errors.
    """
    logger.info("Weekly scan started at %s", datetime.now(timezone.utc).isoformat())
    try:
        return _run_async(_weekly_scan_async())
    except Exception as exc:
        logger.error("Weekly scan failed: %s", exc)
        raise self.retry(exc=exc)


async def _weekly_scan_async() -> dict:
    """Async implementation of the weekly scan."""
    from carbonsnn.analysis.deforestation import DeforestationDetector
    from carbonsnn.api.routes.webhooks import dispatch_webhook
    from carbonsnn.db.crud import (
        create_alert,
        list_active_projects,
        list_webhooks,
    )
    from carbonsnn.db.session import AsyncSessionLocal

    detector = DeforestationDetector()
    stats = {"projects_scanned": 0, "alerts_created": 0, "errors": 0}

    async with AsyncSessionLocal() as db:
        projects = await list_active_projects(db)
        logger.info("Weekly scan: %d active projects", len(projects))

        for project in projects:
            stats["projects_scanned"] += 1
            bbox = [
                project.bbox_west,
                project.bbox_south,
                project.bbox_east,
                project.bbox_north,
            ]

            try:
                alerts = await detector.detect_weekly(
                    project_id=project.id, bbox=bbox
                )

                for alert in alerts:
                    db_alert = await create_alert(
                        db=db,
                        project_id=project.id,
                        area_ha=alert.area_ha,
                        severity=alert.severity,
                        centroid_lon=alert.centroid[0],
                        centroid_lat=alert.centroid[1],
                        geojson=json.dumps(alert.geojson),
                    )
                    stats["alerts_created"] += 1
                    logger.info(
                        "Alert created: project=%s area=%.2f ha severity=%s",
                        project.id,
                        alert.area_ha,
                        alert.severity,
                    )

                    # Dispatch webhooks
                    webhooks = await list_webhooks(db, project.id)
                    for webhook in webhooks:
                        if "alert.created" in webhook.events:
                            await dispatch_webhook(
                                url=webhook.url,
                                secret=webhook.secret,
                                event="alert.created",
                                payload=alert.to_dict(),
                            )

                await db.commit()

            except Exception as exc:
                stats["errors"] += 1
                logger.error("Scan failed for project %s: %s", project.id, exc)
                await db.rollback()

    logger.info(
        "Weekly scan complete: projects=%d alerts=%d errors=%d",
        stats["projects_scanned"],
        stats["alerts_created"],
        stats["errors"],
    )
    return stats


@celery_app.task(name="carbonsnn.scheduler.weekly_scan.scan_single_project")
def scan_single_project(project_id: str) -> dict:
    """On-demand scan for a single project.

    Args:
        project_id: Project UUID to scan.

    Returns:
        Scan result summary.
    """
    return _run_async(_scan_project_async(project_id))


async def _scan_project_async(project_id: str) -> dict:
    """Async implementation for single project scan."""
    from carbonsnn.analysis.deforestation import DeforestationDetector
    from carbonsnn.db.crud import create_alert, get_project
    from carbonsnn.db.session import AsyncSessionLocal
    import json

    async with AsyncSessionLocal() as db:
        project = await get_project(db, project_id)
        if not project:
            return {"error": f"Project {project_id} not found"}

        bbox = [project.bbox_west, project.bbox_south, project.bbox_east, project.bbox_north]
        detector = DeforestationDetector()

        try:
            alerts = await detector.detect_weekly(project_id=project_id, bbox=bbox)
            for alert in alerts:
                await create_alert(
                    db=db,
                    project_id=project_id,
                    area_ha=alert.area_ha,
                    severity=alert.severity,
                    centroid_lon=alert.centroid[0],
                    centroid_lat=alert.centroid[1],
                    geojson=json.dumps(alert.geojson),
                )
            await db.commit()
            return {"project_id": project_id, "alerts_created": len(alerts)}
        except Exception as exc:
            logger.error("Single scan failed for project %s: %s", project_id, exc)
            return {"project_id": project_id, "error": str(exc)}

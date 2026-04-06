"""EUDR analysis pipeline orchestrator — v2.

Runs for a single JobRun:
  1. Load all plots for the project
  2. For each plot: fetch Sentinel-2 → detect change → score risk → save PlotAssessment
  3. Update JobRun status throughout
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from tracecheck.config import settings
from tracecheck.core.change_detector import EUDRChangeDetector
from tracecheck.core.risk_scorer import score_risk
from tracecheck.core.sentinel_fetcher import SentinelFetcher
from tracecheck.db import crud

logger = logging.getLogger(__name__)


async def run_eudr_analysis(job_id: str, db: AsyncSession) -> None:
    """Execute a full EUDR analysis job run.

    This function is designed to run as a background task.
    Updates JobRun status in the DB throughout execution.

    Args:
        job_id: UUID of the JobRun to run.
        db: AsyncSession — must be a NEW session, not shared with request.
    """
    logger.info("Starting EUDR analysis job run: %s", job_id)

    # ── Load job run ──────────────────────────────────────────────────────────
    job = await crud.get_job_run(db, job_id)
    if not job:
        logger.error("JobRun not found: %s", job_id)
        return

    await crud.update_job_run_status(db, job_id, "running")
    await db.commit()

    plots = await crud.list_plots(db, job.project_id)
    if not plots:
        await crud.update_job_run_status(db, job_id, "done", processed_plots=0)
        await db.commit()
        logger.info("Job %s: no plots to process", job_id)
        return

    # ── Get project cutoff date ───────────────────────────────────────────────
    from tracecheck.db.models import Project as ProjectModel
    project = await db.get(ProjectModel, job.project_id)
    cutoff_date = (
        getattr(project, "cutoff_date", settings.eudr_cutoff_date)
        if project else settings.eudr_cutoff_date
    )

    # ── Initialize pipeline components ───────────────────────────────────────
    fetcher = SentinelFetcher(data_dir=Path(settings.data_dir) / "sentinel2")
    detector = EUDRChangeDetector(
        ndvi_threshold=settings.ndvi_threshold,
        min_area_ha=settings.min_changed_area_ha,
    )

    processed = 0
    errors = 0

    for plot in plots:
        try:
            # Extract bbox from plot geometry
            bbox = _get_bbox(plot)

            # Fetch Sentinel-2 scenes (before and after cutoff)
            before_tif, after_tif, before_info, after_info = fetcher.fetch_for_parcel(
                parcel_id=plot.id,
                bbox=bbox,
                cutoff_date=cutoff_date,
            )

            # Run change detection
            change_result = detector.detect(
                parcel_id=plot.id,
                before_tif=before_tif,
                after_tif=after_tif,
                geojson_str=plot.geojson,
                before_scene_date=before_info.acquisition_date,
                after_scene_date=after_info.acquisition_date,
            )

            # Score risk level
            risk = score_risk(change_result)

            # Save plot assessment
            await crud.save_plot_assessment(
                db,
                job_run_id=job_id,
                plot_id=plot.id,
                risk_level=risk.risk_level,
                metrics={
                    "ndvi_before": change_result.ndvi_before,
                    "ndvi_after": change_result.ndvi_after,
                    "delta_ndvi": change_result.delta_ndvi,
                    "nbr_before": change_result.nbr_before,
                    "nbr_after": change_result.nbr_after,
                    "delta_nbr": change_result.delta_nbr,
                    "changed_area_ha": change_result.changed_area_ha,
                    "cloud_fraction": change_result.cloud_fraction,
                    "confidence": risk.confidence,
                    "flag_reason": risk.flag_reason,
                    "before_scene_date": change_result.before_scene_date,
                    "after_scene_date": change_result.after_scene_date,
                    "data_source": change_result.data_source,
                },
            )
            await db.commit()

            processed += 1
            # Periodic progress update (every 10 plots)
            if processed % 10 == 0:
                await crud.update_job_run_status(
                    db, job_id, "running", processed_plots=processed
                )
                await db.commit()

            logger.debug(
                "Job %s plot %s → %s (dNDVI=%.3f)",
                job_id, plot.id[:8], risk.risk_level, change_result.delta_ndvi,
            )

        except Exception as exc:
            errors += 1
            logger.warning("Job %s: plot %s failed: %s", job_id, plot.id[:8], exc)
            # Save failed assessment as REVIEW so it still appears in results
            try:
                await crud.save_plot_assessment(
                    db,
                    job_run_id=job_id,
                    plot_id=plot.id,
                    risk_level="review",
                    metrics={
                        "flag_reason": f"processing_error: {str(exc)[:200]}",
                        "confidence": 0.0,
                        "data_source": "Copernicus Sentinel-2",
                    },
                )
                await db.commit()
                processed += 1
            except Exception:
                pass

    # ── Finalise job run ──────────────────────────────────────────────────────
    final_status = "done" if errors < len(plots) else "failed"
    err_msg = f"{errors}/{len(plots)} plots failed" if errors > 0 else None
    await crud.update_job_run_status(
        db, job_id, final_status,
        processed_plots=processed,
        error_message=err_msg,
    )
    await db.commit()
    logger.info(
        "Job %s complete: %d processed, %d errors, status=%s",
        job_id, processed, errors, final_status,
    )


def _get_bbox(plot) -> tuple[float, float, float, float]:
    """Extract (minx, miny, maxx, maxy) bounding box from a Plot ORM object."""
    # Use cached bbox columns if available
    if all(v is not None for v in [plot.bbox_minx, plot.bbox_miny, plot.bbox_maxx, plot.bbox_maxy]):
        return (plot.bbox_minx, plot.bbox_miny, plot.bbox_maxx, plot.bbox_maxy)

    # Fall back to parsing geojson
    geojson = json.loads(plot.geojson)
    geometry = geojson.get("geometry") or geojson
    geom_type = geometry.get("type", "")
    coords = geometry.get("coordinates", [])

    if geom_type == "Point":
        lon, lat = coords[0], coords[1]
        delta = 0.01  # ~1.1 km buffer
        return (lon - delta, lat - delta, lon + delta, lat + delta)

    if geom_type == "Polygon":
        flat = [c for ring in coords for c in ring]
        lons = [c[0] for c in flat]
        lats = [c[1] for c in flat]
        buf = 0.001
        return (min(lons) - buf, min(lats) - buf, max(lons) + buf, max(lats) + buf)

    raise ValueError(f"Cannot extract bbox from geometry type: {geom_type}")

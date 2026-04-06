"""Risk scorer: converts ChangeResult into EUDR risk levels.

Risk levels:
  LOW    — No significant vegetation change detected after EUDR cutoff.
  REVIEW — Borderline values or data quality issues (cloud cover, etc.).
           Human review recommended before submitting to due diligence report.
  HIGH   — Clear vegetation loss detected. Field verification recommended.

DISCLAIMER: This scoring is a pre-screening aid only and does NOT constitute
a legal determination of EUDR compliance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from tracecheck.config import settings
from tracecheck.core.change_detector import ChangeResult


@dataclass
class RiskScore:
    """Risk assessment result for a single parcel."""

    risk_level: str  # 'low' | 'review' | 'high'
    flag_reason: str | None
    confidence: float


def score_risk(result: ChangeResult) -> RiskScore:
    """Assign an EUDR pre-screening risk level from change detection metrics.

    Args:
        result: Output from EUDRChangeDetector.detect().

    Returns:
        RiskScore with level and human-readable reason.
    """
    # Handle failed detection
    if result.error or math.isnan(result.delta_ndvi):
        return RiskScore(
            risk_level="review",
            flag_reason=f"analysis_error: {result.error or 'unknown'}",
            confidence=0.0,
        )

    cloud = result.cloud_fraction
    delta = result.delta_ndvi  # positive = vegetation loss (before > after)
    area = result.changed_area_ha

    # ── Cloud-forced REVIEW ──────────────────────────────────────────────────
    if cloud > settings.max_cloud_fraction:
        return RiskScore(
            risk_level="review",
            flag_reason=f"cloud_cover_{int(cloud * 100)}pct",
            confidence=result.confidence,
        )

    # ── HIGH risk ────────────────────────────────────────────────────────────
    if delta >= settings.ndvi_high_threshold and area >= settings.min_changed_area_ha:
        reason = f"ndvi_drop_{delta:.3f}_area_{area:.2f}ha"
        return RiskScore(
            risk_level="high",
            flag_reason=reason,
            confidence=result.confidence,
        )

    # ── REVIEW ───────────────────────────────────────────────────────────────
    if delta >= settings.ndvi_threshold or area >= settings.min_changed_area_ha:
        if delta >= settings.ndvi_threshold and area >= settings.min_changed_area_ha:
            reason = f"borderline_ndvi_{delta:.3f}_area_{area:.2f}ha"
        elif delta >= settings.ndvi_threshold:
            reason = f"ndvi_drop_{delta:.3f}"
        else:
            reason = f"changed_area_{area:.2f}ha"
        return RiskScore(
            risk_level="review",
            flag_reason=reason,
            confidence=result.confidence,
        )

    # ── LOW ──────────────────────────────────────────────────────────────────
    return RiskScore(
        risk_level="low",
        flag_reason=None,
        confidence=result.confidence,
    )

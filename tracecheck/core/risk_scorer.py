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
            flag_reason=f"분석 오류 — 전문가 검토 필요 ({result.error or 'unknown'})",
            confidence=0.0,
        )

    cloud = result.cloud_fraction
    delta = result.delta_ndvi  # positive = vegetation loss (before > after)
    area = result.changed_area_ha

    # ── Cloud-forced REVIEW ──────────────────────────────────────────────────
    if cloud > settings.max_cloud_fraction:
        return RiskScore(
            risk_level="review",
            flag_reason=(
                f"구름 피복 {int(cloud * 100)}% — 위성 분석 신뢰도 낮음, 재취득 또는 현장 확인 필요"
            ),
            confidence=result.confidence,
        )

    # ── HIGH risk ────────────────────────────────────────────────────────────
    if delta >= settings.ndvi_high_threshold and area >= settings.min_changed_area_ha:
        reason = (
            f"EUDR 기준일 이후 식생 손실 감지 — dNDVI {delta:.3f} (임계값 {settings.ndvi_high_threshold}), "
            f"변화 면적 {area:.2f} ha → 현장 검증 강력 권고"
        )
        return RiskScore(
            risk_level="high",
            flag_reason=reason,
            confidence=result.confidence,
        )

    # ── REVIEW ───────────────────────────────────────────────────────────────
    if delta >= settings.ndvi_threshold or area >= settings.min_changed_area_ha:
        if delta >= settings.ndvi_threshold and area >= settings.min_changed_area_ha:
            reason = (
                f"경계선 식생 변화 — dNDVI {delta:.3f}, 변화 면적 {area:.2f} ha; "
                "전문가 추가 검토 후 실사 보고서 제출 권장"
            )
        elif delta >= settings.ndvi_threshold:
            reason = (
                f"식생지수 변화 감지 — dNDVI {delta:.3f} (임계값 {settings.ndvi_threshold}); "
                "변화 면적이 기준 미만이나 전문가 확인 권장"
            )
        else:
            reason = (
                f"변화 면적 {area:.2f} ha 감지 — NDVI 변화는 경미하나 면적 기준 초과; "
                "계절성 변화 또는 경작 여부 확인 필요"
            )
        return RiskScore(
            risk_level="review",
            flag_reason=reason,
            confidence=result.confidence,
        )

    # ── LOW ──────────────────────────────────────────────────────────────────
    return RiskScore(
        risk_level="low",
        flag_reason=(
            f"유의미한 식생 변화 없음 — dNDVI {delta:.3f} (임계값 {settings.ndvi_threshold} 미만), "
            f"변화 면적 {area:.2f} ha → EUDR 기준일 이후 산림전용 징후 미검출"
        ),
        confidence=result.confidence,
    )

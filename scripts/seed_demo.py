#!/usr/bin/env python3
"""TraceCheck demo seed script — production-quality demo data.

Creates a demo organisation, admin user, two demo projects pre-loaded
with plots AND completed analysis results (so the demo is ready to show
immediately without running the pipeline).

Usage:
    python scripts/seed_demo.py           # Ensure tables and seed
    python scripts/seed_demo.py --reset   # Drop, recreate, seed (clean slate)
    python scripts/seed_demo.py --clean   # Delete only existing demo data, re-seed

Demo accounts:
    Admin:    demo@tracecheck.io  / TraceCheck2024!
    Analyst:  analyst@tracecheck.io / Analyst2024!
    Viewer:   viewer@tracecheck.io  / Viewer2024!
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tracecheck.api.auth import hash_password
from tracecheck.db.models import (
    AuditLog, Base, EvidenceExport, JobRun,
    Organization, Plot, PlotAssessment, Project,
    RegulatoryFramework, Subscription, User,
)
from tracecheck.db.session import engine, AsyncSessionLocal


# ── Demo credentials ──────────────────────────────────────────────────────────

DEMO_ORG = {
    "name": "ACME Coffee Importers GmbH",
    "slug": "acme-coffee",
    "domain": "acme-coffee.com",
}

DEMO_USERS = [
    {
        "email": "demo@tracecheck.io",
        "password": "TraceCheck2024!",
        "org_name": "ACME Coffee Importers GmbH",
        "full_name": "Carlos Mendez",
        "role": "admin",
        "is_superuser": True,
    },
    {
        "email": "analyst@tracecheck.io",
        "password": "Analyst2024!",
        "org_name": "ACME Coffee Importers GmbH",
        "full_name": "Sarah Chen",
        "role": "analyst",
    },
    {
        "email": "viewer@tracecheck.io",
        "password": "Viewer2024!",
        "org_name": "ACME Coffee Importers GmbH",
        "full_name": "Marco Rossi",
        "role": "viewer",
    },
]


# ── GeoJSON helpers ───────────────────────────────────────────────────────────

def _pt(lon: float, lat: float, name: str) -> str:
    return json.dumps({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"name": name},
    })


def _poly(coords: list[list[float]], name: str) -> str:
    return json.dumps({
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [coords + [coords[0]]]},
        "properties": {"name": name},
    })


# ── Project 1: Colombia Coffee ─────────────────────────────────────────────────

DEMO_PROJECT_1 = {
    "name": "Colombia Coffee Q1-2025",
    "description": "EUDR pre-screening — Colombian Arabica coffee suppliers, Q1 2025 batch. "
                   "Covers Huila, Nariño, and Cauca growing regions.",
    "commodity": "coffee",
    "origin_country": "CO",
    "cutoff_date": "2020-12-31",
    "regulatory_framework": "eudr",
}

DEMO_PLOTS_1 = [
    {"plot_ref": "COL-001", "supplier_name": "Finca La Esperanza",
     "geometry_type": "point", "geojson": _pt(-76.5432, 2.1234, "Finca La Esperanza"),
     "bbox_minx": -76.5532, "bbox_miny": 2.1134, "bbox_maxx": -76.5332, "bbox_maxy": 2.1334,
     "area_ha": 4.2, "country": "CO"},
    {"plot_ref": "COL-002", "supplier_name": "Cooperativa del Sur",
     "geometry_type": "point", "geojson": _pt(-76.4089, 1.8621, "Cooperativa del Sur"),
     "bbox_minx": -76.4189, "bbox_miny": 1.8521, "bbox_maxx": -76.3989, "bbox_maxy": 1.8721,
     "area_ha": 8.7, "country": "CO"},
    {"plot_ref": "COL-003", "supplier_name": "Hacienda Buena Vista",
     "geometry_type": "point", "geojson": _pt(-76.2341, 2.4521, "Hacienda Buena Vista"),
     "bbox_minx": -76.2441, "bbox_miny": 2.4421, "bbox_maxx": -76.2241, "bbox_maxy": 2.4621,
     "area_ha": 6.1, "country": "CO"},
    {"plot_ref": "COL-004", "supplier_name": "Familia Gutierrez",
     "geometry_type": "point", "geojson": _pt(-75.9876, 1.6789, "Familia Gutierrez"),
     "bbox_minx": -75.9976, "bbox_miny": 1.6689, "bbox_maxx": -75.9776, "bbox_maxy": 1.6889,
     "area_ha": 3.5, "country": "CO"},
    {"plot_ref": "COL-005", "supplier_name": "Finca San Pedro",
     "geometry_type": "point", "geojson": _pt(-76.1234, 2.3012, "Finca San Pedro"),
     "bbox_minx": -76.1334, "bbox_miny": 2.2912, "bbox_maxx": -76.1134, "bbox_maxy": 2.3112,
     "area_ha": 5.8, "country": "CO"},
    {"plot_ref": "COL-006", "supplier_name": "Cooperativa Cauca",
     "geometry_type": "point", "geojson": _pt(-76.3210, 1.9456, "Cooperativa Cauca"),
     "bbox_minx": -76.3310, "bbox_miny": 1.9356, "bbox_maxx": -76.3110, "bbox_maxy": 1.9556,
     "area_ha": 12.3, "country": "CO"},
    {"plot_ref": "COL-007", "supplier_name": "Finca El Paraiso",
     "geometry_type": "point", "geojson": _pt(-76.6543, 2.0871, "Finca El Paraiso"),
     "bbox_minx": -76.6643, "bbox_miny": 2.0771, "bbox_maxx": -76.6443, "bbox_maxy": 2.0971,
     "area_ha": 7.9, "country": "CO"},
    {"plot_ref": "COL-008", "supplier_name": "Asociacion Huila Norte",
     "geometry_type": "point", "geojson": _pt(-75.8234, 2.5678, "Asociacion Huila Norte"),
     "bbox_minx": -75.8334, "bbox_miny": 2.5578, "bbox_maxx": -75.8134, "bbox_maxy": 2.5778,
     "area_ha": 15.4, "country": "CO"},
    {"plot_ref": "COL-009", "supplier_name": "Café Nariño Export",
     "geometry_type": "point", "geojson": _pt(-77.1234, 1.2345, "Café Nariño Export"),
     "bbox_minx": -77.1334, "bbox_miny": 1.2245, "bbox_maxx": -77.1134, "bbox_maxy": 1.2445,
     "area_ha": 9.2, "country": "CO"},
    {"plot_ref": "COL-010", "supplier_name": "Montaña Verde SAS",
     "geometry_type": "point", "geojson": _pt(-76.7890, 2.7654, "Montaña Verde SAS"),
     "bbox_minx": -76.7990, "bbox_miny": 2.7554, "bbox_maxx": -76.7790, "bbox_maxy": 2.7754,
     "area_ha": 22.1, "country": "CO"},
]

# ── Project 2: Indonesia Palm Oil ─────────────────────────────────────────────

DEMO_PROJECT_2 = {
    "name": "Indonesia Palm Oil Audit",
    "description": "EUDR pre-screening — Kalimantan palm oil suppliers. High-priority batch "
                   "due to known deforestation risk in the region.",
    "commodity": "palm_oil",
    "origin_country": "ID",
    "cutoff_date": "2020-12-31",
    "regulatory_framework": "eudr",
}

DEMO_PLOTS_2 = [
    {"plot_ref": "IDN-001", "supplier_name": "PT Sawit Makmur",
     "geometry_type": "point", "geojson": _pt(113.4567, -2.3456, "PT Sawit Makmur Block 1"),
     "bbox_minx": 113.4467, "bbox_miny": -2.3556, "bbox_maxx": 113.4667, "bbox_maxy": -2.3356,
     "area_ha": 250.0, "country": "ID"},
    {"plot_ref": "IDN-002", "supplier_name": "Kebun Rakyat Kalimantan",
     "geometry_type": "point", "geojson": _pt(114.1234, -1.9876, "Kebun Rakyat Kalimantan"),
     "bbox_minx": 114.1134, "bbox_miny": -1.9976, "bbox_maxx": 114.1334, "bbox_maxy": -1.9776,
     "area_ha": 180.5, "country": "ID"},
    {"plot_ref": "IDN-003", "supplier_name": "CV Agro Borneo",
     "geometry_type": "point", "geojson": _pt(112.9876, -2.8765, "CV Agro Borneo Site A"),
     "bbox_minx": 112.9776, "bbox_miny": -2.8865, "bbox_maxx": 112.9976, "bbox_maxy": -2.8665,
     "area_ha": 320.0, "country": "ID"},
    {"plot_ref": "IDN-004", "supplier_name": "Rimba Lestari Group",
     "geometry_type": "point", "geojson": _pt(115.2345, -3.1234, "Rimba Lestari Group"),
     "bbox_minx": 115.2245, "bbox_miny": -3.1334, "bbox_maxx": 115.2445, "bbox_maxy": -3.1134,
     "area_ha": 410.0, "country": "ID"},
    {"plot_ref": "IDN-005", "supplier_name": "Usaha Tani Hijau",
     "geometry_type": "point", "geojson": _pt(113.7890, -1.5678, "Usaha Tani Hijau"),
     "bbox_minx": 113.7790, "bbox_miny": -1.5778, "bbox_maxx": 113.7990, "bbox_maxy": -1.5578,
     "area_ha": 95.0, "country": "ID"},
    {"plot_ref": "IDN-006", "supplier_name": "Koperasi Sawit Borneo",
     "geometry_type": "point", "geojson": _pt(114.5678, -2.0123, "Koperasi Sawit Borneo"),
     "bbox_minx": 114.5578, "bbox_miny": -2.0223, "bbox_maxx": 114.5778, "bbox_maxy": -2.0023,
     "area_ha": 560.0, "country": "ID"},
]


# ── Assessment templates for deterministic demo results ───────────────────────
# Format: (risk_level, ndvi_before, ndvi_after, cloud_fraction, flag_reason)

ASSESSMENT_TEMPLATES_1 = [
    # COL-001 to COL-010 — mixed results for a realistic demo
    ("low",    0.62, 0.61, 0.04, None),
    ("low",    0.68, 0.67, 0.03, None),
    ("review", 0.65, 0.52, 0.07, "Borderline NDVI decline: −0.130 (threshold 0.10). Expert review recommended."),
    ("low",    0.71, 0.70, 0.05, None),
    ("high",   0.72, 0.43, 0.04, "Significant vegetation loss detected: dNDVI=−0.290, changed area 2.50 ha. Field verification required."),
    ("low",    0.60, 0.59, 0.06, None),
    ("review", 0.58, 0.56, 0.62, "High cloud coverage (62%) prevents reliable assessment. Re-analyse with clearer imagery."),
    ("low",    0.66, 0.65, 0.08, None),
    ("high",   0.74, 0.44, 0.05, "Clear forest clearing event: dNDVI=−0.300, changed area 3.80 ha. Post-2020 deforestation suspected."),
    ("review", 0.63, 0.51, 0.11, "Moderate vegetation change: dNDVI=−0.120. Seasonal variation possible — review recommended."),
]

ASSESSMENT_TEMPLATES_2 = [
    # IDN-001 to IDN-006
    ("high",   0.71, 0.41, 0.04, "Large-scale vegetation loss: dNDVI=−0.300, changed area 45.2 ha. Immediate field verification required."),
    ("low",    0.58, 0.57, 0.09, None),
    ("high",   0.75, 0.38, 0.03, "Severe deforestation signal: dNDVI=−0.370, changed area 89.1 ha. Highest risk category."),
    ("review", 0.67, 0.55, 0.15, "Borderline change with partial cloud coverage. Independent review strongly advised."),
    ("low",    0.60, 0.59, 0.07, None),
    ("high",   0.69, 0.40, 0.06, "Plantation expansion into forest: dNDVI=−0.290, changed area 62.3 ha. EUDR non-compliance risk HIGH."),
]


# ── DB helpers ────────────────────────────────────────────────────────────────

def _now(delta_days: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=delta_days)


async def reset_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("✓ DB reset: 전체 테이블 삭제 후 재생성")


async def init_db_if_needed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ 테이블 확인 완료")


async def _upsert_org(db: AsyncSession) -> Organization:
    result = await db.execute(select(Organization).where(Organization.slug == DEMO_ORG["slug"]))
    org = result.scalar_one_or_none()
    if not org:
        org = Organization(**DEMO_ORG)
        db.add(org)
        await db.flush()
        await db.refresh(org)

        # Create pro subscription for demo
        sub = Subscription(
            org_id=org.id, tier="pro",
            max_projects=20, max_plots_per_run=500, max_users=5,
            api_access=True, webhook_access=True, white_label=False, pdf_reports=True,
            billing_status="active",
        )
        db.add(sub)
        await db.flush()
        print(f"✓ 조직 생성: {org.name}  [pro tier]")
    else:
        print(f"  기존 조직 사용: {org.name}")
    return org


async def _upsert_user(db: AsyncSession, org: Organization, user_data: dict) -> User:
    result = await db.execute(select(User).where(User.email == user_data["email"]))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            email=user_data["email"],
            hashed_password=hash_password(user_data["password"]),
            org_name=user_data.get("org_name"),
            full_name=user_data.get("full_name"),
            role=user_data.get("role", "analyst"),
            is_superuser=user_data.get("is_superuser", False),
            org_id=org.id,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        print(f"  ✓ 사용자 생성: {user.email} [{user.role}]")
    else:
        # Update org_id if needed
        if not user.org_id:
            user.org_id = org.id
        await db.flush()
        print(f"    기존 사용자: {user.email}")
    return user


async def _upsert_project(
    db: AsyncSession,
    user: User,
    proj_data: dict,
    plots_data: list[dict],
    assessment_templates: list[tuple],
) -> Project:
    result = await db.execute(
        select(Project).where(
            Project.owner_id == user.id,
            Project.name == proj_data["name"],
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        project = Project(owner_id=user.id, org_id=user.org_id, **proj_data)
        db.add(project)
        await db.flush()
        await db.refresh(project)
        print(f"  ✓ 프로젝트 생성: {project.name}  [{project.id[:8]}]")
    else:
        print(f"    기존 프로젝트: {project.name}  [{project.id[:8]}]")

    # Insert plots only if none exist
    existing_plots = (await db.execute(
        select(Plot).where(Plot.project_id == project.id)
    )).scalars().all()

    if not existing_plots:
        plots = []
        for d in plots_data:
            plot = Plot(project_id=project.id, **d)
            db.add(plot)
            plots.append(plot)
        await db.flush()
        print(f"    ✓ 필지 {len(plots)}개 삽입")

        # Create a completed job run with results
        n_plots = len(plots_data)
        job = JobRun(
            project_id=project.id,
            triggered_by=user.id,
            status="done",
            total_plots=n_plots,
            processed_plots=n_plots,
            data_mode="mock",
            started_at=_now(7),
            completed_at=_now(7),
        )
        db.add(job)
        await db.flush()
        await db.refresh(job)

        # Create assessments
        for plot, (risk, ndvi_b, ndvi_a, cloud, reason) in zip(plots, assessment_templates):
            delta = round(ndvi_b - ndvi_a, 4)
            cutoff = proj_data["cutoff_date"]
            co = datetime.strptime(cutoff, "%Y-%m-%d")
            before_date = (co - timedelta(days=180)).strftime("%Y-%m-%d")
            after_date = _now(7).strftime("%Y-%m-%d")

            area = 0.0
            if risk == "high":
                area = abs(delta) * 15.0 + 1.0  # roughly proportional
            elif risk == "review":
                area = abs(delta) * 5.0

            pa = PlotAssessment(
                job_run_id=job.id,
                plot_id=plot.id,
                risk_level=risk,
                ndvi_before=ndvi_b,
                ndvi_after=ndvi_a,
                delta_ndvi=round(-delta, 4),  # positive = loss
                nbr_before=round(ndvi_b * 0.85, 4),
                nbr_after=round(ndvi_a * 0.85, 4),
                delta_nbr=round(-delta * 0.85, 4),
                changed_area_ha=round(area, 2),
                cloud_fraction=cloud,
                confidence=round(max(0.0, 1.0 - cloud), 3),
                flag_reason=reason,
                before_scene_date=before_date,
                after_scene_date=after_date,
                data_source="Copernicus Sentinel-2 L2A (DEMO)",
                assessed_at=_now(7),
            )
            db.add(pa)
        await db.flush()
        print(f"    ✓ 분석 결과 {n_plots}건 삽입 (job: {job.id[:8]})")

        # Audit log entries
        for action, detail, delta_days in [
            ("project.created", {"name": proj_data["name"]}, 10),
            ("plots.upload",    {"created": n_plots, "filename": "supplier_plots.csv"}, 8),
            ("job.started",     {"job_run_id": job.id, "total_plots": n_plots}, 7),
            ("job.completed",   {"job_run_id": job.id, "processed": n_plots}, 7),
            ("export.created",  {"format": "pdf"}, 6),
        ]:
            db.add(AuditLog(
                project_id=project.id,
                user_id=user.id,
                action=action,
                detail=detail,
                occurred_at=_now(delta_days),
            ))
        await db.flush()
    else:
        print(f"    필지/결과 이미 존재 — 건너뜀")

    return project


async def _seed_regulatory_frameworks(db: AsyncSession) -> None:
    """Ensure built-in regulatory frameworks exist."""
    frameworks = [
        {"code": "eudr",  "name": "EU Deforestation Regulation (EUDR)",
         "description": "EU 2023/1115 — Regulation on deforestation-free products.",
         "default_cutoff_date": "2020-12-31",
         "applicable_commodities": ["coffee", "cocoa", "palm_oil", "soy", "cattle", "wood", "rubber"],
         "status": "active"},
        {"code": "cbam",  "name": "Carbon Border Adjustment Mechanism (CBAM)",
         "description": "EU carbon price on certain goods from outside the EU.",
         "default_cutoff_date": "2020-12-31",
         "applicable_commodities": ["soy", "palm_oil", "wood"],
         "status": "active"},
        {"code": "csrd",  "name": "Corporate Sustainability Reporting Directive (CSRD)",
         "description": "EU directive requiring sustainability disclosure.",
         "default_cutoff_date": "2020-12-31",
         "applicable_commodities": ["coffee", "cocoa", "palm_oil", "soy", "cattle", "wood", "rubber"],
         "status": "active"},
    ]
    seeded = 0
    for fw_data in frameworks:
        existing = (await db.execute(
            select(RegulatoryFramework).where(RegulatoryFramework.code == fw_data["code"])
        )).scalar_one_or_none()
        if not existing:
            db.add(RegulatoryFramework(**fw_data))
            seeded += 1
    if seeded:
        await db.flush()
        print(f"  ✓ 규제 프레임워크 {seeded}개 삽입 (EUDR, CBAM, CSRD)")


async def clean_demo_data(db: AsyncSession) -> None:
    result = await db.execute(select(User).where(User.email == DEMO_USERS[0]["email"]))
    user = result.scalar_one_or_none()
    if not user:
        return
    projects = (await db.execute(
        select(Project).where(Project.owner_id == user.id)
    )).scalars().all()
    for p in projects:
        await db.delete(p)
    await db.flush()
    print(f"✓ 기존 데모 데이터 삭제 ({len(projects)}개 프로젝트)")

    # Delete demo users
    for ud in DEMO_USERS:
        u = (await db.execute(select(User).where(User.email == ud["email"]))).scalar_one_or_none()
        if u:
            await db.delete(u)
    await db.flush()

    # Delete demo org
    org = (await db.execute(
        select(Organization).where(Organization.slug == DEMO_ORG["slug"])
    )).scalar_one_or_none()
    if org:
        await db.delete(org)
    await db.flush()


async def seed(db: AsyncSession, clean: bool = False) -> None:
    if clean:
        await clean_demo_data(db)

    print("\n📦 조직 & 사용자 설정...")
    org = await _upsert_org(db)
    users = []
    for ud in DEMO_USERS:
        u = await _upsert_user(db, org, ud)
        users.append(u)
    admin_user = users[0]

    print("\n🌿 규제 프레임워크...")
    await _seed_regulatory_frameworks(db)

    print("\n📊 프로젝트 & 데이터...")
    await _upsert_project(db, admin_user, DEMO_PROJECT_1, DEMO_PLOTS_1, ASSESSMENT_TEMPLATES_1)
    await _upsert_project(db, admin_user, DEMO_PROJECT_2, DEMO_PLOTS_2, ASSESSMENT_TEMPLATES_2)

    await db.commit()

    print("\n" + "═" * 60)
    print("🎉  TraceCheck 데모 시딩 완료!")
    print("═" * 60)
    print(f"\n  로그인 계정:")
    for ud in DEMO_USERS:
        print(f"    [{ud['role']:8s}] {ud['email']:35s} / {ud['password']}")
    print(f"\n  엔드포인트:")
    print(f"    API 문서:   http://localhost:8000/docs")
    print(f"    대시보드:   http://localhost:8501")
    print(f"    랜딩 페이지: http://localhost:8000/static/index.html")
    print("═" * 60 + "\n")


async def main(reset: bool = False, clean: bool = False) -> None:
    if reset:
        await reset_db()
    else:
        await init_db_if_needed()

    async with AsyncSessionLocal() as db:
        await seed(db, clean=clean)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TraceCheck 데모 데이터 시딩")
    parser.add_argument("--reset", action="store_true", help="DB 전체 초기화 후 재시딩")
    parser.add_argument("--clean", action="store_true", help="기존 데모 데이터만 삭제 후 재시딩")
    args = parser.parse_args()

    asyncio.run(main(reset=args.reset, clean=args.clean))

#!/usr/bin/env python3
"""TraceCheck demo seed script.

Creates a demo user and two demo projects pre-loaded with plots that match
examples/sample_plots.csv (so upload → verify works seamlessly in demo).

Usage:
    python scripts/seed_demo.py           # Ensure tables and seed
    python scripts/seed_demo.py --reset   # Drop, recreate, seed (clean slate)
    python scripts/seed_demo.py --clean   # Delete only existing demo data, re-seed
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tracecheck.api.auth import hash_password
from tracecheck.db.models import Base, User, Project, Plot
from tracecheck.db.session import engine, AsyncSessionLocal


# ── Demo credentials ──────────────────────────────────────────────────────────

DEMO_USER = {
    "email": "demo@tracecheck.io",
    "password": "TraceCheck2024!",
    "org_name": "ACME Coffee Importers",
}

# ── Project 1: Colombia Coffee — matches examples/sample_plots.csv rows 1-8 ──

DEMO_PROJECT_1 = {
    "name": "Colombia Coffee Q1-2025",
    "description": "EUDR 사전점검 — 콜롬비아 아라비카 커피 공급업체 Q1 2025 배치",
    "commodity": "coffee",
    "origin_country": "CO",
    "cutoff_date": "2020-12-31",
}

def _pt(lon: float, lat: float, name: str) -> str:
    return json.dumps({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"name": name},
    })

DEMO_PLOTS_1 = [
    # Exactly matches examples/sample_plots.csv COL-001 ~ COL-007
    {
        "plot_ref": "COL-001", "supplier_name": "Finca La Esperanza",
        "geometry_type": "point",
        "geojson": _pt(-76.5432, 2.1234, "Finca La Esperanza"),
        "bbox_minx": -76.5532, "bbox_miny": 2.1134, "bbox_maxx": -76.5332, "bbox_maxy": 2.1334,
        "area_ha": 4.2, "country": "CO",
    },
    {
        "plot_ref": "COL-002", "supplier_name": "Cooperativa del Sur",
        "geometry_type": "point",
        "geojson": _pt(-76.4089, 1.8621, "Cooperativa del Sur"),
        "bbox_minx": -76.4189, "bbox_miny": 1.8521, "bbox_maxx": -76.3989, "bbox_maxy": 1.8721,
        "area_ha": 8.7, "country": "CO",
    },
    {
        "plot_ref": "COL-003", "supplier_name": "Hacienda Buena Vista",
        "geometry_type": "point",
        "geojson": _pt(-76.2341, 2.4521, "Hacienda Buena Vista"),
        "bbox_minx": -76.2441, "bbox_miny": 2.4421, "bbox_maxx": -76.2241, "bbox_maxy": 2.4621,
        "area_ha": 6.1, "country": "CO",
    },
    {
        "plot_ref": "COL-004", "supplier_name": "Familia Gutierrez",
        "geometry_type": "point",
        "geojson": _pt(-75.9876, 1.6789, "Familia Gutierrez"),
        "bbox_minx": -75.9976, "bbox_miny": 1.6689, "bbox_maxx": -75.9776, "bbox_maxy": 1.6889,
        "area_ha": 3.5, "country": "CO",
    },
    {
        "plot_ref": "COL-005", "supplier_name": "Finca San Pedro",
        "geometry_type": "point",
        "geojson": _pt(-76.1234, 2.3012, "Finca San Pedro"),
        "bbox_minx": -76.1334, "bbox_miny": 2.2912, "bbox_maxx": -76.1134, "bbox_maxy": 2.3112,
        "area_ha": 5.8, "country": "CO",
    },
    {
        "plot_ref": "COL-006", "supplier_name": "Cooperativa Cauca",
        "geometry_type": "point",
        "geojson": _pt(-76.3210, 1.9456, "Cooperativa Cauca"),
        "bbox_minx": -76.3310, "bbox_miny": 1.9356, "bbox_maxx": -76.3110, "bbox_maxy": 1.9556,
        "area_ha": 12.3, "country": "CO",
    },
    {
        "plot_ref": "COL-007", "supplier_name": "Finca El Paraiso",
        "geometry_type": "point",
        "geojson": _pt(-76.6543, 2.0871, "Finca El Paraiso"),
        "bbox_minx": -76.6643, "bbox_miny": 2.0771, "bbox_maxx": -76.6443, "bbox_maxy": 2.0971,
        "area_ha": 7.9, "country": "CO",
    },
]

# ── Project 2: Indonesia Palm Oil — matches IDN rows in sample_plots.csv ──────

DEMO_PROJECT_2 = {
    "name": "Indonesia Palm Oil Audit",
    "description": "EUDR 사전점검 — 칼리만탄 팜유 공급업체 산림전용 리스크 스크리닝",
    "commodity": "palm_oil",
    "origin_country": "ID",
    "cutoff_date": "2020-12-31",
}

DEMO_PLOTS_2 = [
    {
        "plot_ref": "IDN-001", "supplier_name": "PT Sawit Makmur",
        "geometry_type": "point",
        "geojson": _pt(113.4567, -2.3456, "PT Sawit Makmur Block 1"),
        "bbox_minx": 113.4467, "bbox_miny": -2.3556, "bbox_maxx": 113.4667, "bbox_maxy": -2.3356,
        "area_ha": 250.0, "country": "ID",
    },
    {
        "plot_ref": "IDN-002", "supplier_name": "Kebun Rakyat Kalimantan",
        "geometry_type": "point",
        "geojson": _pt(114.1234, -1.9876, "Kebun Rakyat Kalimantan"),
        "bbox_minx": 114.1134, "bbox_miny": -1.9976, "bbox_maxx": 114.1334, "bbox_maxy": -1.9776,
        "area_ha": 180.5, "country": "ID",
    },
    {
        "plot_ref": "IDN-003", "supplier_name": "CV Agro Borneo",
        "geometry_type": "point",
        "geojson": _pt(112.9876, -2.8765, "CV Agro Borneo Site A"),
        "bbox_minx": 112.9776, "bbox_miny": -2.8865, "bbox_maxx": 112.9976, "bbox_maxy": -2.8665,
        "area_ha": 320.0, "country": "ID",
    },
]


# ── DB helpers ────────────────────────────────────────────────────────────────

async def reset_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("✓ DB reset: 전체 테이블 삭제 후 재생성")


async def init_db_if_needed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ 테이블 확인 완료")


async def _upsert_user(db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == DEMO_USER["email"]))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            email=DEMO_USER["email"],
            hashed_password=hash_password(DEMO_USER["password"]),
            org_name=DEMO_USER["org_name"],
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        print(f"✓ 데모 계정 생성: {user.email}")
    else:
        print(f"  기존 계정 사용: {user.email}")
    return user


async def _upsert_project(db: AsyncSession, user: User, proj_data: dict, plots_data: list[dict]) -> Project:
    result = await db.execute(
        select(Project).where(
            Project.owner_id == user.id,
            Project.name == proj_data["name"],
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        project = Project(owner_id=user.id, **proj_data)
        db.add(project)
        await db.flush()
        await db.refresh(project)
        print(f"✓ 프로젝트 생성: {project.name}  [{project.id[:8]}]")
    else:
        print(f"  기존 프로젝트: {project.name}  [{project.id[:8]}]")

    # Insert plots only if none exist
    existing = await db.execute(select(Plot).where(Plot.project_id == project.id))
    if not existing.scalars().all():
        for d in plots_data:
            db.add(Plot(project_id=project.id, **d))
        await db.flush()
        print(f"  ✓ 필지 {len(plots_data)}개 삽입")
    else:
        print(f"  필지 이미 존재 — 삽입 건너뜀")

    return project


async def clean_demo_data(db: AsyncSession) -> None:
    """Remove existing demo user's projects and plots (for --clean mode)."""
    result = await db.execute(select(User).where(User.email == DEMO_USER["email"]))
    user = result.scalar_one_or_none()
    if not user:
        return
    projects = (await db.execute(select(Project).where(Project.owner_id == user.id))).scalars().all()
    for p in projects:
        await db.delete(p)
    await db.flush()
    print(f"✓ 기존 데모 데이터 삭제 ({len(projects)}개 프로젝트)")


async def seed(db: AsyncSession, clean: bool = False) -> None:
    if clean:
        await clean_demo_data(db)

    user = await _upsert_user(db)
    await _upsert_project(db, user, DEMO_PROJECT_1, DEMO_PLOTS_1)
    await _upsert_project(db, user, DEMO_PROJECT_2, DEMO_PLOTS_2)

    await db.commit()

    print("\n" + "─" * 52)
    print("🎉 데모 시딩 완료!")
    print(f"   이메일:    {DEMO_USER['email']}")
    print(f"   비밀번호:  {DEMO_USER['password']}")
    print(f"   API 문서:  http://localhost:8000/docs")
    print(f"   대시보드:  http://localhost:8501")
    print(f"   샘플 CSV:  examples/sample_plots.csv")
    print("─" * 52)


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

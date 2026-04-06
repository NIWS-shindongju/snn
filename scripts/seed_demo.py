#!/usr/bin/env python3
"""TraceCheck demo seed script.

Creates a demo user, project, and sample parcels (coffee origin, Colombia)
to enable immediate demo walkthroughs.

Usage:
    python scripts/seed_demo.py
    python scripts/seed_demo.py --reset   # Drop and recreate DB first
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession

from tracecheck.api.auth import hash_password
from tracecheck.config import settings
from tracecheck.db.models import Base, User, Project, Parcel
from tracecheck.db.session import engine, AsyncSessionLocal


# ── Demo data ─────────────────────────────────────────────────────────────────

DEMO_USER = {
    "email": "demo@tracecheck.io",
    "password": "TraceCheck2024!",
    "org_name": "ACME Coffee Importers",
}

DEMO_PROJECT = {
    "name": "Colombia Coffee Q1-2024",
    "description": "EUDR due diligence for Colombian arabica coffee suppliers — Q1 2024 batch",
    "commodity": "coffee",
    "origin_country": "CO",
    "cutoff_date": "2020-12-31",
}

# Sample parcels in Colombia's coffee belt (Huila/Nariño region)
DEMO_PARCELS = [
    {
        "supplier_name": "Finca La Esperanza",
        "parcel_ref": "COL-001",
        "geometry_type": "point",
        "geojson": json.dumps({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-76.5, 2.1]},
            "properties": {"name": "Finca La Esperanza"},
        }),
        "bbox_minx": -76.51, "bbox_miny": 2.09, "bbox_maxx": -76.49, "bbox_maxy": 2.11,
        "area_ha": 4.2,
        "country": "CO",
    },
    {
        "supplier_name": "Cooperativa del Sur",
        "parcel_ref": "COL-002",
        "geometry_type": "polygon",
        "geojson": json.dumps({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-76.42, 1.85], [-76.40, 1.85],
                    [-76.40, 1.87], [-76.42, 1.87],
                    [-76.42, 1.85]
                ]],
            },
            "properties": {"name": "Cooperativa del Sur, Plot A"},
        }),
        "bbox_minx": -76.42, "bbox_miny": 1.85, "bbox_maxx": -76.40, "bbox_maxy": 1.87,
        "area_ha": 8.7,
        "country": "CO",
    },
    {
        "supplier_name": "Finca Montaña Verde",
        "parcel_ref": "COL-003",
        "geometry_type": "point",
        "geojson": json.dumps({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-77.1, 1.4]},
            "properties": {"name": "Finca Montaña Verde"},
        }),
        "bbox_minx": -77.11, "bbox_miny": 1.39, "bbox_maxx": -77.09, "bbox_maxy": 1.41,
        "area_ha": 3.1,
        "country": "CO",
    },
    {
        "supplier_name": "Hacienda Bella Vista",
        "parcel_ref": "COL-004",
        "geometry_type": "point",
        "geojson": json.dumps({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-75.9, 5.5]},
            "properties": {"name": "Hacienda Bella Vista"},
        }),
        "bbox_minx": -75.91, "bbox_miny": 5.49, "bbox_maxx": -75.89, "bbox_maxy": 5.51,
        "area_ha": 12.3,
        "country": "CO",
    },
    {
        "supplier_name": "Empresa Agro San Juan",
        "parcel_ref": "COL-005",
        "geometry_type": "polygon",
        "geojson": json.dumps({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-76.0, 2.5], [-75.98, 2.5],
                    [-75.98, 2.52], [-76.0, 2.52],
                    [-76.0, 2.5]
                ]],
            },
            "properties": {"name": "Empresa Agro San Juan, Block 2"},
        }),
        "bbox_minx": -76.0, "bbox_miny": 2.5, "bbox_maxx": -75.98, "bbox_maxy": 2.52,
        "area_ha": 6.5,
        "country": "CO",
    },
]

# ── Second demo project: palm oil, Indonesia ──────────────────────────────────

DEMO_PROJECT_2 = {
    "name": "Indonesia Palm Oil Audit",
    "description": "EUDR deforestation risk screen for Kalimantan palm oil suppliers",
    "commodity": "palm_oil",
    "origin_country": "ID",
    "cutoff_date": "2020-12-31",
}

DEMO_PARCELS_2 = [
    {
        "supplier_name": "PT Sawit Kalimantan",
        "parcel_ref": "IDN-001",
        "geometry_type": "point",
        "geojson": json.dumps({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [114.5, 0.5]},
            "properties": {"name": "PT Sawit Kalimantan Block 1"},
        }),
        "bbox_minx": 114.49, "bbox_miny": 0.49, "bbox_maxx": 114.51, "bbox_maxy": 0.51,
        "area_ha": 250.0,
        "country": "ID",
    },
    {
        "supplier_name": "Agro Indo Resources",
        "parcel_ref": "IDN-002",
        "geometry_type": "point",
        "geojson": json.dumps({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [115.3, -1.2]},
            "properties": {"name": "Agro Indo Resources Site A"},
        }),
        "bbox_minx": 115.29, "bbox_miny": -1.21, "bbox_maxx": 115.31, "bbox_maxy": -1.19,
        "area_ha": 180.5,
        "country": "ID",
    },
]


# ── Async helpers ─────────────────────────────────────────────────────────────

async def reset_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Database reset (drop + create all tables)")


async def init_db_if_needed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Tables ensured")


async def seed(db: AsyncSession) -> None:
    from sqlalchemy import select

    # ── User ──────────────────────────────────────────────────────────────────
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
        print(f"✓ Created user: {user.email}")
    else:
        print(f"  User already exists: {user.email}")

    # ── Project 1: Coffee ─────────────────────────────────────────────────────
    result = await db.execute(
        select(Project).where(
            Project.owner_id == user.id,
            Project.name == DEMO_PROJECT["name"],
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        project = Project(owner_id=user.id, **DEMO_PROJECT)
        db.add(project)
        await db.flush()
        await db.refresh(project)
        print(f"✓ Created project: {project.name} [{project.id[:8]}]")
    else:
        print(f"  Project already exists: {project.name}")

    # Add coffee parcels
    result = await db.execute(select(Parcel).where(Parcel.project_id == project.id))
    existing_count = len(result.scalars().all())
    if existing_count == 0:
        for p_data in DEMO_PARCELS:
            parcel = Parcel(project_id=project.id, **p_data)
            db.add(parcel)
        await db.flush()
        print(f"  ✓ Inserted {len(DEMO_PARCELS)} coffee parcels")
    else:
        print(f"  Parcels already exist ({existing_count})")

    # ── Project 2: Palm oil ───────────────────────────────────────────────────
    result = await db.execute(
        select(Project).where(
            Project.owner_id == user.id,
            Project.name == DEMO_PROJECT_2["name"],
        )
    )
    project2 = result.scalar_one_or_none()
    if not project2:
        project2 = Project(owner_id=user.id, **DEMO_PROJECT_2)
        db.add(project2)
        await db.flush()
        await db.refresh(project2)
        print(f"✓ Created project: {project2.name} [{project2.id[:8]}]")
    else:
        print(f"  Project already exists: {project2.name}")

    result = await db.execute(select(Parcel).where(Parcel.project_id == project2.id))
    existing_count2 = len(result.scalars().all())
    if existing_count2 == 0:
        for p_data in DEMO_PARCELS_2:
            parcel = Parcel(project_id=project2.id, **p_data)
            db.add(parcel)
        await db.flush()
        print(f"  ✓ Inserted {len(DEMO_PARCELS_2)} palm oil parcels")
    else:
        print(f"  Parcels already exist ({existing_count2})")

    await db.commit()
    print("\n🎉 Demo seed complete!")
    print(f"   Login:    {DEMO_USER['email']}")
    print(f"   Password: {DEMO_USER['password']}")
    print(f"   API docs: http://localhost:8000/docs")


async def main(reset: bool = False) -> None:
    if reset:
        await reset_db()
    else:
        await init_db_if_needed()

    async with AsyncSessionLocal() as db:
        await seed(db)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed TraceCheck demo data")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate DB before seeding")
    args = parser.parse_args()

    asyncio.run(main(reset=args.reset))

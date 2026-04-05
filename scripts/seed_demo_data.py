"""Seed database with demo data for development and testing.

Creates:
- 1 demo user with API key
- 3 projects: Amazon / Borneo / Congo
- 10 deforestation alerts
- 2 webhooks

Usage:
    python scripts/seed_demo_data.py
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from random import choice, random, uniform

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Demo fixtures
# ──────────────────────────────────────────────────────────

DEMO_USER = {
    "email": "demo@carbonsnn.io",
    "password": "DemoPassword123!",
}

DEMO_PROJECTS = [
    {
        "name": "Amazon Basin Monitoring",
        "country": "Brazil",
        "description": "Continuous monitoring of primary Amazon rainforest in Pará state.",
        "bbox": [-55.0, -5.0, -50.0, -1.0],
    },
    {
        "name": "Borneo Central Highlands",
        "country": "Indonesia",
        "description": "Tropical peat-swamp and hill forest monitoring in Kalimantan.",
        "bbox": [112.0, -1.5, 117.0, 2.5],
    },
    {
        "name": "Congo Basin Forest Watch",
        "country": "Democratic Republic of Congo",
        "description": "REDD+ monitoring site in the Congo Basin — second largest tropical forest.",
        "bbox": [23.0, -3.0, 28.0, 2.0],
    },
]


def _random_alert(project_id: str, bbox: list[float]) -> dict:
    """Generate a randomised deforestation alert within the project bbox."""
    west, south, east, north = bbox
    lat = uniform(south, north)
    lon = uniform(west, east)
    area_ha = round(uniform(0.5, 80.0), 2)
    severity = "low" if area_ha < 5 else ("medium" if area_ha < 20 else "high")
    days_ago = int(uniform(0, 90))
    detected = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        "project_id": project_id,
        "area_ha": area_ha,
        "severity": severity,
        "centroid_lon": round(lon, 6),
        "centroid_lat": round(lat, 6),
        "detected_date": detected,
        "geojson": json.dumps({
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [lon - 0.01, lat - 0.01],
                        [lon + 0.01, lat - 0.01],
                        [lon + 0.01, lat + 0.01],
                        [lon - 0.01, lat + 0.01],
                        [lon - 0.01, lat - 0.01],
                    ]],
                },
                "properties": {"area_ha": area_ha, "severity": severity},
            }],
        }),
    }


# ──────────────────────────────────────────────────────────
# Async seed function
# ──────────────────────────────────────────────────────────

async def seed() -> None:
    """Create all demo data records in the database."""
    from carbonsnn.api.auth import hash_password
    from carbonsnn.db import crud
    from carbonsnn.db.models import Alert, APIKey
    from carbonsnn.db.session import AsyncSessionLocal, init_db

    logger.info("Initialising database schema…")
    await init_db()

    async with AsyncSessionLocal() as db:
        # ── Demo user ─────────────────────────────────────
        existing = await crud.get_user_by_email(db, DEMO_USER["email"])
        if existing:
            logger.info("Demo user already exists: %s", DEMO_USER["email"])
            user = existing
        else:
            user = await crud.create_user(
                db=db,
                email=DEMO_USER["email"],
                hashed_password=hash_password(DEMO_USER["password"]),
                is_superuser=True,
            )
            logger.info("Created demo user: %s", DEMO_USER["email"])

        # ── API key ────────────────────────────────────────
        raw_key, api_key = await crud.create_api_key(
            db=db, user_id=user.id, name="Demo Key"
        )
        logger.info("Demo API key created: %s…", raw_key[:20])

        # ── Projects + Alerts ──────────────────────────────
        project_ids: list[str] = []
        for project_data in DEMO_PROJECTS:
            proj = await crud.create_project(
                db=db,
                owner_id=user.id,
                name=project_data["name"],
                country=project_data["country"],
                bbox=project_data["bbox"],
                description=project_data["description"],
            )
            project_ids.append(proj.id)
            logger.info("Created project: %s (%s)", proj.name, proj.id)

            # 3–4 alerts per project
            num_alerts = 3 if project_data["country"] != "Brazil" else 4
            for _ in range(num_alerts):
                alert_data = _random_alert(proj.id, project_data["bbox"])
                alert = Alert(
                    project_id=proj.id,
                    area_ha=alert_data["area_ha"],
                    severity=alert_data["severity"],
                    centroid_lon=alert_data["centroid_lon"],
                    centroid_lat=alert_data["centroid_lat"],
                    detected_date=alert_data["detected_date"],
                    geojson=alert_data["geojson"],
                )
                db.add(alert)

        # ── Webhooks ───────────────────────────────────────
        from carbonsnn.db.models import Webhook

        webhooks = [
            Webhook(
                project_id=project_ids[0],
                url="http://localhost:9000/webhook/deforestation",
                secret="demo-secret-amazon-12345678",
                events="alert.created",
            ),
            Webhook(
                project_id=project_ids[1],
                url="http://localhost:9000/webhook/borneo",
                secret="demo-secret-borneo-12345678",
                events="alert.created,alert.updated",
            ),
        ]
        for wh in webhooks:
            db.add(wh)

        await db.commit()
        logger.info("Demo data seeded successfully")

    # Print summary
    print("\n" + "=" * 55)
    print("CarbonSNN Demo Data Seed Complete")
    print("=" * 55)
    print(f"Email:   {DEMO_USER['email']}")
    print(f"Password: {DEMO_USER['password']}")
    print(f"API Key:  {raw_key}")
    print("-" * 55)
    print(f"Projects: {len(DEMO_PROJECTS)}")
    print("  • Amazon Basin Monitoring (Brazil)")
    print("  • Borneo Central Highlands (Indonesia)")
    print("  • Congo Basin Forest Watch (DRC)")
    print(f"Alerts:   ~10 across all projects")
    print(f"Webhooks: 2")
    print("=" * 55)
    print("\nAdd to your .env:")
    print(f"  CARBONSNN_API_KEY={raw_key}")
    print()


def main() -> None:
    """CLI entry point."""
    asyncio.run(seed())


if __name__ == "__main__":
    main()

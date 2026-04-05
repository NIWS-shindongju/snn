"""seed_demo_data.py: Seed the SpikeEO database with demo users and API keys.

Usage:
    python scripts/seed_demo_data.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def seed() -> None:
    """Create demo user and API key in the database."""
    import warnings
    warnings.filterwarnings("ignore", message=".*error reading bcrypt version.*")

    from spikeeo.db.session import init_db, AsyncSessionLocal
    from spikeeo.db.crud import create_user, create_api_key, get_user_by_email
    from spikeeo.api.auth import hash_password

    logger.info("Initialising database schema...")
    await init_db()
    logger.info("Schema ready.")

    async with AsyncSessionLocal() as session:
        existing = await get_user_by_email(session, "demo@spikeeo.ai")
        if existing:
            logger.info("Demo user already exists (id=%s)", existing.id)
        else:
            user = await create_user(
                session,
                email="demo@spikeeo.ai",
                hashed_password=hash_password("spikeeo-demo-2024"),
                is_superuser=True,
            )
            await session.commit()
            logger.info("Created demo user: %s (id=%s)", user.email, user.id)

            raw_key, api_key = await create_api_key(session, user.id, name="Demo Key")
            await session.commit()
            logger.info("Created API key: %s", api_key.name)
            logger.info("Raw API key (save this): %s", raw_key)

    logger.info("Demo data seeded successfully.")


if __name__ == "__main__":
    asyncio.run(seed())

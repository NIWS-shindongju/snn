"""Pytest configuration and shared fixtures for SpikeEO tests."""

import os

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# ── Environment setup ─────────────────────────────────────────
os.environ.setdefault("SPIKEEO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SPIKEEO_APP_DEBUG", "true")
os.environ.setdefault("SPIKEEO_LOG_LEVEL", "WARNING")

# ── DB helpers ────────────────────────────────────────────────

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def async_db():
    """In-memory SQLite async session for tests."""
    from spikeeo.db.models import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()

"""API tests for spikeeo.api.server."""

import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

os.environ["SPIKEEO_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SPIKEEO_APP_DEBUG"] = "true"


# Must create override BEFORE importing app
async def _override_get_db():
    from spikeeo.db.models import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


from spikeeo.api.server import app
from spikeeo.api.deps import get_db

app.dependency_overrides[get_db] = _override_get_db


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """GET /health returns 200 OK."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_root_endpoint(client):
    """GET / returns a message."""
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "message" in resp.json()


@pytest.mark.asyncio
async def test_list_tasks(client):
    """GET /api/v1/tasks returns task list."""
    resp = await client.get("/api/v1/tasks")
    assert resp.status_code == 200
    tasks = resp.json()
    assert isinstance(tasks, list)
    assert len(tasks) >= 5
    names = [t["name"] for t in tasks]
    assert "classification" in names
    assert "change_detection" in names


@pytest.mark.asyncio
async def test_list_models(client):
    """GET /api/v1/tasks/models returns model config."""
    resp = await client.get("/api/v1/tasks/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "backbone_depths" in data
    assert "supported_tasks" in data

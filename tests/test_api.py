"""FastAPI endpoint integration tests.

Tests:
- Health check
- Project CRUD
- Analysis request/status
- Alert listing/acknowledgement
- Webhook CRUD
- Auth rejection for invalid keys
"""

import logging
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from carbonsnn.api.main import app
from carbonsnn.api.auth import hash_password
from carbonsnn.db.crud import create_api_key, create_user
from carbonsnn.db.models import Base
from carbonsnn.db.session import get_db

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Test DB setup
# ──────────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

_test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSessionLocal = async_sessionmaker(bind=_test_engine, expire_on_commit=False)


async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = _override_get_db


# ──────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────

@pytest_asyncio.fixture(autouse=True)
async def setup_db() -> AsyncGenerator[None, None]:
    """Create tables before each test and drop after."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def api_key() -> str:
    """Create a test user and return a raw API key."""
    async with _TestSessionLocal() as db:
        user = await create_user(
            db=db,
            email="test@example.com",
            hashed_password=hash_password("test123"),
        )
        raw_key, _ = await create_api_key(db=db, user_id=user.id, name="Test Key")
        await db.commit()
    return raw_key


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Return an async HTTP client for the test app."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest_asyncio.fixture
async def authed_client(api_key: str) -> AsyncGenerator[AsyncClient, None]:
    """Return an authenticated client with the test API key."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": api_key},
    ) as c:
        yield c


# ──────────────────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────────────────

class TestHealthCheck:
    """Tests for /health endpoint."""

    async def test_health_returns_ok(self, client: AsyncClient) -> None:
        """Health endpoint should return 200 with status=ok."""
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data

    async def test_root_returns_200(self, client: AsyncClient) -> None:
        """Root endpoint should return 200."""
        resp = await client.get("/")
        assert resp.status_code == 200


# ──────────────────────────────────────────────────────────
# Authentication
# ──────────────────────────────────────────────────────────

class TestAuthentication:
    """Tests for API key authentication."""

    async def test_missing_key_returns_401(self, client: AsyncClient) -> None:
        """Requests without X-API-Key should return 401."""
        resp = await client.get("/api/v1/projects")
        assert resp.status_code == 401

    async def test_invalid_key_returns_401(self, client: AsyncClient) -> None:
        """Requests with an invalid key should return 401."""
        resp = await client.get(
            "/api/v1/projects", headers={"X-API-Key": "csk_invalid_key_xyz"}
        )
        assert resp.status_code == 401

    async def test_valid_key_returns_200(self, authed_client: AsyncClient) -> None:
        """Requests with a valid key should succeed."""
        resp = await authed_client.get("/api/v1/projects")
        assert resp.status_code == 200


# ──────────────────────────────────────────────────────────
# Projects CRUD
# ──────────────────────────────────────────────────────────

VALID_PROJECT = {
    "name": "Test Amazon Project",
    "country": "Brazil",
    "bbox": {"west": -60.0, "south": -5.0, "east": -50.0, "north": 0.0},
    "description": "Integration test project",
}


class TestProjectsCRUD:
    """Tests for project endpoints."""

    async def test_create_project(self, authed_client: AsyncClient) -> None:
        """POST /projects should return 201 with project data."""
        resp = await authed_client.post("/api/v1/projects", json=VALID_PROJECT)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == VALID_PROJECT["name"]
        assert data["country"] == VALID_PROJECT["country"]
        assert "id" in data

    async def test_list_projects(self, authed_client: AsyncClient) -> None:
        """GET /projects should return a list."""
        await authed_client.post("/api/v1/projects", json=VALID_PROJECT)
        resp = await authed_client.get("/api/v1/projects")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    async def test_get_project(self, authed_client: AsyncClient) -> None:
        """GET /projects/{id} should return the specific project."""
        create_resp = await authed_client.post("/api/v1/projects", json=VALID_PROJECT)
        project_id = create_resp.json()["id"]
        resp = await authed_client.get(f"/api/v1/projects/{project_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == project_id

    async def test_get_nonexistent_project_returns_404(
        self, authed_client: AsyncClient
    ) -> None:
        """GET /projects/{nonexistent_id} should return 404."""
        resp = await authed_client.get("/api/v1/projects/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    async def test_delete_project(self, authed_client: AsyncClient) -> None:
        """DELETE /projects/{id} should return 204."""
        create_resp = await authed_client.post("/api/v1/projects", json=VALID_PROJECT)
        project_id = create_resp.json()["id"]
        del_resp = await authed_client.delete(f"/api/v1/projects/{project_id}")
        assert del_resp.status_code == 204

    async def test_invalid_bbox_returns_422(self, authed_client: AsyncClient) -> None:
        """BBox with east <= west should fail validation."""
        bad_project = dict(VALID_PROJECT)
        bad_project["bbox"] = {"west": -40.0, "south": -5.0, "east": -50.0, "north": 0.0}
        resp = await authed_client.post("/api/v1/projects", json=bad_project)
        assert resp.status_code == 422


# ──────────────────────────────────────────────────────────
# Analysis
# ──────────────────────────────────────────────────────────

class TestAnalysis:
    """Tests for analysis request endpoints."""

    async def test_request_analysis(self, authed_client: AsyncClient) -> None:
        """POST /analyses should return 202 with pending status."""
        create_resp = await authed_client.post("/api/v1/projects", json=VALID_PROJECT)
        project_id = create_resp.json()["id"]

        resp = await authed_client.post(
            "/api/v1/analyses", json={"project_id": project_id}
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] in ("pending", "running", "completed")
        assert data["project_id"] == project_id

    async def test_list_analyses(self, authed_client: AsyncClient) -> None:
        """GET /analyses/project/{id} should return a list."""
        create_resp = await authed_client.post("/api/v1/projects", json=VALID_PROJECT)
        project_id = create_resp.json()["id"]
        await authed_client.post("/api/v1/analyses", json={"project_id": project_id})

        resp = await authed_client.get(f"/api/v1/analyses/project/{project_id}")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ──────────────────────────────────────────────────────────
# Alerts
# ──────────────────────────────────────────────────────────

class TestAlerts:
    """Tests for alert endpoints."""

    async def test_list_alerts_empty(self, authed_client: AsyncClient) -> None:
        """Listing alerts for a new user should return empty list."""
        resp = await authed_client.get("/api/v1/alerts")
        assert resp.status_code == 200
        assert resp.json() == []

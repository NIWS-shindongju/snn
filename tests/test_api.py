"""TraceCheck API integration tests.

Run: cd /home/work/.openclaw/workspace/snn && .venv/bin/python -m pytest tests/ -v
"""
import pytest
import httpx
import asyncio
import os
import sys

BASE_URL = os.getenv("TRACECHECK_TEST_URL", "http://localhost:8000")
API = f"{BASE_URL}/api/v1"

DEMO_EMAIL = "demo@tracecheck.io"
DEMO_PASSWORD = "TraceCheck2024!"


@pytest.fixture(scope="module")
def token():
    """Get auth token for demo user."""
    resp = httpx.post(f"{API}/auth/token", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    assert "access_token" in data
    return data["access_token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


class TestAuth:
    """Authentication endpoint tests."""

    def test_login_success(self):
        resp = httpx.post(f"{API}/auth/token", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_wrong_password(self):
        resp = httpx.post(f"{API}/auth/token", json={"email": DEMO_EMAIL, "password": "wrong"})
        assert resp.status_code == 401

    def test_login_nonexistent_user(self):
        resp = httpx.post(f"{API}/auth/token", json={"email": "nobody@test.com", "password": "test"})
        assert resp.status_code == 401

    def test_register_new_user(self):
        import uuid
        email = f"test_{uuid.uuid4().hex[:8]}@test.io"
        resp = httpx.post(f"{API}/auth/register", json={
            "email": email, "password": "TestPass123!", "org_name": "TestOrg"
        })
        assert resp.status_code in (200, 201), f"Register failed: {resp.text}"

    def test_me_unauthorized(self):
        resp = httpx.get(f"{API}/auth/me")
        assert resp.status_code in (401, 403)

    def test_me_authorized(self, headers):
        resp = httpx.get(f"{API}/auth/me", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == DEMO_EMAIL


class TestProjects:
    """Project CRUD tests."""

    def test_list_projects(self, headers):
        resp = httpx.get(f"{API}/projects", headers=headers)
        assert resp.status_code == 200
        projects = resp.json()
        assert isinstance(projects, list)
        assert len(projects) >= 2  # demo data has 2+ projects

    def test_create_project(self, headers):
        resp = httpx.post(f"{API}/projects", headers=headers, json={
            "name": "Test Project E2E",
            "description": "Automated test project"
        })
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["name"] == "Test Project E2E"
        assert "id" in data
        return data["id"]

    def test_get_project(self, headers):
        # Get first project from list
        projects = httpx.get(f"{API}/projects", headers=headers).json()
        pid = projects[0]["id"]
        resp = httpx.get(f"{API}/projects/{pid}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == pid


class TestPlots:
    """Plot upload and listing tests."""

    def test_list_plots(self, headers):
        projects = httpx.get(f"{API}/projects", headers=headers).json()
        # Find a project with plots (skip empty ones)
        pid = None
        for p in projects:
            if p.get("plot_count", 0) > 0:
                pid = p["id"]
                break
        if not pid:
            pid = projects[0]["id"]
        resp = httpx.get(f"{API}/projects/{pid}/plots", headers=headers)
        assert resp.status_code == 200
        plots = resp.json()
        assert isinstance(plots, list)

    def test_upload_csv(self, headers):
        import io
        projects = httpx.get(f"{API}/projects", headers=headers).json()
        # Find a project or create one
        pid = projects[0]["id"]
        csv_content = "ref,latitude,longitude,area_ha,supplier\nTST-001,-1.5,110.5,3.0,TestSupplier\n"
        files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        resp = httpx.post(f"{API}/projects/{pid}/plots/upload", headers=headers, files=files)
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["created_count"] >= 1


class TestAnalysis:
    """Analysis execution and results tests."""

    def test_run_analysis(self, headers):
        projects = httpx.get(f"{API}/projects", headers=headers).json()
        pid = projects[0]["id"]
        resp = httpx.post(f"{API}/projects/{pid}/analyze", headers=headers)
        assert resp.status_code in (200, 201, 202)
        data = resp.json()
        assert "id" in data  # job ID

    def test_list_jobs(self, headers):
        projects = httpx.get(f"{API}/projects", headers=headers).json()
        pid = projects[0]["id"]
        resp = httpx.get(f"{API}/projects/{pid}/jobs", headers=headers)
        assert resp.status_code == 200
        jobs = resp.json()
        assert isinstance(jobs, list)
        assert len(jobs) > 0

    def test_job_summary(self, headers):
        projects = httpx.get(f"{API}/projects", headers=headers).json()
        pid = projects[0]["id"]
        jobs = httpx.get(f"{API}/projects/{pid}/jobs", headers=headers).json()
        done_jobs = [j for j in jobs if j["status"] in ("done", "completed")]
        assert len(done_jobs) > 0, "No completed jobs found"
        jid = done_jobs[0]["id"]
        resp = httpx.get(f"{API}/jobs/{jid}/results/summary", headers=headers)
        assert resp.status_code == 200
        summary = resp.json()
        assert "high" in summary
        assert "review" in summary
        assert "low" in summary
        assert summary["total"] > 0

    def test_job_results(self, headers):
        projects = httpx.get(f"{API}/projects", headers=headers).json()
        pid = projects[0]["id"]
        jobs = httpx.get(f"{API}/projects/{pid}/jobs", headers=headers).json()
        done_jobs = [j for j in jobs if j["status"] in ("done", "completed")]
        jid = done_jobs[0]["id"]
        resp = httpx.get(f"{API}/jobs/{jid}/results", headers=headers)
        assert resp.status_code == 200
        results = resp.json()
        assert isinstance(results, list)
        assert len(results) > 0
        # Each result should have risk_level
        for r in results:
            assert r["risk_level"] in ("high", "review", "low")


class TestReports:
    """Report generation and download tests."""

    def test_generate_pdf_report(self, headers):
        projects = httpx.get(f"{API}/projects", headers=headers).json()
        pid = projects[0]["id"]
        jobs = httpx.get(f"{API}/projects/{pid}/jobs", headers=headers).json()
        done_jobs = [j for j in jobs if j["status"] in ("done", "completed")]
        jid = done_jobs[0]["id"]
        resp = httpx.post(f"{API}/jobs/{jid}/reports", headers=headers, json={"format": "pdf"})
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert "id" in data
        assert data["format"] == "pdf"

    def test_generate_json_report(self, headers):
        projects = httpx.get(f"{API}/projects", headers=headers).json()
        pid = projects[0]["id"]
        jobs = httpx.get(f"{API}/projects/{pid}/jobs", headers=headers).json()
        done_jobs = [j for j in jobs if j["status"] in ("done", "completed")]
        jid = done_jobs[0]["id"]
        resp = httpx.post(f"{API}/jobs/{jid}/reports", headers=headers, json={"format": "json"})
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["format"] == "json"

    def test_list_reports(self, headers):
        projects = httpx.get(f"{API}/projects", headers=headers).json()
        pid = projects[0]["id"]
        jobs = httpx.get(f"{API}/projects/{pid}/jobs", headers=headers).json()
        done_jobs = [j for j in jobs if j["status"] in ("done", "completed")]
        jid = done_jobs[0]["id"]
        resp = httpx.get(f"{API}/jobs/{jid}/reports", headers=headers)
        assert resp.status_code == 200
        reports = resp.json()
        assert isinstance(reports, list)


class TestHealth:
    """System health checks."""

    def test_health_endpoint(self):
        resp = httpx.get(f"{BASE_URL}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "features" in data

    def test_openapi_spec(self):
        resp = httpx.get(f"{BASE_URL}/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()
        assert "paths" in spec
        assert "/api/v1/auth/token" in spec["paths"]

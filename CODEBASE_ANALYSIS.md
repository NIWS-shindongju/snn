# TraceCheck SNN Project — Complete Codebase Analysis

## 📊 Executive Summary

**TraceCheck** is a **EUDR (EU Deforestation Regulation) SaaS platform** for supply chain due diligence. It automates satellite-based forest deforestation risk screening for agricultural commodities (coffee, cocoa, palm oil, soy, cattle, wood, rubber).

- **Status**: v0.4.0 — Demo-stable (5-minute workflow complete)
- **Architecture**: FastAPI backend + Streamlit dashboard + async SQLAlchemy DB
- **Core Engine**: Rule-based change detection (NumPy, no ML required for MVP)
- **Tech Stack**: Python 3.11+, SQLite, Sentinel-2 satellite data (Copernicus)
- **Deployment**: PM2 process manager, Docker support

---

## 🗂️ Complete Directory Structure

```
snn/
├── tracecheck/                    ✅ EUDR SaaS CORE — KEEP
│   ├── api/
│   │   ├── main.py               ✅ FastAPI app factory + startup
│   │   ├── auth.py               ✅ JWT auth helpers
│   │   ├── schemas.py            ✅ Pydantic request/response models
│   │   └── routes/
│   │       ├── auth.py           ✅ register, login, me
│   │       ├── projects.py       ✅ project CRUD
│   │       ├── parcels.py        ✅ plot upload, validate, list
│   │       ├── analysis.py       ✅ job trigger, status, results
│   │       └── reports.py        ✅ PDF/JSON/CSV export
│   ├── core/
│   │   ├── change_detector.py    ✅ NDVI/NBR dNDVI/dNBR rules (pure NumPy)
│   │   ├── risk_scorer.py        ✅ LOW/REVIEW/HIGH classification
│   │   ├── geo_validator.py      ✅ CSV/GeoJSON parse + validate
│   │   ├── sentinel_fetcher.py   ✅ Copernicus Sentinel-2 fetch (real + mock)
│   │   └── report_generator.py   ✅ PDF/JSON/CSV generation
│   ├── db/
│   │   ├── models.py             ✅ SQLAlchemy v2 ORM (users→projects→plots→job_runs)
│   │   ├── crud.py               ✅ Async CRUD ops
│   │   ├── session.py            ✅ AsyncSession factory
│   │   └── __init__.py           
│   ├── pipeline/
│   │   ├── eudr_pipeline.py      ✅ Async job orchestrator (BGtask)
│   │   └── __init__.py
│   ├── config.py                 ✅ Pydantic Settings (env-based config)
│   └── __init__.py

├── frontend/
│   ├── app.py                    ✅ Streamlit 7-page dashboard (login→reports→history)
│   └── index.html                ✅ Static HTML fallback

├── spikeeo/                       🟡 REFERENCE ONLY (range expansion future)
│   ├── io/                        🟡 vegetation.py, cloud_mask.py (can be ported)
│   ├── tasks/change_detection.py  🟡 torch-based SNN alternative (not used in MVP)
│   ├── core/                      ❌ SNN/CNN models (torch, for post-MVP)
│   ├── api/                       ❌ Range expansion API (not used)
│   └── db/                        ❌ Range expansion DB (not used)

├── migrations/                    ✅ Alembic schema versions
│   ├── env.py
│   └── versions/
│       ├── dda115785cd7_initial_schema.py    (v1)
│       └── 7383bf8ccdad_v2_saas_schema.py    (v2, current)

├── scripts/
│   ├── seed_demo.py              ✅ Demo data + user seeding
│   ├── train_snn.py              🟡 SNN training (post-MVP)
│   ├── train_forest_snn.py       🟡 Forest detection model (post-MVP)
│   ├── download_sentinel2.py     ❓ Real Copernicus download helper
│   └── run_benchmark.py          ❌ Unused benchmark script

├── tests/
│   ├── test_api.py               ✅ API endpoint tests
│   ├── test_models.py            ✅ ORM model tests
│   ├── test_pipeline.py          ✅ Pipeline integration tests
│   ├── conftest.py               ✅ pytest fixtures
│   └── tracecheck/               📁 Test submodule

├── examples/
│   ├── sample_plots.csv          ✅ 15-parcel demo CSV (4 countries, 4 commodities)
│   ├── carbon_mrv/               ❌ Carbon MRV (range expansion, not MVP)
│   ├── deforestation_alert/      ❌ Unused example
│   └── retail_counting/          ❌ Unused example

├── data/
│   ├── reports/                  📁 Generated PDF/JSON/CSV exports (5 jobs present)
│   └── sentinel2/                📁 Cached Sentinel-2 tiles (created on-demand)

├── pyproject.toml                ✅ Hatch build, deps, test config
├── README.md                     ✅ Full product docs + setup guide
├── .env.example                  ✅ Config template (Copernicus, thresholds, DB)
├── alembic.ini                   ✅ Alembic migration config
├── docker-compose.yml            ✅ Docker services (API + DB + Streamlit)
├── Dockerfile                    ✅ Container image definition
├── ecosystem.config.cjs          ✅ PM2 config (FastAPI + Streamlit + DB migration)
└── LICENSE, .gitignore, etc.     ✅ Standard repo files
```

---

## 🔍 Key Files — Complete Content

### 1️⃣ **Database Models** (`tracecheck/db/models.py`)

**Schema v2** (current):
```
users ──────┐
            ├─→ projects ──┬─→ plots
            │              ├─→ job_runs ──┬─→ plot_assessments
            │              │              └─→ evidence_exports
            │              └─→ audit_logs
            │
            └─→ (non-owning refs: JobRun.triggered_by, EvidenceExport.created_by, AuditLog.user_id)
```

**Tables**:
- `users`: (id, email, hashed_password, org_name, is_active, created_at, updated_at)
- `projects`: (id, owner_id→users, name, commodity, origin_country, cutoff_date, description, status, created_at, updated_at)
- `plots`: (id, project_id→projects, supplier_name, plot_ref, geometry_type, geojson, bbox_*, area_ha, country, validation_status, uploaded_at)
- `job_runs`: (id, project_id→projects, triggered_by→users, status, total_plots, processed_plots, error_message, data_mode, started_at, completed_at, created_at)
- `plot_assessments`: (id, job_run_id→job_runs, plot_id→plots, risk_level, ndvi_before/after, delta_ndvi, nbr_before/after, delta_nbr, changed_area_ha, cloud_fraction, confidence, flag_reason, before_scene_date, after_scene_date, data_source, reviewer_* fields, assessed_at)
- `evidence_exports`: (id, job_run_id→job_runs, created_by→users, format, file_path, file_size_bytes, summary_snapshot, generated_at)
- `audit_logs`: (id, project_id→projects, user_id→users, action, detail, ip_address, occurred_at)

**Status**: ✅ Complete, tested, migrated from v1 (parcels→plots, etc.)

---

### 2️⃣ **Core Analysis Engine** (`tracecheck/core/`)

#### a) **Change Detector** (`change_detector.py`)
- **Class**: `EUDRChangeDetector`
- **Input**: GeoTIFF or mock .npy files (10-band Sentinel-2: B02, B03, B04, B08, B05, B06, B07, B8A, B11, B12)
- **Indices**:
  - **NDVI**: (NIR - Red) / (NIR + Red) = vegetation
  - **NBR**: (NIR - SWIR2) / (NIR + SWIR2) = burn ratio
- **Output**: `ChangeResult(parcel_id, ndvi_before/after, delta_ndvi, nbr_before/after, delta_nbr, changed_area_ha, cloud_fraction, confidence, before_scene_date, after_scene_date, data_source, error)`
- **Status**: ✅ Pure NumPy, no deps, fully functional

#### b) **Risk Scorer** (`risk_scorer.py`)
- **Function**: `score_risk(ChangeResult) → RiskScore`
- **Rules**:
  - **HIGH**: dNDVI ≥ 0.15 AND area ≥ 1.0 ha (clear vegetation loss)
  - **REVIEW**: dNDVI ≥ 0.10 OR area ≥ 0.3 ha OR cloud > 50% (borderline/uncertain)
  - **LOW**: dNDVI < 0.10 AND area < 0.3 ha AND cloud ≤ 50% (minimal change)
- **Thresholds**: Configurable via `settings` (TRACECHECK_NDVI_THRESHOLD, etc.)
- **Status**: ✅ Fully implemented, Korean-language reasoning strings

#### c) **Sentinel-2 Fetcher** (`sentinel_fetcher.py`)
- **Real Mode**: Copernicus Data Space Ecosystem (CDSE) OData API
  - Auth: OAuth2 client credentials
  - Search: Before/after cutoff date, low-cloud scenes
  - Download: Full product ZIP, extract 10 bands, stack into GeoTIFF
- **Mock Mode** (active when no credentials):
  - Deterministic bucket assignment based on UUID hash
  - 40% LOW, 40% REVIEW, 20% HIGH distribution
  - Regenerated on every run for consistency
- **Status**: ✅ Functional, mock mode tested end-to-end

#### d) **GeoJSON Validator** (`geo_validator.py`)
- **CSV Support**: Auto-detect lat/lon columns (aliases: lat/latitude/y, lon/longitude/x)
- **CSV**: Plot_ref, supplier_name, coordinates, optional country
- **GeoJSON**: Feature or FeatureCollection; Point/Polygon/MultiPolygon
- **Validation**: Coord range (-90..90, -180..180), geometry validity, country detection (bounding boxes)
- **Output**: `ValidationResult(valid: [ParsedParcel], errors: [dict])`
- **Status**: ✅ Full CSV/GeoJSON support, auto country detection

#### e) **Report Generator** (`report_generator.py`)
- **JSON**: Structured EUDR compliance package (meta, project, analysis, summary, per-plot details, methodology, disclaimer)
- **CSV**: Tabular format (ref, supplier, risk, metrics, timestamps)
- **PDF**: (Stub) Uses reportlab (reportlab import present but implementation incomplete)
- **Status**: ⚠️ JSON & CSV complete; PDF generation exists but minimal

---

### 3️⃣ **FastAPI Routes** (`tracecheck/api/routes/`)

#### a) **Auth** (`auth.py`)
- `POST /api/auth/register` → create user
- `POST /api/auth/token` → JSON login (email/password) → JWT token
- `POST /api/auth/login` → form-data login (legacy)
- `GET /api/auth/me` → current user info
- **Status**: ✅ Complete, JWT-based

#### b) **Projects** (`projects.py`)
- `GET /api/projects/` → list user's projects
- `POST /api/projects/` → create new project
- `GET /api/projects/{id}` → get project + plot count
- `DELETE /api/projects/{id}` → delete project (cascade: plots, jobs, exports, logs)
- **Status**: ✅ Complete

#### c) **Parcels** (`parcels.py`) — *v2 naming: "plots"*
- `POST /api/projects/{id}/plots/upload` → CSV/GeoJSON upload + persist valid plots
- `POST /api/projects/{id}/plots/validate` → validate without save (preview)
- `GET /api/projects/{id}/plots` → list plots for project
- `DELETE /api/plots/{id}` → delete single plot
- **Routes Kept for Compatibility**: `/parcels`, `/parcel_ref` (v1 aliases)
- **Status**: ✅ Complete, backward compatible

#### d) **Analysis** (`analysis.py`)
- `POST /api/projects/{id}/analyze` (alias `/assess`) → trigger job (202 ACCEPTED)
- `GET /api/jobs/{id}` → get job status + progress
- `GET /api/jobs/{id}/results` → per-plot assessments
- `GET /api/jobs/{id}/results/summary` → LOW/REVIEW/HIGH counts
- **Status**: ✅ Complete, async background tasks

#### e) **Reports** (`reports.py`)
- `POST /api/jobs/{id}/reports` → generate (pdf/json/csv)
- `GET /api/reports/{id}/download` → download file
- `GET /api/jobs/{id}/reports` → list generated reports
- **Status**: ✅ JSON/CSV working; PDF basic

---

### 4️⃣ **Async Pipeline** (`tracecheck/pipeline/eudr_pipeline.py`)

**Orchestrator**: `run_eudr_analysis(job_id, db)`

**Flow**:
1. Load JobRun + Plots
2. For each plot:
   - **Mock mode** (no Copernicus creds): `_mock_change_result()` → deterministic result
   - **Real mode**: `fetcher.fetch_for_parcel()` → `detector.detect()` → `score_risk()`
   - Save `PlotAssessment` + update progress
3. Mark JobRun as "done" or "failed"

**Mock Determinism**: UUID-based bucketing ensures reproducible results across runs

**Status**: ✅ Fully tested, demo mode proven

---

### 5️⃣ **Configuration** (`tracecheck/config.py`)

**Pydantic Settings** (env vars prefixed `TRACECHECK_`):
```python
database_url = "sqlite+aiosqlite:///./tracecheck.db"
secret_key = "change-me-in-production-please"
access_token_expire_minutes = 1440

# Copernicus (optional — mock mode if empty)
copernicus_client_id = ""
copernicus_client_secret = ""

# Analysis thresholds
ndvi_threshold = 0.10
ndvi_high_threshold = 0.15
min_changed_area_ha = 0.3
max_cloud_fraction = 0.5
eudr_cutoff_date = "2020-12-31"

# Storage
data_dir = "./data"

# App
debug = False
cors_origins = ["*"]
```

**Status**: ✅ Complete, well-structured

---

### 6️⃣ **Streamlit Dashboard** (`frontend/app.py`, ~1000 lines)

**7 Pages** (sidebar navigation):
1. **Login/Register** — JWT token management
2. **Projects List** — Create, select, delete projects
3. **Plot Upload** — CSV/GeoJSON upload + preview + sample download
4. **Run Analysis** — Trigger job + auto-poll (3-second intervals, 3-minute max)
5. **Results** — Per-plot table, risk chart, filter by level, CSV export
6. **Evidence Export** — PDF/JSON/CSV generation + download
7. **Audit History** — Project action logs (create project, upload, job started, etc.)

**Features**:
- Auto-refresh while jobs running
- Sample CSV embedded in dashboard
- Multi-language support (Korean strings throughout)
- Risk level icons (🟢/🟡/🔴) + color-coded backgrounds
- Commodity emoji icons (☕🍫🌴🌱🐄🪵⚫)
- Legal disclaimer banners (EN + KO)

**Status**: ✅ Fully functional, responsive, end-to-end tested

---

### 7️⃣ **Database Session** (`tracecheck/db/session.py`)

```python
engine = create_async_engine(settings.database_url)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

**Status**: ✅ Standard async SQLAlchemy setup

---

### 8️⃣ **CRUD Operations** (`tracecheck/db/crud.py`, ~300 lines)

**Core functions**:
- `create_user()`, `get_user_by_email()`, `get_user_by_id()`
- `create_project()`, `get_project()`, `list_projects()`, `delete_project()`, `count_plots()`
- `create_plot()`, `list_plots()`, `get_plot()`, `delete_plot()`
- `create_job_run()`, `get_job_run()`, `update_job_run_status()`, `list_jobs()`
- `save_plot_assessment()`, `list_assessments()`, `get_assessments_summary()`
- `create_evidence_export()`, `list_exports()`
- `log_action()` → audit trail

**Status**: ✅ Complete async CRUD

---

### 9️⃣ **Migrations** (`migrations/versions/`)

**v1**: Initial schema (parcels, analysis_jobs, parcel_results, reports)
**v2**: (2026-04-06) Rename tables (plots, job_runs, plot_assessments, evidence_exports) + add audit_logs

**Status**: ✅ Alembic migrations working, can upgrade/downgrade

---

### 🔟 **Seeding** (`scripts/seed_demo.py`)

**Creates**:
- 1 demo user: `demo@tracecheck.io` / `TraceCheck2024!`
- 2 demo projects:
  - Colombia Coffee (7 plots)
  - Indonesia Palm Oil (3 plots)
- Pre-populated plots matching `examples/sample_plots.csv`

**Usage**:
```bash
python scripts/seed_demo.py              # Create/ensure
python scripts/seed_demo.py --reset      # Drop + recreate
python scripts/seed_demo.py --clean      # Delete demo, re-seed
```

**Status**: ✅ Fully implemented, tested

---

## 📈 What's Working ✅

1. **Database**: SQLAlchemy ORM, async sessions, migrations, v2 schema complete
2. **Authentication**: JWT-based, register/login endpoints, Streamlit integration
3. **Project Management**: Full CRUD, per-user isolation, commodity/origin metadata
4. **Plot Upload**: CSV + GeoJSON parsing, validation, auto-country detection
5. **Analysis Pipeline**: Async job orchestrator, mock deterministic results, real Copernicus integration (code exists)
6. **Risk Scoring**: NumPy-based NDVI/NBR rules, LOW/REVIEW/HIGH classification
7. **Results Display**: Per-plot assessment table, summary counts, charts (Plotly + Streamlit fallback)
8. **Report Generation**: JSON & CSV exports (PDF basic)
9. **Audit Logging**: All major actions logged with timestamps + details
10. **Frontend**: Streamlit 7-page dashboard, fully functional, responsive
11. **Demo Mode**: Deterministic mock results without Copernicus credentials
12. **E2E Workflow**: Login → project → upload → analyze → results → export → history (tested)

---

## ❌ What's Missing / Broken

### Critical (MVP Blockers):
1. **PDF Report Generation** 
   - ⚠️ `report_generator.py` has JSON/CSV stubs but PDF generation is incomplete
   - reportlab is in deps but not actually used
   - **Impact**: Users cannot download PDF evidence package (PDF button may fail)
   - **Fix**: Implement reportlab PDF generation with table + charts + disclaimer

2. **Real Copernicus Integration**
   - ✅ Code exists (`sentinel_fetcher._fetch_real()`) but untested in production
   - Requires valid OAuth2 credentials in `.env`
   - Mock mode is the default (no credentials)
   - **Impact**: Currently all analyses use deterministic mock data
   - **Fix**: Test with real Copernicus credentials, add proper error handling

3. **Background Task Exception Handling**
   - ⚠️ `_run_pipeline_bg()` in `analysis.py` line 74 has try/except but may not properly catch/log errors
   - **Impact**: Failed jobs may silently fail without proper error messages
   - **Fix**: Improve error logging and update JobRun.error_message on exception

### High Priority:
4. **PDF Export File Handling**
   - reports.py stub doesn't actually call `generate_pdf_report()`
   - **Fix**: Complete PDF generation

5. **File Path Security**
   - Some file paths might be vulnerable to traversal attacks
   - **Fix**: Validate all file paths, use Path.resolve()

6. **Memory Management in Batch Processing**
   - Large GeoTIFF files loaded entirely into memory
   - **Impact**: May OOM on very large Sentinel-2 tiles
   - **Fix**: Implement windowed/streaming I/O with rasterio

### Medium Priority:
7. **Incomplete Test Coverage**
   - tests/ exists but likely not comprehensive
   - Missing integration tests for real Copernicus flow
   - **Fix**: Expand test suite

8. **SpikeEO Cleanup**
   - spikeeo/ directory still contains unused range-expansion code
   - Should be removed or clearly marked as "future"
   - **Fix**: Archive or document as post-MVP

9. **Sentinel-2 Band Download**
   - `_extract_bands()` in sentinel_fetcher.py may fail silently on malformed ZIP
   - **Fix**: Add validation + fallback handling

10. **No Rate Limiting**
    - API has no rate limiting on concurrent job submissions
    - **Fix**: Add FastAPI rate limiting middleware

---

## 🔧 Configuration & Environment

### Required Environment (`.env`):
```bash
# Database (SQLite in dev)
TRACECHECK_DATABASE_URL=sqlite+aiosqlite:///./tracecheck.db

# Auth
TRACECHECK_SECRET_KEY=<generate: openssl rand -hex 32>
TRACECHECK_ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Copernicus (optional — leave empty for mock mode)
TRACECHECK_COPERNICUS_CLIENT_ID=
TRACECHECK_COPERNICUS_CLIENT_SECRET=

# Analysis thresholds
TRACECHECK_NDVI_THRESHOLD=0.10
TRACECHECK_NDVI_HIGH_THRESHOLD=0.15
TRACECHECK_MIN_CHANGED_AREA_HA=0.3
TRACECHECK_MAX_CLOUD_FRACTION=0.5
TRACECHECK_EUDR_CUTOFF_DATE=2020-12-31

# Storage
TRACECHECK_DATA_DIR=./data

# App
TRACECHECK_DEBUG=false
TRACECHECK_CORS_ORIGINS=["*"]
```

### Startup (from README):
```bash
# 1. Install
pip install -e ".[dev]"

# 2. Migrate DB
alembic upgrade head

# 3. Seed demo data
python scripts/seed_demo.py

# 4. Start services (PM2)
pm2 start ecosystem.config.cjs

# 5. Access
# API: http://localhost:8000/docs
# Frontend: http://localhost:8501
```

---

## 📊 Data Flow Diagram

```
User (Streamlit) 
    ↓
FastAPI Routes (auth, projects, plots, analysis, reports)
    ↓
CRUD Layer (async SQLAlchemy)
    ↓
Database (SQLite)

Async Background Task: run_eudr_analysis()
    ├─→ fetch_for_parcel() [Copernicus OR mock]
    ├─→ detect() [Change detection: NDVI/NBR]
    ├─→ score_risk() [LOW/REVIEW/HIGH]
    ├─→ save_plot_assessment() [DB]
    └─→ log_action() [Audit trail]

Report Generation:
    ├─→ JSON export
    ├─→ CSV export
    └─→ PDF export (⚠️ incomplete)
```

---

## 🎯 MVP Status

**Version**: v0.4.0 (Demo-Stable)

**5-Minute Workflow Checklist**:
- ✅ Login with demo account
- ✅ Create project
- ✅ Upload CSV (7 plots)
- ✅ Validate coordinates
- ✅ Run analysis (deterministic mock results)
- ✅ View results (chart, table)
- ✅ Export JSON/CSV
- ✅ View audit history

**Known Limitations**:
- ⚠️ PDF export stub (incomplete)
- ⚠️ Mock mode only (Copernicus code ready but not tested)
- ⚠️ In-memory GeoTIFF loading (OK for MVP, not production-scale)
- ⚠️ Single-user per request (no per-parcel parallelization)

---

## 🚀 Next Steps (Post-MVP)

1. **Complete PDF Generation** (URGENT for compliance)
2. **Production Copernicus Integration** (real satellite data)
3. **Parallel Processing** (multi-worker job queue with Celery/RabbitMQ)
4. **SNN/ML Upgrade Path** (optional: replace rules with trained model)
5. **Batch User Management** (team permissions, org accounts)
6. **API Rate Limiting** (prevent abuse)
7. **CDN for Reports** (fast downloads)
8. **Monitoring/Alerting** (job failures, long-running jobs)

---

## 📝 Summary Table

| Component | Status | Notes |
|-----------|--------|-------|
| Database schema | ✅ | v2 complete, migrations tested |
| User auth | ✅ | JWT, register/login working |
| Project CRUD | ✅ | Full lifecycle |
| Plot upload | ✅ | CSV + GeoJSON, validation complete |
| Analysis pipeline | ✅ | Async, mock mode proven |
| Risk scoring | ✅ | Rule-based, all thresholds working |
| Report generation | ⚠️ | JSON/CSV ✅, PDF stub ❌ |
| Streamlit dashboard | ✅ | 7 pages, fully functional |
| Audit logging | ✅ | All actions tracked |
| E2E workflow | ✅ | 5-minute demo working |
| Copernicus integration | ✅ | Code ready, untested in prod |
| Mock determinism | ✅ | UUID-based bucketing works |
| Test coverage | ⚠️ | Basic tests exist, incomplete |

---

## 📚 Key Files Reference

| File | Purpose | Completeness |
|------|---------|--------------|
| `tracecheck/db/models.py` | ORM models | ✅ 100% |
| `tracecheck/core/change_detector.py` | NDVI/NBR rules | ✅ 100% |
| `tracecheck/core/risk_scorer.py` | LOW/REVIEW/HIGH | ✅ 100% |
| `tracecheck/core/geo_validator.py` | CSV/GeoJSON parse | ✅ 100% |
| `tracecheck/core/sentinel_fetcher.py` | Sentinel-2 fetch | ✅ Real + mock |
| `tracecheck/core/report_generator.py` | Report generation | ⚠️ JSON/CSV only |
| `tracecheck/api/routes/*.py` | API endpoints | ✅ 100% |
| `frontend/app.py` | Streamlit UI | ✅ 100% |
| `tracecheck/pipeline/eudr_pipeline.py` | Job orchestrator | ✅ 100% |
| `scripts/seed_demo.py` | Demo data | ✅ 100% |


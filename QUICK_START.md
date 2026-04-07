# TraceCheck — Quick Start & Common Tasks

## 🚀 First-Time Setup

```bash
cd /home/work/.openclaw/workspace/snn/

# 1. Install dependencies
pip install -e ".[dev]"

# 2. Initialize database
alembic upgrade head

# 3. Seed demo data
python scripts/seed_demo.py

# 4. Start services (PM2)
pm2 start ecosystem.config.cjs

# 5. Access
#   API docs:  http://localhost:8000/docs
#   Dashboard: http://localhost:8501
#   Demo login: demo@tracecheck.io / TraceCheck2024!
```

---

## 📝 Common Development Tasks

### **View API Documentation**
```bash
# Automatically generated FastAPI/OpenAPI docs
http://localhost:8000/docs
```

### **Run Tests**
```bash
pytest tests/ -v
pytest tests/test_api.py -k "test_login" -v
pytest tests/test_pipeline.py --cov=tracecheck
```

### **Database Migrations**

```bash
# Show current migration status
alembic current

# Create new migration (after model changes)
alembic revision --autogenerate -m "add new_column to plots"

# Apply migrations
alembic upgrade head

# Rollback to previous
alembic downgrade -1
```

### **Reset Demo Data**
```bash
python scripts/seed_demo.py --reset      # Drop all + recreate
python scripts/seed_demo.py --clean      # Delete demo, re-seed
```

### **Access Database Directly**
```bash
# SQLite CLI
sqlite3 tracecheck.db

# Inside Python
from tracecheck.db.session import AsyncSessionLocal
from tracecheck.db.models import User, Project

# Query (sync code for quick checks)
import asyncio
from tracecheck.db import crud

async def check():
    from tracecheck.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        user = await crud.get_user_by_email(db, "demo@tracecheck.io")
        print(user.email, user.org_name)

asyncio.run(check())
```

### **Stop Services**
```bash
pm2 stop ecosystem.config.cjs
pm2 delete ecosystem.config.cjs  # Remove from PM2
```

### **View Logs**
```bash
pm2 logs                          # All services
pm2 logs tracecheck-api           # API only
pm2 logs tracecheck-frontend      # Streamlit only
pm2 kill                          # Stop daemon
```

---

## 🔍 Debugging Tips

### **Enable Debug Mode**
```bash
# In .env
TRACECHECK_DEBUG=true

# Then restart API
pm2 restart tracecheck-api
```

### **Print SQL Queries**
```python
# In config.py or test
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)
```

### **Test a Single API Endpoint**
```bash
# 1. Get a token
TOKEN=$(curl -X POST http://localhost:8000/api/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@tracecheck.io","password":"TraceCheck2024!"}' \
  | jq -r '.access_token')

# 2. Use token
curl http://localhost:8000/api/projects/ \
  -H "Authorization: Bearer $TOKEN" | jq

# 3. Create project
curl -X POST http://localhost:8000/api/projects/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Project",
    "commodity": "coffee",
    "origin_country": "CO",
    "cutoff_date": "2020-12-31"
  }' | jq
```

### **Simulate Job Analysis Failure**
```python
# In pipeline/eudr_pipeline.py, add:
if plot.id == "SPECIFIC_PLOT_ID":
    raise Exception("Simulated failure for testing")
```

---

## 📊 Code Navigation

### **Entry Points**
- **API**: `tracecheck/api/main.py` → `create_app()`
- **Frontend**: `frontend/app.py` → `main()`
- **Pipeline**: `tracecheck/pipeline/eudr_pipeline.py` → `run_eudr_analysis()`

### **Key Data Flows**

#### **User Registration**
```
frontend/app.py: page_login()
  → requests.post("/api/auth/register")
    → tracecheck/api/routes/auth.py: register()
      → crud.create_user()
        → db.add(User)
          → db.commit()
```

#### **Plot Upload**
```
frontend/app.py: page_upload()
  → st.file_uploader()
    → requests.post("/api/projects/{id}/plots/upload")
      → tracecheck/api/routes/parcels.py: upload_plots()
        → geo_validator.validate_upload()
          → validate_csv() or validate_geojson()
            → [ParsedParcel, ...]
        → crud.create_plot() [per parcel]
          → db.commit()
```

#### **Analysis Job**
```
frontend/app.py: page_analysis()
  → st.button("🚀 분석 시작")
    → requests.post("/api/projects/{id}/analyze")
      → tracecheck/api/routes/analysis.py: trigger_analysis()
        → crud.create_job_run()
        → background_tasks.add_task(_run_pipeline_bg, job_id)
        → return 202 ACCEPTED (immediately)
        
Meanwhile (in background):
  _run_pipeline_bg(job_id)
    → eudr_pipeline.run_eudr_analysis(job_id, db)
      → for plot in plots:
        ├─ sentinel_fetcher.fetch_for_parcel()
        ├─ detector.detect()
        ├─ scorer.score_risk()
        └─ crud.save_plot_assessment()
      → crud.update_job_run_status(done)
```

#### **Report Generation**
```
frontend/app.py: page_reports()
  → st.button("PDF 생성 & 다운로드")
    → requests.post("/api/jobs/{id}/reports", json={"format": "pdf"})
      → tracecheck/api/routes/reports.py: generate_report()
        → report_generator.generate_pdf_report()
        → save to data/reports/{job_id}/
        → crud.create_evidence_export()
      → requests.get("/api/reports/{id}/download")
        → return file content
```

---

## 🔐 Environment Configuration

### **.env Template**
```bash
# Database
TRACECHECK_DATABASE_URL=sqlite+aiosqlite:///./tracecheck.db

# Auth
TRACECHECK_SECRET_KEY=$(openssl rand -hex 32)
TRACECHECK_ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Copernicus (leave empty for mock mode)
TRACECHECK_COPERNICUS_CLIENT_ID=
TRACECHECK_COPERNICUS_CLIENT_SECRET=

# Thresholds (from config.py defaults)
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

### **Generate Secure Secret Key**
```bash
openssl rand -hex 32
# Copy output to TRACECHECK_SECRET_KEY
```

---

## 🧪 Testing Workflow

### **Unit Tests**
```bash
pytest tests/test_models.py -v
pytest tests/test_api.py::test_register_user -v
```

### **Integration Tests**
```bash
pytest tests/test_api.py -v --tb=short
```

### **Pipeline Tests**
```bash
pytest tests/test_pipeline.py -v
```

### **Test with Coverage**
```bash
pytest tests/ --cov=tracecheck --cov-report=html
# Open htmlcov/index.html in browser
```

---

## 📦 Adding Dependencies

### **Add a Package**
```bash
# 1. Edit pyproject.toml
# Add to [project] dependencies or [project.optional-dependencies]

# 2. Reinstall
pip install -e ".[dev]"

# 3. Commit
git add pyproject.toml
git commit -m "feat: add new dependency"
```

---

## 🐛 Troubleshooting

### **"Port 8000 already in use"**
```bash
lsof -i :8000
kill -9 <PID>
# Or use PM2
pm2 kill
```

### **"Database is locked"**
```bash
# SQLite file-lock issue; usually transient
rm -f tracecheck.db
python scripts/seed_demo.py
```

### **"JWT token expired"**
```bash
# Streamlit session state issue; clear browser cache + restart browser
```

### **"Streamlit rerun infinite loop"**
```python
# Use @st.cache_data or session_state wisely
if "key" not in st.session_state:
    st.session_state.key = initial_value
```

### **"Background job stuck in 'running'"**
```bash
# Check PM2 logs
pm2 logs tracecheck-api | grep ERROR

# Restart
pm2 restart tracecheck-api
```

---

## 📚 Further Reading

- **Full Analysis**: See `CODEBASE_ANALYSIS.md`
- **Architecture**: See `ARCHITECTURE_DECISIONS.md`
- **README**: See `README.md` (product docs)
- **API Docs**: http://localhost:8000/docs (when running)

---

## ✅ Pre-Commit Checklist

Before pushing code:

- [ ] Run tests: `pytest tests/ -v`
- [ ] Format: `black tracecheck/`
- [ ] Lint: `ruff check tracecheck/`
- [ ] Type check: `mypy tracecheck/`
- [ ] Docs updated (if API changed)
- [ ] Database migration created (if models changed)
- [ ] Git commit message clear and descriptive

```bash
# All checks in one go
black tracecheck/ && ruff check tracecheck/ && mypy tracecheck/ && pytest tests/
```


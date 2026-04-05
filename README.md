# CarbonSNN

**Satellite-based Deforestation Detection & Carbon MRV SaaS**
powered by Spiking Neural Networks (SNN)

---

## Overview

CarbonSNN monitors tropical and temperate forests using Sentinel-2 satellite imagery and energy-efficient Spiking Neural Networks. It detects deforestation events, estimates carbon stock changes, and generates Verra VCS-compatible MRV reports — all accessible via a REST API and Streamlit dashboard.

### Key Features

| Feature | Description |
|---|---|
| **ForestSNN** | 2-class (Forest / Non-Forest) SNN — 10-band Sentinel-2 input |
| **CarbonSNN** | 11-class IPCC land cover SNN + vegetation density regression |
| **HybridClassifier** | SNN first pass → ResNet-18 CNN for uncertain tiles only |
| **Change Detector** | dNDVI/dNBR rule-based + Siamese SNN (5 change types) |
| **Carbon MRV** | IPCC Tier-2 AGB+BGB estimation, Verra VCS JSON reports |
| **Weekly Scan** | Celery beat — automated Monday 06:00 UTC scans |
| **REST API** | FastAPI with API-key auth, rate limiting, webhook delivery |
| **Dashboard** | Streamlit 5-page UI with Folium maps + Plotly charts |

---

## Quick Start

### 1. Clone & Configure

```bash
git clone https://github.com/your-org/carbonsnn.git
cd carbonsnn
cp .env.example .env
# Edit .env: set APP_SECRET_KEY and Copernicus credentials
```

### 2. Install (local development)

```bash
pip install -e ".[dev]"
```

### 3. Seed demo data & run

```bash
# Initialise DB + create demo user/projects
python scripts/seed_demo_data.py

# Start API server
uvicorn carbonsnn.api.main:app --reload

# Start dashboard (separate terminal)
streamlit run carbonsnn/dashboard/app.py
```

Open:
- API docs: http://localhost:8000/docs
- Dashboard: http://localhost:8501

### 4. Docker Compose (production)

```bash
docker compose up -d
```

Services exposed:
- `localhost:8000` — FastAPI
- `localhost:8501` — Streamlit
- `localhost:6379` — Redis

---

## Architecture

```
carbonsnn/
├── carbonsnn/
│   ├── config.py              # Pydantic Settings
│   ├── models/
│   │   ├── forest_snn.py      # Binary SNN (Forest / Non-Forest)
│   │   ├── carbon_snn.py      # 11-class SNN + vegetation regression
│   │   ├── change_detector.py # Rule-based + Siamese SNN
│   │   └── hybrid.py          # SNN→CNN fallback routing
│   ├── data/
│   │   ├── sentinel2.py       # Copernicus OAuth2 download
│   │   ├── cloud_mask.py      # SCL band cloud masking
│   │   ├── preprocessor.py    # Tiling, normalisation, band stacking
│   │   └── vegetation.py      # NDVI / EVI / NBR / NDMI / LAI
│   ├── analysis/
│   │   ├── deforestation.py   # Full detection pipeline → GeoJSON alerts
│   │   ├── carbon_stock.py    # IPCC Tier-2 AGB + BGB estimation
│   │   └── mrv_report.py      # Verra VCS JSON report generation
│   ├── api/                   # FastAPI (auth, routes, schemas)
│   ├── dashboard/app.py       # Streamlit 5-page dashboard
│   ├── scheduler/             # Celery weekly scan
│   └── db/                    # SQLAlchemy ORM + CRUD
├── scripts/
│   ├── train_forest_snn.py    # EuroSAT → 2-class SNN training
│   ├── seed_demo_data.py      # Demo data generator
│   └── download_sentinel2.py  # CLI Sentinel-2 downloader
└── tests/                     # pytest suite
```

---

## API Reference

All endpoints require `X-API-Key` header. Rate limit: 60 req/min.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/api/v1/projects` | Create project |
| GET | `/api/v1/projects` | List projects |
| GET | `/api/v1/projects/{id}` | Get project |
| PATCH | `/api/v1/projects/{id}` | Update project |
| DELETE | `/api/v1/projects/{id}` | Delete project |
| POST | `/api/v1/analyses` | Request analysis |
| GET | `/api/v1/analyses/{id}` | Get analysis result |
| GET | `/api/v1/analyses/{id}/download` | Download GeoTIFF |
| GET | `/api/v1/alerts` | List alerts |
| POST | `/api/v1/alerts/{id}/acknowledge` | Acknowledge alert |
| POST | `/api/v1/webhooks` | Register webhook |
| DELETE | `/api/v1/webhooks/{id}` | Remove webhook |

Full interactive docs: http://localhost:8000/docs

---

## Training ForestSNN

```bash
python scripts/train_forest_snn.py \
    --epochs 30 \
    --batch-size 64 \
    --output models/weights/forest_snn.pt
```

A synthetic EuroSAT-like dataset is generated automatically if the
real EuroSAT dataset is unavailable. Outputs: trained weights +
confusion matrix + learning curves in `models/plots/`.

---

## Download Sentinel-2 Data

```bash
# Requires COPERNICUS_CLIENT_ID and COPERNICUS_CLIENT_SECRET in .env
python scripts/download_sentinel2.py \
    --bbox -55.0 -5.0 -50.0 -1.0 \
    --start 2024-01-01 \
    --end 2024-03-31 \
    --max-products 3 \
    --output-dir ./data/sentinel2
```

---

## Testing

```bash
# All tests
pytest

# With coverage report
pytest --cov=carbonsnn --cov-report=html

# Specific test module
pytest tests/test_models.py -v
pytest tests/test_carbon.py -v
```

---

## Environment Variables

See [.env.example](.env.example) for the full list of configurable variables.

Key variables:

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy async DB URL | `sqlite+aiosqlite:///./carbonsnn.db` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `COPERNICUS_CLIENT_ID` | Copernicus Data Space client ID | — |
| `COPERNICUS_CLIENT_SECRET` | Copernicus Data Space secret | — |
| `APP_SECRET_KEY` | JWT/signing secret | `change-me` |
| `CONFIDENCE_THRESHOLD` | SNN→CNN routing threshold | `0.75` |
| `MIN_DEFORESTATION_AREA_HA` | Minimum alert area | `0.5` |

---

## Carbon Methodology

Carbon stock estimates follow **IPCC 2006 Guidelines for National
Greenhouse Gas Inventories, Volume 4: Agriculture, Forestry and Other
Land Use** (updated 2019 Refinement).

- **AGB**: Above-Ground Biomass carbon density (Mg C/ha)
- **BGB**: Below-Ground Biomass = AGB × root-to-shoot ratio (0.26)
- **CO2e**: Carbon × 3.667 (molecular mass ratio)
- **Uncertainty**: ±20% (IPCC Tier 2 default)
- **MRV Standard**: Verra Verified Carbon Standard (VCS)

---

## License

MIT License — see LICENSE file for details.

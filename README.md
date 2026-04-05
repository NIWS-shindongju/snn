# SpikeEO

**Energy-Efficient Satellite Image Analysis Engine**
powered by Spiking Neural Networks (SNN)

---

## Overview

SpikeEO analyses multispectral satellite imagery (Sentinel-2, 10-band) using biologically-inspired Spiking Neural Networks. It classifies land cover, detects change events, estimates carbon stocks, and counts objects — with a hybrid SNN→CNN routing architecture that cuts inference cost by routing only uncertain tiles through the heavier CNN fallback.

### Key Features

| Feature | Description |
|---|---|
| **SNNBackbone** | Configurable SNN (light / standard / deep) — 10-band Sentinel-2 input |
| **HybridRouter** | SNN first pass → ResNet-18 CNN fallback for uncertain tiles only |
| **ChangeDetectionTask** | dNDVI/dNBR rule-based + Siamese SNN (5 change types) |
| **ClassificationTask** | N-class land cover classification with per-class area stats |
| **SegmentationTask** | Dense per-pixel semantic segmentation via tile-level inference |
| **DetectionTask** | Object counting via sliding-window inference |
| **BenchmarkRunner** | SNN vs CNN latency, energy, and cost comparison |
| **REST API** | FastAPI with API-key auth, rate limiting, async job tracking |
| **Carbon MRV** | IPCC Tier-2 AGB+BGB estimation, example pipeline included |

---

## Quick Start

### 1. Clone & Configure

```bash
git clone https://github.com/NIWS-shindongju/snn.git
cd snn
cp .env.example .env
# Edit .env: set SPIKEEO_APP_SECRET_KEY
```

### 2. Install (local development)

```bash
pip install -e ".[dev]"
```

### 3. Run inference

```python
import spikeeo

engine = spikeeo.Engine(task="classification", num_classes=2)
result = engine.run("scene.tif", output_dir="./out/", output_format="geojson")
print(result)
```

### 4. CLI

```bash
# Classify a GeoTIFF
spikeeo run scene.tif --task classification --num-classes 11

# Change detection between two images
spikeeo change before.tif after.tif --output ./out/

# Benchmark SNN vs CNN
spikeeo benchmark --tile-size 64 --num-tiles 200

# Start API server
spikeeo serve --host 0.0.0.0 --port 8000
```

### 5. Docker Compose

```bash
docker compose up -d
```

---

## Architecture

```
spikeeo/
├── spikeeo/
│   ├── __init__.py            # Engine export + version
│   ├── config.py              # Pydantic Settings (SPIKEEO_ prefix)
│   ├── engine.py              # Unified Engine entry point
│   ├── cli.py                 # Click CLI (run / change / benchmark / serve / info)
│   ├── core/
│   │   ├── snn_backbone.py    # SNNBackbone (light / standard / deep)
│   │   ├── cnn_fallback.py    # ResNet-18 CNN fallback
│   │   ├── hybrid_router.py   # HybridRouter + CostReport
│   │   └── converter.py       # CNN-to-SNN weight transfer
│   ├── tasks/
│   │   ├── classification.py  # N-class land cover classification
│   │   ├── change_detection.py# Rule-based + Siamese SNN change detection
│   │   ├── segmentation.py    # Dense semantic segmentation
│   │   ├── detection.py       # Object detection / counting
│   │   └── anomaly.py         # Anomaly / outlier detection
│   ├── io/
│   │   ├── geotiff_reader.py  # GeoTIFF band loading + resampling
│   │   ├── tiler.py           # Overlapping tile / untile
│   │   ├── cloud_mask.py      # SCL cloud masking
│   │   ├── vegetation.py      # NDVI / EVI / NBR / NDMI / LAI
│   │   └── output_writer.py   # GeoJSON / JSON / CSV / COG output
│   ├── benchmark/
│   │   ├── cnn_vs_snn.py      # Latency / energy / cost benchmarking
│   │   └── cost_calculator.py # Cloud GPU cost estimation
│   ├── api/                   # FastAPI server (auth, routes, schemas)
│   └── db/                    # SQLAlchemy ORM + async CRUD
├── examples/
│   ├── carbon_mrv/            # IPCC Tier-2 carbon MRV pipeline
│   ├── deforestation_alert/   # Change detection → GeoJSON alerts
│   └── retail_counting/       # Object detection demo
├── scripts/
│   ├── train_backbone.py      # EuroSAT → SNN backbone training
│   ├── seed_demo_data.py      # Demo data generator
│   └── download_sentinel2.py  # CLI Sentinel-2 downloader
└── tests/                     # pytest suite (94 tests)
```

---

## API Reference

All endpoints require `X-API-Key` header. Rate limit: 60 req/min (configurable).

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/inference` | Run inference on uploaded tile |
| POST | `/inference/batch` | Batch inference |
| POST | `/inference/change-detection` | Two-image change detection |
| POST | `/benchmark` | SNN vs CNN benchmark |
| GET | `/tasks` | List available task types |
| GET | `/tasks/models` | List available model configurations |

Full interactive docs: http://localhost:8000/docs

---

## Testing

```bash
# Full test suite with coverage
pytest

# Specific modules
pytest tests/test_backbone.py -v
pytest tests/test_tasks.py -v
pytest tests/test_pipeline.py -v
```

---

## Environment Variables

See [.env.example](.env.example) for all configurable variables. Key settings:

| Variable | Description | Default |
|---|---|---|
| `SPIKEEO_DATABASE_URL` | SQLAlchemy async DB URL | `sqlite+aiosqlite:///./spikeeo.db` |
| `SPIKEEO_APP_SECRET_KEY` | API auth signing secret | `change-me` |
| `SPIKEEO_CONFIDENCE_THRESHOLD` | SNN→CNN routing threshold | `0.75` |
| `SPIKEEO_DEFAULT_DEPTH` | SNN depth (light/standard/deep) | `standard` |
| `COPERNICUS_CLIENT_ID` | Copernicus Data Space client ID | — |
| `COPERNICUS_CLIENT_SECRET` | Copernicus Data Space secret | — |

---

## Carbon Methodology

Carbon stock estimates follow **IPCC 2006 Guidelines for National Greenhouse Gas Inventories, Volume 4: Agriculture, Forestry and Other Land Use** (updated 2019 Refinement).

- **AGB**: Above-Ground Biomass carbon density (Mg C/ha)
- **BGB**: Below-Ground Biomass = AGB × root-to-shoot ratio (0.26)
- **CO2e**: Carbon × 3.667 (molecular mass ratio)
- **Uncertainty**: ±20% (IPCC Tier 2 default)

See [examples/carbon_mrv/](examples/carbon_mrv/) for the full pipeline.

---

## License

MIT License — see LICENSE file for details.

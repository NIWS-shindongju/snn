"""Tests for carbon stock estimation and MRV reporting.

Validates:
- IPCC Tier-2 AGB/BGB calculations
- Climate zone detection by latitude
- CO2 equivalent conversion
- Uncertainty ranges
- MRV JSON report structure
"""

import json
import logging
from datetime import datetime, timezone

import numpy as np
import pytest

from carbonsnn.analysis.carbon_stock import CarbonStockEstimator
from carbonsnn.analysis.mrv_report import MRVReportGenerator
from carbonsnn.models.carbon_snn import CarbonLandCoverConfig

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────

@pytest.fixture
def estimator() -> CarbonStockEstimator:
    """Return a CarbonStockEstimator with default IPCC Tier-2 factors."""
    return CarbonStockEstimator(pixel_size_m=10.0, uncertainty_pct=0.20)


@pytest.fixture
def config() -> CarbonLandCoverConfig:
    """Return default land cover configuration."""
    return CarbonLandCoverConfig()


@pytest.fixture
def generator() -> MRVReportGenerator:
    """Return a default MRVReportGenerator."""
    return MRVReportGenerator()


# ──────────────────────────────────────────────────────────
# Climate Zone Detection
# ──────────────────────────────────────────────────────────

class TestClimateZoneDetection:
    """Tests for latitude-based climate zone inference."""

    def test_tropical_equator(self, estimator: CarbonStockEstimator) -> None:
        """Equator latitude should return 'tropical'."""
        assert estimator.detect_climate_zone(0.0) == "tropical"

    def test_tropical_max_lat(self, estimator: CarbonStockEstimator) -> None:
        """23.5° N/S should still be tropical."""
        assert estimator.detect_climate_zone(23.5) == "tropical"
        assert estimator.detect_climate_zone(-23.5) == "tropical"

    def test_temperate(self, estimator: CarbonStockEstimator) -> None:
        """Mid-latitudes should be temperate."""
        assert estimator.detect_climate_zone(45.0) == "temperate"
        assert estimator.detect_climate_zone(-35.0) == "temperate"

    def test_boreal(self, estimator: CarbonStockEstimator) -> None:
        """High latitudes should be boreal."""
        assert estimator.detect_climate_zone(70.0) == "boreal"
        assert estimator.detect_climate_zone(-65.0) == "boreal"


# ──────────────────────────────────────────────────────────
# Carbon Stock Estimation
# ──────────────────────────────────────────────────────────

class TestCarbonStockEstimation:
    """Tests for total carbon stock calculation."""

    def test_all_tropical_forest(
        self, estimator: CarbonStockEstimator, config: CarbonLandCoverConfig
    ) -> None:
        """100% tropical forest map should yield maximum carbon density."""
        class_map = np.zeros((100, 100), dtype=np.int64)  # all class 0 = Tropical Forest
        result = estimator.estimate_total_stock(class_map, latitude=0.0)

        # 100×100 pixels × 0.01 ha/pixel = 100 ha
        assert abs(result.area_ha - 100.0) < 0.01

        expected_agb = 100.0 * config.carbon_density_agb[0]  # 200 Mg C/ha × 100 ha
        expected_bgb = 100.0 * config.carbon_density_bgb[0]  # 52 Mg C/ha × 100 ha
        assert abs(result.total_agb_mg - expected_agb) < 0.5
        assert abs(result.total_bgb_mg - expected_bgb) < 0.5

    def test_total_equals_agb_plus_bgb(self, estimator: CarbonStockEstimator) -> None:
        """Total carbon must equal AGB + BGB."""
        class_map = np.random.randint(0, 11, size=(50, 50), dtype=np.int64)
        result = estimator.estimate_total_stock(class_map)
        assert abs(result.total_carbon_mg - (result.total_agb_mg + result.total_bgb_mg)) < 0.01

    def test_bare_land_zero_carbon(self, estimator: CarbonStockEstimator) -> None:
        """Bare land (class 8) should have zero carbon stock."""
        class_map = np.full((50, 50), 8, dtype=np.int64)  # all Bare Land
        result = estimator.estimate_total_stock(class_map)
        assert result.total_carbon_mg == pytest.approx(0.0, abs=0.01)

    def test_uncertainty_range(self, estimator: CarbonStockEstimator) -> None:
        """Uncertainty bounds should be ±20% of central estimate."""
        class_map = np.zeros((100, 100), dtype=np.int64)
        result = estimator.estimate_total_stock(class_map)

        expected_low = result.total_carbon_mg * 0.80
        expected_high = result.total_carbon_mg * 1.20
        assert abs(result.uncertainty_low - expected_low) < 0.01
        assert abs(result.uncertainty_high - expected_high) < 0.01

    def test_class_breakdown_sums_to_total(self, estimator: CarbonStockEstimator) -> None:
        """Sum of per-class carbon should equal total carbon."""
        class_map = np.random.randint(0, 11, size=(100, 100), dtype=np.int64)
        result = estimator.estimate_total_stock(class_map)

        breakdown_total = sum(v["total_carbon_mg_c"] for v in result.class_breakdown.values())
        assert abs(breakdown_total - result.total_carbon_mg) < 0.5


# ──────────────────────────────────────────────────────────
# Carbon Change Impact
# ──────────────────────────────────────────────────────────

class TestCarbonChangeImpact:
    """Tests for deforestation carbon release estimation."""

    def test_tropical_forest_to_bare_land(
        self, estimator: CarbonStockEstimator, config: CarbonLandCoverConfig
    ) -> None:
        """Converting tropical forest to bare land should release maximum carbon."""
        area_ha = 10.0
        result = estimator.estimate_change_impact(
            area_ha=area_ha,
            from_class=0,   # Tropical Forest
            to_class=8,     # Bare Land
            latitude=0.0,
        )
        expected_carbon = area_ha * config.total_carbon(0)
        assert abs(result.carbon_lost_mg - expected_carbon) < 0.5

    def test_co2_equivalent_conversion(self, estimator: CarbonStockEstimator) -> None:
        """CO2e should be carbon × 3.667."""
        result = estimator.estimate_change_impact(
            area_ha=1.0, from_class=0, to_class=8, latitude=0.0
        )
        expected_co2e = result.carbon_lost_mg * 3.667
        assert abs(result.co2_equivalent_mg - expected_co2e) < 0.5

    def test_no_change_no_emission(self, estimator: CarbonStockEstimator) -> None:
        """Converting a class to itself should emit zero carbon."""
        result = estimator.estimate_change_impact(
            area_ha=100.0, from_class=5, to_class=5  # Cropland → Cropland
        )
        assert result.carbon_lost_mg == pytest.approx(0.0, abs=0.01)

    def test_regrowth_positive_sequestration(
        self, estimator: CarbonStockEstimator
    ) -> None:
        """Bare land → tropical forest should have zero emission (gain not loss)."""
        result = estimator.estimate_change_impact(
            area_ha=5.0,
            from_class=8,   # Bare Land
            to_class=0,     # Tropical Forest (gain)
            latitude=0.0,
        )
        # Carbon lost must be >= 0 (clamped)
        assert result.carbon_lost_mg >= 0.0

    def test_uncertainty_range_method(self, estimator: CarbonStockEstimator) -> None:
        """uncertainty_range() should return (central×0.8, central×1.2)."""
        low, high = estimator.uncertainty_range(1000.0)
        assert abs(low - 800.0) < 0.1
        assert abs(high - 1200.0) < 0.1


# ──────────────────────────────────────────────────────────
# MRV Report Generation
# ──────────────────────────────────────────────────────────

class TestMRVReportGenerator:
    """Tests for VCS-compatible MRV report generation."""

    def test_generate_json_structure(
        self, generator: MRVReportGenerator, estimator: CarbonStockEstimator
    ) -> None:
        """Generated JSON should contain all required VCS fields."""
        class_map = np.zeros((100, 100), dtype=np.int64)
        carbon_stock = estimator.estimate_total_stock(class_map)
        now = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 12, 31, tzinfo=timezone.utc)

        report = generator.generate_json(
            project_id="proj-123",
            project_name="Amazon Test",
            country="Brazil",
            reference_period_start=now,
            reference_period_end=end,
            monitoring_period_start=now,
            monitoring_period_end=end,
            carbon_stock=carbon_stock,
        )

        required_keys = [
            "report_id",
            "schema_version",
            "generated_at",
            "generator",
            "project",
            "periods",
            "methodology",
            "area",
            "carbon_stocks",
            "emissions",
            "uncertainty",
            "data_sources",
        ]
        for key in required_keys:
            assert key in report, f"Missing key: {key}"

    def test_generate_json_serialisable(
        self, generator: MRVReportGenerator, estimator: CarbonStockEstimator
    ) -> None:
        """Report should be JSON-serialisable."""
        class_map = np.zeros((50, 50), dtype=np.int64)
        carbon_stock = estimator.estimate_total_stock(class_map)
        now = datetime(2024, 1, 1, tzinfo=timezone.utc)
        report = generator.generate_json(
            project_id="proj-456",
            project_name="Test",
            country="DRC",
            reference_period_start=now,
            reference_period_end=now,
            monitoring_period_start=now,
            monitoring_period_end=now,
            carbon_stock=carbon_stock,
        )
        json_str = json.dumps(report, default=str)
        assert len(json_str) > 100

    def test_generate_geojson_structure(self, generator: MRVReportGenerator) -> None:
        """GeoJSON output should be a valid FeatureCollection."""
        geojson = generator.generate_geojson(
            project_id="proj-789",
            project_name="Borneo",
            bbox=[112.0, -1.5, 117.0, 2.5],
        )
        assert geojson["type"] == "FeatureCollection"
        assert isinstance(geojson["features"], list)
        assert len(geojson["features"]) >= 1  # boundary feature

    def test_save_report(
        self,
        generator: MRVReportGenerator,
        estimator: CarbonStockEstimator,
        tmp_path,
    ) -> None:
        """save() should write valid JSON to disk."""
        class_map = np.zeros((10, 10), dtype=np.int64)
        carbon_stock = estimator.estimate_total_stock(class_map)
        now = datetime(2024, 1, 1, tzinfo=timezone.utc)
        report = generator.generate_json(
            project_id="save-test",
            project_name="Save Test",
            country="Test",
            reference_period_start=now,
            reference_period_end=now,
            monitoring_period_start=now,
            monitoring_period_end=now,
            carbon_stock=carbon_stock,
        )
        path = tmp_path / "report.json"
        generator.save(report, path)
        assert path.exists()
        with path.open() as fh:
            loaded = json.load(fh)
        assert loaded["project"]["id"] == "save-test"

    def test_carbon_values_in_report(
        self, generator: MRVReportGenerator, estimator: CarbonStockEstimator
    ) -> None:
        """Carbon values in report should match estimator output."""
        class_map = np.zeros((100, 100), dtype=np.int64)
        carbon_stock = estimator.estimate_total_stock(class_map)
        now = datetime(2024, 1, 1, tzinfo=timezone.utc)
        report = generator.generate_json(
            project_id="carbon-test",
            project_name="Carbon Test",
            country="Brazil",
            reference_period_start=now,
            reference_period_end=now,
            monitoring_period_start=now,
            monitoring_period_end=now,
            carbon_stock=carbon_stock,
            deforestation_area_ha=5.0,
            carbon_lost_mg=1260.0,
            co2_equivalent_mg=4620.0,
        )
        ref_stock = report["carbon_stocks"]["reference_period"]
        assert abs(ref_stock["total_mg_c"] - carbon_stock.total_carbon_mg) < 0.1
        assert abs(ref_stock["agb_mg_c"] - carbon_stock.total_agb_mg) < 0.1

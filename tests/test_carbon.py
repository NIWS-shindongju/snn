"""Tests for carbon stock estimation using the carbon_mrv example module.

Validates:
- IPCC Tier-2 AGB/BGB land cover configuration
- Climate zone detection by latitude
- Carbon stock estimation logic
- CO2 equivalent conversion
- Uncertainty ranges
- Per-class carbon breakdown
"""

import logging

import pytest

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────

@pytest.fixture
def config():
    from examples.carbon_mrv.config import CarbonLandCoverConfig
    return CarbonLandCoverConfig()


# ──────────────────────────────────────────────────────────
# CarbonLandCoverConfig Tests
# ──────────────────────────────────────────────────────────

class TestCarbonLandCoverConfig:
    """Tests for IPCC Tier-2 land cover configuration."""

    def test_num_classes(self, config) -> None:
        """Should have exactly 11 IPCC land cover classes."""
        assert config.num_classes == 11

    def test_carbon_density_lengths(self, config) -> None:
        """AGB, BGB, and hex_colors must all have 11 entries."""
        assert len(config.carbon_density_agb) == 11
        assert len(config.carbon_density_bgb) == 11
        assert len(config.hex_colors) == 11

    def test_tropical_forest_highest_agb(self, config) -> None:
        """Tropical forest (class 0) should have the highest AGB density."""
        assert config.carbon_density_agb[0] == max(config.carbon_density_agb)

    def test_bare_land_zero_carbon(self, config) -> None:
        """Bare Land (class 8) should have zero carbon."""
        assert config.carbon_density_agb[8] == 0.0
        assert config.carbon_density_bgb[8] == 0.0

    def test_total_carbon_equals_agb_plus_bgb(self, config) -> None:
        """total_carbon() should equal AGB + BGB for each class."""
        for i in range(config.num_classes):
            expected = config.carbon_density_agb[i] + config.carbon_density_bgb[i]
            assert abs(config.total_carbon(i) - expected) < 1e-6

    def test_hex_colors_format(self, config) -> None:
        """All hex colors should be valid 7-char hex strings."""
        for color in config.hex_colors:
            assert color.startswith("#"), f"Invalid hex color: {color}"
            assert len(color) == 7, f"Invalid hex color length: {color}"


# ──────────────────────────────────────────────────────────
# Climate Zone Detection Tests
# ──────────────────────────────────────────────────────────

class TestClimateZoneDetection:
    """Tests for latitude-based climate zone inference."""

    def test_tropical_equator(self) -> None:
        from examples.carbon_mrv.pipeline import detect_climate_zone
        assert detect_climate_zone(0.0) == "tropical"

    def test_tropical_max_lat(self) -> None:
        from examples.carbon_mrv.pipeline import detect_climate_zone
        assert detect_climate_zone(23.5) == "tropical"
        assert detect_climate_zone(-23.5) == "tropical"

    def test_temperate(self) -> None:
        from examples.carbon_mrv.pipeline import detect_climate_zone
        assert detect_climate_zone(45.0) == "temperate"
        assert detect_climate_zone(-35.0) == "temperate"

    def test_boreal(self) -> None:
        from examples.carbon_mrv.pipeline import detect_climate_zone
        assert detect_climate_zone(70.0) == "boreal"
        assert detect_climate_zone(-65.0) == "boreal"


# ──────────────────────────────────────────────────────────
# Carbon Stock Estimation Tests
# ──────────────────────────────────────────────────────────

class TestCarbonStockEstimation:
    """Tests for estimate_carbon_stock() function."""

    def test_all_tropical_forest(self, config) -> None:
        """100% tropical forest should give maximum carbon density."""
        from examples.carbon_mrv.pipeline import estimate_carbon_stock
        class_ids = [0] * 100  # all tropical forest
        result = estimate_carbon_stock(class_ids, latitude=0.0)
        assert result.total_carbon_mg > 0.0
        assert result.climate_zone == "tropical"
        assert result.area_ha > 0.0

    def test_bare_land_zero_carbon(self) -> None:
        """All bare land (class 8) should give zero carbon."""
        from examples.carbon_mrv.pipeline import estimate_carbon_stock
        class_ids = [8] * 50
        result = estimate_carbon_stock(class_ids, latitude=0.0)
        assert result.total_carbon_mg == pytest.approx(0.0, abs=0.01)

    def test_co2_equivalent_greater_than_carbon(self) -> None:
        """CO2 equivalent must exceed carbon mass (factor ~3.667)."""
        from examples.carbon_mrv.pipeline import estimate_carbon_stock
        class_ids = [0] * 20 + [1] * 20
        result = estimate_carbon_stock(class_ids, latitude=5.0)
        if result.total_carbon_mg > 0:
            assert result.co2_equivalent_mg > result.total_carbon_mg

    def test_uncertainty_range(self) -> None:
        """Uncertainty high should be above uncertainty low."""
        from examples.carbon_mrv.pipeline import estimate_carbon_stock
        class_ids = [0] * 50
        result = estimate_carbon_stock(class_ids)
        assert result.uncertainty_high > result.uncertainty_low

    def test_class_breakdown_keys(self, config) -> None:
        """Breakdown should contain entries for each class that appeared."""
        from examples.carbon_mrv.pipeline import estimate_carbon_stock
        class_ids = [0] * 10 + [4] * 10  # tropical forest + grassland
        result = estimate_carbon_stock(class_ids, latitude=0.0)
        assert "Tropical Forest" in result.class_breakdown
        assert "Grassland" in result.class_breakdown

    def test_carbon_density_consistent(self) -> None:
        """Carbon density should be total_carbon / area."""
        from examples.carbon_mrv.pipeline import estimate_carbon_stock
        class_ids = [0] * 30
        result = estimate_carbon_stock(class_ids, latitude=0.0)
        if result.area_ha > 0:
            expected_density = result.total_carbon_mg / result.area_ha
            assert abs(result.carbon_density_mg_ha - expected_density) < 1.0

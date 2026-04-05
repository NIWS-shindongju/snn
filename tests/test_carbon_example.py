"""Tests for examples/carbon_mrv pipeline."""

import pytest


def test_carbon_land_cover_config():
    """CarbonLandCoverConfig has correct number of classes."""
    from examples.carbon_mrv.config import CarbonLandCoverConfig
    config = CarbonLandCoverConfig()
    assert config.num_classes == 11
    assert len(config.class_names) == 11
    assert len(config.carbon_density_agb) == 11
    assert config.total_carbon(0) > 0.0  # Tropical forest has carbon


def test_detect_climate_zone():
    """detect_climate_zone returns correct zones."""
    from examples.carbon_mrv.pipeline import detect_climate_zone
    assert detect_climate_zone(0.0) == "tropical"
    assert detect_climate_zone(45.0) == "temperate"
    assert detect_climate_zone(70.0) == "boreal"
    assert detect_climate_zone(-5.0) == "tropical"


def test_estimate_carbon_stock():
    """estimate_carbon_stock returns a valid CarbonStockResult."""
    from examples.carbon_mrv.pipeline import estimate_carbon_stock
    # 10 tropical forest tiles (class 0), 10 grassland tiles (class 4)
    class_ids = [0] * 10 + [4] * 10
    result = estimate_carbon_stock(class_ids, latitude=5.0)
    assert result.total_carbon_mg >= 0.0
    assert result.co2_equivalent_mg >= result.total_carbon_mg
    assert result.climate_zone == "tropical"
    assert result.uncertainty_high > result.uncertainty_low

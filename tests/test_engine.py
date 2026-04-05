"""Integration tests for spikeeo.Engine."""

import numpy as np
import pytest
import tempfile
from pathlib import Path


def make_test_geotiff(num_bands: int = 10, size: int = 128) -> str:
    """Create a temporary GeoTIFF for testing."""
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_bounds
    import numpy as np

    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
        bands = (np.random.rand(num_bands, size, size) * 3000).astype(np.float32)
        profile = {
            "driver": "GTiff",
            "dtype": "float32",
            "width": size,
            "height": size,
            "count": num_bands,
            "crs": "EPSG:4326",
            "transform": from_bounds(-0.01, -0.01, 0.01, 0.01, size, size),
        }
        with rasterio.open(tmp.name, "w", **profile) as dst:
            dst.write(bands)
        return tmp.name


def test_engine_init_classification():
    """Engine initialises correctly for classification task."""
    import spikeeo
    engine = spikeeo.Engine(task="classification", num_classes=2)
    assert engine.task == "classification"
    assert engine.num_classes == 2
    assert engine._backbone is not None


def test_engine_init_all_tasks():
    """Engine initialises for all supported tasks."""
    import spikeeo
    for task in ["classification", "detection", "change_detection", "segmentation", "anomaly"]:
        engine = spikeeo.Engine(task=task, num_classes=2)
        assert engine.task == task


def test_engine_invalid_task():
    """Engine raises ValueError for unknown task."""
    import spikeeo
    with pytest.raises(ValueError, match="Unsupported task"):
        spikeeo.Engine(task="invalid_task")


def test_engine_repr():
    """Engine has a meaningful __repr__."""
    import spikeeo
    engine = spikeeo.Engine(task="classification", num_classes=3)
    r = repr(engine)
    assert "classification" in r
    assert "3" in r


def test_engine_run_with_geotiff():
    """Engine.run returns expected keys on a real GeoTIFF."""
    import spikeeo
    tif_path = make_test_geotiff()
    try:
        engine = spikeeo.Engine(task="classification", num_classes=2, use_hybrid=False)
        result = engine.run(tif_path)
        assert "metadata" in result
        assert result["metadata"]["task"] == "classification"
    finally:
        Path(tif_path).unlink(missing_ok=True)


def test_engine_get_cost_report():
    """get_cost_report returns a dict with expected keys."""
    import spikeeo
    engine = spikeeo.Engine(task="classification", num_classes=2, use_hybrid=True)
    tif_path = make_test_geotiff()
    try:
        engine.run(tif_path)
        report = engine.get_cost_report()
        assert "cost_saving_pct" in report
        assert report["cost_saving_pct"] >= 0.0
    finally:
        Path(tif_path).unlink(missing_ok=True)

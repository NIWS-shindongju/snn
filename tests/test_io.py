"""Tests for spikeeo.io modules."""

import numpy as np
import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def sample_bands():
    """Return a 10-band 128x128 numpy array."""
    return np.random.rand(10, 128, 128).astype(np.float32) * 3000


@pytest.fixture
def sample_geotiff(sample_bands):
    """Create a temporary GeoTIFF and yield its path."""
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_bounds

    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
        profile = {
            "driver": "GTiff", "dtype": "float32",
            "width": 128, "height": 128, "count": 10,
            "crs": "EPSG:4326",
            "transform": from_bounds(-0.01, -0.01, 0.01, 0.01, 128, 128),
        }
        with rasterio.open(tmp.name, "w", **profile) as dst:
            dst.write(sample_bands)
        yield tmp.name

    Path(tmp.name).unlink(missing_ok=True)


def test_read_geotiff(sample_geotiff):
    """read_geotiff returns (C, H, W) array with CRS and transform."""
    from spikeeo.io.geotiff_reader import read_geotiff
    bands, crs, transform = read_geotiff(sample_geotiff)
    assert bands.shape == (10, 128, 128)
    assert crs is not None
    assert transform is not None


def test_read_geotiff_missing():
    """read_geotiff raises FileNotFoundError for missing file."""
    from spikeeo.io.geotiff_reader import read_geotiff
    with pytest.raises(FileNotFoundError):
        read_geotiff("/nonexistent/path/file.tif")


def test_tiler_basic(sample_bands):
    """Tiler.tile splits image into expected number of tiles."""
    from spikeeo.io.tiler import Tiler
    tiler = Tiler(tile_size=64, overlap=0)
    tiles, positions = tiler.tile(sample_bands, normalize=False)
    assert len(tiles) > 0
    assert all(t.shape == (10, 64, 64) for t in tiles)
    assert len(tiles) == len(positions)


def test_tiler_normalize(sample_bands):
    """Tiler normalises bands to [0, 1] range."""
    from spikeeo.io.tiler import Tiler
    tiler = Tiler(tile_size=64, band_max=3000.0)
    tiles, _ = tiler.tile(sample_bands, normalize=True)
    assert len(tiles) > 0
    assert tiles[0].min() >= 0.0
    assert tiles[0].max() <= 1.0 + 1e-6


def test_tiler_small_image():
    """Tiler handles image smaller than tile_size by padding."""
    from spikeeo.io.tiler import Tiler
    small_image = np.random.rand(10, 32, 32).astype(np.float32)
    tiler = Tiler(tile_size=64)
    tiles, positions = tiler.tile(small_image, normalize=False)
    assert len(tiles) >= 1


def test_cloud_masker():
    """CloudMasker correctly identifies cloud pixels from SCL."""
    from spikeeo.io.cloud_mask import CloudMasker
    scl = np.zeros((10, 10), dtype=np.int32)
    scl[0, 0] = 9   # High probability cloud
    scl[1, 1] = 3   # Cloud shadow
    masker = CloudMasker(max_cloud_cover=50.0)
    result = masker.mask(scl)
    assert result.mask[0, 0] == True
    assert result.mask[1, 1] == True
    assert result.cloud_percentage > 0.0


def test_vegetation_indices():
    """VegetationIndexCalculator.compute_all returns all indices."""
    from spikeeo.io.vegetation import VegetationIndexCalculator
    bands = np.random.rand(10, 32, 32).astype(np.float64) * 5000
    calc = VegetationIndexCalculator()
    indices = calc.compute_all(bands)
    assert indices.ndvi.shape == (32, 32)
    assert indices.evi.shape == (32, 32)
    assert indices.nbr.shape == (32, 32)
    assert indices.lai.shape == (32, 32)


def test_output_writer_json(tmp_path):
    """write_json creates a valid JSON file."""
    from spikeeo.io.output_writer import write_json
    data = {"result": "test", "count": 42}
    out_path = tmp_path / "result.json"
    write_json(data, out_path)
    import json
    with out_path.open() as fh:
        loaded = json.load(fh)
    assert loaded["count"] == 42


def test_output_writer_geojson(tmp_path):
    """write_geojson creates a valid GeoJSON file."""
    from spikeeo.io.output_writer import write_geojson
    geojson = {"type": "FeatureCollection", "features": []}
    out_path = tmp_path / "result.geojson"
    write_geojson(geojson, out_path)
    import json
    with out_path.open() as fh:
        loaded = json.load(fh)
    assert loaded["type"] == "FeatureCollection"

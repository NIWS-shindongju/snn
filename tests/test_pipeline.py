"""End-to-end pipeline tests (spikeeo).

Tests the integration between:
- Vegetation index computation
- Cloud masking
- Image tiling / untiling
- Rule-based change detection
"""

import logging

import numpy as np
import pytest

from spikeeo.io.vegetation import VegetationIndexCalculator
from spikeeo.io.cloud_mask import CloudMasker
from spikeeo.io.tiler import Tiler
from spikeeo.tasks.change_detection import RuleBasedChangeDetector

logger = logging.getLogger(__name__)

H, W = 128, 128
BANDS = 10


# ──────────────────────────────────────────────────────────
# Vegetation Index Tests
# ──────────────────────────────────────────────────────────

class TestVegetationIndexCalculator:
    """Tests for vegetation index calculations."""

    @pytest.fixture
    def calc(self) -> VegetationIndexCalculator:
        return VegetationIndexCalculator()

    def test_ndvi_perfect_vegetation(self, calc: VegetationIndexCalculator) -> None:
        """NDVI should be 1.0 when NIR = max and Red = 0."""
        nir = np.ones((H, W)) * 1.0
        red = np.zeros((H, W))
        result = calc.ndvi(nir, red)
        np.testing.assert_allclose(result, 1.0, atol=1e-5)

    def test_ndvi_bare_soil(self, calc: VegetationIndexCalculator) -> None:
        """NDVI should be close to 0 when NIR ≈ Red."""
        arr = np.ones((H, W)) * 0.5
        result = calc.ndvi(arr, arr)
        np.testing.assert_allclose(result, 0.0, atol=1e-5)

    def test_ndvi_no_nan(self, calc: VegetationIndexCalculator) -> None:
        """NDVI should not produce NaN for typical values."""
        nir = np.random.rand(H, W) * 0.8 + 0.1
        red = np.random.rand(H, W) * 0.3
        result = calc.ndvi(nir, red)
        assert not np.any(np.isnan(result))

    def test_nbr_range(self, calc: VegetationIndexCalculator) -> None:
        """NBR should be in [-1, 1]."""
        nir = np.random.rand(H, W)
        swir2 = np.random.rand(H, W)
        result = calc.nbr(nir, swir2)
        assert result.min() >= -1.0
        assert result.max() <= 1.0

    def test_lai_range(self, calc: VegetationIndexCalculator) -> None:
        """LAI estimates should be clamped to [0, 8]."""
        ndvi = np.random.uniform(-0.5, 1.0, (H, W))
        result = calc.lai_estimate(ndvi)
        assert result.min() >= 0.0
        assert result.max() <= 8.0

    def test_compute_all_returns_dataclass(self, calc: VegetationIndexCalculator) -> None:
        """compute_all() should return VegetationIndices with all fields."""
        bands = np.random.rand(BANDS, H, W).astype(np.float32)
        result = calc.compute_all(bands)
        assert result.ndvi.shape == (H, W)
        assert result.evi.shape == (H, W)
        assert result.nbr.shape == (H, W)
        assert result.ndmi.shape == (H, W)
        assert result.lai.shape == (H, W)


# ──────────────────────────────────────────────────────────
# Cloud Masking Tests
# ──────────────────────────────────────────────────────────

class TestCloudMasker:
    """Tests for SCL-based cloud masking."""

    @pytest.fixture
    def masker(self) -> CloudMasker:
        return CloudMasker(max_cloud_cover=20.0)

    def test_clear_scene_is_usable(self, masker: CloudMasker) -> None:
        """A scene with only vegetation should be usable."""
        scl = np.full((H, W), 4, dtype=np.uint8)
        result = masker.mask(scl)
        assert result.is_usable
        assert result.cloud_percentage < 1.0

    def test_cloudy_scene_not_usable(self, masker: CloudMasker) -> None:
        """A fully cloudy scene should not be usable."""
        scl = np.full((H, W), 9, dtype=np.uint8)
        result = masker.mask(scl)
        assert not result.is_usable
        assert result.cloud_percentage == pytest.approx(100.0, abs=0.1)

    def test_apply_mask_shape(self, masker: CloudMasker) -> None:
        """apply_mask() should return same shape as input image."""
        image = np.random.rand(BANDS, H, W).astype(np.float32)
        scl = np.random.choice([4, 5, 8, 9], size=(H, W)).astype(np.uint8)
        masked = masker.apply_mask(image, scl)
        assert masked.shape == image.shape

    def test_apply_mask_nans_in_cloud(self, masker: CloudMasker) -> None:
        """Cloudy pixels should be NaN after masking."""
        image = np.ones((BANDS, H, W), dtype=np.float32)
        scl = np.full((H, W), 4, dtype=np.uint8)
        scl[0, 0] = 9
        masked = masker.apply_mask(image, scl)
        assert np.isnan(masked[:, 0, 0]).all()
        assert not np.isnan(masked[:, 1, 1]).any()

    def test_spatial_mismatch_raises(self, masker: CloudMasker) -> None:
        """Mismatched image/SCL sizes should raise ValueError."""
        image = np.ones((BANDS, H, W))
        scl = np.ones((H + 10, W), dtype=np.uint8)
        with pytest.raises(ValueError, match="spatial size"):
            masker.apply_mask(image, scl)


# ──────────────────────────────────────────────────────────
# Tiler Tests
# ──────────────────────────────────────────────────────────

class TestTiler:
    """Tests for image tiling and reconstruction."""

    @pytest.fixture
    def tiler(self) -> Tiler:
        return Tiler(tile_size=32, overlap=0)

    def test_normalize_range(self, tiler: Tiler) -> None:
        """Normalised values should be in [0, 1]."""
        raw = np.random.randint(0, 12000, (BANDS, H, W)).astype(np.float32)
        normed = tiler.normalize(raw)
        assert normed.min() >= 0.0
        assert normed.max() <= 1.0

    def test_tile_produces_correct_count(self, tiler: Tiler) -> None:
        """Tiling a 128×128 image with tile=32/overlap=0 gives 4×4=16 tiles."""
        image = np.random.rand(BANDS, H, W).astype(np.float32)
        tiles, positions = tiler.tile(image, normalize=False)
        assert len(tiles) == 16
        assert len(positions) == 16
        assert tiles[0].shape == (BANDS, 32, 32)

    def test_untile_reconstructs_shape(self, tiler: Tiler) -> None:
        """Untiling should recover the original spatial shape."""
        image = np.random.rand(BANDS, H, W).astype(np.float32)
        tiles, positions = tiler.tile(image, normalize=False)
        reconstructed = tiler.untile(tiles, positions, (H, W))
        assert reconstructed.shape == (BANDS, H, W)


# ──────────────────────────────────────────────────────────
# Rule-Based Change Detection Integration
# ──────────────────────────────────────────────────────────

class TestRuleBasedPipeline:
    """Integration tests for the spectral-index change detection pipeline."""

    @pytest.fixture
    def calc(self) -> VegetationIndexCalculator:
        return VegetationIndexCalculator()

    @pytest.fixture
    def detector(self) -> RuleBasedChangeDetector:
        return RuleBasedChangeDetector(ndvi_threshold=0.15, min_area_ha=0.01)

    def test_detects_significant_change(
        self, calc: VegetationIndexCalculator, detector: RuleBasedChangeDetector
    ) -> None:
        """Drastic NDVI drop should produce an above-threshold change result."""
        bands_before = np.ones((BANDS, H, W), dtype=np.float32) * 0.5
        bands_after = np.ones((BANDS, H, W), dtype=np.float32) * 0.1
        # Band layout: B02=0, B03=1, B04=2(Red), B08=3(NIR)
        bands_before[3] = 0.8  # high NIR
        bands_before[2] = 0.1  # low Red → high NDVI
        bands_after[3] = 0.2   # NIR drops
        bands_after[2] = 0.5   # Red increases → low NDVI

        indices_before = calc.compute_all(bands_before)
        indices_after = calc.compute_all(bands_after)

        result = detector.detect(
            indices_before.ndvi, indices_after.ndvi,
            indices_before.nbr, indices_after.nbr,
        )
        assert result.is_above_threshold
        assert result.area_ha > 0
        assert result.pixel_count > 0

    def test_no_alert_for_stable_scene(
        self, calc: VegetationIndexCalculator, detector: RuleBasedChangeDetector
    ) -> None:
        """Identical images should not produce an alert."""
        bands = np.random.rand(BANDS, H, W).astype(np.float32) * 0.5 + 0.3
        indices = calc.compute_all(bands)
        result = detector.detect(indices.ndvi, indices.ndvi, indices.nbr, indices.nbr)
        assert result.pixel_count == 0
        assert not result.is_above_threshold

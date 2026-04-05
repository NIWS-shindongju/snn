"""End-to-end pipeline tests.

Tests the integration between:
- Vegetation index computation
- Cloud masking
- Image preprocessing (tiling/untiling)
- Deforestation detection pipeline
"""

import logging

import numpy as np
import pytest

from carbonsnn.analysis.deforestation import DeforestationAlert, DeforestationDetector
from carbonsnn.data.cloud_mask import CloudMasker
from carbonsnn.data.preprocessor import ImagePreprocessor
from carbonsnn.data.vegetation import VegetationIndexCalculator

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
        """Return a VegetationIndexCalculator instance."""
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
        """Return a CloudMasker with default settings."""
        return CloudMasker(max_cloud_cover=20.0)

    def test_clear_scene_is_usable(self, masker: CloudMasker) -> None:
        """A scene with only vegetation should be usable."""
        scl = np.full((H, W), 4, dtype=np.uint8)  # all Vegetation
        result = masker.mask(scl)
        assert result.is_usable
        assert result.cloud_percentage < 1.0

    def test_cloudy_scene_not_usable(self, masker: CloudMasker) -> None:
        """A fully cloudy scene should not be usable."""
        scl = np.full((H, W), 9, dtype=np.uint8)  # all Cloud High Prob
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
        scl = np.full((H, W), 4, dtype=np.uint8)   # all clear
        scl[0, 0] = 9  # one cloudy pixel
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
# Preprocessor Tests
# ──────────────────────────────────────────────────────────

class TestImagePreprocessor:
    """Tests for tiling and normalisation."""

    @pytest.fixture
    def preprocessor(self) -> ImagePreprocessor:
        """Return a default ImagePreprocessor."""
        return ImagePreprocessor(tile_size=32, overlap=0)

    def test_normalize_range(self, preprocessor: ImagePreprocessor) -> None:
        """Normalised values should be in [0, 1]."""
        raw = np.random.randint(0, 12000, (BANDS, H, W)).astype(np.float32)
        normed = preprocessor.normalize(raw)
        assert normed.min() >= 0.0
        assert normed.max() <= 1.0

    def test_tile_produces_correct_count(self, preprocessor: ImagePreprocessor) -> None:
        """Tiling a 128×128 image with 32 tile/0 overlap should give 4×4=16 tiles."""
        image = np.random.rand(BANDS, H, W).astype(np.float32)
        tiles, positions = preprocessor.tile(image)
        assert len(tiles) == 16
        assert len(positions) == 16
        assert tiles[0].shape == (BANDS, 32, 32)

    def test_untile_reconstructs_shape(self, preprocessor: ImagePreprocessor) -> None:
        """Untiling should recover the original spatial shape."""
        image = np.random.rand(BANDS, H, W).astype(np.float32)
        tiles, positions = preprocessor.tile(image)
        reconstructed = preprocessor.untile(tiles, positions, (H, W))
        assert reconstructed.shape == (BANDS, H, W)


# ──────────────────────────────────────────────────────────
# Deforestation Detection Pipeline Tests
# ──────────────────────────────────────────────────────────

class TestDeforestationDetector:
    """Integration tests for the deforestation detection pipeline."""

    @pytest.fixture
    def detector(self) -> DeforestationDetector:
        """Return a DeforestationDetector with low area threshold."""
        return DeforestationDetector(min_area_ha=0.01)

    def test_detects_significant_change(self, detector: DeforestationDetector) -> None:
        """Should return an alert when deforestation is clearly present."""
        from datetime import datetime

        # Create before/after pair with drastic NDVI drop
        bands_before = np.ones((BANDS, H, W), dtype=np.float32) * 0.5
        bands_after = np.ones((BANDS, H, W), dtype=np.float32) * 0.1

        # NIR (band index 6 = B08) high, Red (band 2) low → high NDVI before
        bands_before[6] = 0.8
        bands_before[2] = 0.1
        # After: NIR drops, Red increases → NDVI loss
        bands_after[6] = 0.2
        bands_after[2] = 0.5

        alert = detector.detect_from_pair(
            bands_before=bands_before,
            bands_after=bands_after,
            project_id="test-project-001",
            sensing_date_before=datetime(2024, 1, 1),
            sensing_date_after=datetime(2024, 2, 1),
        )
        assert alert is not None
        assert alert.area_ha > 0
        assert alert.severity in ("low", "medium", "high")
        assert alert.project_id == "test-project-001"

    def test_no_alert_for_stable_scene(self, detector: DeforestationDetector) -> None:
        """Identical images should not produce an alert."""
        from datetime import datetime

        bands = np.random.rand(BANDS, H, W).astype(np.float32) * 0.5 + 0.3

        alert = detector.detect_from_pair(
            bands_before=bands,
            bands_after=bands,  # identical
            project_id="test-project-002",
            sensing_date_before=datetime(2024, 1, 1),
            sensing_date_after=datetime(2024, 2, 1),
        )
        assert alert is None

    def test_alert_severity_thresholds(self) -> None:
        """Test severity classification at boundary values."""
        assert DeforestationAlert.severity_from_area(0.5) == "low"
        assert DeforestationAlert.severity_from_area(1.0) == "medium"
        assert DeforestationAlert.severity_from_area(5.0) == "medium"
        assert DeforestationAlert.severity_from_area(10.0) == "high"
        assert DeforestationAlert.severity_from_area(100.0) == "high"

    def test_alert_to_dict_serialisable(self, detector: DeforestationDetector) -> None:
        """Alert.to_dict() should return JSON-serialisable content."""
        from datetime import datetime

        import json

        bands_b = np.ones((BANDS, H, W)) * 0.7
        bands_a = np.ones((BANDS, H, W)) * 0.1
        bands_b[6] = 0.9
        bands_b[2] = 0.05

        alert = detector.detect_from_pair(
            bands_before=bands_b.astype(np.float32),
            bands_after=bands_a.astype(np.float32),
            project_id="test-project-003",
            sensing_date_before=datetime(2024, 1, 1),
            sensing_date_after=datetime(2024, 2, 1),
        )

        if alert:
            d = alert.to_dict()
            json.dumps(d)  # should not raise

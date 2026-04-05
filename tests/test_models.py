"""Unit tests for SNN model architectures (spikeeo).

Tests:
- SNNBackbone (light = ForestSNN equivalent): output shape, prediction, save/load
- SNNBackbone (standard + regression = CarbonSNN equivalent): dual-head shapes
- HybridRouter: routing logic, cost report
- SiameseChangeDetectorSNN: output shape
- RuleBasedChangeDetector: threshold logic
"""

import logging
from pathlib import Path

import numpy as np
import pytest
import torch

from spikeeo.core.snn_backbone import SNNBackbone
from spikeeo.core.hybrid_router import HybridRouter
from spikeeo.tasks.change_detection import RuleBasedChangeDetector, SiameseChangeDetectorSNN

logger = logging.getLogger(__name__)

# ── Fixtures ──────────────────────────────────────────────

BATCH = 4
TILE = 32    # small for fast tests
BANDS = 10


@pytest.fixture(scope="module")
def forest_snn() -> SNNBackbone:
    """Return a light SNNBackbone (ForestSNN equivalent) for testing."""
    return SNNBackbone(num_classes=2, depth="light", num_steps=3, tile_size=TILE)


@pytest.fixture(scope="module")
def carbon_snn() -> SNNBackbone:
    """Return a standard SNNBackbone with regression head (CarbonSNN equivalent)."""
    return SNNBackbone(num_classes=11, depth="standard", num_steps=3, regression_head=True)


@pytest.fixture
def dummy_batch() -> torch.Tensor:
    """Return random 10-band input tensor."""
    return torch.rand(BATCH, BANDS, TILE, TILE)


# ── ForestSNN (SNNBackbone light) ─────────────────────────

class TestForestSNN:
    """Tests for SNNBackbone with depth='light' (ForestSNN equivalent)."""

    def test_forward_shape(self, forest_snn: SNNBackbone, dummy_batch: torch.Tensor) -> None:
        """Forward pass should return (B, 2) logits."""
        logits = forest_snn(dummy_batch)
        assert logits.shape == (BATCH, 2), f"Expected (4, 2), got {logits.shape}"

    def test_predict_shapes(self, forest_snn: SNNBackbone, dummy_batch: torch.Tensor) -> None:
        """predict() should return two (B,) tensors."""
        cls_ids, confs = forest_snn.predict(dummy_batch)
        assert cls_ids.shape == (BATCH,)
        assert confs.shape == (BATCH,)

    def test_class_ids_binary(self, forest_snn: SNNBackbone, dummy_batch: torch.Tensor) -> None:
        """Class IDs must be 0 or 1."""
        cls_ids, _ = forest_snn.predict(dummy_batch)
        assert cls_ids.max().item() <= 1
        assert cls_ids.min().item() >= 0

    def test_confidence_range(self, forest_snn: SNNBackbone, dummy_batch: torch.Tensor) -> None:
        """Confidence scores must be in (0, 1]."""
        _, confs = forest_snn.predict(dummy_batch)
        assert confs.min().item() > 0.0
        assert confs.max().item() <= 1.0

    def test_save_load(self, forest_snn: SNNBackbone, tmp_path: Path, dummy_batch: torch.Tensor) -> None:
        """Model should round-trip through save/load."""
        ckpt_path = tmp_path / "test_forest_snn.pt"
        forest_snn.save(ckpt_path)
        assert ckpt_path.exists()

        loaded = SNNBackbone.load(ckpt_path)
        cls_orig, _ = forest_snn.predict(dummy_batch)
        cls_load, _ = loaded.predict(dummy_batch)
        assert torch.all(cls_orig == cls_load)

    def test_load_missing_file(self, tmp_path: Path) -> None:
        """Loading a non-existent checkpoint should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            SNNBackbone.load(tmp_path / "nonexistent.pt")

    def test_dummy_input_shape(self) -> None:
        """dummy_input() should return the right shape."""
        x = SNNBackbone.dummy_input(batch_size=3, tile_size=48)
        assert x.shape == (3, 10, 48, 48)


# ── CarbonSNN (SNNBackbone standard + regression) ─────────

class TestCarbonSNN:
    """Tests for SNNBackbone with depth='standard' and regression_head=True."""

    def test_forward_shapes(self, carbon_snn: SNNBackbone, dummy_batch: torch.Tensor) -> None:
        """Forward pass should return (B, 11) and (B, 1) when regression_head=True."""
        result = carbon_snn(dummy_batch)
        assert isinstance(result, tuple), "Expected tuple when regression_head=True"
        cls_logits, veg_density = result
        assert cls_logits.shape == (BATCH, 11), f"Expected (4, 11), got {cls_logits.shape}"
        assert veg_density.shape == (BATCH, 1), f"Expected (4, 1), got {veg_density.shape}"

    def test_predict_shapes(self, carbon_snn: SNNBackbone, dummy_batch: torch.Tensor) -> None:
        """predict() should return (class_ids, confidences)."""
        cls_ids, confs = carbon_snn.predict(dummy_batch)
        assert cls_ids.shape == (BATCH,)
        assert confs.shape == (BATCH,)

    def test_vegetation_density_range(self, carbon_snn: SNNBackbone, dummy_batch: torch.Tensor) -> None:
        """Vegetation density output should be in [0, 1] (sigmoid)."""
        result = carbon_snn(dummy_batch)
        assert isinstance(result, tuple)
        _, veg = result
        assert veg.min().item() >= 0.0
        assert veg.max().item() <= 1.0

    def test_class_ids_in_range(self, carbon_snn: SNNBackbone, dummy_batch: torch.Tensor) -> None:
        """Class IDs should be in [0, 10]."""
        cls_ids, _ = carbon_snn.predict(dummy_batch)
        assert cls_ids.max().item() <= 10
        assert cls_ids.min().item() >= 0

    def test_config_num_classes(self) -> None:
        """CarbonLandCoverConfig should have exactly 11 classes."""
        from examples.carbon_mrv.config import CarbonLandCoverConfig
        config = CarbonLandCoverConfig()
        assert config.num_classes == 11
        assert len(config.carbon_density_agb) == 11
        assert len(config.carbon_density_bgb) == 11
        assert len(config.hex_colors) == 11

    def test_total_carbon(self) -> None:
        """Total carbon should equal AGB + BGB."""
        from examples.carbon_mrv.config import CarbonLandCoverConfig
        config = CarbonLandCoverConfig()
        for i in range(config.num_classes):
            expected = config.carbon_density_agb[i] + config.carbon_density_bgb[i]
            assert abs(config.total_carbon(i) - expected) < 1e-6


# ── HybridRouter ──────────────────────────────────────────

class TestHybridRouter:
    """Tests for the SNN→CNN HybridRouter."""

    def test_predict_shapes(self, dummy_batch: torch.Tensor) -> None:
        """forward() should return (B,) class IDs and confidences."""
        snn = SNNBackbone(num_classes=2, depth="light", num_steps=3, tile_size=TILE)
        router = HybridRouter(snn=snn, confidence_threshold=0.5)
        cls_ids, confs = router(dummy_batch)
        assert cls_ids.shape == (BATCH,)
        assert confs.shape == (BATCH,)

    def test_cost_report_structure(self, dummy_batch: torch.Tensor) -> None:
        """Cost report should account for all tiles."""
        snn = SNNBackbone(num_classes=2, depth="light", num_steps=3, tile_size=TILE)
        router = HybridRouter(snn=snn, confidence_threshold=1.0)  # force all CNN
        router(dummy_batch)
        report = router.get_cost_report()
        assert report.total_tiles == BATCH
        assert report.snn_pct + report.cnn_pct == pytest.approx(100.0, abs=0.1)


# ── RuleBasedChangeDetector ────────────────────────────────

class TestRuleBasedChangeDetector:
    """Tests for rule-based spectral change detection."""

    def test_detects_large_change(self) -> None:
        """Significant NDVI drop should be flagged above threshold."""
        detector = RuleBasedChangeDetector(ndvi_threshold=0.15, min_area_ha=0.5)
        h, w = 100, 100
        ndvi_before = np.ones((h, w)) * 0.8
        ndvi_after = np.ones((h, w)) * 0.2
        nbr_before = np.ones((h, w)) * 0.6
        nbr_after = np.ones((h, w)) * 0.4

        result = detector.detect(ndvi_before, ndvi_after, nbr_before, nbr_after)
        assert result.is_above_threshold
        assert result.pixel_count == h * w
        assert result.area_ha > 0

    def test_ignores_small_change(self) -> None:
        """Small area change below minimum threshold should not flag."""
        detector = RuleBasedChangeDetector(min_area_ha=100.0)
        h, w = 10, 10
        ndvi_before = np.ones((h, w)) * 0.7
        ndvi_after = np.ones((h, w)) * 0.3
        nbr = np.ones((h, w)) * 0.5

        result = detector.detect(ndvi_before, ndvi_after, nbr, nbr)
        assert not result.is_above_threshold

    def test_no_change(self) -> None:
        """Identical NDVI arrays should produce no change."""
        detector = RuleBasedChangeDetector(ndvi_threshold=0.15)
        ndvi = np.ones((50, 50)) * 0.75
        nbr = np.ones((50, 50)) * 0.5
        result = detector.detect(ndvi, ndvi, nbr, nbr)
        assert result.pixel_count == 0
        assert not result.is_above_threshold


# ── SiameseChangeDetectorSNN ───────────────────────────────

class TestSiameseChangeDetectorSNN:
    """Tests for the Siamese SNN change detector."""

    def test_output_shape(self, dummy_batch: torch.Tensor) -> None:
        """Output should have shape (B, 5)."""
        model = SiameseChangeDetectorSNN(num_steps=3)
        x0, x1 = model.dummy_inputs(batch_size=BATCH, tile_size=TILE)
        logits = model(x0, x1)
        assert logits.shape == (BATCH, 5)

    def test_predict(self) -> None:
        """predict() should return class IDs and confidences."""
        model = SiameseChangeDetectorSNN(num_steps=3)
        x0, x1 = model.dummy_inputs(batch_size=BATCH, tile_size=TILE)
        cls_ids, confs = model.predict(x0, x1)
        assert cls_ids.shape == (BATCH,)
        assert confs.min().item() > 0.0

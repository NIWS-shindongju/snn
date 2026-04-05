"""Tests for spikeeo.tasks modules."""

import numpy as np
import torch
import pytest


@pytest.fixture
def dummy_tiles():
    """Return 4 dummy 10-band 64x64 tiles as numpy arrays."""
    return [np.random.rand(10, 64, 64).astype(np.float32) for _ in range(4)]


@pytest.fixture
def snn_backbone():
    """Return a small SNNBackbone for testing."""
    from spikeeo.core.snn_backbone import SNNBackbone
    return SNNBackbone(num_bands=10, num_classes=2, depth="light", num_steps=3)


def test_classification_task(snn_backbone, dummy_tiles):
    """ClassificationTask returns expected keys."""
    from spikeeo.tasks.classification import ClassificationTask
    task = ClassificationTask(num_classes=2)
    result = task.run(snn_backbone, dummy_tiles, {})
    assert "class_ids" in result
    assert "confidences" in result
    assert "class_areas" in result
    assert "geojson" in result
    assert len(result["class_ids"]) == 4


def test_detection_task(snn_backbone, dummy_tiles):
    """DetectionTask returns object_count and centroids."""
    from spikeeo.tasks.detection import DetectionTask
    task = DetectionTask(num_classes=2)
    result = task.run(snn_backbone, dummy_tiles, {})
    assert "detections" in result
    assert "object_count" in result
    assert isinstance(result["object_count"], int)


def test_change_detection_task(snn_backbone, dummy_tiles):
    """ChangeDetectionTask returns change_stats."""
    from spikeeo.tasks.change_detection import ChangeDetectionTask
    task = ChangeDetectionTask()
    meta = {"tiles_after": dummy_tiles}
    result = task.run(snn_backbone, dummy_tiles, meta)
    assert "change_map" in result
    assert "change_stats" in result
    assert "change_area_ha" in result["change_stats"]


def test_segmentation_task(snn_backbone, dummy_tiles):
    """SegmentationTask returns segment_map."""
    from spikeeo.tasks.segmentation import SegmentationTask
    task = SegmentationTask(num_classes=2)
    result = task.run(snn_backbone, dummy_tiles, {})
    assert "segment_map" in result
    assert "class_areas" in result


def test_anomaly_task(snn_backbone, dummy_tiles):
    """AnomalyTask returns anomaly_scores and count."""
    from spikeeo.tasks.anomaly import AnomalyTask
    task = AnomalyTask()
    result = task.run(snn_backbone, dummy_tiles, {})
    assert "anomaly_scores" in result
    assert "anomaly_count" in result
    assert isinstance(result["anomaly_count"], int)


def test_siamese_change_detector():
    """SiameseChangeDetectorSNN forward pass returns correct shape."""
    from spikeeo.tasks.change_detection import SiameseChangeDetectorSNN
    model = SiameseChangeDetectorSNN(num_steps=3)
    x0, x1 = SiameseChangeDetectorSNN.dummy_inputs(batch_size=2, tile_size=32)
    out = model(x0, x1)
    assert out.shape == (2, 5)

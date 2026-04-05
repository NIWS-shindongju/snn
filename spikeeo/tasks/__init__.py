"""SpikeEO task modules for satellite image analysis."""

from spikeeo.tasks.classification import ClassificationTask
from spikeeo.tasks.detection import DetectionTask
from spikeeo.tasks.change_detection import ChangeDetectionTask
from spikeeo.tasks.segmentation import SegmentationTask
from spikeeo.tasks.anomaly import AnomalyTask

__all__ = [
    "ClassificationTask",
    "DetectionTask",
    "ChangeDetectionTask",
    "SegmentationTask",
    "AnomalyTask",
]

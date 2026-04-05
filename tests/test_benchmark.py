"""Tests for spikeeo.benchmark modules."""

import torch
import pytest
from torch.utils.data import DataLoader, TensorDataset


@pytest.fixture
def simple_loader():
    """Return a DataLoader with 8 random 10-band 64x64 samples."""
    x = torch.rand(8, 10, 64, 64)
    y = torch.randint(0, 2, (8,))
    return DataLoader(TensorDataset(x, y), batch_size=4)


def test_benchmark_runner(simple_loader):
    """BenchmarkRunner produces a valid BenchmarkReport."""
    from spikeeo.benchmark.cnn_vs_snn import BenchmarkRunner
    from spikeeo.core.snn_backbone import SNNBackbone
    from spikeeo.core.cnn_fallback import CNNFallback

    snn = SNNBackbone(num_bands=10, num_classes=2, depth="light", num_steps=3)
    cnn = CNNFallback(num_bands=10, num_classes=2)
    runner = BenchmarkRunner()
    report = runner.run(snn, cnn, simple_loader, device="cpu")

    assert 0.0 <= report.snn_accuracy <= 1.0
    assert 0.0 <= report.cnn_accuracy <= 1.0
    assert report.snn_inference_time_ms >= 0.0
    assert report.speedup_ratio >= 0.0
    assert report.num_batches == 2


def test_cost_calculator():
    """CostCalculator estimate returns valid savings."""
    from spikeeo.benchmark.cost_calculator import CostCalculator
    calc = CostCalculator(gpu_cost_per_hour=3.0, snn_speedup=5.0)
    result = calc.estimate(total_km2=1000.0)
    assert result["saving_pct"] > 0.0
    assert result["cnn_cost_usd"] > result["snn_cost_usd"]
    assert result["tiles_processed"] > 0


def test_benchmark_report_str():
    """BenchmarkReport.__str__ is human-readable."""
    from spikeeo.benchmark.cnn_vs_snn import BenchmarkReport
    r = BenchmarkReport(
        snn_accuracy=0.91,
        cnn_accuracy=0.93,
        accuracy_gap=0.02,
        speedup_ratio=4.8,
        cost_saving_estimate_pct=79.5,
    )
    s = str(r)
    assert "0.910" in s or "0.91" in s

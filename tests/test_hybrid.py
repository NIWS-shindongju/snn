"""Tests for HybridRouter (spikeeo/core/hybrid_router.py)."""

import torch
import pytest


def test_hybrid_router_all_snn():
    """All-SNN routing: CNN not called when all confidences are high."""
    from spikeeo.core.snn_backbone import SNNBackbone
    from spikeeo.core.hybrid_router import HybridRouter, CostReport

    snn = SNNBackbone(num_bands=10, num_classes=2, depth="light", num_steps=5)
    router = HybridRouter(snn=snn, confidence_threshold=0.0)  # threshold=0 means never route to CNN

    x = torch.rand(4, 10, 64, 64)
    class_ids, confs = router(x)
    assert class_ids.shape == (4,)
    assert confs.shape == (4,)

    report = router.get_cost_report()
    assert isinstance(report, CostReport)
    assert report.total_tiles == 4
    assert report.cost_saving_pct >= 0.0


def test_hybrid_router_all_cnn():
    """All-CNN routing when threshold=1.0 (always route to CNN)."""
    from spikeeo.core.snn_backbone import SNNBackbone
    from spikeeo.core.hybrid_router import HybridRouter

    snn = SNNBackbone(num_bands=10, num_classes=2, depth="light", num_steps=5)
    router = HybridRouter(snn=snn, confidence_threshold=1.0)  # always route to CNN

    x = torch.rand(4, 10, 64, 64)
    class_ids, confs = router(x)
    assert class_ids.shape == (4,)

    report = router.get_cost_report()
    assert report.cnn_tiles == 4
    assert report.cost_saving_pct == 0.0


def test_cost_saving_formula():
    """Verify cost_saving_pct formula: SNN=100% -> ~80%, CNN=100% -> 0%."""
    from spikeeo.core.snn_backbone import SNNBackbone
    from spikeeo.core.hybrid_router import HybridRouter

    snn = SNNBackbone(num_bands=10, num_classes=2, depth="light", num_steps=5)

    # All SNN case (threshold=0): saving = (1 - N*1 / N*5) * 100 = 80%
    router_snn = HybridRouter(snn=snn, confidence_threshold=0.0)
    x = torch.rand(10, 10, 64, 64)
    router_snn(x)
    report_snn = router_snn.get_cost_report()
    assert abs(report_snn.cost_saving_pct - 80.0) < 1.0

    # All CNN case (threshold=1.0): saving = 0%
    router_cnn = HybridRouter(snn=snn, confidence_threshold=1.0)
    router_cnn(x)
    report_cnn = router_cnn.get_cost_report()
    assert report_cnn.cost_saving_pct == 0.0


def test_hybrid_router_reset():
    """reset_cost_tracking() clears all counters."""
    from spikeeo.core.snn_backbone import SNNBackbone
    from spikeeo.core.hybrid_router import HybridRouter

    snn = SNNBackbone(num_bands=10, num_classes=2, depth="light", num_steps=5)
    router = HybridRouter(snn=snn)
    x = torch.rand(4, 10, 64, 64)
    router(x)
    router.reset_cost_tracking()
    report = router.get_cost_report()
    assert report.total_tiles == 0

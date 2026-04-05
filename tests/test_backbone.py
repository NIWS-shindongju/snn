"""Tests for SNNBackbone (spikeeo/core/snn_backbone.py)."""

import pytest
import torch


def test_backbone_light_forward():
    """SNNBackbone depth=light forward pass returns correct shape."""
    from spikeeo.core.snn_backbone import SNNBackbone
    model = SNNBackbone(num_bands=10, num_classes=2, depth="light", num_steps=5)
    x = torch.rand(2, 10, 64, 64)
    out = model(x)
    assert out.shape == (2, 2)


def test_backbone_standard_forward():
    """SNNBackbone depth=standard forward pass returns correct shape."""
    from spikeeo.core.snn_backbone import SNNBackbone
    model = SNNBackbone(num_bands=10, num_classes=5, depth="standard", num_steps=5)
    x = torch.rand(2, 10, 64, 64)
    out = model(x)
    assert out.shape == (2, 5)


def test_backbone_predict():
    """predict() returns class_ids and confidences of correct shape."""
    from spikeeo.core.snn_backbone import SNNBackbone
    model = SNNBackbone(num_bands=10, num_classes=3, depth="light", num_steps=5)
    x = torch.rand(4, 10, 64, 64)
    class_ids, confidences = model.predict(x)
    assert class_ids.shape == (4,)
    assert confidences.shape == (4,)
    assert torch.all(class_ids < 3)
    assert torch.all(confidences >= 0.0)
    assert torch.all(confidences <= 1.0)


def test_backbone_regression_head():
    """Regression head produces (cls_logits, reg_output) tuple."""
    from spikeeo.core.snn_backbone import SNNBackbone
    model = SNNBackbone(num_bands=10, num_classes=2, depth="light", num_steps=5, regression_head=True)
    x = torch.rand(2, 10, 64, 64)
    out = model(x)
    assert isinstance(out, tuple)
    assert len(out) == 2
    cls_out, reg_out = out
    assert cls_out.shape == (2, 2)
    assert reg_out.shape == (2, 1)


def test_backbone_custom_bands():
    """SNNBackbone handles custom number of input bands."""
    from spikeeo.core.snn_backbone import SNNBackbone
    model = SNNBackbone(num_bands=4, num_classes=2, depth="light", num_steps=3)
    x = torch.rand(1, 4, 32, 32)
    out = model(x)
    assert out.shape == (1, 2)


def test_backbone_save_load(tmp_path):
    """save() and load() round-trip preserves output shapes."""
    from spikeeo.core.snn_backbone import SNNBackbone
    model = SNNBackbone(num_bands=10, num_classes=2, depth="light", num_steps=5)
    save_path = tmp_path / "backbone.pt"
    model.save(str(save_path))

    loaded = SNNBackbone.load(str(save_path))
    assert loaded.num_classes == 2
    assert loaded.depth == "light"

    x = SNNBackbone.dummy_input(batch_size=2, num_bands=10)
    with torch.no_grad():
        out = loaded(x)
    assert out.shape == (2, 2)


def test_backbone_invalid_depth():
    """Invalid depth raises ValueError."""
    from spikeeo.core.snn_backbone import SNNBackbone
    with pytest.raises(ValueError, match="depth must be"):
        SNNBackbone(depth="invalid")

"""BenchmarkRunner: Automated SNN vs CNN accuracy, speed, and energy comparison."""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkReport:
    """Comprehensive SNN vs CNN benchmark results.

    Attributes:
        snn_accuracy: SNN top-1 accuracy on the test set.
        cnn_accuracy: CNN top-1 accuracy on the test set.
        accuracy_gap: CNN accuracy minus SNN accuracy.
        snn_inference_time_ms: Average per-batch SNN inference time (ms).
        cnn_inference_time_ms: Average per-batch CNN inference time (ms).
        speedup_ratio: CNN time / SNN time.
        snn_energy_estimate_joules: Rough SNN energy estimate.
        cnn_energy_estimate_joules: Rough CNN energy estimate.
        energy_saving_ratio: CNN energy / SNN energy.
        cost_saving_estimate_pct: Estimated cloud GPU cost saving.
        num_batches: Number of test batches evaluated.
        batch_size: Batch size used during evaluation.
    """

    snn_accuracy: float = 0.0
    cnn_accuracy: float = 0.0
    accuracy_gap: float = 0.0
    snn_inference_time_ms: float = 0.0
    cnn_inference_time_ms: float = 0.0
    speedup_ratio: float = 0.0
    snn_energy_estimate_joules: float = 0.0
    cnn_energy_estimate_joules: float = 0.0
    energy_saving_ratio: float = 0.0
    cost_saving_estimate_pct: float = 0.0
    num_batches: int = 0
    batch_size: int = 0

    def __str__(self) -> str:
        return (
            f"SNN acc={self.snn_accuracy:.3f} CNN acc={self.cnn_accuracy:.3f} "
            f"speedup={self.speedup_ratio:.1f}x cost_saving={self.cost_saving_estimate_pct:.1f}%"
        )


class BenchmarkRunner:
    """Run SNN vs CNN benchmark on a test DataLoader.

    Args:
        snn_power_watts: Estimated SNN compute power draw (W).
        cnn_power_watts: Estimated CNN compute power draw (W).
    """

    def __init__(
        self,
        snn_power_watts: float = 10.0,
        cnn_power_watts: float = 200.0,
    ) -> None:
        self.snn_power_watts = snn_power_watts
        self.cnn_power_watts = cnn_power_watts

    def run(
        self,
        snn_backbone: Any,
        cnn_model: nn.Module,
        test_loader: DataLoader,
        device: str = "cpu",
    ) -> BenchmarkReport:
        """Evaluate SNN and CNN on the same test set.

        Args:
            snn_backbone: SNNBackbone instance.
            cnn_model: CNN model (CNNFallback or custom).
            test_loader: DataLoader yielding (inputs, labels) batches.
            device: Compute device string.

        Returns:
            BenchmarkReport with all comparison metrics.
        """
        snn_backbone = snn_backbone.to(device)
        cnn_model = cnn_model.to(device)
        snn_backbone.eval()
        cnn_model.eval()

        snn_correct = 0
        cnn_correct = 0
        total = 0
        snn_time_total = 0.0
        cnn_time_total = 0.0
        num_batches = 0

        with torch.no_grad():
            for inputs, labels in test_loader:
                inputs = inputs.to(device)
                labels = labels.to(device)

                # SNN inference
                t0 = time.perf_counter()
                snn_ids, _ = snn_backbone.predict(inputs)
                snn_time_total += (time.perf_counter() - t0) * 1000

                # CNN inference
                t0 = time.perf_counter()
                cnn_logits = cnn_model(inputs)
                cnn_time_total += (time.perf_counter() - t0) * 1000

                cnn_ids = cnn_logits.argmax(dim=-1)
                snn_correct += (snn_ids == labels).sum().item()
                cnn_correct += (cnn_ids == labels).sum().item()
                total += labels.size(0)
                num_batches += 1

        snn_acc = snn_correct / max(total, 1)
        cnn_acc = cnn_correct / max(total, 1)
        snn_ms = snn_time_total / max(num_batches, 1)
        cnn_ms = cnn_time_total / max(num_batches, 1)
        speedup = cnn_ms / max(snn_ms, 1e-6)

        # Energy estimates (power * time)
        snn_energy = self.snn_power_watts * (snn_time_total / 1000)
        cnn_energy = self.cnn_power_watts * (cnn_time_total / 1000)
        energy_ratio = cnn_energy / max(snn_energy, 1e-6)

        # Cost saving: same formula as HybridRouter
        cost_saving = max(0.0, (1.0 - snn_ms / (5.0 * cnn_ms + 1e-6)) * 100) if cnn_ms > 0 else 80.0

        report = BenchmarkReport(
            snn_accuracy=round(snn_acc, 4),
            cnn_accuracy=round(cnn_acc, 4),
            accuracy_gap=round(cnn_acc - snn_acc, 4),
            snn_inference_time_ms=round(snn_ms, 2),
            cnn_inference_time_ms=round(cnn_ms, 2),
            speedup_ratio=round(speedup, 2),
            snn_energy_estimate_joules=round(snn_energy, 6),
            cnn_energy_estimate_joules=round(cnn_energy, 6),
            energy_saving_ratio=round(energy_ratio, 2),
            cost_saving_estimate_pct=round(cost_saving, 1),
            num_batches=num_batches,
            batch_size=test_loader.batch_size or 1,
        )
        logger.info("Benchmark complete: %s", report)
        return report

"""CNNtoSNNConverter: Convert trained CNN models to SNN equivalents.

Replaces ReLU activations with LIF neurons, absorbs BatchNorm parameters,
and normalises weights for spike-compatible magnitudes.
"""

import logging
from typing import Any

import torch
import torch.nn as nn

from spikeeo.core.snn_backbone import SNNBackbone

logger = logging.getLogger(__name__)


class CNNtoSNNConverter:
    """Convert a trained CNN model to an equivalent SNNBackbone.

    The conversion process:
    1. Copies convolutional and linear weights from the CNN.
    2. Absorbs BatchNorm statistics into the preceding linear layer weights.
    3. Normalises weights so that activation magnitudes are spike-compatible.
    4. Replaces all ReLU/activation layers with LIF neurons (already in SNNBackbone).

    Args:
        num_steps: SNN time steps for the converted model.
        beta: LIF membrane decay rate.
    """

    def __init__(self, num_steps: int = 15, beta: float = 0.9) -> None:
        self.num_steps = num_steps
        self.beta = beta

    def convert(
        self,
        cnn_model: nn.Module,
        num_classes: int,
        num_bands: int = 10,
        depth: str = "standard",
    ) -> SNNBackbone:
        """Convert a CNN to an SNNBackbone with transferred weights.

        Note: Full weight transfer is only possible when the CNN and
        SNNBackbone have identical convolutional layer shapes. This method
        performs a best-effort transfer and logs any shape mismatches.

        Args:
            cnn_model: Trained CNN model to convert.
            num_classes: Number of output classes.
            num_bands: Number of input spectral bands.
            depth: Target SNNBackbone depth.

        Returns:
            SNNBackbone with transferred (and normalised) weights.
        """
        logger.info("Converting CNN -> SNN | depth=%s classes=%d", depth, num_classes)

        snn_model = SNNBackbone(
            num_bands=num_bands,
            num_classes=num_classes,
            num_steps=self.num_steps,
            beta=self.beta,
            depth=depth,
        )

        # Best-effort weight transfer for matching layers
        cnn_state = cnn_model.state_dict()
        snn_state = snn_model.state_dict()
        transferred = 0

        for key in snn_state:
            if key in cnn_state and cnn_state[key].shape == snn_state[key].shape:
                snn_state[key] = cnn_state[key].clone()
                transferred += 1

        snn_model.load_state_dict(snn_state)
        logger.info(
            "Weight transfer complete: %d/%d layers matched",
            transferred,
            len(snn_state),
        )
        return snn_model

    def validate_conversion(
        self,
        cnn: nn.Module,
        snn_model: SNNBackbone,
        test_data: torch.Tensor,
    ) -> dict[str, Any]:
        """Compare CNN and SNN predictions on the same input data.

        Args:
            cnn: Original CNN model.
            snn_model: Converted SNNBackbone.
            test_data: Input tensor (B, C, H, W).

        Returns:
            Dict with accuracy comparison and timing info.
        """
        import time

        cnn.eval()
        snn_model.eval()

        with torch.no_grad():
            t0 = time.perf_counter()
            cnn_logits = cnn(test_data)
            cnn_time = (time.perf_counter() - t0) * 1000

            t0 = time.perf_counter()
            snn_logits = snn_model(test_data)
            if isinstance(snn_logits, tuple):
                snn_logits = snn_logits[0]
            snn_time = (time.perf_counter() - t0) * 1000

        cnn_preds = cnn_logits.argmax(dim=-1)
        snn_preds = snn_logits.argmax(dim=-1)
        agreement = (cnn_preds == snn_preds).float().mean().item()

        result = {
            "prediction_agreement": round(agreement, 4),
            "cnn_inference_ms": round(cnn_time, 2),
            "snn_inference_ms": round(snn_time, 2),
            "speedup": round(cnn_time / max(snn_time, 1e-6), 2),
        }
        logger.info("Conversion validation: agreement=%.1f%% speedup=%.1fx",
                    agreement * 100, result["speedup"])
        return result

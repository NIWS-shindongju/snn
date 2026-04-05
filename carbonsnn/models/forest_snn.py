"""ForestSNN: 2-class (Forest / Non-Forest) Spiking Neural Network.

Classifies Sentinel-2 10-band multi-spectral tiles into binary
forest / non-forest labels using a leaky integrate-and-fire (LIF)
neuron model via snntorch.
"""

import logging
from pathlib import Path
from typing import Any

import snntorch as snn
import torch
import torch.nn as nn
from snntorch import surrogate

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────
NUM_BANDS: int = 10          # Sentinel-2 10-m bands: B2 B3 B4 B5 B6 B7 B8 B8A B11 B12
NUM_CLASSES: int = 2         # 0 = Non-Forest, 1 = Forest
DEFAULT_NUM_STEPS: int = 15


class ForestSNN(nn.Module):
    """Binary forest / non-forest classifier using a spiking neural network.

    Architecture:
        1. 1×1 spectral projection (10 → 32 channels)
        2. Three Conv-BN-Pool-LIF blocks (32→64→128→256)
        3. Global average pooling
        4. FC-LIF hidden layer (256 → 128)
        5. FC output layer (128 → 2)

    Args:
        num_steps: Number of SNN time steps for spike accumulation.
        beta: LIF neuron membrane potential decay rate.
        spike_grad: Surrogate gradient function for back-propagation.
        tile_size: Spatial extent of input tiles (H = W = tile_size).
    """

    def __init__(
        self,
        num_steps: int = DEFAULT_NUM_STEPS,
        beta: float = 0.9,
        spike_grad: Any = surrogate.fast_sigmoid(slope=25),
        tile_size: int = 64,
    ) -> None:
        super().__init__()
        self.num_steps = num_steps
        self.tile_size = tile_size

        # ── Spectral projection ──────────────────────────────
        self.spectral_proj = nn.Sequential(
            nn.Conv2d(NUM_BANDS, 32, kernel_size=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
        )

        # ── Conv blocks ──────────────────────────────────────
        self.conv1 = nn.Conv2d(32, 64, kernel_size=3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.pool1 = nn.MaxPool2d(2, 2)
        self.lif1 = snn.Leaky(beta=beta, spike_grad=spike_grad, init_hidden=True)

        self.conv2 = nn.Conv2d(64, 128, kernel_size=3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(128)
        self.pool2 = nn.MaxPool2d(2, 2)
        self.lif2 = snn.Leaky(beta=beta, spike_grad=spike_grad, init_hidden=True)

        self.conv3 = nn.Conv2d(128, 256, kernel_size=3, padding=1, bias=False)
        self.bn3 = nn.BatchNorm2d(256)
        self.pool3 = nn.AdaptiveAvgPool2d(1)
        self.lif3 = snn.Leaky(beta=beta, spike_grad=spike_grad, init_hidden=True)

        # ── Fully connected head ─────────────────────────────
        self.fc1 = nn.Linear(256, 128)
        self.lif_fc1 = snn.Leaky(beta=beta, spike_grad=spike_grad, init_hidden=True)
        self.fc_out = nn.Linear(128, NUM_CLASSES)

        logger.info(
            "ForestSNN initialised | bands=%d classes=%d num_steps=%d tile=%d",
            NUM_BANDS,
            NUM_CLASSES,
            self.num_steps,
            self.tile_size,
        )

    # ── Forward pass ─────────────────────────────────────────
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Run SNN forward pass and return accumulated spike counts.

        Args:
            x: Input tensor of shape (B, 10, H, W).

        Returns:
            Spike count tensor of shape (B, 2).
        """
        # Reset hidden states for every new sample batch
        self.lif1.reset_hidden()
        self.lif2.reset_hidden()
        self.lif3.reset_hidden()
        self.lif_fc1.reset_hidden()

        spike_sum = torch.zeros(x.size(0), NUM_CLASSES, device=x.device)

        x_proj = self.spectral_proj(x)

        for _ in range(self.num_steps):
            # Block 1
            z = self.pool1(self.bn1(self.conv1(x_proj)))
            s1, _ = self.lif1(z)

            # Block 2
            z = self.pool2(self.bn2(self.conv2(s1)))
            s2, _ = self.lif2(z)

            # Block 3
            z = self.pool3(self.bn3(self.conv3(s2)))
            z = z.flatten(1)
            s3, _ = self.lif3(z)

            # FC head
            z = self.fc1(s3)
            sf, _ = self.lif_fc1(z)
            spike_sum += self.fc_out(sf)

        return spike_sum

    # ── Inference utilities ───────────────────────────────────
    @torch.no_grad()
    def predict(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Classify tiles and return class labels with confidence scores.

        Args:
            x: Input tensor of shape (B, 10, H, W).

        Returns:
            Tuple of (class_ids, confidences) each of shape (B,).
            class_ids: 0 = Non-Forest, 1 = Forest.
            confidences: Softmax probability of the predicted class.
        """
        self.eval()
        logits = self.forward(x)
        probs = torch.softmax(logits, dim=-1)
        confidences, class_ids = probs.max(dim=-1)
        return class_ids, confidences

    # ── Persistence ──────────────────────────────────────────
    def save(self, path: str | Path) -> None:
        """Save model weights to disk.

        Args:
            path: Destination file path (*.pt or *.pth).
        """
        save_path = Path(path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "state_dict": self.state_dict(),
                "config": {
                    "num_steps": self.num_steps,
                    "tile_size": self.tile_size,
                },
            },
            save_path,
        )
        logger.info("ForestSNN saved to %s", save_path)

    @classmethod
    def load(cls, path: str | Path, device: str = "cpu") -> "ForestSNN":
        """Load model weights from disk.

        Args:
            path: Source file path created by :meth:`save`.
            device: PyTorch device string.

        Returns:
            Loaded ForestSNN instance.

        Raises:
            FileNotFoundError: If the checkpoint file does not exist.
        """
        load_path = Path(path)
        if not load_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {load_path}")
        checkpoint = torch.load(load_path, map_location=device)
        config = checkpoint.get("config", {})
        model = cls(**config)
        model.load_state_dict(checkpoint["state_dict"])
        model.to(device)
        logger.info("ForestSNN loaded from %s (device=%s)", load_path, device)
        return model

    # ── Testing helper ────────────────────────────────────────
    @staticmethod
    def dummy_input(batch_size: int = 2, tile_size: int = 64) -> torch.Tensor:
        """Generate a random dummy input for smoke-testing.

        Args:
            batch_size: Number of samples in the batch.
            tile_size: Spatial resolution (H = W).

        Returns:
            Random tensor of shape (B, 10, H, W) in [0, 1].
        """
        return torch.rand(batch_size, NUM_BANDS, tile_size, tile_size)

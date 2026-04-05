"""SNNBackbone: Generic Spiking Neural Network backbone for satellite imagery.

Merges the ForestSNN (binary, light) and CarbonSNN (multi-class, standard)
architectures into a single configurable class.
"""

import logging
from pathlib import Path
from typing import Any

import snntorch as snn
import torch
import torch.nn as nn
from snntorch import surrogate

logger = logging.getLogger(__name__)


class SNNBackbone(nn.Module):
    """Generic SNN backbone for satellite image classification.

    Supports three depth configurations:
    - 'light':    3 Conv-BN-Pool-LIF blocks (32->64->128->256)   ~ForestSNN
    - 'standard': 4 Conv-BN-Pool-LIF blocks (64->128->256->512)  ~CarbonSNN
    - 'deep':     6 Conv-BN-Pool-LIF blocks (64->128->256->512->512->512)

    Args:
        num_bands: Number of input spectral bands (default 10 for Sentinel-2).
        num_classes: Number of output classification classes.
        num_steps: Number of SNN time steps for spike accumulation.
        beta: LIF neuron membrane potential decay rate.
        spike_grad: Surrogate gradient function.
        tile_size: Spatial tile size (H = W).
        depth: Architecture depth: 'light', 'standard', or 'deep'.
        regression_head: If True, add a continuous value regression head.
    """

    def __init__(
        self,
        num_bands: int = 10,
        num_classes: int = 2,
        num_steps: int = 15,
        beta: float = 0.9,
        spike_grad: Any = surrogate.fast_sigmoid(slope=25),
        tile_size: int = 64,
        depth: str = "standard",
        regression_head: bool = False,
    ) -> None:
        super().__init__()

        if depth not in ("light", "standard", "deep"):
            raise ValueError(f"depth must be 'light', 'standard', or 'deep', got {depth!r}")

        self.num_bands = num_bands
        self.num_classes = num_classes
        self.num_steps = num_steps
        self.tile_size = tile_size
        self.depth = depth
        self.regression_head = regression_head

        proj_channels = 32 if depth == "light" else 64

        # Spectral projection (1x1 conv to reduce band dimensionality)
        self.spectral_proj = nn.Sequential(
            nn.Conv2d(num_bands, proj_channels, kernel_size=1, bias=False),
            nn.BatchNorm2d(proj_channels),
            nn.ReLU(inplace=True),
        )

        # Build convolutional blocks based on depth
        if depth == "light":
            # 3 blocks: 32->64->128->256
            self._build_light(proj_channels, beta, spike_grad)
            final_channels = 256
            fc_hidden = 128
        elif depth == "standard":
            # 4 blocks: 64->128->256->512->512
            self._build_standard(proj_channels, beta, spike_grad)
            final_channels = 512
            fc_hidden = 256
        else:
            # deep: 6 blocks
            self._build_deep(proj_channels, beta, spike_grad)
            final_channels = 512
            fc_hidden = 256

        self.gap = nn.AdaptiveAvgPool2d(1)

        # Shared FC-LIF encoder
        self.fc_shared = nn.Linear(final_channels, fc_hidden)
        self.lif_shared = snn.Leaky(beta=beta, spike_grad=spike_grad)

        # Classification head
        self.fc_cls1 = nn.Linear(fc_hidden, fc_hidden // 2)
        self.lif_cls = snn.Leaky(beta=beta, spike_grad=spike_grad)
        self.fc_cls_out = nn.Linear(fc_hidden // 2, num_classes)

        # Optional regression head
        if regression_head:
            self.fc_reg1 = nn.Linear(fc_hidden, fc_hidden // 4)
            self.fc_reg_out = nn.Linear(fc_hidden // 4, 1)
        else:
            self.fc_reg1 = None  # type: ignore[assignment]
            self.fc_reg_out = None  # type: ignore[assignment]

        logger.info(
            "SNNBackbone initialised | bands=%d classes=%d depth=%s steps=%d tile=%d",
            num_bands, num_classes, depth, num_steps, tile_size,
        )

    # ── Block builders ─────────────────────────────────────────

    def _make_lif(self, beta: float, spike_grad: Any) -> snn.Leaky:
        return snn.Leaky(beta=beta, spike_grad=spike_grad)

    def _build_light(self, in_ch: int, beta: float, spike_grad: Any) -> None:
        """Build 3 Conv-BN-Pool-LIF blocks."""
        self.conv1 = nn.Conv2d(in_ch, 64, 3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.pool1 = nn.MaxPool2d(2, 2)
        self.lif1 = self._make_lif(beta, spike_grad)

        self.conv2 = nn.Conv2d(64, 128, 3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(128)
        self.pool2 = nn.MaxPool2d(2, 2)
        self.lif2 = self._make_lif(beta, spike_grad)

        self.conv3 = nn.Conv2d(128, 256, 3, padding=1, bias=False)
        self.bn3 = nn.BatchNorm2d(256)
        self.pool3 = nn.AdaptiveAvgPool2d(1)
        self.lif3 = self._make_lif(beta, spike_grad)

        # Stubs for unused layers in standard/deep paths
        self.conv4 = self.bn4 = self.pool4 = self.lif4 = None  # type: ignore
        self.conv5 = self.bn5 = self.pool5 = self.lif5 = None  # type: ignore
        self.conv6 = self.bn6 = self.pool6 = self.lif6 = None  # type: ignore
        self._num_blocks = 3

    def _build_standard(self, in_ch: int, beta: float, spike_grad: Any) -> None:
        """Build 4 Conv-BN-Pool-LIF blocks."""
        self.conv1 = nn.Conv2d(in_ch, 128, 3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(128)
        self.pool1 = nn.MaxPool2d(2, 2)
        self.lif1 = self._make_lif(beta, spike_grad)

        self.conv2 = nn.Conv2d(128, 256, 3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(256)
        self.pool2 = nn.MaxPool2d(2, 2)
        self.lif2 = self._make_lif(beta, spike_grad)

        self.conv3 = nn.Conv2d(256, 512, 3, padding=1, bias=False)
        self.bn3 = nn.BatchNorm2d(512)
        self.pool3 = nn.MaxPool2d(2, 2)
        self.lif3 = self._make_lif(beta, spike_grad)

        self.conv4 = nn.Conv2d(512, 512, 3, padding=1, bias=False)
        self.bn4 = nn.BatchNorm2d(512)
        self.pool4 = nn.AdaptiveAvgPool2d(1)
        self.lif4 = self._make_lif(beta, spike_grad)

        self.conv5 = self.bn5 = self.pool5 = self.lif5 = None  # type: ignore
        self.conv6 = self.bn6 = self.pool6 = self.lif6 = None  # type: ignore
        self._num_blocks = 4

    def _build_deep(self, in_ch: int, beta: float, spike_grad: Any) -> None:
        """Build 6 Conv-BN-Pool-LIF blocks."""
        self._build_standard(in_ch, beta, spike_grad)

        self.conv5 = nn.Conv2d(512, 512, 3, padding=1, bias=False)
        self.bn5 = nn.BatchNorm2d(512)
        self.pool5 = nn.MaxPool2d(2, 2)
        self.lif5 = self._make_lif(beta, spike_grad)

        self.conv6 = nn.Conv2d(512, 512, 3, padding=1, bias=False)
        self.bn6 = nn.BatchNorm2d(512)
        self.pool6 = nn.AdaptiveAvgPool2d(1)
        self.lif6 = self._make_lif(beta, spike_grad)
        self._num_blocks = 6

    # ── Forward pass ───────────────────────────────────────────

    def forward(self, x: torch.Tensor) -> torch.Tensor | tuple[torch.Tensor, torch.Tensor]:
        """Run SNN forward pass and return accumulated logits.

        Args:
            x: Input tensor of shape (B, num_bands, H, W).

        Returns:
            Class logits (B, num_classes), or tuple of
            (class_logits, regression_output) if regression_head=True.
        """
        cls_sum = torch.zeros(x.size(0), self.num_classes, device=x.device)
        reg_sum = torch.zeros(x.size(0), 1, device=x.device) if self.regression_head else None

        xp = self.spectral_proj(x)

        # Pre-initialise membrane states
        mem1 = self.lif1.init_leaky()
        mem2 = self.lif2.init_leaky()
        mem3 = self.lif3.init_leaky()
        mem4 = self.lif4.init_leaky() if self.lif4 is not None else None
        mem5 = self.lif5.init_leaky() if self.lif5 is not None else None
        mem6 = self.lif6.init_leaky() if self.lif6 is not None else None
        mem_shared = self.lif_shared.init_leaky()
        mem_cls = self.lif_cls.init_leaky()

        for _ in range(self.num_steps):
            # Block 1
            z = self.pool1(self.bn1(self.conv1(xp)))
            s1, mem1 = self.lif1(z, mem1)

            # Block 2
            z = self.pool2(self.bn2(self.conv2(s1)))
            s2, mem2 = self.lif2(z, mem2)

            # Block 3
            z = self.pool3(self.bn3(self.conv3(s2)))
            s3, mem3 = self.lif3(z, mem3)

            # Block 4 (standard/deep only)
            if self._num_blocks >= 4 and self.conv4 is not None:
                assert self.bn4 is not None and self.pool4 is not None and self.lif4 is not None and mem4 is not None
                z = self.pool4(self.bn4(self.conv4(s3)))
                feat_in, mem4 = self.lif4(z, mem4)
            else:
                feat_in = s3

            # Blocks 5 & 6 (deep only)
            if self._num_blocks >= 6 and self.conv5 is not None:
                assert self.bn5 is not None and self.pool5 is not None and self.lif5 is not None and mem5 is not None
                z = self.pool5(self.bn5(self.conv5(feat_in)))
                feat_in, mem5 = self.lif5(z, mem5)
                assert self.conv6 is not None and self.bn6 is not None and self.pool6 is not None and self.lif6 is not None and mem6 is not None
                z = self.pool6(self.bn6(self.conv6(feat_in)))
                feat_in, mem6 = self.lif6(z, mem6)

            feat = self.gap(feat_in).flatten(1)
            sf, mem_shared = self.lif_shared(self.fc_shared(feat), mem_shared)

            sc, mem_cls = self.lif_cls(self.fc_cls1(sf), mem_cls)
            cls_sum += self.fc_cls_out(sc)

            if self.regression_head and self.fc_reg1 is not None and reg_sum is not None:
                reg = torch.relu(self.fc_reg1(sf))
                reg_sum += torch.sigmoid(self.fc_reg_out(reg))

        if self.regression_head and reg_sum is not None:
            return cls_sum, reg_sum / self.num_steps
        return cls_sum

    @torch.no_grad()
    def predict(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Classify tiles and return class labels with confidence scores.

        Args:
            x: Input tensor of shape (B, num_bands, H, W).

        Returns:
            Tuple of (class_ids (B,), confidences (B,)).
        """
        self.eval()
        output = self.forward(x)
        logits = output[0] if isinstance(output, tuple) else output
        probs = torch.softmax(logits, dim=-1)
        confidences, class_ids = probs.max(dim=-1)
        return class_ids, confidences

    def save(self, path: str | Path) -> None:
        """Save model weights and configuration to disk.

        Args:
            path: Destination file path (.pt or .pth).
        """
        save_path = Path(path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "state_dict": self.state_dict(),
                "config": {
                    "num_bands": self.num_bands,
                    "num_classes": self.num_classes,
                    "num_steps": self.num_steps,
                    "tile_size": self.tile_size,
                    "depth": self.depth,
                    "regression_head": self.regression_head,
                },
            },
            save_path,
        )
        logger.info("SNNBackbone saved to %s", save_path)

    @classmethod
    def load(cls, path: str | Path, device: str = "cpu") -> "SNNBackbone":
        """Load a saved checkpoint.

        Args:
            path: Source .pt/.pth file created by :meth:`save`.
            device: Target device string.

        Returns:
            Loaded SNNBackbone instance.

        Raises:
            FileNotFoundError: If checkpoint does not exist.
        """
        load_path = Path(path)
        if not load_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {load_path}")
        checkpoint = torch.load(load_path, map_location=device, weights_only=False)
        config = checkpoint.get("config", {})
        model = cls(**config)
        model.load_state_dict(checkpoint["state_dict"])
        model.to(device)
        logger.info("SNNBackbone loaded from %s (device=%s)", load_path, device)
        return model

    @staticmethod
    def dummy_input(
        batch_size: int = 2,
        num_bands: int = 10,
        tile_size: int = 64,
    ) -> torch.Tensor:
        """Generate a random dummy input for smoke-testing.

        Args:
            batch_size: Batch size.
            num_bands: Number of spectral bands.
            tile_size: Spatial size.

        Returns:
            Random float32 tensor of shape (B, num_bands, H, W).
        """
        return torch.rand(batch_size, num_bands, tile_size, tile_size)

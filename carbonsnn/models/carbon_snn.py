"""CarbonSNN: 11-class land cover SNN with carbon stock estimation.

Dual-head architecture: classification (11 IPCC land cover classes)
+ vegetation density regression (0–1 continuous).
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import snntorch as snn
import torch
import torch.nn as nn
from snntorch import surrogate

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Land-Cover / Carbon Configuration
# ──────────────────────────────────────────────────────────

@dataclass
class CarbonLandCoverConfig:
    """IPCC Tier-2 land cover classes with carbon density and display colours.

    Attributes:
        class_names: Ordered list of 11 land cover names.
        carbon_density_agb: Above-ground biomass carbon (Mg C/ha) per class.
        carbon_density_bgb: Below-ground biomass carbon (Mg C/ha) per class.
        hex_colors: HEX display colours for map rendering.
    """

    class_names: list[str] = field(default_factory=lambda: [
        "Tropical Forest",        # 0
        "Temperate Forest",       # 1
        "Boreal Forest",          # 2
        "Shrubland",              # 3
        "Grassland",              # 4
        "Cropland",               # 5
        "Wetland",                # 6
        "Settlement",             # 7
        "Bare Land",              # 8
        "Water Body",             # 9
        "Permanent Snow/Ice",     # 10
    ])

    # IPCC Tier-2 default AGB carbon densities (Mg C/ha)
    carbon_density_agb: list[float] = field(default_factory=lambda: [
        200.0,   # Tropical Forest
        120.0,   # Temperate Forest
        80.0,    # Boreal Forest
        18.0,    # Shrubland
        3.5,     # Grassland
        5.0,     # Cropland
        50.0,    # Wetland
        0.0,     # Settlement
        0.0,     # Bare Land
        0.0,     # Water Body
        0.0,     # Permanent Snow/Ice
    ])

    # Root-to-shoot ratio × AGB  (IPCC default 0.26 for tropical forests)
    carbon_density_bgb: list[float] = field(default_factory=lambda: [
        52.0,    # Tropical Forest
        31.2,    # Temperate Forest
        20.8,    # Boreal Forest
        4.7,     # Shrubland
        0.9,     # Grassland
        1.3,     # Cropland
        13.0,    # Wetland
        0.0,     # Settlement
        0.0,     # Bare Land
        0.0,     # Water Body
        0.0,     # Permanent Snow/Ice
    ])

    hex_colors: list[str] = field(default_factory=lambda: [
        "#1A6B1A",   # Tropical Forest
        "#4CA64C",   # Temperate Forest
        "#8FBC8F",   # Boreal Forest
        "#D2B48C",   # Shrubland
        "#98FB98",   # Grassland
        "#FFD700",   # Cropland
        "#4169E1",   # Wetland
        "#FF4500",   # Settlement
        "#D2691E",   # Bare Land
        "#00BFFF",   # Water Body
        "#E0E0E0",   # Permanent Snow/Ice
    ])

    @property
    def num_classes(self) -> int:
        """Return number of land cover classes."""
        return len(self.class_names)

    def total_carbon(self, class_idx: int) -> float:
        """Return total carbon density (AGB + BGB) for a class.

        Args:
            class_idx: Land cover class index.

        Returns:
            Total carbon density in Mg C/ha.
        """
        return self.carbon_density_agb[class_idx] + self.carbon_density_bgb[class_idx]


# ──────────────────────────────────────────────────────────
# CarbonSNN Model
# ──────────────────────────────────────────────────────────

class _ConvBlock(nn.Module):
    """Reusable Conv-BN-LIF building block."""

    def __init__(
        self,
        in_ch: int,
        out_ch: int,
        beta: float,
        spike_grad: Any,
        pool: bool = True,
    ) -> None:
        super().__init__()
        self.conv = nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False)
        self.proj = nn.Conv2d(in_ch, out_ch, 1, bias=False)
        self.bn = nn.BatchNorm2d(out_ch)
        self.pool = nn.MaxPool2d(2, 2) if pool else nn.Identity()
        self.lif = snn.Leaky(beta=beta, spike_grad=spike_grad, init_hidden=True)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Forward pass returning (spikes, membrane)."""
        z = self.pool(self.bn(self.conv(self.proj(x))))
        return self.lif(z)


class CarbonSNN(nn.Module):
    """Dual-head SNN for land cover classification and vegetation density regression.

    Architecture:
        1. 1×1 spectral projection (10 → 64 channels)
        2. Four _ConvBlock layers (64→128→256→512→512)
        3. Global average pooling
        4. FC-LIF shared encoder (512 → 256)
        5. Classification head: FC(256 → 128) → LIF → FC(128 → 11)
        6. Regression head: FC(256 → 64) → ReLU → FC(64 → 1) → Sigmoid

    Args:
        num_steps: Number of SNN time steps.
        beta: LIF decay rate.
        spike_grad: Surrogate gradient function.
        config: Land cover / carbon configuration.
    """

    def __init__(
        self,
        num_steps: int = 25,
        beta: float = 0.9,
        spike_grad: Any = surrogate.fast_sigmoid(slope=25),
        config: CarbonLandCoverConfig | None = None,
    ) -> None:
        super().__init__()
        self.num_steps = num_steps
        self.config = config or CarbonLandCoverConfig()
        num_classes = self.config.num_classes

        # Spectral projection
        self.spectral_proj = nn.Sequential(
            nn.Conv2d(10, 64, 1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
        )

        # Four convolutional blocks
        self.block1 = _ConvBlock(64, 128, beta, spike_grad)
        self.block2 = _ConvBlock(128, 256, beta, spike_grad)
        self.block3 = _ConvBlock(256, 512, beta, spike_grad)
        self.block4 = _ConvBlock(512, 512, beta, spike_grad, pool=False)

        self.gap = nn.AdaptiveAvgPool2d(1)

        # Shared FC-LIF encoder
        self.fc_shared = nn.Linear(512, 256)
        self.lif_shared = snn.Leaky(beta=beta, spike_grad=spike_grad, init_hidden=True)

        # Classification head
        self.fc_cls1 = nn.Linear(256, 128)
        self.lif_cls = snn.Leaky(beta=beta, spike_grad=spike_grad, init_hidden=True)
        self.fc_cls_out = nn.Linear(128, num_classes)

        # Regression head (vegetation density 0-1)
        self.fc_reg1 = nn.Linear(256, 64)
        self.fc_reg_out = nn.Linear(64, 1)

        logger.info(
            "CarbonSNN initialised | classes=%d num_steps=%d",
            num_classes,
            num_steps,
        )

    def forward(
        self, x: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Run forward pass.

        Args:
            x: Input of shape (B, 10, H, W).

        Returns:
            Tuple of (class_logits (B, 11), veg_density (B, 1)).
        """
        # Reset all hidden states
        for lif in [self.lif_shared, self.lif_cls]:
            lif.reset_hidden()
        self.block1.lif.reset_hidden()
        self.block2.lif.reset_hidden()
        self.block3.lif.reset_hidden()
        self.block4.lif.reset_hidden()

        cls_sum = torch.zeros(x.size(0), self.config.num_classes, device=x.device)
        reg_sum = torch.zeros(x.size(0), 1, device=x.device)

        xp = self.spectral_proj(x)

        for _ in range(self.num_steps):
            s1, _ = self.block1(xp)
            s2, _ = self.block2(s1)
            s3, _ = self.block3(s2)
            s4, _ = self.block4(s3)

            feat = self.gap(s4).flatten(1)
            sf, _ = self.lif_shared(self.fc_shared(feat))

            # Classification branch
            sc, _ = self.lif_cls(self.fc_cls1(sf))
            cls_sum += self.fc_cls_out(sc)

            # Regression branch
            reg = torch.relu(self.fc_reg1(sf))
            reg_sum += torch.sigmoid(self.fc_reg_out(reg))

        return cls_sum, reg_sum / self.num_steps

    @torch.no_grad()
    def predict(
        self, x: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Inference with class labels, confidences and vegetation density.

        Args:
            x: Input tensor (B, 10, H, W).

        Returns:
            Tuple of (class_ids (B,), confidences (B,), veg_density (B, 1)).
        """
        self.eval()
        cls_logits, veg = self.forward(x)
        probs = torch.softmax(cls_logits, dim=-1)
        confidences, class_ids = probs.max(dim=-1)
        return class_ids, confidences, veg

    def save(self, path: str | Path) -> None:
        """Persist model weights.

        Args:
            path: Destination *.pt file.
        """
        save_path = Path(path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"state_dict": self.state_dict(), "num_steps": self.num_steps}, save_path)
        logger.info("CarbonSNN saved to %s", save_path)

    @classmethod
    def load(cls, path: str | Path, device: str = "cpu") -> "CarbonSNN":
        """Load from checkpoint.

        Args:
            path: Checkpoint path.
            device: Target device.

        Returns:
            Loaded CarbonSNN instance.
        """
        load_path = Path(path)
        if not load_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {load_path}")
        ckpt = torch.load(load_path, map_location=device)
        model = cls(num_steps=ckpt.get("num_steps", 25))
        model.load_state_dict(ckpt["state_dict"])
        model.to(device)
        return model

    @staticmethod
    def dummy_input(batch_size: int = 2, tile_size: int = 64) -> torch.Tensor:
        """Return random dummy input for smoke-testing."""
        return torch.rand(batch_size, 10, tile_size, tile_size)

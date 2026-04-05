"""CNNFallback: Lightweight ResNet-18 based CNN for hybrid routing.

Used by HybridRouter to re-classify low-confidence SNN tiles.
"""

import logging

import torch
import torch.nn as nn
import torchvision.models as tv_models

logger = logging.getLogger(__name__)


class CNNFallback(nn.Module):
    """ResNet-18 CNN fallback accepting variable-band satellite imagery.

    Replaces the standard 3-channel first conv with a num_bands-channel
    equivalent, and resizes the classification head to num_classes.

    Args:
        num_bands: Number of input spectral bands.
        num_classes: Number of output classes.
        pretrained: If True, initialise RGB channels from ImageNet weights.
    """

    def __init__(
        self,
        num_bands: int = 10,
        num_classes: int = 2,
        pretrained: bool = False,
    ) -> None:
        super().__init__()
        weights = tv_models.ResNet18_Weights.DEFAULT if pretrained else None
        base = tv_models.resnet18(weights=weights)
        # Replace first conv to accept num_bands input channels
        base.conv1 = nn.Conv2d(num_bands, 64, kernel_size=7, stride=2, padding=3, bias=False)
        # Replace classifier head
        base.fc = nn.Linear(512, num_classes)
        self.model = base
        logger.info(
            "CNNFallback (ResNet-18) initialised | bands=%d classes=%d pretrained=%s",
            num_bands, num_classes, pretrained,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Tile tensor (B, num_bands, H, W).

        Returns:
            Class logits (B, num_classes).
        """
        return self.model(x)

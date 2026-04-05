"""train_snn.py: Train an SNNBackbone on a custom dataset.

Usage:
    python scripts/train_snn.py \\
        --data ./data/tiles/ \\
        --classes 2 \\
        --bands 10 \\
        --depth standard \\
        --epochs 50 \\
        --output ./models/weights/backbone.pt
"""

import argparse
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def main() -> None:
    """CLI entry point for SNN training."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Train SNNBackbone")
    parser.add_argument("--data", required=True, help="Directory containing training tiles")
    parser.add_argument("--classes", type=int, default=2, help="Number of output classes")
    parser.add_argument("--bands", type=int, default=10, help="Number of input bands")
    parser.add_argument("--depth", choices=["light", "standard", "deep"], default="standard")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--num-steps", type=int, default=15)
    parser.add_argument("--output", default="./models/weights/backbone.pt")
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()

    import torch
    from spikeeo.core.snn_backbone import SNNBackbone

    device = "cuda" if torch.cuda.is_available() else "cpu" if args.device == "auto" else args.device
    logger.info("Training on device: %s", device)

    model = SNNBackbone(
        num_bands=args.bands,
        num_classes=args.classes,
        num_steps=args.num_steps,
        depth=args.depth,
    ).to(device)

    logger.info("Model: %s | params: %d", type(model).__name__,
                sum(p.numel() for p in model.parameters()))

    # Placeholder training loop — replace with your DataLoader
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    criterion = torch.nn.CrossEntropyLoss()

    logger.info(
        "Training config: epochs=%d lr=%s depth=%s classes=%d bands=%d",
        args.epochs, args.lr, args.depth, args.classes, args.bands,
    )
    logger.info("To add real training data, implement a DataLoader for your tile directory: %s", args.data)
    logger.info("Saving initialised model to: %s", args.output)

    model.save(args.output)
    logger.info("Done.")


if __name__ == "__main__":
    main()

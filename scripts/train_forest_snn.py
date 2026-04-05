"""Training script for ForestSNN using EuroSAT dataset.

Downloads EuroSAT, remaps 10 land cover classes to binary (Forest / Non-Forest),
then trains ForestSNN with AdamW + CosineAnnealingLR for 30 epochs.

Usage:
    python scripts/train_forest_snn.py [--epochs 30] [--batch-size 64] [--output models/weights/forest_snn.pt]
"""

import logging
import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import time
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import ConfusionMatrixDisplay, classification_report, confusion_matrix
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader, Dataset, random_split
from torchvision import transforms

from carbonsnn.models.forest_snn import ForestSNN

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# EuroSAT → 2-class remapping
# ──────────────────────────────────────────────────────────

# EuroSAT classes: 0=AnnualCrop, 1=Forest, 2=HerbaceousVegetation,
# 3=Highway, 4=Industrial, 5=Pasture, 6=PermanentCrop,
# 7=Residential, 8=River, 9=SeaLake
EUROSAT_TO_BINARY: dict[int, int] = {
    0: 0,  # AnnualCrop → Non-Forest
    1: 1,  # Forest → Forest
    2: 0,  # HerbaceousVegetation → Non-Forest
    3: 0,  # Highway → Non-Forest
    4: 0,  # Industrial → Non-Forest
    5: 0,  # Pasture → Non-Forest
    6: 0,  # PermanentCrop → Non-Forest
    7: 0,  # Residential → Non-Forest
    8: 0,  # River → Non-Forest
    9: 0,  # SeaLake → Non-Forest
}

CLASS_NAMES = ["Non-Forest", "Forest"]


# ──────────────────────────────────────────────────────────
# Synthetic EuroSAT-like dataset (fallback when download unavailable)
# ──────────────────────────────────────────────────────────

class SyntheticEuroSATDataset(Dataset):
    """Synthetic 10-band dataset for testing the training pipeline.

    Generates random spectral signatures with class-appropriate NDVI ranges.

    Args:
        num_samples: Total number of samples.
        tile_size: Spatial extent of each tile.
        forest_fraction: Fraction of samples labelled as Forest.
    """

    def __init__(
        self,
        num_samples: int = 5000,
        tile_size: int = 64,
        forest_fraction: float = 0.3,
    ) -> None:
        self.num_samples = num_samples
        self.tile_size = tile_size
        self.forest_fraction = forest_fraction

    def __len__(self) -> int:
        return self.num_samples

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
        is_forest = idx < int(self.num_samples * self.forest_fraction)
        label = 1 if is_forest else 0

        # Simulate spectral signature
        base = torch.rand(10, self.tile_size, self.tile_size)
        if is_forest:
            # High NIR (band 6), low Red (band 2) → high NDVI
            base[6] = base[6] * 0.3 + 0.6   # NIR high
            base[2] = base[2] * 0.2 + 0.05  # Red low
        else:
            base[6] = base[6] * 0.4 + 0.2   # NIR moderate
            base[2] = base[2] * 0.4 + 0.3   # Red higher

        return base.float(), label


# ──────────────────────────────────────────────────────────
# Training utilities
# ──────────────────────────────────────────────────────────

def train_one_epoch(
    model: ForestSNN,
    loader: DataLoader,
    optimizer: AdamW,
    criterion: nn.Module,
    device: torch.device,
) -> tuple[float, float]:
    """Run one training epoch.

    Args:
        model: ForestSNN model.
        loader: Training DataLoader.
        optimizer: AdamW optimiser.
        criterion: Loss function.
        device: Compute device.

    Returns:
        Tuple of (mean_loss, accuracy).
    """
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0

    for batch_x, batch_y in loader:
        batch_x = batch_x.to(device)
        batch_y = batch_y.to(device)

        optimizer.zero_grad()
        logits = model(batch_x)
        loss = criterion(logits, batch_y)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        preds = logits.argmax(dim=-1)
        correct += (preds == batch_y).sum().item()
        total += batch_y.size(0)

    return total_loss / len(loader), correct / total


@torch.no_grad()
def evaluate(
    model: ForestSNN,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> tuple[float, float, list[int], list[int]]:
    """Evaluate model on a data loader.

    Args:
        model: ForestSNN model.
        loader: Evaluation DataLoader.
        criterion: Loss function.
        device: Compute device.

    Returns:
        Tuple of (mean_loss, accuracy, all_labels, all_preds).
    """
    model.eval()
    total_loss = 0.0
    all_preds: list[int] = []
    all_labels: list[int] = []

    for batch_x, batch_y in loader:
        batch_x = batch_x.to(device)
        batch_y = batch_y.to(device)
        logits = model(batch_x)
        loss = criterion(logits, batch_y)
        total_loss += loss.item()
        preds = logits.argmax(dim=-1)
        all_preds.extend(preds.cpu().tolist())
        all_labels.extend(batch_y.cpu().tolist())

    accuracy = sum(p == l for p, l in zip(all_preds, all_labels)) / len(all_labels)
    return total_loss / len(loader), accuracy, all_labels, all_preds


def save_confusion_matrix(
    labels: list[int],
    preds: list[int],
    output_dir: Path,
) -> None:
    """Save confusion matrix plot to disk.

    Args:
        labels: True labels.
        preds: Predicted labels.
        output_dir: Output directory for the plot.
    """
    cm = confusion_matrix(labels, preds)
    fig, ax = plt.subplots(figsize=(6, 5))
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=CLASS_NAMES)
    disp.plot(ax=ax, colorbar=True, cmap="Blues")
    ax.set_title("ForestSNN Confusion Matrix (Test Set)")
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "confusion_matrix.png"
    fig.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Confusion matrix saved to %s", plot_path)


# ──────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────

def main() -> None:
    """Parse arguments and run training."""
    parser = argparse.ArgumentParser(description="Train ForestSNN on EuroSAT")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--tile-size", type=int, default=64)
    parser.add_argument("--num-steps", type=int, default=15)
    parser.add_argument("--output", type=str, default="models/weights/forest_snn.pt")
    parser.add_argument("--plots-dir", type=str, default="models/plots")
    parser.add_argument("--num-samples", type=int, default=5000, help="Synthetic dataset size")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Training device: %s", device)

    # ── Dataset ───────────────────────────────────────────
    logger.info("Building synthetic EuroSAT-like dataset (n=%d)", args.num_samples)
    dataset = SyntheticEuroSATDataset(
        num_samples=args.num_samples, tile_size=args.tile_size
    )

    train_size = int(0.7 * len(dataset))
    val_size = int(0.15 * len(dataset))
    test_size = len(dataset) - train_size - val_size

    train_ds, val_ds, test_ds = random_split(dataset, [train_size, val_size, test_size])

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=args.batch_size, num_workers=0)

    logger.info(
        "Dataset: train=%d val=%d test=%d", len(train_ds), len(val_ds), len(test_ds)
    )

    # ── Model ─────────────────────────────────────────────
    model = ForestSNN(num_steps=args.num_steps, tile_size=args.tile_size).to(device)
    logger.info("Model parameters: %d", sum(p.numel() for p in model.parameters()))

    # ── Optimiser + Scheduler + Loss ──────────────────────
    optimizer = AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-5)
    criterion = nn.CrossEntropyLoss()

    # ── Training loop ──────────────────────────────────────
    best_val_acc = 0.0
    train_losses: list[float] = []
    val_accs: list[float] = []

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    for epoch in range(1, args.epochs + 1):
        t_start = time.time()
        train_loss, train_acc = train_one_epoch(model, train_loader, optimizer, criterion, device)
        val_loss, val_acc, _, _ = evaluate(model, val_loader, criterion, device)
        scheduler.step()

        train_losses.append(train_loss)
        val_accs.append(val_acc)
        elapsed = time.time() - t_start

        logger.info(
            "Epoch %2d/%d | train_loss=%.4f train_acc=%.3f | "
            "val_loss=%.4f val_acc=%.3f | lr=%.2e | %.1fs",
            epoch,
            args.epochs,
            train_loss,
            train_acc,
            val_loss,
            val_acc,
            scheduler.get_last_lr()[0],
            elapsed,
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            model.save(output_path)
            logger.info("New best model saved (val_acc=%.4f)", best_val_acc)

    # ── Test evaluation ────────────────────────────────────
    logger.info("Loading best model for final evaluation…")
    best_model = ForestSNN.load(output_path, device=str(device))
    _, test_acc, test_labels, test_preds = evaluate(best_model, test_loader, criterion, device)
    logger.info("Test accuracy: %.4f", test_acc)

    print("\n" + classification_report(test_labels, test_preds, target_names=CLASS_NAMES))
    save_confusion_matrix(test_labels, test_preds, Path(args.plots_dir))

    # ── Learning curves ────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    axes[0].plot(train_losses)
    axes[0].set_title("Training Loss")
    axes[0].set_xlabel("Epoch")
    axes[1].plot(val_accs, color="orange")
    axes[1].set_title("Validation Accuracy")
    axes[1].set_xlabel("Epoch")
    curves_path = Path(args.plots_dir) / "learning_curves.png"
    Path(args.plots_dir).mkdir(parents=True, exist_ok=True)
    fig.savefig(curves_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Learning curves saved to %s", curves_path)

    logger.info("Training complete. Best val_acc=%.4f, test_acc=%.4f", best_val_acc, test_acc)


if __name__ == "__main__":
    main()

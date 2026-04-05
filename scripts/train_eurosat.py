"""Train SNNBackbone and ResNet-18 CNN on EuroSAT RGB dataset.

Downloads EuroSAT via torchvision; falls back to synthetic 10-class data
if the download fails.  Trains both models under identical conditions and
saves weights + training-curve plots.

Usage:
    python scripts/train_eurosat.py \\
        --epochs 50 --batch-size 64 --lr 1e-3 \\
        --snn-depth standard --snn-steps 25 \\
        --output-dir results/ --data-dir data/eurosat/
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
import torchvision.models as tv_models
import torchvision.transforms as T
from sklearn.metrics import ConfusionMatrixDisplay, confusion_matrix
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader, Dataset, random_split
from tqdm import tqdm

# ── project root on path ──────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from spikeeo.core.snn_backbone import SNNBackbone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

torch.manual_seed(42)
np.random.seed(42)

# ── Class definitions ─────────────────────────────────────────────────────────

EUROSAT_CLASSES: list[str] = [
    "AnnualCrop",
    "Forest",
    "HerbaceousVegetation",
    "Highway",
    "Industrial",
    "Pasture",
    "PermanentCrop",
    "Residential",
    "River",
    "SeaLake",
]
NUM_CLASSES = len(EUROSAT_CLASSES)
NUM_BANDS = 3   # RGB
TILE_SIZE = 64


# ── Synthetic fallback dataset ────────────────────────────────────────────────

class SyntheticEuroSATDataset(Dataset):
    """10-class synthetic satellite tiles (RGB 64×64).

    Each class has a distinct spectral signature to make the task learnable.

    Args:
        num_samples: Total samples (evenly distributed across 10 classes).
        tile_size: Spatial resolution (H = W).
        augment: Apply random flip/rotation augmentation.
    """

    def __init__(
        self,
        num_samples: int = 5000,
        tile_size: int = TILE_SIZE,
        augment: bool = False,
    ) -> None:
        super().__init__()
        self.num_samples = num_samples
        self.tile_size = tile_size
        self.augment = augment
        self.per_class = num_samples // NUM_CLASSES

        # Per-class mean RGB reflectance (0-1 range)
        self._means = torch.tensor([
            [0.4, 0.5, 0.2],   # AnnualCrop
            [0.1, 0.6, 0.1],   # Forest
            [0.2, 0.7, 0.2],   # HerbaceousVegetation
            [0.5, 0.5, 0.5],   # Highway
            [0.6, 0.5, 0.5],   # Industrial
            [0.3, 0.6, 0.3],   # Pasture
            [0.5, 0.6, 0.2],   # PermanentCrop
            [0.7, 0.6, 0.5],   # Residential
            [0.3, 0.4, 0.6],   # River
            [0.2, 0.3, 0.8],   # SeaLake
        ], dtype=torch.float32)  # (10, 3)

    def __len__(self) -> int:
        return self.num_samples

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
        label = idx % NUM_CLASSES
        rng = torch.Generator()
        rng.manual_seed(idx)
        noise = torch.randn(NUM_BANDS, self.tile_size, self.tile_size, generator=rng) * 0.08
        mean = self._means[label].view(NUM_BANDS, 1, 1).expand(NUM_BANDS, self.tile_size, self.tile_size)
        tile = (mean + noise).clamp(0.0, 1.0)

        if self.augment:
            if torch.rand(1).item() > 0.5:
                tile = tile.flip(dims=[2])
            if torch.rand(1).item() > 0.5:
                tile = tile.flip(dims=[1])

        return tile, label


# ── Dataset loading ───────────────────────────────────────────────────────────

def build_datasets(
    data_dir: str,
) -> tuple[Dataset, Dataset, Dataset]:
    """Try to load EuroSAT via torchvision; fall back to synthetic data.

    Args:
        data_dir: Directory for storing / reading EuroSAT files.

    Returns:
        Tuple of (train_dataset, val_dataset, test_dataset).
    """
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)

    base_transforms = T.Compose([
        T.Resize((TILE_SIZE, TILE_SIZE)),
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    aug_transforms = T.Compose([
        T.Resize((TILE_SIZE, TILE_SIZE)),
        T.RandomHorizontalFlip(),
        T.RandomVerticalFlip(),
        T.RandomRotation(90),
        T.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1),
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    try:
        import torchvision.datasets as tvd
        logger.info("Attempting EuroSAT download to %s …", data_dir)
        full_dataset = tvd.EuroSAT(root=data_dir, transform=aug_transforms, download=True)
        val_dataset_raw = tvd.EuroSAT(root=data_dir, transform=base_transforms, download=False)

        n = len(full_dataset)
        train_n = int(0.70 * n)
        val_n = int(0.15 * n)
        test_n = n - train_n - val_n

        gen = torch.Generator().manual_seed(42)
        train_ds, val_ds_aug, test_ds_aug = random_split(
            full_dataset, [train_n, val_n, test_n], generator=gen
        )

        # Val/test use base transforms — rebuild subsets without augmentation
        gen2 = torch.Generator().manual_seed(42)
        _, val_ds, test_ds = random_split(
            val_dataset_raw, [train_n, val_n, test_n], generator=gen2
        )

        logger.info(
            "EuroSAT loaded: train=%d val=%d test=%d", len(train_ds), len(val_ds), len(test_ds)
        )
        return train_ds, val_ds, test_ds

    except Exception as exc:
        logger.warning("EuroSAT download failed (%s) — using synthetic data.", exc)
        total = 5000
        per_class = total // NUM_CLASSES
        n = per_class * NUM_CLASSES
        train_n = int(0.70 * n)
        val_n = int(0.15 * n)
        test_n = n - train_n - val_n

        gen = torch.Generator().manual_seed(42)
        full = SyntheticEuroSATDataset(num_samples=n, augment=False)
        full_aug = SyntheticEuroSATDataset(num_samples=n, augment=True)

        train_ds, _, _ = random_split(full_aug, [train_n, val_n, test_n], generator=gen)
        gen2 = torch.Generator().manual_seed(42)
        _, val_ds, test_ds = random_split(full, [train_n, val_n, test_n], generator=gen2)

        logger.info(
            "Synthetic dataset: train=%d val=%d test=%d", len(train_ds), len(val_ds), len(test_ds)
        )
        return train_ds, val_ds, test_ds


# ── CNN model factory ─────────────────────────────────────────────────────────

def build_cnn(num_classes: int = NUM_CLASSES) -> nn.Module:
    """Build ResNet-18 with 3-channel input and custom head.

    Args:
        num_classes: Number of output classes.

    Returns:
        Modified ResNet-18 nn.Module.
    """
    model = tv_models.resnet18(weights=None)
    model.fc = nn.Linear(512, num_classes)
    return model


# ── Training / eval utilities ─────────────────────────────────────────────────

def train_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: AdamW,
    criterion: nn.CrossEntropyLoss,
    device: torch.device,
    desc: str = "Train",
) -> tuple[float, float]:
    """Run one training epoch.

    Args:
        model: The model to train.
        loader: Training DataLoader.
        optimizer: AdamW optimiser.
        criterion: CrossEntropyLoss.
        device: Compute device.
        desc: tqdm description prefix.

    Returns:
        Tuple of (mean_loss, accuracy).
    """
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0

    pbar = tqdm(loader, desc=desc, leave=False, ncols=90)
    for x, y in pbar:
        x, y = x.to(device), y.to(device)
        optimizer.zero_grad()
        out = model(x)
        loss = criterion(out, y)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        preds = out.argmax(dim=-1)
        correct += (preds == y).sum().item()
        total += y.size(0)
        pbar.set_postfix(loss=f"{loss.item():.4f}")

    return total_loss / len(loader), correct / total


@torch.no_grad()
def evaluate(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.CrossEntropyLoss,
    device: torch.device,
) -> tuple[float, float, list[int], list[int]]:
    """Evaluate model on a DataLoader.

    Args:
        model: Model to evaluate.
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

    for x, y in loader:
        x, y = x.to(device), y.to(device)
        out = model(x)
        total_loss += criterion(out, y).item()
        preds = out.argmax(dim=-1)
        all_preds.extend(preds.cpu().tolist())
        all_labels.extend(y.cpu().tolist())

    accuracy = sum(p == l for p, l in zip(all_preds, all_labels)) / max(len(all_labels), 1)
    return total_loss / len(loader), accuracy, all_labels, all_preds


# ── Plotting helpers ──────────────────────────────────────────────────────────

def save_confusion_matrix(
    labels: list[int],
    preds: list[int],
    path: Path,
    title: str = "Confusion Matrix",
) -> None:
    """Save a confusion matrix PNG.

    Args:
        labels: True labels.
        preds: Predicted labels.
        path: Output file path.
        title: Chart title.
    """
    cm = confusion_matrix(labels, preds)
    fig, ax = plt.subplots(figsize=(10, 8))
    disp = ConfusionMatrixDisplay(cm, display_labels=EUROSAT_CLASSES)
    disp.plot(ax=ax, colorbar=True, cmap="Blues", xticks_rotation=45)
    ax.set_title(title, fontsize=13)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    logger.info("Saved: %s", path)


def save_training_curves(
    snn_train_losses: list[float],
    snn_val_losses: list[float],
    snn_train_accs: list[float],
    snn_val_accs: list[float],
    cnn_train_losses: list[float],
    cnn_val_losses: list[float],
    cnn_train_accs: list[float],
    cnn_val_accs: list[float],
    path: Path,
) -> None:
    """Save a 2×2 subplot of training curves for SNN and CNN.

    Args:
        snn_train_losses: SNN training loss per epoch.
        snn_val_losses: SNN validation loss per epoch.
        snn_train_accs: SNN training accuracy per epoch.
        snn_val_accs: SNN validation accuracy per epoch.
        cnn_train_losses: CNN training loss per epoch.
        cnn_val_losses: CNN validation loss per epoch.
        cnn_train_accs: CNN training accuracy per epoch.
        cnn_val_accs: CNN validation accuracy per epoch.
        path: Output file path.
    """
    epochs = range(1, len(snn_train_losses) + 1)
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("SNN vs CNN Training Curves — EuroSAT 10-Class", fontsize=14, y=1.02)

    axes[0, 0].plot(epochs, snn_train_losses, label="Train Loss")
    axes[0, 0].plot(epochs, snn_val_losses, label="Val Loss")
    axes[0, 0].set_title("SNN — Loss")
    axes[0, 0].set_xlabel("Epoch")
    axes[0, 0].set_ylabel("Cross-Entropy Loss")
    axes[0, 0].legend()
    axes[0, 0].grid(alpha=0.3)

    axes[0, 1].plot(epochs, snn_train_accs, label="Train Acc")
    axes[0, 1].plot(epochs, snn_val_accs, label="Val Acc")
    axes[0, 1].set_title("SNN — Accuracy")
    axes[0, 1].set_xlabel("Epoch")
    axes[0, 1].set_ylabel("Accuracy")
    axes[0, 1].legend()
    axes[0, 1].grid(alpha=0.3)

    axes[1, 0].plot(epochs, cnn_train_losses, label="Train Loss", color="orange")
    axes[1, 0].plot(epochs, cnn_val_losses, label="Val Loss", color="red")
    axes[1, 0].set_title("CNN (ResNet-18) — Loss")
    axes[1, 0].set_xlabel("Epoch")
    axes[1, 0].set_ylabel("Cross-Entropy Loss")
    axes[1, 0].legend()
    axes[1, 0].grid(alpha=0.3)

    axes[1, 1].plot(epochs, cnn_train_accs, label="Train Acc", color="orange")
    axes[1, 1].plot(epochs, cnn_val_accs, label="Val Acc", color="red")
    axes[1, 1].set_title("CNN (ResNet-18) — Accuracy")
    axes[1, 1].set_xlabel("Epoch")
    axes[1, 1].set_ylabel("Accuracy")
    axes[1, 1].legend()
    axes[1, 1].grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved: %s", path)


# ── Training loop with early stopping ─────────────────────────────────────────

class EarlyStopping:
    """Stop training when validation accuracy stops improving.

    Args:
        patience: Number of epochs without improvement before stopping.
        min_delta: Minimum change to count as improvement.
    """

    def __init__(self, patience: int = 10, min_delta: float = 1e-4) -> None:
        self.patience = patience
        self.min_delta = min_delta
        self._best: float = -1.0
        self._counter: int = 0

    def __call__(self, val_acc: float) -> bool:
        """Return True if training should stop.

        Args:
            val_acc: Current epoch validation accuracy.

        Returns:
            True if early stopping triggered.
        """
        if val_acc > self._best + self.min_delta:
            self._best = val_acc
            self._counter = 0
        else:
            self._counter += 1
        return self._counter >= self.patience


def train_model(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    epochs: int,
    lr: float,
    save_path: Path,
    device: torch.device,
    label: str,
    patience: int = 10,
) -> tuple[list[float], list[float], list[float], list[float], float]:
    """Train model with early stopping and best-checkpoint saving.

    Args:
        model: Model to train.
        train_loader: Training DataLoader.
        val_loader: Validation DataLoader.
        epochs: Maximum number of training epochs.
        lr: Initial learning rate.
        save_path: Path to save best model weights.
        device: Compute device.
        label: Human-readable model name for logging.
        patience: Early stopping patience.

    Returns:
        Tuple of (train_losses, val_losses, train_accs, val_accs, best_val_acc).
    """
    optimizer = AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)
    criterion = nn.CrossEntropyLoss()
    early_stop = EarlyStopping(patience=patience)

    train_losses: list[float] = []
    val_losses: list[float] = []
    train_accs: list[float] = []
    val_accs: list[float] = []
    best_val_acc = 0.0

    # Allow graceful interrupt — save current best model
    interrupted = False

    def _handler(sig: int, frame: object) -> None:
        nonlocal interrupted
        logger.warning("KeyboardInterrupt — saving current best model and exiting.")
        interrupted = True

    prev_handler = signal.signal(signal.SIGINT, _handler)

    t_start = time.time()
    try:
        for epoch in range(1, epochs + 1):
            if interrupted:
                break

            train_loss, train_acc = train_epoch(
                model, train_loader, optimizer, criterion, device,
                desc=f"{label} [{epoch}/{epochs}]",
            )
            val_loss, val_acc, _, _ = evaluate(model, val_loader, criterion, device)
            scheduler.step()

            train_losses.append(train_loss)
            val_losses.append(val_loss)
            train_accs.append(train_acc)
            val_accs.append(val_acc)

            if val_acc > best_val_acc:
                best_val_acc = val_acc
                if isinstance(model, SNNBackbone):
                    model.save(save_path)
                else:
                    torch.save(model.state_dict(), save_path)
                logger.info(
                    "[%s] Epoch %d/%d | train_loss=%.4f train_acc=%.3f "
                    "| val_loss=%.4f val_acc=%.3f ✓ new best",
                    label, epoch, epochs, train_loss, train_acc, val_loss, val_acc,
                )
            else:
                logger.info(
                    "[%s] Epoch %d/%d | train_loss=%.4f train_acc=%.3f "
                    "| val_loss=%.4f val_acc=%.3f",
                    label, epoch, epochs, train_loss, train_acc, val_loss, val_acc,
                )

            if early_stop(val_acc):
                logger.info("[%s] Early stopping at epoch %d (patience=%d).", label, epoch, patience)
                break

    finally:
        signal.signal(signal.SIGINT, prev_handler)

    elapsed = time.time() - t_start
    logger.info(
        "[%s] Training finished in %.1fs — best val_acc=%.4f", label, elapsed, best_val_acc
    )
    return train_losses, val_losses, train_accs, val_accs, best_val_acc


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    """Parse CLI arguments and run SNN + CNN training."""
    parser = argparse.ArgumentParser(
        description="Train SNNBackbone + ResNet-18 on EuroSAT RGB"
    )
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--snn-depth", choices=["light", "standard", "deep"], default="standard")
    parser.add_argument("--snn-steps", type=int, default=25)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--output-dir", default="results/")
    parser.add_argument("--data-dir", default="data/eurosat/")
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument(
        "--max-samples", type=int, default=0,
        help="Cap total samples for fast dev runs (0 = use full dataset)",
    )
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Device: %s", device)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pretrained_dir = Path("pretrained")
    pretrained_dir.mkdir(parents=True, exist_ok=True)

    # ── Data ──────────────────────────────────────────────
    train_ds, val_ds, test_ds = build_datasets(args.data_dir)

    # Optional cap for fast dev-run validation
    if args.max_samples > 0:
        from torch.utils.data import Subset
        n_train = min(len(train_ds), int(args.max_samples * 0.70))
        n_val = min(len(val_ds), int(args.max_samples * 0.15))
        n_test = min(len(test_ds), int(args.max_samples * 0.15))
        gen = torch.Generator().manual_seed(42)
        train_ds = Subset(train_ds, torch.randperm(len(train_ds), generator=gen)[:n_train].tolist())
        val_ds = Subset(val_ds, torch.randperm(len(val_ds), generator=gen)[:n_val].tolist())
        test_ds = Subset(test_ds, torch.randperm(len(test_ds), generator=gen)[:n_test].tolist())
        logger.info(
            "max_samples cap applied: train=%d val=%d test=%d",
            len(train_ds), len(val_ds), len(test_ds),
        )

    train_loader = DataLoader(
        train_ds, batch_size=args.batch_size, shuffle=True,
        num_workers=args.num_workers, pin_memory=(device.type == "cuda"),
    )
    val_loader = DataLoader(
        val_ds, batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers,
    )
    test_loader = DataLoader(
        test_ds, batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers,
    )

    # ── Train SNN ──────────────────────────────────────────
    logger.info(
        "Building SNNBackbone(bands=%d, classes=%d, depth=%s, steps=%d)",
        NUM_BANDS, NUM_CLASSES, args.snn_depth, args.snn_steps,
    )
    snn_model = SNNBackbone(
        num_bands=NUM_BANDS,
        num_classes=NUM_CLASSES,
        depth=args.snn_depth,
        num_steps=args.snn_steps,
        tile_size=TILE_SIZE,
    ).to(device)
    logger.info("SNN parameters: %d", sum(p.numel() for p in snn_model.parameters()))

    snn_save = pretrained_dir / "eurosat_snn_standard.pt"
    (
        snn_tl, snn_vl, snn_ta, snn_va, snn_best
    ) = train_model(
        snn_model, train_loader, val_loader,
        epochs=args.epochs, lr=args.lr,
        save_path=snn_save, device=device,
        label="SNN", patience=args.patience,
    )

    # ── Train CNN ──────────────────────────────────────────
    logger.info("Building ResNet-18 CNN (classes=%d)", NUM_CLASSES)
    cnn_model = build_cnn(NUM_CLASSES).to(device)
    logger.info("CNN parameters: %d", sum(p.numel() for p in cnn_model.parameters()))

    cnn_save = pretrained_dir / "eurosat_cnn_resnet18.pt"
    (
        cnn_tl, cnn_vl, cnn_ta, cnn_va, cnn_best
    ) = train_model(
        cnn_model, train_loader, val_loader,
        epochs=args.epochs, lr=args.lr,
        save_path=cnn_save, device=device,
        label="CNN", patience=args.patience,
    )

    # ── Training curves ────────────────────────────────────
    curves_path = out_dir / "training_curves.png"
    save_training_curves(
        snn_tl, snn_vl, snn_ta, snn_va,
        cnn_tl, cnn_vl, cnn_ta, cnn_va,
        curves_path,
    )

    # ── Confusion matrices (best models on test set) ───────
    criterion = nn.CrossEntropyLoss()

    # SNN test eval
    snn_best_model = SNNBackbone.load(snn_save, device=str(device))
    _, snn_test_acc, snn_test_labels, snn_test_preds = evaluate(
        snn_best_model, test_loader, criterion, device
    )
    save_confusion_matrix(
        snn_test_labels, snn_test_preds,
        out_dir / "snn_confusion_matrix.png",
        title=f"SNN (SNNBackbone {args.snn_depth}) — EuroSAT Test Accuracy: {snn_test_acc:.1%}",
    )

    # CNN test eval
    cnn_best_model = build_cnn(NUM_CLASSES).to(device)
    cnn_best_model.load_state_dict(torch.load(cnn_save, map_location=device, weights_only=True))
    _, cnn_test_acc, cnn_test_labels, cnn_test_preds = evaluate(
        cnn_best_model, test_loader, criterion, device
    )
    save_confusion_matrix(
        cnn_test_labels, cnn_test_preds,
        out_dir / "cnn_confusion_matrix.png",
        title=f"CNN (ResNet-18) — EuroSAT Test Accuracy: {cnn_test_acc:.1%}",
    )

    # ── Summary ────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("RESULTS SUMMARY")
    logger.info("  SNN best val acc : %.4f  |  test acc : %.4f", snn_best, snn_test_acc)
    logger.info("  CNN best val acc : %.4f  |  test acc : %.4f", cnn_best, cnn_test_acc)
    logger.info("  Accuracy gap     : %+.4f (CNN - SNN)", cnn_test_acc - snn_test_acc)
    logger.info("  SNN weights      : %s", snn_save)
    logger.info("  CNN weights      : %s", cnn_save)
    logger.info("  Training curves  : %s", curves_path)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

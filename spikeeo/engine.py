"""SpikeEO unified inference engine.

Entry point for all satellite image analysis tasks. Wraps SNNBackbone,
HybridRouter, task modules, and IO utilities into a single interface.
"""

import logging
from pathlib import Path
from typing import Any

import numpy as np
import torch

logger = logging.getLogger(__name__)

SUPPORTED_TASKS: list[str] = [
    "classification",
    "detection",
    "change_detection",
    "segmentation",
    "anomaly",
]


class Engine:
    """SpikeEO unified inference engine.

    Example:
        >>> import spikeeo
        >>> engine = spikeeo.Engine(task="classification", num_classes=10)
        >>> result = engine.run("scene.tif")
        >>> report = engine.benchmark(test_data_dir="./test_tiles/")

    Args:
        task: Inference task type. One of 'classification', 'detection',
            'change_detection', 'segmentation', 'anomaly'.
        num_classes: Number of output classes.
        num_bands: Number of input spectral bands.
        tile_size: Spatial tile size (H = W = tile_size).
        num_steps: SNN time steps.
        confidence_threshold: Minimum SNN confidence to skip CNN fallback.
        use_hybrid: Whether to use SNN+CNN hybrid routing.
        device: Compute device ('auto', 'cpu', 'cuda').
        weights_path: Optional path to pretrained weights.
    """

    def __init__(
        self,
        task: str = "classification",
        num_classes: int = 2,
        num_bands: int = 10,
        tile_size: int = 64,
        num_steps: int = 15,
        confidence_threshold: float = 0.75,
        use_hybrid: bool = True,
        device: str = "auto",
        weights_path: str | None = None,
    ) -> None:
        if task not in SUPPORTED_TASKS:
            raise ValueError(f"Unsupported task '{task}'. Choose from: {SUPPORTED_TASKS}")

        self.task = task
        self.num_classes = num_classes
        self.num_bands = num_bands
        self.tile_size = tile_size
        self.num_steps = num_steps
        self.confidence_threshold = confidence_threshold
        self.use_hybrid = use_hybrid

        # Device resolution
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        # Lazy-initialised components
        self._backbone: Any = None
        self._router: Any = None
        self._task_module: Any = None
        self._tiler: Any = None

        self._init_components()

        if weights_path:
            self.load_weights(weights_path)

        logger.info(
            "Engine initialised | task=%s classes=%d bands=%d device=%s hybrid=%s",
            task, num_classes, num_bands, self.device, use_hybrid,
        )

    # ── Initialisation ─────────────────────────────────────────

    def _init_components(self) -> None:
        """Initialise SNN backbone, router, task module and tiler."""
        from spikeeo.core.snn_backbone import SNNBackbone
        from spikeeo.core.hybrid_router import HybridRouter
        from spikeeo.io.tiler import Tiler

        depth = "light" if self.num_classes <= 2 else "standard"

        self._backbone = SNNBackbone(
            num_bands=self.num_bands,
            num_classes=self.num_classes,
            num_steps=self.num_steps,
            tile_size=self.tile_size,
            depth=depth,
        ).to(self.device)

        if self.use_hybrid:
            self._router = HybridRouter(
                snn=self._backbone,
                confidence_threshold=self.confidence_threshold,
            )

        self._tiler = Tiler(tile_size=self.tile_size, overlap=8)
        self._task_module = self._build_task_module()

    def _build_task_module(self) -> Any:
        """Instantiate the appropriate task module."""
        if self.task == "classification":
            from spikeeo.tasks.classification import ClassificationTask
            return ClassificationTask(num_classes=self.num_classes)
        elif self.task == "detection":
            from spikeeo.tasks.detection import DetectionTask
            return DetectionTask(num_classes=self.num_classes)
        elif self.task == "change_detection":
            from spikeeo.tasks.change_detection import ChangeDetectionTask
            return ChangeDetectionTask()
        elif self.task == "segmentation":
            from spikeeo.tasks.segmentation import SegmentationTask
            return SegmentationTask(num_classes=self.num_classes)
        elif self.task == "anomaly":
            from spikeeo.tasks.anomaly import AnomalyTask
            return AnomalyTask()
        raise ValueError(f"Unknown task: {self.task}")

    # ── Inference ──────────────────────────────────────────────

    def run(
        self,
        input_path: str,
        output_dir: str | None = None,
        output_format: str = "geojson",
    ) -> dict[str, Any]:
        """Run inference on a single GeoTIFF.

        Args:
            input_path: Path to input GeoTIFF file.
            output_dir: Optional directory to write output files.
            output_format: Output format ('geojson', 'json', 'csv', 'cog').

        Returns:
            Dictionary with keys: task, class_map, confidence_map,
            geojson, metadata, cost_report.
        """
        from spikeeo.io.geotiff_reader import read_geotiff

        logger.info("Engine.run: %s (format=%s)", input_path, output_format)

        bands, crs, transform = read_geotiff(input_path)
        tiles, positions = self._tiler.tile(bands)

        # Run inference
        raw_outputs = self._infer_tiles(tiles)

        # Task-specific postprocessing
        original_shape = (bands.shape[1], bands.shape[2])
        result = self._task_module.run(
            self._backbone, tiles, {"crs": crs, "transform": transform}
        )
        result["raw_outputs"] = raw_outputs
        result["metadata"] = {
            "input_path": str(input_path),
            "crs": str(crs),
            "shape": original_shape,
            "num_tiles": len(tiles),
            "task": self.task,
            "num_classes": self.num_classes,
        }

        if self.use_hybrid and self._router is not None:
            result["cost_report"] = self._router.get_cost_report().__dict__

        # Write outputs if requested
        if output_dir:
            self._write_outputs(result, output_dir, output_format, Path(input_path).stem)

        return result

    def run_batch(
        self,
        input_paths: list[str],
        output_dir: str,
        output_format: str = "geojson",
    ) -> list[dict[str, Any]]:
        """Run inference on multiple GeoTIFFs.

        Args:
            input_paths: List of input GeoTIFF paths.
            output_dir: Directory to write output files.
            output_format: Output format.

        Returns:
            List of result dicts (one per input).
        """
        logger.info("Engine.run_batch: %d files", len(input_paths))
        results = []
        for path in input_paths:
            try:
                result = self.run(path, output_dir=output_dir, output_format=output_format)
                results.append(result)
            except Exception as exc:
                logger.error("Failed to process %s: %s", path, exc)
                results.append({"error": str(exc), "input_path": path})
        return results

    def run_change(
        self,
        before_path: str,
        after_path: str,
        output_dir: str | None = None,
    ) -> dict[str, Any]:
        """Detect changes between two GeoTIFFs.

        Args:
            before_path: Path to the 'before' GeoTIFF.
            after_path: Path to the 'after' GeoTIFF.
            output_dir: Optional output directory.

        Returns:
            Dictionary with change_map, change_stats, geojson, metadata.
        """
        from spikeeo.io.geotiff_reader import read_geotiff
        from spikeeo.tasks.change_detection import ChangeDetectionTask

        logger.info("Engine.run_change: %s vs %s", before_path, after_path)

        bands_before, crs, transform = read_geotiff(before_path)
        bands_after, _, _ = read_geotiff(after_path)

        task = ChangeDetectionTask()
        tiles_before, positions = self._tiler.tile(bands_before)
        tiles_after, _ = self._tiler.tile(bands_after)

        result = task.run(
            self._backbone,
            tiles_before,
            {"crs": crs, "transform": transform, "tiles_after": tiles_after},
        )
        result["metadata"] = {
            "before_path": str(before_path),
            "after_path": str(after_path),
            "crs": str(crs),
            "task": "change_detection",
        }
        return result

    def benchmark(
        self,
        test_data_dir: str,
        cnn_model: str = "resnet18",
    ) -> dict[str, Any]:
        """Benchmark SNN vs CNN on test data.

        Args:
            test_data_dir: Directory containing test GeoTIFF tiles.
            cnn_model: CNN architecture to compare against.

        Returns:
            BenchmarkReport as a dictionary.
        """
        from spikeeo.benchmark.cnn_vs_snn import BenchmarkRunner
        from spikeeo.core.cnn_fallback import CNNFallback
        import torch
        from torch.utils.data import DataLoader, TensorDataset

        logger.info("Engine.benchmark: data_dir=%s cnn=%s", test_data_dir, cnn_model)

        # Build synthetic test loader from directory
        test_dir = Path(test_data_dir)
        tif_files = list(test_dir.glob("*.tif")) + list(test_dir.glob("*.tiff"))

        if tif_files:
            from spikeeo.io.geotiff_reader import read_geotiff
            bands_list = []
            for p in tif_files[:20]:
                try:
                    b, _, _ = read_geotiff(str(p))
                    tiles, _ = self._tiler.tile(b)
                    if tiles:
                        bands_list.append(
                            torch.tensor(tiles[0], dtype=torch.float32).unsqueeze(0)
                        )
                except Exception:
                    pass
            if bands_list:
                x = torch.cat(bands_list, dim=0)
            else:
                x = torch.rand(8, self.num_bands, self.tile_size, self.tile_size)
        else:
            x = torch.rand(8, self.num_bands, self.tile_size, self.tile_size)

        labels = torch.randint(0, self.num_classes, (x.size(0),))
        loader = DataLoader(TensorDataset(x, labels), batch_size=4)

        cnn = CNNFallback(num_bands=self.num_bands, num_classes=self.num_classes)
        runner = BenchmarkRunner()
        report = runner.run(self._backbone, cnn, loader, device=self.device)
        return report.__dict__

    def load_weights(self, path: str) -> None:
        """Load pretrained weights into the backbone.

        Args:
            path: Path to a .pt / .pth checkpoint saved by SNNBackbone.save().
        """
        self._backbone.load(path, device=self.device)
        logger.info("Engine: loaded weights from %s", path)

    def get_cost_report(self) -> dict[str, Any]:
        """Return cumulative hybrid routing cost statistics.

        Returns:
            CostReport as a dict (empty if hybrid=False).
        """
        if self._router is None:
            return {}
        return self._router.get_cost_report().__dict__

    # ── Internal helpers ───────────────────────────────────────

    @torch.no_grad()
    def _infer_tiles(self, tiles: list[np.ndarray]) -> list[tuple[np.ndarray, np.ndarray]]:
        """Run forward pass on a list of tiles.

        Args:
            tiles: List of (C, H, W) numpy arrays.

        Returns:
            List of (class_ids, confidences) pairs.
        """
        results = []
        batch_size = 8
        backbone = self._backbone
        backbone.eval()

        for i in range(0, len(tiles), batch_size):
            batch = np.stack(tiles[i : i + batch_size], axis=0)
            x = torch.tensor(batch, dtype=torch.float32).to(self.device)
            class_ids, confidences = backbone.predict(x)
            results.extend(
                zip(
                    class_ids.cpu().numpy(),
                    confidences.cpu().numpy(),
                )
            )
        return results

    def _write_outputs(
        self,
        result: dict[str, Any],
        output_dir: str,
        output_format: str,
        stem: str,
    ) -> None:
        """Write inference results to disk.

        Args:
            result: Inference result dictionary.
            output_dir: Output directory.
            output_format: Format string.
            stem: Base filename (without extension).
        """
        from spikeeo.io.output_writer import write_geojson, write_json, write_csv

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        if output_format == "geojson" and "geojson" in result:
            write_geojson(result["geojson"], out_dir / f"{stem}.geojson")
        elif output_format == "json":
            safe = {k: v for k, v in result.items() if isinstance(v, (dict, list, str, int, float, bool, type(None)))}
            write_json(safe, out_dir / f"{stem}.json")
        elif output_format == "csv" and "class_map" in result:
            write_csv(result, out_dir / f"{stem}.csv")

    def __repr__(self) -> str:
        """Return a human-readable engine summary."""
        return (
            f"Engine(task={self.task!r}, num_classes={self.num_classes}, "
            f"num_bands={self.num_bands}, device={self.device!r}, "
            f"hybrid={self.use_hybrid})"
        )

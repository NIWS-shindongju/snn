# DEPRECATED: Use scripts/run_benchmark.py instead.
# This file is kept for backward compatibility with Engine-based benchmark workflows.
"""benchmark_run.py: CLI benchmark runner using spikeeo.Engine (deprecated stub).

DEPRECATED: scripts/run_benchmark.py provides a full, EuroSAT-validated benchmark
pipeline with 4 output artefacts (JSON report + 3 charts + cost projection).
Use this script only when benchmarking via the Engine.benchmark() interface.

Usage:
    python scripts/benchmark_run.py --data ./test_tiles/ --output benchmark.json
"""

import argparse
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def main() -> None:
    """CLI entry point for benchmark runner."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="SpikeEO SNN vs CNN Benchmark")
    parser.add_argument("--data", required=True, help="Test data directory")
    parser.add_argument("--classes", type=int, default=2)
    parser.add_argument("--bands", type=int, default=10)
    parser.add_argument("--cnn", default="resnet18")
    parser.add_argument("--output", default="benchmark_report.json")
    args = parser.parse_args()

    import spikeeo

    engine = spikeeo.Engine(task="classification", num_classes=args.classes, num_bands=args.bands)
    report = engine.benchmark(test_data_dir=args.data, cnn_model=args.cnn)

    with open(args.output, "w") as fh:
        json.dump(report, fh, indent=2, default=str)

    logger.info("Benchmark complete:")
    logger.info("  SNN accuracy:    %.3f", report.get("snn_accuracy", 0))
    logger.info("  CNN accuracy:    %.3f", report.get("cnn_accuracy", 0))
    logger.info("  Speedup:         %.1fx", report.get("speedup_ratio", 0))
    logger.info("  Cost saving:     %.1f%%", report.get("cost_saving_estimate_pct", 0))
    logger.info("Report saved to: %s", args.output)


if __name__ == "__main__":
    main()

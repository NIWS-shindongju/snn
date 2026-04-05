"""Benchmark API routes."""

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from spikeeo.api.schemas import BenchmarkRequest, BenchmarkResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/benchmark", tags=["Benchmark"])


@router.post("", response_model=BenchmarkResponse)
async def run_benchmark(request: Request, body: BenchmarkRequest) -> BenchmarkResponse:
    """Run SNN vs CNN benchmark on a test data directory.

    Args:
        request: FastAPI request.
        body: Benchmark configuration.

    Returns:
        BenchmarkResponse with accuracy/speed/cost comparison.
    """
    import spikeeo

    test_dir = Path(body.test_data_dir)
    if not test_dir.exists():
        raise HTTPException(status_code=404, detail=f"Test directory not found: {body.test_data_dir}")

    engine = spikeeo.Engine(
        task="classification",
        num_classes=body.num_classes,
        num_bands=body.num_bands,
    )
    try:
        report = engine.benchmark(test_data_dir=body.test_data_dir, cnn_model=body.cnn_model)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return BenchmarkResponse(
        snn_accuracy=report.get("snn_accuracy", 0.0),
        cnn_accuracy=report.get("cnn_accuracy", 0.0),
        accuracy_gap=report.get("accuracy_gap", 0.0),
        snn_inference_time_ms=report.get("snn_inference_time_ms", 0.0),
        cnn_inference_time_ms=report.get("cnn_inference_time_ms", 0.0),
        speedup_ratio=report.get("speedup_ratio", 0.0),
        energy_saving_ratio=report.get("energy_saving_ratio", 0.0),
        cost_saving_estimate_pct=report.get("cost_saving_estimate_pct", 0.0),
    )

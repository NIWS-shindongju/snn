"""
Accuracy benchmark endpoint — public (no auth required).
Provides transparency about TraceCheck's detection accuracy.
"""
from fastapi import APIRouter
from tracecheck.core.accuracy_validator import get_benchmark_report

router = APIRouter(prefix="/accuracy", tags=["Accuracy"])


@router.get("/benchmark")
async def get_benchmark():
    """
    Returns the official accuracy benchmark report.
    
    Public endpoint — no authentication required.
    Updated quarterly based on validation against Global Forest Watch data.
    """
    return get_benchmark_report()

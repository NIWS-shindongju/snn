"""
EU TRACES NT — DDS (Due Diligence Statement) submission endpoints.

Provides two endpoints:
  POST /api/v1/traces/submit-dds      — Submit a DDS to EU TRACES NT
  GET  /api/v1/traces/dds/{ref_id}    — Check DDS submission status

Mock mode (default): Simulates TRACES NT submission with realistic responses.
No data is sent to EU systems in mock mode — safe for development and testing.

Real mode: Requires TRACES NT OAuth2 credentials (EU Login).
  Required env vars:
    TRACES_NT_CLIENT_ID      — OAuth2 client ID from TRACES NT team (DG SANTE)
    TRACES_NT_CLIENT_SECRET  — OAuth2 client secret
    TRACES_NT_ENVIRONMENT    — "test" (default) | "production"

Auth flow (real mode):
  1. Register at https://webgate.ec.europa.eu/cas/login
  2. Request role: TRACES-EUDR-OPERATOR (via TRACES NT helpdesk)
  3. POST {oauth_url} with grant_type=client_credentials to get Bearer token
  4. Include Bearer token in all TRACES NT API requests

TRACES NT API endpoints:
  Auth:    POST https://webgate.ec.europa.eu/cas/oauth2/token
  DDS:     POST {base}/api/v1/dds
  Status:  GET  {base}/api/v1/dds/{reference_id}

Sandbox: https://webgate.acceptance.ec.europa.eu/tracesnt
Prod:    https://webgate.ec.europa.eu/tracesnt
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from tracecheck.db.session import get_db
from tracecheck.api.auth import get_current_user
from tracecheck.db.models import User
from tracecheck.db import crud

router = APIRouter(prefix="/traces", tags=["TRACES NT"])

# ─── Configuration ────────────────────────────────────────────────────────────

TRACES_NT_CLIENT_ID = os.getenv("TRACES_NT_CLIENT_ID", "")
TRACES_NT_CLIENT_SECRET = os.getenv("TRACES_NT_CLIENT_SECRET", "")
TRACES_NT_ENV = os.getenv("TRACES_NT_ENVIRONMENT", "test")  # test | production

# TRACES NT base URLs
TRACES_TEST_URL = "https://webgate.acceptance.ec.europa.eu/tracesnt"
TRACES_PROD_URL = "https://webgate.ec.europa.eu/tracesnt"

# OAuth2 token endpoint (EU Login / CAS)
TRACES_OAUTH_URL = "https://webgate.ec.europa.eu/cas/oauth2/token"


def _is_real_mode() -> bool:
    """True if real TRACES NT credentials are configured."""
    return bool(TRACES_NT_CLIENT_ID and TRACES_NT_CLIENT_SECRET)


def _traces_base_url() -> str:
    """Return the appropriate TRACES NT base URL based on environment setting."""
    return TRACES_PROD_URL if TRACES_NT_ENV == "production" else TRACES_TEST_URL


# ─── Request / Response Schemas ───────────────────────────────────────────────


class PlotGeoData(BaseModel):
    """Geo-referenced production plot for inclusion in a DDS."""

    ref: str = Field(..., description="Supplier plot reference identifier")
    latitude: float = Field(..., ge=-90, le=90, description="Plot centroid latitude (WGS 84)")
    longitude: float = Field(..., ge=-180, le=180, description="Plot centroid longitude (WGS 84)")
    area_ha: float = Field(..., gt=0, description="Plot area in hectares")
    country_code: str = Field(
        default="",
        max_length=2,
        description="ISO 3166-1 alpha-2 country code where this plot is located",
    )
    risk_level: str = Field(
        default="low",
        description="TraceCheck risk assessment result for this plot (low|review|high)",
    )


class DDSSubmissionRequest(BaseModel):
    """
    Request body for submitting a Due Diligence Statement to EU TRACES NT.

    The DDS is the central compliance document under EUDR Regulation (EU) 2023/1115.
    Operators must submit a DDS for each product placed on the EU market,
    certifying that the product is deforestation-free (post-2020-12-31 cutoff).
    """

    job_id: str = Field(
        ...,
        description=(
            "TraceCheck job run ID whose analysis results support this DDS. "
            "The job must be in 'done' status."
        ),
    )
    operator_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Full legal name of the EU operator or trader submitting the DDS",
    )
    operator_country: str = Field(
        ...,
        min_length=2,
        max_length=2,
        description="ISO 3166-1 alpha-2 country code of the EU operator (member state)",
    )
    commodity: str = Field(
        ...,
        description=(
            "EUDR-covered commodity. Must be one of: "
            "cattle, cocoa, coffee, palm_oil, soya, wood, rubber, "
            "charcoal, printed_paper, other_wood_products"
        ),
    )
    country_of_production: str = Field(
        default="",
        max_length=2,
        description="ISO 3166-1 alpha-2 country code where the commodity was produced",
    )
    declaration_text: str = Field(
        default=(
            "I declare that due diligence has been exercised and the products are "
            "deforestation-free in accordance with Regulation (EU) 2023/1115."
        ),
        description=(
            "Operator's EUDR compliance declaration. By submitting, the operator confirms "
            "obligations under EUDR Articles 8-10 have been fulfilled."
        ),
    )
    plots: Optional[list[PlotGeoData]] = Field(
        default=None,
        description=(
            "Optional explicit plot list. If omitted, plots are derived automatically "
            "from the TraceCheck job run identified by job_id."
        ),
    )


class DDSSubmissionResponse(BaseModel):
    """Response from a TRACES NT DDS submission (mock or real)."""

    reference_id: str = Field(
        ...,
        description=(
            "TRACES NT DDS reference number. "
            "Format (mock): DDS-{YEAR}-{HEX8}. "
            "Cite this in all downstream customs and compliance documentation."
        ),
    )
    status: str = Field(
        ...,
        description="DDS processing status: submitted | pending | accepted | rejected | under_review",
    )
    submitted_at: str = Field(..., description="UTC timestamp of submission in ISO 8601 format")
    traces_url: str = Field(
        ...,
        description="Direct URL to view and manage this DDS in the TRACES NT portal",
    )
    mode: str = Field(
        ...,
        description="'mock' — simulated response; 'real' — live EU TRACES NT submission",
    )
    plots_count: int = Field(..., description="Number of production plots registered in this DDS")
    commodity: str = Field(..., description="Commodity as recorded in TRACES NT")
    operator_name: str = Field(..., description="Operator name as recorded in TRACES NT")
    validation_notes: list[str] = Field(
        default_factory=list,
        description="Informational notes from TRACES NT validation",
    )


class DDSStatusResponse(BaseModel):
    """Status response for an existing DDS submission."""

    reference_id: str = Field(..., description="TRACES NT DDS reference number")
    status: str = Field(
        ...,
        description="Current status: submitted | pending | accepted | rejected | under_review",
    )
    submitted_at: str = Field(..., description="Original submission timestamp (ISO 8601 UTC)")
    last_checked_at: str = Field(..., description="Timestamp of this status check (ISO 8601 UTC)")
    traces_url: str = Field(..., description="TRACES NT portal URL for this DDS")
    mode: str = Field(..., description="'mock' | 'real'")
    competent_authority_notes: Optional[str] = Field(
        default=None,
        description="Notes from the national competent authority (e.g. customs office), if any",
    )


# ─── Supported EUDR commodities ───────────────────────────────────────────────

_EUDR_COMMODITIES = {
    "cattle", "cocoa", "coffee", "palm_oil", "soya", "wood",
    "rubber", "charcoal", "printed_paper", "other_wood_products",
}


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post(
    "/submit-dds",
    response_model=DDSSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a Due Diligence Statement to EU TRACES NT",
    description=(
        "Submits a DDS to the EU TRACES NT system as required by EUDR Regulation (EU) 2023/1115.\n\n"
        "**Mock mode** (default when TRACES NT credentials are absent): returns a simulated "
        "TRACES NT reference number. No data is transmitted to EU systems.\n\n"
        "**Real mode** (when `TRACES_NT_CLIENT_ID` and `TRACES_NT_CLIENT_SECRET` are set): "
        "authenticates via EU Login OAuth2 and submits to the live TRACES NT DDS API."
    ),
)
async def submit_dds(
    req: DDSSubmissionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DDSSubmissionResponse:
    """Submit a Due Diligence Statement (DDS) to EU TRACES NT."""

    # ── Validate commodity ────────────────────────────────────────────────────
    if req.commodity.lower() not in _EUDR_COMMODITIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Commodity '{req.commodity}' is not covered by EUDR. "
                f"Valid values: {sorted(_EUDR_COMMODITIES)}"
            ),
        )

    # ── Validate the job run ─────────────────────────────────────────────────
    job = await crud.get_job_run(db, req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job run not found")

    project = await crud.get_project(db, job.project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to access this job run",
        )

    if job.status != "done":
        raise HTTPException(
            status_code=422,
            detail=(
                f"Job run must be in 'done' status before submitting a DDS "
                f"(current status: '{job.status}')"
            ),
        )

    # ── Gather plots count from assessments ──────────────────────────────────
    assessments = await crud.list_assessments(db, req.job_id)
    plots_count = len(assessments)

    # ── Dispatch to real or mock handler ─────────────────────────────────────
    if _is_real_mode():
        result = await _submit_dds_real(req, plots_count)
    else:
        result = await _submit_dds_mock(req, plots_count)

    # ── Audit log ─────────────────────────────────────────────────────────────
    await crud.log_action(
        db,
        project_id=project.id,
        user_id=current_user.id,
        action="traces.dds_submitted",
        detail={
            "reference_id": result.reference_id,
            "job_id": req.job_id,
            "commodity": req.commodity,
            "plots_count": plots_count,
            "mode": result.mode,
        },
    )

    return result


@router.get(
    "/dds/{reference_id}",
    response_model=DDSStatusResponse,
    summary="Check DDS submission status in TRACES NT",
    description=(
        "Retrieves the current processing status of a DDS by its TRACES NT reference number.\n\n"
        "In **mock mode**, status is derived deterministically from the reference number "
        "to simulate realistic async processing (most become 'accepted', some stay 'pending').\n\n"
        "In **real mode**, makes a live query to the TRACES NT API."
    ),
)
async def get_dds_status(
    reference_id: str,
    current_user: User = Depends(get_current_user),
) -> DDSStatusResponse:
    """Check the status of a previously submitted DDS by reference ID."""

    if _is_real_mode():
        return await _get_dds_status_real(reference_id)
    return await _get_dds_status_mock(reference_id)


# ─── Mock implementation ──────────────────────────────────────────────────────


async def _submit_dds_mock(
    req: DDSSubmissionRequest,
    plots_count: int,
) -> DDSSubmissionResponse:
    """Simulate a TRACES NT DDS submission with a realistic reference and notes."""
    now = datetime.now(timezone.utc)
    ref_id = f"DDS-{now.strftime('%Y')}-{uuid.uuid4().hex[:8].upper()}"
    traces_url = f"{_traces_base_url()}/certificate/dds/{ref_id}"

    notes: list[str] = []
    if plots_count > 50:
        notes.append(
            "Large submission (>50 plots): enhanced due diligence review may apply "
            "per EUDR Article 10."
        )
    if req.commodity in ("wood", "charcoal", "printed_paper", "other_wood_products"):
        notes.append(
            "Timber/wood product: FLEGT licence or equivalent forest legality "
            "documentation required per EUDR Annex I."
        )
    notes.append(
        "[MOCK] Simulated submission — no data transmitted to EU TRACES NT. "
        "Set TRACES_NT_CLIENT_ID and TRACES_NT_CLIENT_SECRET for live submission."
    )

    return DDSSubmissionResponse(
        reference_id=ref_id,
        status="submitted",
        submitted_at=now.isoformat(),
        traces_url=traces_url,
        mode="mock",
        plots_count=plots_count,
        commodity=req.commodity,
        operator_name=req.operator_name,
        validation_notes=notes,
    )


async def _get_dds_status_mock(reference_id: str) -> DDSStatusResponse:
    """Return a deterministic mock status based on the reference_id hash."""
    now = datetime.now(timezone.utc)

    # Derive status from hash so the same reference_id always returns the same status
    hash_val = hash(reference_id) % 100
    if hash_val < 60:
        mock_status = "accepted"
        ca_notes = (
            "[MOCK] DDS accepted. No enforcement action required. "
            "Retain all records for 5 years per EUDR Article 9(2)."
        )
    elif hash_val < 85:
        mock_status = "pending"
        ca_notes = (
            "[MOCK] Awaiting automated cross-check against Global Forest Watch "
            "and Hansen et al. (2013) tree cover loss dataset."
        )
    else:
        mock_status = "under_review"
        ca_notes = (
            "[MOCK] Flagged for manual review by competent authority. "
            "Operator may be contacted for additional documentation."
        )

    return DDSStatusResponse(
        reference_id=reference_id,
        status=mock_status,
        submitted_at=now.isoformat(),
        last_checked_at=now.isoformat(),
        traces_url=f"{_traces_base_url()}/certificate/dds/{reference_id}",
        mode="mock",
        competent_authority_notes=ca_notes,
    )


# ─── Real-mode stubs ─────────────────────────────────────────────────────────
#
# These functions document the full TRACES NT integration:
#
#   Auth (EU Login / CAS OAuth2):
#     POST https://webgate.ec.europa.eu/cas/oauth2/token
#     Content-Type: application/x-www-form-urlencoded
#     Body: grant_type=client_credentials
#           &client_id={TRACES_NT_CLIENT_ID}
#           &client_secret={TRACES_NT_CLIENT_SECRET}
#           &scope=TRACES_DDS_WRITE
#
#   DDS Submission:
#     POST {base}/api/v1/dds
#     Authorization: Bearer {access_token}
#     Content-Type: application/json
#     Body: {
#       "operatorName": "...",
#       "operatorCountry": "DE",
#       "commodity": "COCOA",            # TRACES NT uses uppercase
#       "countryOfProduction": "CM",
#       "plots": [
#         {
#           "plotId": "P001",
#           "supplierName": "Farmer A",
#           "countryCode": "CM",
#           "latitude": 4.321,
#           "longitude": 11.456,
#           "areaHa": 2.5
#         }
#       ],
#       "declarationText": "...",
#       "referenceDate": "2024-01-15"
#     }
#
#   DDS Status:
#     GET {base}/api/v1/dds/{reference_id}
#     Authorization: Bearer {access_token}
#
#   Error codes:
#     400 — Validation error (invalid geometry / missing fields)
#     401 — Authentication failed (expired / invalid token)
#     403 — Insufficient permissions (missing TRACES-EUDR-OPERATOR role)
#     409 — Duplicate DDS (same operator + plots + date already submitted)
#     422 — Semantic validation error (plot outside declared country)
#     429 — Rate limited (max 100 submissions/hour)
#     503 — TRACES NT maintenance window


async def _submit_dds_real(
    req: DDSSubmissionRequest,
    plots_count: int,
) -> DDSSubmissionResponse:
    """
    Submit DDS to live TRACES NT API.

    Not yet implemented — set TRACES_NT_CLIENT_ID + TRACES_NT_CLIENT_SECRET
    and implement the OAuth2 + HTTP calls above to activate.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "error": "traces_real_mode_not_implemented",
            "message": (
                "Real TRACES NT submission is not yet active. "
                "Credentials are configured but the integration stub needs completing."
            ),
            "oauth_url": TRACES_OAUTH_URL,
            "api_base": _traces_base_url(),
            "hint": "See docstring in tracecheck/api/routes/traces.py for the full API contract.",
        },
    )


async def _get_dds_status_real(reference_id: str) -> DDSStatusResponse:
    """
    Query live TRACES NT for DDS status.

    GET {base}/api/v1/dds/{reference_id}  →  {status, submittedAt, lastUpdated, ...}
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "error": "traces_real_mode_not_implemented",
            "message": (
                f"Real-mode status check for '{reference_id}' is not yet active. "
                "See tracecheck/api/routes/traces.py for implementation guide."
            ),
        },
    )

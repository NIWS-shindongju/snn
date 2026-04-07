"""Webhook management endpoints — high-risk alert notifications."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tracecheck.api.auth import get_current_user
from tracecheck.db.models import User, Webhook
from tracecheck.db.session import get_db

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


# ─── Schemas ──────────────────────────────────────────────────────────────────

VALID_EVENTS = {"job.completed", "plot.high_risk", "export.created", "job.failed"}


class WebhookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=8)
    secret: Optional[str] = None
    events: list[str] = Field(default_factory=lambda: ["job.completed", "plot.high_risk"])


class WebhookOut(BaseModel):
    id: str
    name: str
    url: str
    events: Optional[Any]
    status: str
    last_fired_at: Optional[datetime]
    last_response_code: Optional[int]
    failure_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    events: Optional[list[str]] = None
    status: Optional[str] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("", response_model=WebhookOut, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: WebhookCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookOut:
    """Register a new webhook endpoint (pro/enterprise tier required)."""
    # Validate events
    invalid = set(body.events) - VALID_EVENTS
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid event types: {invalid}. Valid: {VALID_EVENTS}",
        )

    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Must belong to an organisation to use webhooks",
        )

    wh = Webhook(
        org_id=current_user.org_id,
        created_by=current_user.id,
        name=body.name,
        url=body.url,
        secret=body.secret,
        events=body.events,
    )
    db.add(wh)
    await db.flush()
    await db.commit()
    await db.refresh(wh)
    return WebhookOut.model_validate(wh)


@router.get("", response_model=list[WebhookOut])
async def list_webhooks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WebhookOut]:
    """List all webhooks for current user's organisation."""
    if not current_user.org_id:
        return []
    result = await db.execute(
        select(Webhook).where(Webhook.org_id == current_user.org_id)
    )
    return [WebhookOut.model_validate(w) for w in result.scalars().all()]


@router.patch("/{webhook_id}", response_model=WebhookOut)
async def update_webhook(
    webhook_id: str,
    body: WebhookUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookOut:
    """Update a webhook endpoint."""
    wh = await db.get(Webhook, webhook_id)
    if not wh or wh.org_id != current_user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    if body.name is not None:
        wh.name = body.name
    if body.url is not None:
        wh.url = body.url
    if body.events is not None:
        wh.events = body.events
    if body.status in ("active", "disabled"):
        wh.status = body.status

    await db.flush()
    await db.commit()
    await db.refresh(wh)
    return WebhookOut.model_validate(wh)


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a webhook endpoint."""
    wh = await db.get(Webhook, webhook_id)
    if not wh or wh.org_id != current_user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    await db.delete(wh)
    await db.commit()


@router.post("/{webhook_id}/test", status_code=status.HTTP_200_OK)
async def test_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send a test ping to the webhook URL."""
    wh = await db.get(Webhook, webhook_id)
    if not wh or wh.org_id != current_user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    payload = {
        "event": "test.ping",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "webhook_id": webhook_id,
        "message": "TraceCheck webhook test — if you receive this, your endpoint is working!",
    }

    try:
        result = await _fire_webhook(wh, payload)
        return {"status": "sent", "response_code": result}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


# ─── Internal webhook dispatcher ─────────────────────────────────────────────

async def _fire_webhook(wh: Webhook, payload: dict[str, Any]) -> int:
    """POST payload to webhook URL. Returns HTTP status code."""
    import httpx

    body = json.dumps(payload, ensure_ascii=False, default=str)
    headers = {"Content-Type": "application/json", "User-Agent": "TraceCheck-Webhook/1.0"}

    if wh.secret:
        sig = hmac.new(wh.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        headers["X-TraceCheck-Signature"] = f"sha256={sig}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(wh.url, content=body, headers=headers)
            return r.status_code
    except Exception as exc:
        logger.warning("Webhook %s delivery failed: %s", wh.id, exc)
        raise


async def dispatch_event(
    event: str,
    payload: dict[str, Any],
    org_id: str,
    db: AsyncSession,
) -> None:
    """Find active webhooks subscribed to `event` and fire them."""
    result = await db.execute(
        select(Webhook).where(
            Webhook.org_id == org_id,
            Webhook.status == "active",
        )
    )
    webhooks = result.scalars().all()

    full_payload = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **payload,
    }

    for wh in webhooks:
        subscribed = wh.events or []
        if event not in subscribed:
            continue
        try:
            code = await _fire_webhook(wh, full_payload)
            wh.last_fired_at = datetime.now(timezone.utc)
            wh.last_response_code = code
            if 200 <= code < 300:
                wh.failure_count = 0
            else:
                wh.failure_count += 1
        except Exception:
            wh.failure_count += 1
            wh.last_fired_at = datetime.now(timezone.utc)
            wh.last_response_code = 0
        await db.flush()

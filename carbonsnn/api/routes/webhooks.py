"""Webhook management endpoints."""

import logging

from fastapi import APIRouter, HTTPException, status

from carbonsnn.api.deps import CurrentUserDep, DbDep
from carbonsnn.api.schemas import WebhookCreate, WebhookResponse
from carbonsnn.db import crud

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: WebhookCreate,
    project_id: str,
    user: CurrentUserDep,
    db: DbDep,
) -> WebhookResponse:
    """Register a new webhook endpoint for a project.

    Args:
        body: Webhook configuration.
        project_id: Target project UUID (query parameter).
        user: Authenticated user.
        db: Database session.

    Returns:
        Created webhook record.
    """
    project = await crud.get_project(db, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    webhook = await crud.create_webhook(
        db=db,
        project_id=project_id,
        url=body.url,
        secret=body.secret,
        events=body.events,
    )
    logger.info("Webhook created for project %s: %s", project_id, body.url)
    return WebhookResponse.model_validate(webhook)


@router.get("/project/{project_id}", response_model=list[WebhookResponse])
async def list_webhooks(
    project_id: str,
    user: CurrentUserDep,
    db: DbDep,
) -> list[WebhookResponse]:
    """List all active webhooks for a project.

    Args:
        project_id: Project UUID.
        user: Authenticated user.
        db: Database session.

    Returns:
        List of webhook records.
    """
    project = await crud.get_project(db, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    webhooks = await crud.list_webhooks(db, project_id)
    return [WebhookResponse.model_validate(w) for w in webhooks]


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: str,
    user: CurrentUserDep,
    db: DbDep,
) -> None:
    """Remove a webhook registration.

    Args:
        webhook_id: Webhook UUID.
        user: Authenticated user.
        db: Database session.
    """
    from carbonsnn.db.models import Webhook

    webhook = await db.get(Webhook, webhook_id)
    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    project = await crud.get_project(db, webhook.project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    await crud.delete_webhook(db, webhook_id)
    logger.info("Webhook deleted: %s", webhook_id)


async def dispatch_webhook(
    url: str,
    secret: str,
    event: str,
    payload: dict,
) -> bool:
    """Send an outbound webhook notification with HMAC signature.

    Args:
        url: Target URL.
        secret: HMAC signing secret.
        event: Event type string.
        payload: JSON-serialisable event payload.

    Returns:
        True if delivery succeeded (2xx response).
    """
    import hashlib
    import hmac
    import json
    import time

    import httpx
    from tenacity import retry, stop_after_attempt, wait_exponential

    body = json.dumps({"event": event, "data": payload, "timestamp": int(time.time())})
    signature = hmac.new(
        secret.encode(), body.encode(), hashlib.sha256
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-CarbonSNN-Signature": f"sha256={signature}",
        "X-CarbonSNN-Event": event,
    }

    from carbonsnn.config import get_settings
    settings = get_settings()

    try:
        async with httpx.AsyncClient(timeout=settings.webhook_timeout_seconds) as client:
            response = await client.post(url, content=body, headers=headers)
            response.raise_for_status()
            logger.info("Webhook delivered to %s (status=%d)", url, response.status_code)
            return True
    except Exception as exc:
        logger.error("Webhook delivery failed to %s: %s", url, exc)
        return False

"""CRUD operations for SpikeEO ORM models."""

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from spikeeo.db.models import APIKey, APIUsage, InferenceJob, User

logger = logging.getLogger(__name__)


def _hash_key(raw_key: str) -> str:
    """SHA-256 hash a raw API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def create_user(db: AsyncSession, email: str, hashed_password: str, is_superuser: bool = False) -> User:
    """Create and persist a new User.

    Args:
        db: Database session.
        email: Unique email.
        hashed_password: Bcrypt-hashed password.
        is_superuser: Admin flag.

    Returns:
        Newly created User instance.
    """
    user = User(email=email, hashed_password=hashed_password, is_superuser=is_superuser)
    db.add(user)
    await db.flush()
    logger.info("Created user: %s", email)
    return user


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Fetch a User by email.

    Args:
        db: Database session.
        email: Email to look up.

    Returns:
        User or None.
    """
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """Fetch a User by UUID.

    Args:
        db: Database session.
        user_id: UUID string.

    Returns:
        User or None.
    """
    return await db.get(User, user_id)


async def create_api_key(db: AsyncSession, user_id: str, name: str) -> tuple[str, APIKey]:
    """Generate and persist a new API key.

    Args:
        db: Database session.
        user_id: Owning user UUID.
        name: Human-readable key label.

    Returns:
        Tuple of (raw_key, APIKey instance).
    """
    raw_key = f"spk_{secrets.token_urlsafe(32)}"
    api_key = APIKey(key_hash=_hash_key(raw_key), name=name, user_id=user_id)
    db.add(api_key)
    await db.flush()
    logger.info("Created API key '%s' for user %s", name, user_id)
    return raw_key, api_key


async def get_api_key_by_raw(db: AsyncSession, raw_key: str) -> APIKey | None:
    """Retrieve an active API key by the raw key value.

    Args:
        db: Database session.
        raw_key: Unhashed raw key string.

    Returns:
        Active APIKey or None.
    """
    key_hash = _hash_key(raw_key)
    result = await db.execute(
        select(APIKey).where(APIKey.key_hash == key_hash, APIKey.is_active == True)  # noqa: E712
    )
    return result.scalar_one_or_none()


async def create_inference_job(
    db: AsyncSession,
    owner_id: str,
    task: str,
    input_filename: str | None = None,
) -> InferenceJob:
    """Create a pending inference job record.

    Args:
        db: Database session.
        owner_id: Owning user UUID.
        task: Inference task type.
        input_filename: Original filename.

    Returns:
        Newly created InferenceJob.
    """
    job = InferenceJob(owner_id=owner_id, task=task, input_filename=input_filename, status="pending")
    db.add(job)
    await db.flush()
    return job


async def record_api_usage(
    db: AsyncSession,
    api_key_id: str,
    endpoint: str,
    method: str,
    status_code: int,
    latency_ms: float = 0.0,
) -> None:
    """Log an API call for auditing.

    Args:
        db: Database session.
        api_key_id: API key UUID.
        endpoint: Request path.
        method: HTTP method.
        status_code: HTTP response status.
        latency_ms: Processing latency.
    """
    usage = APIUsage(
        api_key_id=api_key_id,
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        latency_ms=latency_ms,
    )
    db.add(usage)
    await db.flush()

"""API key authentication and password utilities."""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from carbonsnn.db.crud import get_api_key_by_raw
from carbonsnn.db.models import APIKey, User

logger = logging.getLogger(__name__)

# ── Password hashing ──────────────────────────────────────

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Hash a plain-text password with bcrypt.

    Args:
        plain: Plain-text password.

    Returns:
        Bcrypt-hashed string.
    """
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a stored hash.

    Args:
        plain: Plain-text password.
        hashed: Stored bcrypt hash.

    Returns:
        True if the password matches.
    """
    return _pwd_context.verify(plain, hashed)


# ── API Key extraction ────────────────────────────────────

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_api_key(
    raw_key: str | None = Security(_api_key_header),
    db: AsyncSession | None = None,
) -> APIKey:
    """Extract and validate the API key from the X-API-Key header.

    Args:
        raw_key: Raw key string from the request header.
        db: Injected database session.

    Returns:
        Validated APIKey ORM instance.

    Raises:
        HTTPException 401: If the key is missing, invalid, or expired.
    """
    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Include X-API-Key header.",
        )

    api_key = await get_api_key_by_raw(db, raw_key)  # type: ignore[arg-type]

    if not api_key:
        logger.warning("Invalid API key attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key.",
        )

    # Check expiry
    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired.",
        )

    # Update last used timestamp (fire-and-forget)
    api_key.last_used_at = datetime.now(timezone.utc)

    return api_key

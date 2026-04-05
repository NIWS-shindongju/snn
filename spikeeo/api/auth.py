"""API key authentication and password utilities."""

import logging
import warnings
from datetime import datetime, timezone

warnings.filterwarnings("ignore", message=".*error reading bcrypt version.*")

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from spikeeo.db.crud import get_api_key_by_raw
from spikeeo.db.models import APIKey

logger = logging.getLogger(__name__)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


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


async def get_current_api_key(
    raw_key: str | None = Security(_api_key_header),
    db: AsyncSession | None = None,
) -> APIKey:
    """Validate the X-API-Key header value.

    Args:
        raw_key: Raw key string from header.
        db: Database session.

    Returns:
        Validated APIKey ORM instance.

    Raises:
        HTTPException 401: If key is missing, invalid, or expired.
    """
    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Include X-API-Key header.",
        )
    api_key = await get_api_key_by_raw(db, raw_key)  # type: ignore[arg-type]
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")
    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key expired.")
    api_key.last_used_at = datetime.now(timezone.utc)
    return api_key

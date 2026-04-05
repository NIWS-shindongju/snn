"""FastAPI dependency injection helpers."""

import logging
import time
from typing import Annotated, AsyncGenerator

from fastapi import Depends, HTTPException, Request, Security, status
from sqlalchemy.ext.asyncio import AsyncSession

from carbonsnn.api.auth import _api_key_header, get_current_api_key
from carbonsnn.db.crud import get_api_key_by_raw, get_user_by_id, record_api_usage
from carbonsnn.db.models import APIKey, User
from carbonsnn.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# DB Session
# ──────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session.

    Yields:
        AsyncSession committed on success, rolled back on error.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


DbDep = Annotated[AsyncSession, Depends(get_db)]


# ──────────────────────────────────────────────────────────
# Current API Key + User
# ──────────────────────────────────────────────────────────

async def get_api_key(
    raw_key: str | None = Security(_api_key_header),
    db: AsyncSession = Depends(get_db),
) -> APIKey:
    """Dependency that validates the X-API-Key header.

    Args:
        raw_key: Extracted header value.
        db: Database session.

    Returns:
        Validated APIKey ORM instance.
    """
    return await get_current_api_key(raw_key=raw_key, db=db)


ApiKeyDep = Annotated[APIKey, Depends(get_api_key)]


async def get_current_user(
    api_key: ApiKeyDep,
    db: DbDep,
) -> User:
    """Resolve the User associated with the current API key.

    Args:
        api_key: Validated API key.
        db: Database session.

    Returns:
        Active User ORM instance.

    Raises:
        HTTPException 401: If the user is inactive or deleted.
    """
    user = await get_user_by_id(db, api_key.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account inactive or deleted.",
        )
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


# ──────────────────────────────────────────────────────────
# Pagination
# ──────────────────────────────────────────────────────────

class PaginationParams:
    """Common pagination query parameters.

    Attributes:
        skip: Number of records to skip.
        limit: Maximum number of records to return.
    """

    def __init__(self, skip: int = 0, limit: int = 50) -> None:
        if skip < 0:
            raise HTTPException(status_code=400, detail="skip must be >= 0")
        if not (1 <= limit <= 200):
            raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
        self.skip = skip
        self.limit = limit


PageDep = Annotated[PaginationParams, Depends(PaginationParams)]

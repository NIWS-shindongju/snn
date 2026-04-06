"""JWT-based authentication utilities for TraceCheck."""

from __future__ import annotations

import warnings
from datetime import datetime, timedelta, timezone
from typing import Any

warnings.filterwarnings("ignore", message=".*error reading bcrypt version.*")

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from tracecheck.config import settings
from tracecheck.db.crud import get_user_by_id
from tracecheck.db.models import User
from tracecheck.db.session import get_db

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ─────────────────────────────────────────────────────────────────────────────
# Password helpers
# ─────────────────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ─────────────────────────────────────────────────────────────────────────────
# JWT helpers
# ─────────────────────────────────────────────────────────────────────────────

def create_access_token(data: dict[str, Any]) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI dependency
# ─────────────────────────────────────────────────────────────────────────────

async def get_current_user(
    token: str = Depends(_oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate Bearer JWT and return the authenticated user."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = await get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise credentials_exc
    return user

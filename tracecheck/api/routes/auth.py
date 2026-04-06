"""Auth endpoints: register / login / me.

Supports two login methods:
  1. POST /auth/login   — OAuth2 form-data (username=email, password=...)
  2. POST /auth/token   — JSON body {"email": "...", "password": "..."}
     (also aliased at /auth/login/json for Streamlit / API clients)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from tracecheck.api.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from tracecheck.api.schemas import RegisterRequest, TokenResponse, UserOut
from tracecheck.db.crud import create_user, get_user_by_email
from tracecheck.db.models import User
from tracecheck.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


# ── helpers ───────────────────────────────────────────────────────────────────

async def _authenticate(db: AsyncSession, email: str, password: str) -> User:
    """Shared auth logic — raises 401 on failure."""
    user = await get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    return user


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> User:
    """Create a new user account."""
    existing = await get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = await create_user(
        db,
        email=body.email,
        hashed_password=hash_password(body.password),
        org_name=body.org_name,
    )
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate via OAuth2 form-data and return a JWT.

    Use email as the ``username`` field (required by OAuth2 spec).
    """
    user = await _authenticate(db, form.username, form.password)
    token = create_access_token({"sub": user.id, "email": user.email})
    return TokenResponse(access_token=token)


class _JsonLoginRequest(BaseModel):
    email: str
    password: str


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Login with JSON body (email + password)",
)
async def login_json(
    body: _JsonLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate via JSON body ``{email, password}`` — convenience for API clients.

    Equivalent to POST /auth/login but accepts JSON instead of form-data.
    """
    user = await _authenticate(db, body.email, body.password)
    token = create_access_token({"sub": user.id, "email": user.email})
    return TokenResponse(access_token=token)


# Alias for legacy / Streamlit usage
@router.post(
    "/login/json",
    response_model=TokenResponse,
    include_in_schema=False,
)
async def login_json_alias(
    body: _JsonLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    return await login_json(body, db)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> User:
    """Return the currently authenticated user."""
    return current_user

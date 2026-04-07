"""Organization management endpoints — multi-tenancy & RBAC."""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from tracecheck.api.auth import get_current_user
from tracecheck.db.models import Organization, Subscription, User
from tracecheck.db.session import get_db

router = APIRouter(prefix="/organizations", tags=["organizations"])


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class OrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: Optional[str] = None
    domain: Optional[str] = None


class OrgOut(BaseModel):
    id: str
    name: str
    slug: str
    domain: Optional[str]
    brand_name: Optional[str]
    status: str

    model_config = {"from_attributes": True}


class SubscriptionOut(BaseModel):
    id: str
    org_id: str
    tier: str
    max_projects: int
    max_plots_per_run: int
    max_users: int
    api_access: bool
    webhook_access: bool
    white_label: bool
    pdf_reports: bool
    billing_status: str

    model_config = {"from_attributes": True}


class UserInvite(BaseModel):
    email: str
    role: str = Field(default="analyst")


class UserRoleUpdate(BaseModel):
    role: str


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:80] if slug else "org"


TIER_LIMITS = {
    "free":       {"max_projects": 3,  "max_plots_per_run": 50,   "max_users": 1,  "api_access": False, "webhook_access": False, "white_label": False},
    "pro":        {"max_projects": 20, "max_plots_per_run": 500,  "max_users": 5,  "api_access": True,  "webhook_access": True,  "white_label": False},
    "enterprise": {"max_projects": -1, "max_plots_per_run": -1,   "max_users": -1, "api_access": True,  "webhook_access": True,  "white_label": True},
}


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("", response_model=OrgOut, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrgCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgOut:
    """Create a new organisation and assign current user as admin."""
    slug = body.slug or _slugify(body.name)

    # Ensure unique slug
    existing = await db.execute(select(Organization).where(Organization.slug == slug))
    if existing.scalar_one_or_none():
        slug = f"{slug}-{current_user.id[:6]}"

    org = Organization(name=body.name, slug=slug, domain=body.domain)
    db.add(org)
    await db.flush()

    # Assign free subscription
    sub = Subscription(org_id=org.id, tier="free", **{k: v for k, v in TIER_LIMITS["free"].items()})
    db.add(sub)

    # Assign current user as admin of this org
    current_user.org_id = org.id
    current_user.role = "admin"

    await db.flush()
    await db.commit()
    await db.refresh(org)
    return OrgOut.model_validate(org)


@router.get("/me", response_model=OrgOut)
async def get_my_organization(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgOut:
    """Get the current user's organisation."""
    if not current_user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No organisation assigned")
    org = await db.get(Organization, current_user.org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")
    return OrgOut.model_validate(org)


@router.get("/me/subscription", response_model=SubscriptionOut)
async def get_my_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionOut:
    """Get subscription/plan details for current user's organisation."""
    if not current_user.org_id:
        # Return default free limits for users without org
        return SubscriptionOut(
            id="default", org_id="", tier="free",
            billing_status="active", pdf_reports=True,
            **TIER_LIMITS["free"],
        )
    result = await db.execute(
        select(Subscription).where(Subscription.org_id == current_user.org_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return SubscriptionOut(
            id="default", org_id=current_user.org_id, tier="free",
            billing_status="active", pdf_reports=True,
            **TIER_LIMITS["free"],
        )
    return SubscriptionOut.model_validate(sub)


@router.get("/me/members")
async def list_org_members(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all members in the current user's organisation (admin only)."""
    if current_user.role not in ("admin",) and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    if not current_user.org_id:
        return []
    result = await db.execute(
        select(User).where(User.org_id == current_user.org_id)
    )
    members = result.scalars().all()
    return [
        {"id": u.id, "email": u.email, "full_name": u.full_name,
         "role": u.role, "is_active": u.is_active, "created_at": u.created_at.isoformat()}
        for u in members
    ]


@router.patch("/me/members/{user_id}/role")
async def update_member_role(
    user_id: str,
    body: UserRoleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update a member's role (admin only). Roles: admin | analyst | viewer."""
    if current_user.role != "admin" and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    if body.role not in ("admin", "analyst", "viewer"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid role")

    user = await db.get(User, user_id)
    if not user or user.org_id != current_user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in org")

    user.role = body.role
    await db.flush()
    await db.commit()
    return {"id": user.id, "email": user.email, "role": user.role}

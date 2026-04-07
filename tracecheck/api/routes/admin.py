"""Platform admin endpoints — superuser only."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tracecheck.api.auth import get_current_user
from tracecheck.db.models import (
    JobRun, Organization, Plot, PlotAssessment,
    Project, RegulatoryFramework, Subscription, User,
)
from tracecheck.db.session import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


async def _require_superuser(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser access required")
    return current_user


@router.get("/stats")
async def platform_stats(
    _: User = Depends(_require_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Platform-wide statistics dashboard."""
    users_count = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    orgs_count  = (await db.execute(select(func.count()).select_from(Organization))).scalar() or 0
    projects    = (await db.execute(select(func.count()).select_from(Project))).scalar() or 0
    plots       = (await db.execute(select(func.count()).select_from(Plot))).scalar() or 0
    jobs        = (await db.execute(select(func.count()).select_from(JobRun))).scalar() or 0
    assessments = (await db.execute(select(func.count()).select_from(PlotAssessment))).scalar() or 0
    high_risk   = (await db.execute(
        select(func.count()).select_from(PlotAssessment)
        .where(PlotAssessment.risk_level == "high")
    )).scalar() or 0

    # Subscription tier breakdown
    tier_rows = (await db.execute(
        select(Subscription.tier, func.count().label("n"))
        .group_by(Subscription.tier)
    )).all()
    tiers = {row.tier: row.n for row in tier_rows}

    return {
        "users": users_count,
        "organizations": orgs_count,
        "projects": projects,
        "total_plots": plots,
        "analysis_jobs": jobs,
        "total_assessments": assessments,
        "high_risk_assessments": high_risk,
        "subscriptions_by_tier": tiers,
    }


@router.get("/users")
async def list_all_users(
    _: User = Depends(_require_superuser),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all platform users."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [
        {
            "id": u.id, "email": u.email, "org_name": u.org_name,
            "org_id": u.org_id, "role": u.role, "is_active": u.is_active,
            "is_superuser": u.is_superuser, "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.patch("/users/{user_id}/activate")
async def toggle_user_active(
    user_id: str,
    active: bool = True,
    _: User = Depends(_require_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Activate or deactivate a user account."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_active = active
    await db.flush()
    await db.commit()
    return {"id": user.id, "email": user.email, "is_active": user.is_active}


@router.get("/organizations")
async def list_all_organizations(
    _: User = Depends(_require_superuser),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all organisations with subscription info."""
    orgs = (await db.execute(select(Organization).order_by(Organization.created_at.desc()))).scalars().all()
    out = []
    for org in orgs:
        sub = (await db.execute(
            select(Subscription).where(Subscription.org_id == org.id)
        )).scalar_one_or_none()
        user_count = (await db.execute(
            select(func.count()).select_from(User).where(User.org_id == org.id)
        )).scalar() or 0
        out.append({
            "id": org.id, "name": org.name, "slug": org.slug, "status": org.status,
            "user_count": user_count,
            "tier": sub.tier if sub else "free",
            "billing_status": sub.billing_status if sub else "active",
            "created_at": org.created_at.isoformat(),
        })
    return out


@router.patch("/organizations/{org_id}/subscription")
async def update_subscription_tier(
    org_id: str,
    tier: str,
    _: User = Depends(_require_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update an organisation's subscription tier."""
    if tier not in ("free", "pro", "enterprise"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid tier")

    LIMITS = {
        "free":       {"max_projects": 3,  "max_plots_per_run": 50,   "max_users": 1,  "api_access": False, "webhook_access": False, "white_label": False},
        "pro":        {"max_projects": 20, "max_plots_per_run": 500,  "max_users": 5,  "api_access": True,  "webhook_access": True,  "white_label": False},
        "enterprise": {"max_projects": -1, "max_plots_per_run": -1,   "max_users": -1, "api_access": True,  "webhook_access": True,  "white_label": True},
    }

    result = await db.execute(select(Subscription).where(Subscription.org_id == org_id))
    sub = result.scalar_one_or_none()
    if not sub:
        sub = Subscription(org_id=org_id, tier=tier, **LIMITS[tier])
        db.add(sub)
    else:
        sub.tier = tier
        for k, v in LIMITS[tier].items():
            setattr(sub, k, v)

    await db.flush()
    await db.commit()
    return {"org_id": org_id, "tier": tier, **LIMITS[tier]}


# ── Regulatory Frameworks ─────────────────────────────────────────────────────

@router.get("/frameworks")
async def list_frameworks(
    _: User = Depends(_require_superuser),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all registered regulatory frameworks."""
    result = await db.execute(select(RegulatoryFramework))
    frameworks = result.scalars().all()
    return [
        {
            "id": f.id, "code": f.code, "name": f.name, "status": f.status,
            "default_cutoff_date": f.default_cutoff_date,
            "applicable_commodities": f.applicable_commodities,
        }
        for f in frameworks
    ]


@router.post("/frameworks/seed", status_code=status.HTTP_201_CREATED)
async def seed_frameworks(
    _: User = Depends(_require_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Seed built-in regulatory frameworks (idempotent)."""
    frameworks = [
        RegulatoryFramework(
            code="eudr",
            name="EU Deforestation Regulation (EUDR)",
            description="EU 2023/1115 — Regulation on deforestation-free products. "
                        "Requires due diligence that products don't contribute to deforestation.",
            default_cutoff_date="2020-12-31",
            applicable_commodities=["coffee", "cocoa", "palm_oil", "soy", "cattle", "wood", "rubber"],
            applicable_regions=["EU"],
            reporting_requirements="Due diligence statement with geolocation data for all supply chain activities.",
            status="active",
        ),
        RegulatoryFramework(
            code="cbam",
            name="Carbon Border Adjustment Mechanism (CBAM)",
            description="EU mechanism that puts a carbon price on imports of certain goods "
                        "from outside the EU where less ambitious climate policies apply.",
            default_cutoff_date="2020-12-31",
            applicable_commodities=["soy", "palm_oil", "wood"],
            applicable_regions=["EU"],
            reporting_requirements="Embedded carbon reporting for imported goods.",
            status="active",
        ),
        RegulatoryFramework(
            code="csrd",
            name="Corporate Sustainability Reporting Directive (CSRD)",
            description="EU directive requiring companies to disclose information on risks and "
                        "opportunities arising from social and environmental issues.",
            default_cutoff_date="2020-12-31",
            applicable_commodities=["coffee", "cocoa", "palm_oil", "soy", "cattle", "wood", "rubber"],
            applicable_regions=["EU"],
            reporting_requirements="Sustainability reporting covering environmental, social and governance factors.",
            status="active",
        ),
    ]
    seeded = 0
    for fw in frameworks:
        existing = (await db.execute(
            select(RegulatoryFramework).where(RegulatoryFramework.code == fw.code)
        )).scalar_one_or_none()
        if not existing:
            db.add(fw)
            seeded += 1
    await db.flush()
    await db.commit()
    return {"seeded": seeded, "total": len(frameworks)}

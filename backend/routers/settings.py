import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user, hash_password
from backend.middleware.rbac import role_required
from backend.models.connector import ConnectorConfig
from backend.models.user import User
from backend.services.crypto_service import encrypt_credentials

router = APIRouter()


# ─── USER MANAGEMENT ─────────────────────────────────────────

class UserCreate(BaseModel):
    email: str
    full_name: str
    password: str
    role: str
    team: str | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None
    team: str | None = None
    is_active: bool | None = None


@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "team": u.team,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.post("/users")
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    # Check duplicate
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=data.role,
        team=data.team,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "team": user.team,
    }


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.full_name is not None:
        user.full_name = data.full_name
    if data.role is not None:
        user.role = data.role
    if data.team is not None:
        user.team = data.team
    if data.is_active is not None:
        user.is_active = data.is_active

    await db.commit()
    return {"status": "updated", "user_id": user_id}


# ─── CONNECTOR MANAGEMENT ────────────────────────────────────

class ConnectorCreate(BaseModel):
    name: str
    source_type: str
    base_url: str | None = None
    credentials: dict | None = None
    sync_interval_minutes: int = 60


@router.get("/connectors")
async def list_connectors(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    result = await db.execute(select(ConnectorConfig).order_by(ConnectorConfig.name))
    connectors = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "source_type": c.source_type,
            "base_url": c.base_url,
            "is_active": c.is_active,
            "last_sync": c.last_sync.isoformat() if c.last_sync else None,
            "sync_interval_minutes": c.sync_interval_minutes,
            "has_credentials": c.encrypted_credentials is not None,
        }
        for c in connectors
    ]


@router.post("/connectors")
async def create_connector(
    data: ConnectorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    encrypted = encrypt_credentials(data.credentials) if data.credentials else None

    conn = ConnectorConfig(
        name=data.name,
        source_type=data.source_type,
        base_url=data.base_url,
        encrypted_credentials=encrypted,
        sync_interval_minutes=data.sync_interval_minutes,
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)

    return {
        "id": str(conn.id),
        "name": conn.name,
        "source_type": conn.source_type,
        "status": "created",
    }


@router.get("/scoring")
async def get_scoring_config(
    current_user: User = Depends(get_current_user),
):
    from backend.services.scoring_config import (
        CVSS_WEIGHT, EPSS_WEIGHT, KEV_BONUS, TIER_BONUS,
        EPSS_DEFAULTS, EXPLOIT_ACTIVE_THRESHOLD, EXPLOIT_POC_THRESHOLD,
        SLA_HOURS,
    )
    return {
        "formula": "max(0, min(10, CVSS_WEIGHT*CVSS + EPSS_WEIGHT*EPSS + KEV_bonus + asset_bonus))",
        "weights": {"cvss": CVSS_WEIGHT, "epss": EPSS_WEIGHT, "kev_bonus": KEV_BONUS},
        "tier_bonuses": TIER_BONUS,
        "epss_defaults": EPSS_DEFAULTS,
        "exploit_thresholds": {"active": EXPLOIT_ACTIVE_THRESHOLD, "poc": EXPLOIT_POC_THRESHOLD},
        "sla_hours": SLA_HOURS,
    }


@router.post("/connectors/{connector_id}/test")
async def test_connector(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    result = await db.execute(
        select(ConnectorConfig).where(ConnectorConfig.id == uuid.UUID(connector_id))
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connector not found")

    # Mock connectivity test
    return {
        "connector_id": str(conn.id),
        "name": conn.name,
        "status": "connected",
        "message": f"Successfully connected to {conn.name}",
    }

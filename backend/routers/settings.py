from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user, hash_password
from backend.middleware.module_gate import require_module
from backend.middleware.rbac import role_required
from backend.middleware.tenant import TenantContext
from backend.models.audit_log import AuditLog
from backend.models.connector import ConnectorConfig
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.schemas.auth import EmailField  # M2 — soft email validator
from backend.services.crypto_service import encrypt_credentials
from backend.services.tenant_query import apply_tenant_filter
from backend.utils import parse_uuid

# CRIT-007 — settings (users, connectors, scoring) are CORE platform features.
router = APIRouter(dependencies=[Depends(require_module("CORE"))])


# ─── Scoring weight bounds (validation only — applied per-field below) ──────
# We allow [0, 100] per weight to prevent obvious abuse / bugs that would
# cause runaway composite scores.  Anything negative or beyond 100 is rejected.
_SCORING_WEIGHT_MIN = 0.0
_SCORING_WEIGHT_MAX = 100.0


# ─── USER MANAGEMENT ─────────────────────────────────────────

class UserCreate(BaseModel):
    # M2 (Kimi MED-001) — EmailField rejects malformed emails at the API
    # boundary (no @, no TLD, etc).  Soft-form validator that still accepts
    # the *.test / *.example fixture domains used across the test suite.
    email: EmailField
    full_name: str = Field(..., min_length=1, max_length=150)
    # M1 (Kimi MED-002 + MED-003) — Password policy:
    #   * min 12 chars (NIST SP 800-63B baseline)
    #   * max 72 BYTES — bcrypt silently truncates beyond 72 bytes,
    #     producing identical hashes for two passphrases sharing the first
    #     72 bytes.  Reject at the boundary so the user gets a 422 instead
    #     of a silent truncation.
    password: str = Field(..., min_length=12, max_length=72)
    role: str
    team: str | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None
    team: str | None = None
    is_active: bool | None = None


class UserRead(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    team: str | None
    is_active: bool
    created_at: datetime


class UserCreateResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    team: str | None


class UserUpdateResponse(BaseModel):
    status: str
    user_id: str


@router.get("/users", response_model=list[UserRead])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    # Tenant-scoped — a CISO from tenant A may only see tenant A users.
    query = select(User).order_by(User.created_at.desc())
    query = apply_tenant_filter(query, User)
    result = await db.execute(query)
    users = result.scalars().all()
    return [
        UserRead(
            id=str(u.id),
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            team=u.team,
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.post("/users", response_model=UserCreateResponse, status_code=201)
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    # L10 (Codex LOW-005) — scope email-uniqueness check to current tenant.
    # Previously a CISO trying to create a user with an email used in
    # ANOTHER tenant got a 409 "Email already registered", which leaked
    # cross-tenant user existence.  We now only refuse the request when
    # the email is taken WITHIN the caller's tenant; if a global UNIQUE
    # constraint fires at the DB layer (legacy schema), translate the
    # IntegrityError into a generic message that does not reveal why.
    caller_tenant_id = TenantContext.get()
    existing = await db.execute(
        select(User).where(
            User.email == data.email,
            User.tenant_id == caller_tenant_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    # New users are stamped with the caller's tenant — never cross-tenant.
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=data.role,
        team=data.team,
        tenant_id=caller_tenant_id,
    )
    db.add(user)
    # Flush to obtain user.id before audit row inserts in the same txn
    await db.flush()
    db.add(AuditLog(
        user_id=current_user.id,
        action="user_created",
        resource_type="user",
        resource_id=user.id,
        details={"email": data.email, "role": data.role},
        tenant_id=caller_tenant_id,
    ))
    # L10 — translate global UNIQUE(email) violation into a generic 409.
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Could not create user")
    await db.refresh(user)

    return UserCreateResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        team=user.team,
    )


@router.patch("/users/{user_id}", response_model=UserUpdateResponse)
async def update_user(
    user_id: str,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    # Tenant-scope the lookup.  Cross-tenant write attempts → 404.
    result = await db.execute(
        select(User).where(
            User.id == parse_uuid(user_id, "user_id"),
            User.tenant_id == TenantContext.get(),
        )
    )
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

    db.add(AuditLog(
        user_id=current_user.id,
        action="user_updated",
        resource_type="user",
        resource_id=user.id,
        details={"changes": data.model_dump(exclude_none=True)},
        tenant_id=TenantContext.get(),
    ))
    await db.commit()
    return UserUpdateResponse(status="updated", user_id=user_id)


# ─── CONNECTOR MANAGEMENT ────────────────────────────────────

class ConnectorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    source_type: str = Field(..., min_length=1, max_length=30)
    base_url: str | None = Field(default=None, max_length=500)
    credentials: dict | None = None
    sync_interval_minutes: int = Field(default=60, ge=1, le=1440)


class ConnectorRead(BaseModel):
    id: str
    name: str
    source_type: str
    base_url: str | None
    is_active: bool
    last_sync: datetime | None
    sync_interval_minutes: int
    has_credentials: bool


class ConnectorCreateResponse(BaseModel):
    id: str
    name: str
    source_type: str
    status: str


class ConnectorTestResponse(BaseModel):
    connector_id: str
    name: str
    status: str
    message: str


@router.get("/connectors", response_model=list[ConnectorRead])
async def list_connectors(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    # Tenant-scoped — connectors with tenant_id != caller's tenant are hidden.
    query = select(ConnectorConfig).order_by(ConnectorConfig.name)
    query = apply_tenant_filter(query, ConnectorConfig)
    result = await db.execute(query)
    connectors = result.scalars().all()
    return [
        ConnectorRead(
            id=str(c.id),
            name=c.name,
            source_type=c.source_type,
            base_url=c.base_url,
            is_active=c.is_active,
            last_sync=c.last_sync,
            sync_interval_minutes=c.sync_interval_minutes,
            has_credentials=c.encrypted_credentials is not None,
        )
        for c in connectors
    ]


@router.post("/connectors", response_model=ConnectorCreateResponse, status_code=201)
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
        tenant_id=TenantContext.get(),
    )
    db.add(conn)
    await db.flush()
    db.add(AuditLog(
        user_id=current_user.id,
        action="connector_created",
        resource_type="connector",
        resource_id=conn.id,
        details={"name": data.name, "source_type": data.source_type},
        tenant_id=TenantContext.get(),
    ))
    await db.commit()
    await db.refresh(conn)

    return ConnectorCreateResponse(
        id=str(conn.id),
        name=conn.name,
        source_type=conn.source_type,
        status="created",
    )


# ─── Scoring config Pydantic schemas ────────────────────────────────────────


class ScoringWeights(BaseModel):
    cvss: float
    epss: float
    kev_bonus: float


class ScoringConfigResponse(BaseModel):
    formula_version: str
    formula: str
    weights: ScoringWeights
    tier_bonuses: dict[int, float]
    epss_defaults: dict[str, float]
    exploit_thresholds: dict[str, float]
    sla_hours: dict[str, int]


def _validate_weight(name: str, v: float) -> float:
    if v < _SCORING_WEIGHT_MIN:
        raise ValueError(f"{name} weight must be ≥ {_SCORING_WEIGHT_MIN}; got {v}")
    if v > _SCORING_WEIGHT_MAX:
        raise ValueError(f"{name} weight must be ≤ {_SCORING_WEIGHT_MAX}; got {v}")
    return float(v)


class ScoringWeightsUpdate(BaseModel):
    """
    Patch payload for tenant scoring weights.  All three fields are optional
    individually but the request MUST contain at least one.
    """
    cvss: float | None = Field(default=None, ge=_SCORING_WEIGHT_MIN, le=_SCORING_WEIGHT_MAX)
    epss: float | None = Field(default=None, ge=_SCORING_WEIGHT_MIN, le=_SCORING_WEIGHT_MAX)
    kev_bonus: float | None = Field(default=None, ge=_SCORING_WEIGHT_MIN, le=_SCORING_WEIGHT_MAX)

    @model_validator(mode="after")
    def _at_least_one(self):
        if self.cvss is None and self.epss is None and self.kev_bonus is None:
            raise ValueError(
                "At least one of {cvss, epss, kev_bonus} must be supplied."
            )
        return self


def _resolve_scoring_weights(tenant_overrides: dict | None) -> ScoringWeights:
    """Merge defaults from scoring_config with optional tenant overrides."""
    from backend.services.scoring_config import CVSS_WEIGHT, EPSS_WEIGHT, KEV_BONUS

    overrides = tenant_overrides or {}
    return ScoringWeights(
        cvss=float(overrides.get("cvss", CVSS_WEIGHT)),
        epss=float(overrides.get("epss", EPSS_WEIGHT)),
        kev_bonus=float(overrides.get("kev_bonus", KEV_BONUS)),
    )


async def _load_tenant(db: AsyncSession) -> Tenant:
    tid = TenantContext.get()
    result = await db.execute(select(Tenant).where(Tenant.id == tid))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.get("/scoring", response_model=ScoringConfigResponse)
async def get_scoring_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from backend.services.scoring_config import (
        TIER_BONUS,
        EPSS_DEFAULTS, EXPLOIT_ACTIVE_THRESHOLD, EXPLOIT_POC_THRESHOLD,
        SLA_HOURS, FORMULA_VERSION,
    )

    # Use tenant-specific overrides if present.  Super-admin (no tenant ctx)
    # falls back to defaults.
    tenant_overrides = None
    if TenantContext.get_or_none() is not None:
        tenant = await _load_tenant(db)
        tenant_overrides = (tenant.settings or {}).get("scoring_weights")

    return ScoringConfigResponse(
        formula_version=FORMULA_VERSION,
        formula="max(0, min(10, CVSS_WEIGHT*CVSS + EPSS_WEIGHT*EPSS + KEV_bonus + asset_bonus))",
        weights=_resolve_scoring_weights(tenant_overrides),
        tier_bonuses=TIER_BONUS,
        epss_defaults=EPSS_DEFAULTS,
        exploit_thresholds={
            "active": EXPLOIT_ACTIVE_THRESHOLD,
            "poc": EXPLOIT_POC_THRESHOLD,
        },
        sla_hours=SLA_HOURS,
    )


@router.patch("/scoring", response_model=ScoringConfigResponse)
async def update_scoring_weights(
    data: ScoringWeightsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    """
    Update the current tenant's scoring weight overrides.

    Storage
    -------
    Persisted into `tenants.settings.scoring_weights` (JSONB) — no separate
    table needed.  Only the fields supplied in the request are merged; missing
    fields keep their previous (or default) value.

    Audit
    -----
    Every successful update writes one AuditLog row with
    action="scoring_weights_updated" and the diff in `details`.
    """
    tenant = await _load_tenant(db)
    settings_blob = dict(tenant.settings or {})
    current_weights = dict(settings_blob.get("scoring_weights") or {})

    diff: dict[str, dict[str, float]] = {}
    for field in ("cvss", "epss", "kev_bonus"):
        new_val = getattr(data, field)
        if new_val is None:
            continue
        validated = _validate_weight(field, float(new_val))
        old_val = current_weights.get(field)
        if old_val != validated:
            diff[field] = {"old": old_val, "new": validated}
            current_weights[field] = validated

    settings_blob["scoring_weights"] = current_weights
    tenant.settings = settings_blob  # reassign to trigger SQLAlchemy dirty tracking

    db.add(AuditLog(
        user_id=current_user.id,
        action="scoring_weights_updated",
        resource_type="tenant",
        resource_id=tenant.id,
        details={"diff": diff, "tenant_slug": tenant.slug},
        tenant_id=tenant.id,
    ))

    await db.commit()
    await db.refresh(tenant)

    # Re-render full config so client gets a single canonical view.
    from backend.services.scoring_config import (
        TIER_BONUS,
        EPSS_DEFAULTS, EXPLOIT_ACTIVE_THRESHOLD, EXPLOIT_POC_THRESHOLD,
        SLA_HOURS, FORMULA_VERSION,
    )
    return ScoringConfigResponse(
        formula_version=FORMULA_VERSION,
        formula="max(0, min(10, CVSS_WEIGHT*CVSS + EPSS_WEIGHT*EPSS + KEV_bonus + asset_bonus))",
        weights=_resolve_scoring_weights(current_weights),
        tier_bonuses=TIER_BONUS,
        epss_defaults=EPSS_DEFAULTS,
        exploit_thresholds={
            "active": EXPLOIT_ACTIVE_THRESHOLD,
            "poc": EXPLOIT_POC_THRESHOLD,
        },
        sla_hours=SLA_HOURS,
    )


@router.post("/connectors/{connector_id}/test", response_model=ConnectorTestResponse)
async def test_connector(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    # Tenant-scope — cross-tenant probe → 404 (no info leak).
    result = await db.execute(
        select(ConnectorConfig).where(
            ConnectorConfig.id == parse_uuid(connector_id, "connector_id"),
            ConnectorConfig.tenant_id == TenantContext.get(),
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connector not found")

    # Mock connectivity test
    return ConnectorTestResponse(
        connector_id=str(conn.id),
        name=conn.name,
        status="connected",
        message=f"Successfully connected to {conn.name}",
    )

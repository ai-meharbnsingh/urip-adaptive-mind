"""
Tenant onboarding & module subscription router.

Routes
------
Super-admin (platform) routes — all require is_super_admin:
  POST   /admin/tenants                                  — create new tenant
  GET    /admin/tenants                                  — list all tenants
  GET    /admin/tenants/{slug}                           — tenant detail
  PATCH  /admin/tenants/{slug}                           — update white-label settings
  POST   /admin/tenants/{slug}/users                     — provision tenant admin user
  POST   /admin/tenants/{slug}/modules                   — enable a module
  PATCH  /admin/tenants/{slug}/modules/{module_code}     — change tier / expires_at
  DELETE /admin/tenants/{slug}/modules/{module_code}     — soft-disable (is_enabled=false)

Tenant-scoped routes — authenticated users see their own tenant's modules:
  GET    /tenants/{slug}/modules                         — list modules + enabled status
"""

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from backend.schemas.auth import EmailField  # M2 — soft email validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Strict 6-digit hex colour pattern, case-insensitive (#RRGGBB).  3-digit
# shorthand (#RGB) is NOT accepted — front-end design tokens require full hex.
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

from backend.database import get_db
from backend.middleware.auth import create_access_token, get_current_user, hash_password
from backend.middleware.scopes import require_scope
from backend.middleware.tenant import TenantContext
from backend.models.audit_log import AuditLog
from backend.models.subscription import BILLING_TIERS, MODULE_CODES, TenantSubscription
from backend.models.tenant import Tenant
from backend.models.user import User

router = APIRouter()


# ---------------------------------------------------------------------------
# Guard helpers
# ---------------------------------------------------------------------------


def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency: raises 403 if the caller is not a super-admin."""
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super-admin access required.",
        )
    return current_user


async def _get_tenant_by_slug(slug: str, db: AsyncSession) -> Tenant:
    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{slug}' not found.")
    return tenant


# ---------------------------------------------------------------------------
# Pydantic schemas (local — no separate schemas file to avoid cross-worker
# collisions; can be extracted later if needed)
# ---------------------------------------------------------------------------


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    domain: str = Field(..., min_length=1, max_length=255)
    primary_contact_email: str | None = None  # stored in settings for now

    @field_validator("slug")
    @classmethod
    def slug_lowercase(cls, v: str) -> str:
        return v.lower()


class TenantRead(BaseModel):
    id: str
    name: str
    slug: str
    domain: str
    is_active: bool
    settings: dict[str, Any]
    created_at: str

    @classmethod
    def from_orm(cls, t: Tenant) -> "TenantRead":
        return cls(
            id=str(t.id),
            name=t.name,
            slug=t.slug,
            domain=t.domain,
            is_active=t.is_active,
            settings=t.settings or {},
            created_at=t.created_at.isoformat(),
        )


class TenantUpdate(BaseModel):
    """White-label settings update (logo, primary/secondary color, app name)."""
    logo_url: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    app_name: str | None = None
    is_active: bool | None = None

    @field_validator("primary_color", "secondary_color")
    @classmethod
    def _validate_hex(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _HEX_COLOR_RE.match(v):
            raise ValueError(
                "must be a 6-digit hex color in the form #RRGGBB (e.g. #112233)"
            )
        return v

    @field_validator("logo_url")
    @classmethod
    def _validate_logo_url(cls, v: str | None) -> str | None:
        """
        CL-NEW-5 / L1 — Reject `javascript:`, `data:`, `file:`, etc. on logo_url.

        Stored XSS via white-label: a compromised super-admin could otherwise
        set logo_url=javascript:alert(document.cookie) and trigger XSS for
        every user of the targeted tenant when the URL is interpolated into
        <img src=...> / <a href=...>.

        Allow only http(s) URLs and an explicit length cap to prevent abuse.
        Optional image-extension hint (.png/.jpg/.jpeg/.gif/.svg/.webp) is
        encouraged but not required (some CDNs serve images without an
        extension).  The frontend MUST render this strictly via <img src>.
        """
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("logo_url must be a string URL")
        v_stripped = v.strip()
        if not v_stripped:
            return None
        if len(v_stripped) > 2048:
            raise ValueError("logo_url exceeds 2048 character limit")
        # Reject any non-http(s) scheme.  We test for the leading scheme
        # explicitly so URLs like "//evil.example/x.png" (protocol-relative)
        # are also rejected — the frontend may resolve those against
        # whatever protocol the page uses.
        lowered = v_stripped.lower()
        if not (lowered.startswith("http://") or lowered.startswith("https://")):
            raise ValueError(
                "logo_url must use http:// or https:// scheme "
                "(javascript:, data:, file:, etc. are rejected)"
            )
        # Production deployments should require https; allow http only if it
        # looks like a localhost/dev URL so this can be tested.
        if lowered.startswith("http://"):
            host_part = lowered[len("http://"):].split("/", 1)[0].split(":", 1)[0]
            if host_part not in {"localhost", "127.0.0.1"}:
                raise ValueError(
                    "logo_url must use https:// (http allowed only for localhost)"
                )
        return v_stripped


class BrandingResponse(BaseModel):
    """Public-ish branding payload returned by GET /api/tenants/{slug}/branding."""
    app_name: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None


class TenantAdminProvisionResponse(BaseModel):
    user_id: str
    email: str
    full_name: str
    role: str
    tenant_slug: str
    access_token: str
    token_type: str = "Bearer"


# `ModuleDisableResponse` is defined after `ModuleRead` further below to
# avoid a forward reference (kept here so all admin response models live in
# one logical block — see line ~225 for `ModuleRead`).


class TenantAdminUserCreate(BaseModel):
    # M2 (Kimi MED-001) — soft email-format validator at API boundary.
    email: EmailField
    full_name: str = Field(..., min_length=1, max_length=150)
    # M1 (Kimi MED-002 + MED-003) — Password 12..72 bytes.
    # bcrypt silently truncates beyond 72 bytes; we reject on entry.
    password: str = Field(..., min_length=12, max_length=72)
    role: str = Field(default="ciso")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"ciso", "it_team", "executive", "board"}
        if v not in allowed:
            raise ValueError(f"role must be one of {allowed}")
        return v


class ModuleSubscriptionCreate(BaseModel):
    module_code: str
    billing_tier: str = "TRIAL"
    expires_at: datetime | None = None

    @field_validator("module_code")
    @classmethod
    def validate_module(cls, v: str) -> str:
        v = v.upper()
        if v not in MODULE_CODES:
            raise ValueError(f"module_code must be one of {sorted(MODULE_CODES)}")
        return v

    @field_validator("billing_tier")
    @classmethod
    def validate_tier(cls, v: str) -> str:
        v = v.upper()
        if v not in BILLING_TIERS:
            raise ValueError(f"billing_tier must be one of {sorted(BILLING_TIERS)}")
        return v


class ModuleSubscriptionUpdate(BaseModel):
    billing_tier: str | None = None
    expires_at: datetime | None = None
    is_enabled: bool | None = None

    @field_validator("billing_tier")
    @classmethod
    def validate_tier(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.upper()
        if v not in BILLING_TIERS:
            raise ValueError(f"billing_tier must be one of {sorted(BILLING_TIERS)}")
        return v


class ModuleRead(BaseModel):
    id: str
    module_code: str
    is_enabled: bool
    billing_tier: str
    started_at: str
    expires_at: str | None

    @classmethod
    def from_orm(cls, s: TenantSubscription) -> "ModuleRead":
        return cls(
            id=str(s.id),
            module_code=s.module_code,
            is_enabled=s.is_enabled,
            billing_tier=s.billing_tier,
            started_at=s.started_at.isoformat(),
            expires_at=s.expires_at.isoformat() if s.expires_at else None,
        )


class ModuleDisableResponse(BaseModel):
    detail: str
    subscription: ModuleRead


# ---------------------------------------------------------------------------
# Admin routes — super-admin only
# ---------------------------------------------------------------------------


@router.post("/admin/tenants", response_model=TenantRead, status_code=201)
async def create_tenant(
    data: TenantCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_super_admin),
    _scope: User = Depends(require_scope("tenants:write")),
):
    """Create a new tenant. slug must be globally unique."""
    # Check slug uniqueness
    existing = await db.execute(select(Tenant).where(Tenant.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant with slug '{data.slug}' already exists.",
        )

    settings_payload: dict[str, Any] = {}
    if data.primary_contact_email:
        settings_payload["primary_contact_email"] = data.primary_contact_email

    tenant = Tenant(
        id=uuid.uuid4(),
        name=data.name,
        slug=data.slug,
        domain=data.domain,
        is_active=True,
        settings=settings_payload,
    )
    db.add(tenant)
    # Stamp audit row with the *new* tenant_id — super-admin actions against the
    # platform are recorded against the tenant that was created (forensic trail
    # belongs to the affected tenant, never NULL).
    db.add(AuditLog(
        user_id=_admin.id,
        action="tenant_created",
        resource_type="tenant",
        resource_id=tenant.id,
        details={"slug": data.slug, "name": data.name, "domain": data.domain},
        tenant_id=tenant.id,
    ))
    await db.commit()
    await db.refresh(tenant)
    return TenantRead.from_orm(tenant)


@router.get("/admin/tenants", response_model=list[TenantRead])
async def list_tenants(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_super_admin),
    _scope: User = Depends(require_scope("tenants:read")),
):
    """List all tenants (super-admin only)."""
    result = await db.execute(select(Tenant).order_by(Tenant.created_at.asc()))
    tenants = result.scalars().all()
    return [TenantRead.from_orm(t) for t in tenants]


@router.get("/admin/tenants/{slug}", response_model=TenantRead)
async def get_tenant(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_super_admin),
    _scope: User = Depends(require_scope("tenants:read")),
):
    """Get tenant detail by slug (super-admin only)."""
    tenant = await _get_tenant_by_slug(slug, db)
    return TenantRead.from_orm(tenant)


@router.patch("/admin/tenants/{slug}", response_model=TenantRead)
async def update_tenant(
    slug: str,
    data: TenantUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_super_admin),
    _scope: User = Depends(require_scope("tenants:write")),
):
    """
    Update tenant white-label settings (logo_url, primary_color, app_name)
    or activate / deactivate the tenant.
    """
    tenant = await _get_tenant_by_slug(slug, db)

    # Merge white-label fields into settings JSON
    current_settings = dict(tenant.settings or {})
    changed = False
    for field in ("logo_url", "primary_color", "secondary_color", "app_name"):
        val = getattr(data, field)
        if val is not None:
            current_settings[field] = val
            changed = True

    if changed:
        tenant.settings = current_settings  # reassign to trigger SQLAlchemy dirty tracking

    if data.is_active is not None:
        tenant.is_active = data.is_active

    db.add(AuditLog(
        user_id=_admin.id,
        action="tenant_updated",
        resource_type="tenant",
        resource_id=tenant.id,
        details={"changes": data.model_dump(exclude_none=True)},
        tenant_id=tenant.id,
    ))
    await db.commit()
    await db.refresh(tenant)
    return TenantRead.from_orm(tenant)


@router.post(
    "/admin/tenants/{slug}/users",
    response_model=TenantAdminProvisionResponse,
    status_code=201,
)
async def provision_tenant_admin_user(
    slug: str,
    data: TenantAdminUserCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_super_admin),
    _scope: User = Depends(require_scope("tenants:write")),
):
    """
    Bootstrap a tenant admin user.

    This endpoint is intended for one-time provisioning when onboarding a new
    tenant.  The created user gets a JWT so the tenant admin can immediately log in.
    """
    tenant = await _get_tenant_by_slug(slug, db)

    # Check email uniqueness
    existing_user = await db.execute(select(User).where(User.email == data.email))
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{data.email}' already exists.",
        )

    user = User(
        id=uuid.uuid4(),
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=data.role,
        is_active=True,
        is_super_admin=False,
        tenant_id=tenant.id,
    )
    db.add(user)
    db.add(AuditLog(
        user_id=_admin.id,
        action="tenant_admin_provisioned",
        resource_type="user",
        resource_id=user.id,
        details={"email": data.email, "role": data.role, "tenant_slug": slug},
        tenant_id=tenant.id,
    ))
    await db.commit()
    await db.refresh(user)

    token = create_access_token(str(user.id), user.role, tenant_id=str(tenant.id))
    return TenantAdminProvisionResponse(
        user_id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        tenant_slug=slug,
        access_token=token,
    )


# ---------------------------------------------------------------------------
# Module subscription routes — super-admin management
# ---------------------------------------------------------------------------


@router.post("/admin/tenants/{slug}/modules", response_model=ModuleRead, status_code=201)
async def enable_module(
    slug: str,
    data: ModuleSubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_super_admin),
    _scope: User = Depends(require_scope("modules:write")),
):
    """Enable a module subscription for a tenant."""
    tenant = await _get_tenant_by_slug(slug, db)

    # Check if subscription already exists
    existing = await db.execute(
        select(TenantSubscription).where(
            TenantSubscription.tenant_id == tenant.id,
            TenantSubscription.module_code == data.module_code,
        )
    )
    sub = existing.scalar_one_or_none()
    if sub:
        if sub.is_enabled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Module '{data.module_code}' is already enabled for tenant '{slug}'.",
            )
        # Re-enable a previously disabled subscription
        sub.is_enabled = True
        sub.billing_tier = data.billing_tier
        sub.started_at = datetime.now(timezone.utc)
        sub.expires_at = data.expires_at
    else:
        sub = TenantSubscription(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            module_code=data.module_code,
            is_enabled=True,
            billing_tier=data.billing_tier,
            started_at=datetime.now(timezone.utc),
            expires_at=data.expires_at,
        )
        db.add(sub)

    await db.flush()
    db.add(AuditLog(
        user_id=_admin.id,
        action="module_enabled",
        resource_type="module_subscription",
        resource_id=sub.id,
        details={
            "module_code": data.module_code,
            "billing_tier": data.billing_tier,
            "tenant_slug": slug,
        },
        tenant_id=tenant.id,
    ))
    await db.commit()
    await db.refresh(sub)
    return ModuleRead.from_orm(sub)


@router.patch("/admin/tenants/{slug}/modules/{module_code}", response_model=ModuleRead)
async def update_module_subscription(
    slug: str,
    module_code: str,
    data: ModuleSubscriptionUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_super_admin),
    _scope: User = Depends(require_scope("modules:write")),
):
    """Change billing tier, expiry, or enabled state for a module subscription."""
    module_code = module_code.upper()
    if module_code not in MODULE_CODES:
        raise HTTPException(status_code=400, detail=f"Unknown module_code '{module_code}'.")

    tenant = await _get_tenant_by_slug(slug, db)

    result = await db.execute(
        select(TenantSubscription).where(
            TenantSubscription.tenant_id == tenant.id,
            TenantSubscription.module_code == module_code,
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(
            status_code=404,
            detail=f"No subscription for module '{module_code}' on tenant '{slug}'.",
        )

    if data.billing_tier is not None:
        sub.billing_tier = data.billing_tier
    if data.expires_at is not None:
        sub.expires_at = data.expires_at
    if data.is_enabled is not None:
        sub.is_enabled = data.is_enabled

    db.add(AuditLog(
        user_id=_admin.id,
        action="module_updated",
        resource_type="module_subscription",
        resource_id=sub.id,
        details={
            "module_code": module_code,
            "tenant_slug": slug,
            "changes": data.model_dump(exclude_none=True, mode="json"),
        },
        tenant_id=tenant.id,
    ))
    await db.commit()
    await db.refresh(sub)
    return ModuleRead.from_orm(sub)


@router.delete(
    "/admin/tenants/{slug}/modules/{module_code}",
    response_model=ModuleDisableResponse,
    status_code=200,
)
async def disable_module(
    slug: str,
    module_code: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_super_admin),
    _scope: User = Depends(require_scope("modules:write")),
):
    """
    Soft-disable a module subscription (sets is_enabled=False).
    The row is NEVER hard-deleted — audit trail must be preserved.
    """
    module_code = module_code.upper()
    if module_code not in MODULE_CODES:
        raise HTTPException(status_code=400, detail=f"Unknown module_code '{module_code}'.")

    tenant = await _get_tenant_by_slug(slug, db)

    result = await db.execute(
        select(TenantSubscription).where(
            TenantSubscription.tenant_id == tenant.id,
            TenantSubscription.module_code == module_code,
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(
            status_code=404,
            detail=f"No subscription for module '{module_code}' on tenant '{slug}'.",
        )

    if not sub.is_enabled:
        raise HTTPException(
            status_code=409,
            detail=f"Module '{module_code}' is already disabled for tenant '{slug}'.",
        )

    sub.is_enabled = False
    db.add(AuditLog(
        user_id=_admin.id,
        action="module_disabled",
        resource_type="module_subscription",
        resource_id=sub.id,
        details={"module_code": module_code, "tenant_slug": slug},
        tenant_id=tenant.id,
    ))
    await db.commit()
    await db.refresh(sub)
    return ModuleDisableResponse(
        detail=f"Module '{module_code}' disabled for tenant '{slug}'.",
        subscription=ModuleRead.from_orm(sub),
    )


# ---------------------------------------------------------------------------
# Tenant-scoped route — tenant admin or super-admin sees module list
# ---------------------------------------------------------------------------


@router.get("/tenants/{slug}/branding", response_model=BrandingResponse)
async def get_tenant_branding(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return white-label branding fields for the named tenant.

    Access rules:
      - super-admins can read any tenant.
      - regular users can read ONLY their own tenant.
      - cross-tenant access returns 404 (no info leak — same as if the slug
        did not exist).
    """
    tenant_result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = tenant_result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    if not current_user.is_super_admin:
        caller_tenant_id = TenantContext.get_or_none()
        # Cross-tenant probe → return 404, not 403, to avoid disclosing
        # the existence of other tenants by their slug.
        if caller_tenant_id is None or caller_tenant_id != tenant.id:
            raise HTTPException(status_code=404, detail="Tenant not found.")

    s = tenant.settings or {}
    return BrandingResponse(
        app_name=s.get("app_name"),
        logo_url=s.get("logo_url"),
        primary_color=s.get("primary_color"),
        secondary_color=s.get("secondary_color"),
    )


@router.get("/tenants/{slug}/modules", response_model=list[ModuleRead])
async def list_tenant_modules(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all module subscriptions for a tenant.

    Access rules:
    - super-admin can query any tenant's modules.
    - normal users can only query the modules of THEIR OWN tenant.
    """
    # Resolve tenant first.  We will turn cross-tenant access into 404 (not 403)
    # so that an attacker cannot enumerate which tenant slugs exist.
    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{slug}' not found.")

    # Authorization check: normal users may only see their own tenant's modules.
    if not current_user.is_super_admin:
        caller_tenant_id = TenantContext.get_or_none()
        if caller_tenant_id is None or caller_tenant_id != tenant.id:
            # Return 404 — same response shape as if the slug did not exist —
            # to prevent information leakage of other tenants' existence.
            raise HTTPException(status_code=404, detail=f"Tenant '{slug}' not found.")

    sub_result = await db.execute(
        select(TenantSubscription)
        .where(TenantSubscription.tenant_id == tenant.id)
        .order_by(TenantSubscription.module_code.asc())
    )
    subs = sub_result.scalars().all()
    return [ModuleRead.from_orm(s) for s in subs]

"""
P1.4 — Tenant asset taxonomy admin API.

Endpoints (all tenant-scoped via TenantContext):

    GET    /api/asset-taxonomy                — list keywords, optional tier filter
    POST   /api/asset-taxonomy                — add a keyword (admin)
    POST   /api/asset-taxonomy/bulk           — bulk import (admin)
    PATCH  /api/asset-taxonomy/{id}           — update tier or keyword (admin)
    DELETE /api/asset-taxonomy/{id}           — soft-delete (admin)
    POST   /api/asset-taxonomy/import-defaults — seed tenant from legacy JSON (admin)

Authorisation
-------------
All write endpoints require the "ciso" role (which sits at the top of
ROLE_HIERARCHY in backend/middleware/rbac.py).  The ciso role is the
existing "admin" role in URIP — there is no separate `admin` role today.

Tenant scoping
--------------
Every query is filtered through `apply_tenant_filter()` so a caller can
only see / mutate keywords belonging to their own tenant.  The TenantContext
is set by `get_current_user()` from the JWT.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.rbac import role_required
from backend.middleware.tenant import TenantContext
from backend.models.asset_taxonomy import TIER_CODES, TenantAssetTaxonomy
from backend.models.audit_log import AuditLog
from backend.models.user import User
from backend.services.asset_criticality_service import (
    _all_tier_codes_from_legacy,
    invalidate_tenant_cache,
)
from backend.services.tenant_query import apply_tenant_filter

router = APIRouter()

# Admin-equivalent role guard.  In URIP, "ciso" is the highest tenant-level
# role; no separate "admin" role exists in middleware/auth.py.  We reuse the
# existing role_required helper rather than redefining auth.
require_admin = role_required("ciso")


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────


def _validate_tier_code(v: str) -> str:
    v = v.upper()
    if v not in TIER_CODES:
        raise ValueError(f"tier_code must be one of {list(TIER_CODES)}")
    return v


# HIGH-012 — ReDoS via tenant-supplied taxonomy regex.
# classify_asset() compiles every taxonomy keyword as a regex via
# re.compile(p, re.IGNORECASE).  A malicious tenant admin who can write
# taxonomy keywords could submit a catastrophic-backtracking pattern such as
# `(a+)+$` and DOS every subsequent classify call for that tenant.  We
# side-step the entire problem by enforcing that keywords are LITERAL
# substrings only.  If real regex behaviour is ever needed we should switch
# to google-re2 (linear-time guarantees) and lift this restriction.
_REGEX_METACHARS = set(r".*+?^${}()|[]\\")


def _validate_literal_keyword(v: str) -> str:
    """Reject any keyword containing a regex metacharacter."""
    bad = sorted({c for c in v if c in _REGEX_METACHARS})
    if bad:
        raise ValueError(
            f"Keyword {v!r} contains regex metacharacters {bad}. "
            "Regex is not supported — use literal substrings only "
            "(this prevents ReDoS — see HIGH-012)."
        )
    return v


class TaxonomyEntryCreate(BaseModel):
    tier_code: str = Field(..., min_length=2, max_length=2)
    keyword: str = Field(..., min_length=1, max_length=500)
    asset_type: str | None = Field(default=None, max_length=100)

    @field_validator("tier_code")
    @classmethod
    def _check_tier(cls, v: str) -> str:
        return _validate_tier_code(v)

    @field_validator("keyword")
    @classmethod
    def _check_keyword(cls, v: str) -> str:
        return _validate_literal_keyword(v)


class TaxonomyEntryUpdate(BaseModel):
    tier_code: str | None = Field(default=None, min_length=2, max_length=2)
    keyword: str | None = Field(default=None, min_length=1, max_length=500)
    asset_type: str | None = Field(default=None, max_length=100)

    @field_validator("tier_code")
    @classmethod
    def _check_tier(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_tier_code(v)

    @field_validator("keyword")
    @classmethod
    def _check_keyword(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_literal_keyword(v)


class TaxonomyEntryRead(BaseModel):
    id: str
    tenant_id: str
    tier_code: str
    keyword: str
    asset_type: str | None
    created_by_user_id: str | None
    created_at: str
    updated_at: str
    deleted_at: str | None

    @classmethod
    def from_orm(cls, row: TenantAssetTaxonomy) -> "TaxonomyEntryRead":
        return cls(
            id=str(row.id),
            tenant_id=str(row.tenant_id),
            tier_code=row.tier_code,
            keyword=row.keyword,
            asset_type=row.asset_type,
            created_by_user_id=(
                str(row.created_by_user_id) if row.created_by_user_id else None
            ),
            created_at=row.created_at.isoformat(),
            updated_at=row.updated_at.isoformat(),
            deleted_at=row.deleted_at.isoformat() if row.deleted_at else None,
        )


class TaxonomyListResponse(BaseModel):
    items: list[TaxonomyEntryRead]
    total: int
    page: int
    page_size: int


class BulkImportResponse(BaseModel):
    inserted: int
    items: list[TaxonomyEntryRead]


class TaxonomyDeleteResponse(BaseModel):
    detail: str
    entry: TaxonomyEntryRead


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


async def _get_owned_row(db: AsyncSession, taxonomy_id: uuid.UUID) -> TenantAssetTaxonomy:
    """
    Fetch a taxonomy row, enforcing that it belongs to the caller's tenant
    AND has not been soft-deleted.  Raises 404 otherwise.
    """
    query = select(TenantAssetTaxonomy).where(TenantAssetTaxonomy.id == taxonomy_id)
    query = apply_tenant_filter(query, TenantAssetTaxonomy)
    query = query.where(TenantAssetTaxonomy.deleted_at.is_(None))
    result = await db.execute(query)
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Taxonomy entry not found.")
    return row


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────


@router.get("", response_model=TaxonomyListResponse)
async def list_taxonomy(
    tier_code: str | None = Query(default=None, description="Filter by tier (T1-T4)"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    include_deleted: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all taxonomy keywords for the current tenant (paginated)."""
    base = select(TenantAssetTaxonomy)
    base = apply_tenant_filter(base, TenantAssetTaxonomy)

    if tier_code is not None:
        try:
            normalised = _validate_tier_code(tier_code)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        base = base.where(TenantAssetTaxonomy.tier_code == normalised)

    if not include_deleted:
        base = base.where(TenantAssetTaxonomy.deleted_at.is_(None))

    # Total count
    count_query = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_query)).scalar_one()

    # Page
    rows_query = (
        base.order_by(TenantAssetTaxonomy.tier_code.asc(), TenantAssetTaxonomy.keyword.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(rows_query)).scalars().all()

    return TaxonomyListResponse(
        items=[TaxonomyEntryRead.from_orm(r) for r in rows],
        total=int(total),
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=TaxonomyEntryRead, status_code=201)
async def create_taxonomy_entry(
    data: TaxonomyEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Add a single keyword for the current tenant (admin only)."""
    tenant_id = TenantContext.get()
    row = TenantAssetTaxonomy(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        tier_code=data.tier_code,
        keyword=data.keyword,
        asset_type=data.asset_type,
        created_by_user_id=current_user.id,
    )
    db.add(row)
    db.add(AuditLog(
        user_id=current_user.id,
        action="taxonomy_created",
        resource_type="asset_taxonomy",
        resource_id=row.id,
        details={
            "tier_code": data.tier_code,
            "keyword": data.keyword,
            "asset_type": data.asset_type,
        },
        tenant_id=tenant_id,
    ))
    await db.commit()
    await db.refresh(row)
    invalidate_tenant_cache(tenant_id)
    return TaxonomyEntryRead.from_orm(row)


@router.post("/bulk", response_model=BulkImportResponse, status_code=201)
async def bulk_import(
    data: list[TaxonomyEntryCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Bulk-import taxonomy entries for the current tenant (admin only).

    The body is a JSON array of {tier_code, keyword, asset_type?} objects.
    Returns the inserted rows.  All-or-nothing: if any row fails validation
    the entire request is rejected by Pydantic before this handler runs.
    """
    if not data:
        raise HTTPException(status_code=422, detail="Bulk payload must not be empty.")

    tenant_id = TenantContext.get()
    new_rows: list[TenantAssetTaxonomy] = []
    for item in data:
        new_rows.append(
            TenantAssetTaxonomy(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                tier_code=item.tier_code,
                keyword=item.keyword,
                asset_type=item.asset_type,
                created_by_user_id=current_user.id,
            )
        )
    db.add_all(new_rows)
    db.add(AuditLog(
        user_id=current_user.id,
        action="taxonomy_bulk_imported",
        resource_type="asset_taxonomy",
        resource_id=None,  # bulk row — no single resource id
        details={"inserted_count": len(new_rows)},
        tenant_id=tenant_id,
    ))
    await db.commit()
    for r in new_rows:
        await db.refresh(r)
    invalidate_tenant_cache(tenant_id)
    return BulkImportResponse(
        inserted=len(new_rows),
        items=[TaxonomyEntryRead.from_orm(r) for r in new_rows],
    )


@router.patch("/{taxonomy_id}", response_model=TaxonomyEntryRead)
async def update_taxonomy_entry(
    taxonomy_id: uuid.UUID,
    data: TaxonomyEntryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update a keyword's tier and/or text (admin only)."""
    row = await _get_owned_row(db, taxonomy_id)

    changed = False
    if data.tier_code is not None:
        row.tier_code = data.tier_code
        changed = True
    if data.keyword is not None:
        row.keyword = data.keyword
        changed = True
    if data.asset_type is not None:
        row.asset_type = data.asset_type
        changed = True

    if not changed:
        raise HTTPException(status_code=422, detail="No fields supplied to update.")

    db.add(AuditLog(
        user_id=current_user.id,
        action="taxonomy_updated",
        resource_type="asset_taxonomy",
        resource_id=row.id,
        details={"changes": data.model_dump(exclude_none=True)},
        tenant_id=TenantContext.get(),
    ))
    await db.commit()
    await db.refresh(row)
    invalidate_tenant_cache(TenantContext.get())
    return TaxonomyEntryRead.from_orm(row)


@router.delete(
    "/{taxonomy_id}",
    response_model=TaxonomyDeleteResponse,
    status_code=200,
)
async def soft_delete_taxonomy_entry(
    taxonomy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Soft-delete a keyword (admin only).

    The row is preserved with deleted_at = now() so the audit trail of
    historical taxonomy decisions is intact.  Subsequent classify() calls
    ignore soft-deleted rows.
    """
    row = await _get_owned_row(db, taxonomy_id)
    row.deleted_at = datetime.now(timezone.utc)
    db.add(AuditLog(
        user_id=current_user.id,
        action="taxonomy_deleted",
        resource_type="asset_taxonomy",
        resource_id=row.id,
        details={"tier_code": row.tier_code, "keyword": row.keyword},
        tenant_id=TenantContext.get(),
    ))
    await db.commit()
    await db.refresh(row)
    invalidate_tenant_cache(TenantContext.get())
    return TaxonomyDeleteResponse(
        detail="Taxonomy entry soft-deleted.",
        entry=TaxonomyEntryRead.from_orm(row),
    )


@router.post("/import-defaults", response_model=BulkImportResponse, status_code=201)
async def import_legacy_defaults(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Seed the current tenant's taxonomy with the legacy
    `tier_keywords.json` defaults.

    Idempotency
    -----------
    This endpoint is INTENTIONALLY non-idempotent — calling it twice will
    create two copies of every keyword.  The response payload includes the
    inserted rows so the caller can decide how to handle re-imports.  The
    intended workflow is:

        1. New tenant calls /import-defaults once during onboarding.
        2. They delete / edit / add keywords from the UI.

    Returns 409 if the tenant already has any non-deleted taxonomy rows so
    we never silently double-seed.
    """
    tenant_id = TenantContext.get()

    existing_query = (
        select(func.count())
        .select_from(TenantAssetTaxonomy)
        .where(
            TenantAssetTaxonomy.tenant_id == tenant_id,
            TenantAssetTaxonomy.deleted_at.is_(None),
        )
    )
    existing = (await db.execute(existing_query)).scalar_one()
    if existing > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Tenant already has {existing} taxonomy entries. "
                "Delete them first if you want to re-seed from defaults."
            ),
        )

    new_rows: list[TenantAssetTaxonomy] = []
    for tier_code, keyword in _all_tier_codes_from_legacy():
        new_rows.append(
            TenantAssetTaxonomy(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                tier_code=tier_code,
                keyword=keyword,
                asset_type=None,
                created_by_user_id=current_user.id,
            )
        )

    if not new_rows:
        # Should not happen — legacy JSON ships with content — but be defensive.
        raise HTTPException(
            status_code=500,
            detail="No legacy keywords available to seed.",
        )

    db.add_all(new_rows)
    db.add(AuditLog(
        user_id=current_user.id,
        action="taxonomy_defaults_imported",
        resource_type="asset_taxonomy",
        resource_id=None,
        details={"inserted_count": len(new_rows)},
        tenant_id=tenant_id,
    ))
    await db.commit()
    for r in new_rows:
        await db.refresh(r)
    invalidate_tenant_cache(tenant_id)

    return BulkImportResponse(
        inserted=len(new_rows),
        items=[TaxonomyEntryRead.from_orm(r) for r in new_rows],
    )

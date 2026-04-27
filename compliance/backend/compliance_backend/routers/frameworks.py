"""
Framework registry API.

Endpoints:
  GET /frameworks                       — list all frameworks
  GET /frameworks/{short_code}          — framework details + current version
  GET /frameworks/{short_code}/controls — paginated control list, filterable by category

All endpoints require a valid JWT (STANDALONE or INTEGRATED mode).
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from compliance_backend.database import get_async_session
from compliance_backend.middleware.auth import require_auth
from compliance_backend.models.framework import Framework, FrameworkVersion, Control

router = APIRouter(prefix="/frameworks", tags=["frameworks"])


# ---------------------------------------------------------------------------
# Response schemas (Pydantic v2)
# ---------------------------------------------------------------------------

class FrameworkVersionOut(BaseModel):
    id: str
    version: str
    effective_date: Optional[str]
    is_current: bool

    model_config = {"from_attributes": True}


class FrameworkListItem(BaseModel):
    id: str
    name: str
    short_code: str
    category: str
    description: Optional[str]

    model_config = {"from_attributes": True}


class FrameworkDetail(BaseModel):
    id: str
    name: str
    short_code: str
    category: str
    description: Optional[str]
    current_version: Optional[FrameworkVersionOut]
    all_versions: List[FrameworkVersionOut]

    model_config = {"from_attributes": True}


class ControlOut(BaseModel):
    id: str
    control_code: str
    category: str
    title: Optional[str]
    description: str
    rule_function: Optional[str]

    model_config = {"from_attributes": True}


class PaginatedControls(BaseModel):
    items: List[ControlOut]
    total: int
    page: int
    limit: int
    pages: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=List[FrameworkListItem])
async def list_frameworks(
    session: AsyncSession = Depends(get_async_session),
    _claims: dict = Depends(require_auth),
) -> List[FrameworkListItem]:
    """List all frameworks available in the system."""
    result = await session.execute(select(Framework).order_by(Framework.name))
    frameworks = result.scalars().all()
    return [
        FrameworkListItem(
            id=f.id,
            name=f.name,
            short_code=f.short_code,
            category=f.category,
            description=f.description,
        )
        for f in frameworks
    ]


@router.get("/{short_code}", response_model=FrameworkDetail)
async def get_framework(
    short_code: str,
    session: AsyncSession = Depends(get_async_session),
    _claims: dict = Depends(require_auth),
) -> FrameworkDetail:
    """Framework details including current version."""
    result = await session.execute(
        select(Framework).where(Framework.short_code == short_code.upper())
    )
    framework = result.scalars().first()
    if not framework:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Framework '{short_code}' not found",
        )

    # Fetch versions
    versions_result = await session.execute(
        select(FrameworkVersion)
        .where(FrameworkVersion.framework_id == framework.id)
        .order_by(FrameworkVersion.is_current.desc(), FrameworkVersion.version.desc())
    )
    versions = versions_result.scalars().all()

    current = next((v for v in versions if v.is_current), versions[0] if versions else None)

    def _version_out(v: FrameworkVersion) -> FrameworkVersionOut:
        return FrameworkVersionOut(
            id=v.id,
            version=v.version,
            effective_date=v.effective_date.isoformat() if v.effective_date else None,
            is_current=v.is_current,
        )

    return FrameworkDetail(
        id=framework.id,
        name=framework.name,
        short_code=framework.short_code,
        category=framework.category,
        description=framework.description,
        current_version=_version_out(current) if current else None,
        all_versions=[_version_out(v) for v in versions],
    )


@router.get("/{short_code}/controls", response_model=PaginatedControls)
async def list_controls(
    short_code: str,
    category: Optional[str] = Query(None, description="Filter by Trust Services Category or Annex A category"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
    _claims: dict = Depends(require_auth),
) -> PaginatedControls:
    """
    Paginated list of controls for a given framework.

    Uses the framework's current version. Optionally filter by category.
    """
    # Resolve framework
    result = await session.execute(
        select(Framework).where(Framework.short_code == short_code.upper())
    )
    framework = result.scalars().first()
    if not framework:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Framework '{short_code}' not found",
        )

    # Get current version
    versions_result = await session.execute(
        select(FrameworkVersion)
        .where(FrameworkVersion.framework_id == framework.id)
        .order_by(FrameworkVersion.is_current.desc())
    )
    versions = versions_result.scalars().all()
    current_version = next((v for v in versions if v.is_current), versions[0] if versions else None)

    if not current_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No versions found for framework '{short_code}'",
        )

    # Base query
    base_q = select(Control).where(Control.framework_version_id == current_version.id)
    count_q = select(func.count()).where(Control.framework_version_id == current_version.id)

    if category:
        base_q = base_q.where(Control.category == category)
        count_q = count_q.where(Control.category == category)

    # Count
    total_result = await session.execute(count_q)
    total = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * limit
    paginated_q = base_q.order_by(Control.control_code).offset(offset).limit(limit)
    controls_result = await session.execute(paginated_q)
    controls = controls_result.scalars().all()

    import math
    pages = math.ceil(total / limit) if total > 0 else 1

    return PaginatedControls(
        items=[
            ControlOut(
                id=c.id,
                control_code=c.control_code,
                category=c.category,
                title=c.title,
                description=c.description,
                rule_function=c.rule_function,
            )
            for c in controls
        ],
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )

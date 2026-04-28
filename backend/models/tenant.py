import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Tenant(Base):
    """
    Central tenant registry.

    One row per client organisation.  All domain tables reference this table
    via tenant_id FK with ondelete=RESTRICT so a tenant cannot be deleted
    while data still exists under it.

    Fields
    ------
    id          : UUID primary key
    name        : Human-readable display name, e.g. "Acme Corp"
    slug        : URL-safe unique identifier, e.g. "acme" — used in subdomain routing
    domain      : Primary email domain for this tenant, e.g. "example.com"
    is_active   : Soft-disable without deleting (blocks logins, API calls)
    settings    : Arbitrary JSON for branding (logo, colors), scoring weights,
                  module flags, SLA overrides, etc.  Compliance layer reads this too.
    created_at  : Immutable timestamp
    """

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    settings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    # Hybrid-SaaS Phase 4: license key issued by us, used by Docker agent
    # to register itself against the cloud portal.  Constant-time compared
    # in /api/agent-ingest/register.  Nullable on existing rows for backward-compat.
    license_key: Mapped[str | None] = mapped_column(
        String(128), unique=True, nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

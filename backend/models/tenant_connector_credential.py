"""
backend/models/tenant_connector_credential.py
Alembic migration: see alembic/versions/xxxx_add_tenant_connector_credentials.py

P1.6: Connector Framework Abstraction — credential vault DB backing table.

Design decisions
----------------
- One row per (tenant_id, connector_name) — upsert pattern on save.
- encrypted_blob stores the Fernet ciphertext of the credentials dict; the
  application never writes raw credentials to this column.
- LargeBinary used for encrypted_blob: Fernet tokens are byte strings of
  variable length (typically 150–400 bytes for typical credential dicts).
- created_at / updated_at follow the pattern of every other model in this repo.
- The unique constraint (tenant_id, connector_name) enforces one active
  credential set per connector per tenant; credential rotation replaces the row.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, LargeBinary, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class TenantConnectorCredential(Base):
    __tablename__ = "tenant_connector_credentials"
    __table_args__ = (
        UniqueConstraint("tenant_id", "connector_name", name="uq_tenant_connector_cred"),
        Index("idx_tcc_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    connector_name: Mapped[str] = mapped_column(String(50), nullable=False)
    encrypted_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

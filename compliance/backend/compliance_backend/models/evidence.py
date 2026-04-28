"""
Evidence — P2B.4

Tracks a single piece of compliance evidence tied to a control.

Evidence types:
  screenshot  — captured screenshot of a configuration UI
  config      — raw config dump (JSON/YAML/text)
  log         — audit log excerpt
  ticket      — link to a JIRA/Linear ticket
  document    — uploaded PDF/DOCX

Design notes:
  - storage_uri: opaque URI.  For filesystem-backed dev storage: file:///.
    Production will use s3:// or r2:// URIs.
  - metadata: arbitrary JSON dict (e.g. {"source": "aws_config", "region": "us-east-1"})
  - audit_period: ISO string "YYYY" or "YYYY-H1" / "YYYY-H2" — e.g. "2026" or "2026-Q1"
  - captured_by: "system" for auto-collected, user_id for manual uploads
  - UUID stored as String(36) for SQLite compatibility.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from compliance_backend.database import Base


class Evidence(Base):
    """
    A single evidence artifact attached to a control.

    Auto-collected evidence (from control engine): captured_by = "system"
    Manual uploads: captured_by = <user_id>
    """
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    control_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("controls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # framework_id derived at capture time from control's framework_version.framework_id
    framework_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    # M7 (Codex MED-003 + Kimi MED-010) — standardised on String(36) so
    # tenant_id is uniform across all compliance tables; matches a UUID's
    # canonical 36-char form (8-4-4-4-12 with dashes). Prevents implicit
    # truncation / index-mismatch and lets us add a UUID-format CHECK
    # constraint in a follow-up migration.
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    # screenshot | config | log | ticket | document
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Opaque storage URI: file:///..., s3://bucket/key, r2://bucket/key
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    # ISO period string e.g. "2026" or "2026-Q1"
    audit_period: Mapped[str] = mapped_column(String(50), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    # "system" for auto-collected, user_id for manual
    captured_by: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    # Arbitrary metadata (source tool, region, policy name, etc.)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # CRIT-009 — Integrity hash of the stored content (hex SHA-256, 64 chars).
    # Required for new rows; nullable for legacy rows pending backfill.
    # Re-verified on every read; mismatch raises EvidenceTamperError.
    content_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Evidence id={self.id} control={self.control_id} "
            f"tenant={self.tenant_id} type={self.type}>"
        )

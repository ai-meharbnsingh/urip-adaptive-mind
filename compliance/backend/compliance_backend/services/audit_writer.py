"""
Tiny helper for writing ComplianceAuditLog rows from routers.

Why a helper instead of inlining?
  - Centralised JSON serialisation of the details payload (datetimes / UUIDs).
  - One single place to evolve audit semantics (e.g., signing, IP capture)
    without touching every router.
  - Makes router code one-liner: `await write_audit(...)`.

Atomicity rules
  - Caller MUST add the row inside the SAME `await session.commit()` that
    persists the state change.  This helper only `session.add()`s the row;
    it does NOT commit.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.models.compliance_audit_log import ComplianceAuditLog


def _serialise(details: Optional[dict]) -> Optional[str]:
    if details is None:
        return None
    # json.dumps with default=str handles datetimes / UUIDs / dates safely.
    return json.dumps(details, default=str)


async def write_audit(
    session: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
) -> ComplianceAuditLog:
    """
    Stage a ComplianceAuditLog row in the current transaction.

    The caller is responsible for `await session.commit()` afterwards —
    this is what guarantees atomicity with the state mutation.

    `tenant_id` MUST be supplied (NOT NULL on the model).  Do not pass an
    empty string — we treat that as a programming error.
    """
    if not tenant_id:
        raise ValueError("write_audit: tenant_id must be a non-empty string")
    if not user_id:
        raise ValueError("write_audit: user_id must be a non-empty string")

    row = ComplianceAuditLog(
        tenant_id=tenant_id,
        user_id=str(user_id),
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        details_json=_serialise(details),
    )
    session.add(row)
    await session.flush()  # assign id; flush within current transaction
    return row

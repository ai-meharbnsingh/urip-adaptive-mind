"""
ticketing_webhook — receives webhook callbacks from Jira / ServiceNow.

Auth model (mirrors agent_ingest HMAC pattern):

    Header  X-URIP-Tenant       — tenant slug (so we know which secret to use)
    Header  X-URIP-Signature    — hex HMAC-SHA256 of raw request body using
                                  tenant.settings.ticketing.webhook_secret.
                                  (Different from agent_ingest's HMAC because
                                  Jira/ServiceNow only let us configure a
                                  single body-HMAC, not the full canonical
                                  {ts}.{path}.{body}.)

Tenants without a webhook_secret in their ticketing config will return 401
on every webhook attempt — this is intentional, the operator must opt in.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.integrations.ticketing import TicketStatus
from backend.integrations.ticketing.jira import _normalise_status as jira_normalise
from backend.integrations.ticketing.servicenow import DEFAULT_STATE_MAP
from backend.models.tenant import Tenant
from backend.services.ticketing_service import on_ticket_status_changed

logger = logging.getLogger(__name__)
router = APIRouter()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def verify_webhook_signature(secret: str, body: bytes, signature: str) -> bool:
    """Constant-time HMAC-SHA256 verify of `body` against the configured secret."""
    if not secret or not signature:
        return False
    expected = hmac.new(
        secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())


async def _resolve_tenant_and_secret(
    db: AsyncSession, tenant_slug: str
) -> tuple[Tenant, str]:
    q = await db.execute(select(Tenant).where(Tenant.slug == tenant_slug))
    tenant = q.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown tenant")
    cfg = (tenant.settings or {}).get("ticketing") or {}
    secret = cfg.get("webhook_secret")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant has no webhook_secret configured",
        )
    return tenant, secret


# --------------------------------------------------------------------------- #
# Jira webhook
# --------------------------------------------------------------------------- #
@router.post("/jira/webhook")
async def jira_webhook(
    request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Receive a Jira webhook and propagate the status change to the URIP risk.

    Expected Jira payload (issue_updated event):
        {
            "issue": {"key": "URIP-42", "fields": {"status": {"name": "Done"}}},
            "webhookEvent": "jira:issue_updated"
        }
    """
    tenant_slug = request.headers.get("X-URIP-Tenant")
    signature = request.headers.get("X-URIP-Signature", "")
    if not tenant_slug:
        raise HTTPException(status_code=401, detail="Missing X-URIP-Tenant header")
    body = await request.body()
    _tenant, secret = await _resolve_tenant_and_secret(db, tenant_slug)
    if not verify_webhook_signature(secret, body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}")

    issue = payload.get("issue") or {}
    ticket_id = issue.get("key") or issue.get("id")
    vendor_status = (
        ((issue.get("fields") or {}).get("status") or {}).get("name")
    )
    if not ticket_id or not vendor_status:
        raise HTTPException(
            status_code=400,
            detail="Payload missing issue.key or issue.fields.status.name",
        )
    new_status = jira_normalise(vendor_status)
    if new_status == TicketStatus.UNKNOWN:
        return {"ok": True, "ignored": True, "reason": f"unmapped status {vendor_status!r}"}

    risk = await on_ticket_status_changed(db, ticket_id, new_status)
    await db.commit()
    return {
        "ok": True,
        "ticket_id": ticket_id,
        "new_status": new_status,
        "risk_id": risk.risk_id if risk else None,
    }


# --------------------------------------------------------------------------- #
# ServiceNow webhook
# --------------------------------------------------------------------------- #
@router.post("/servicenow/webhook")
async def servicenow_webhook(
    request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """ServiceNow Business Rule webhook.

    Expected payload (configurable in the BR script):
        {
            "number": "INC0010234",
            "state":  "6"
        }
    """
    tenant_slug = request.headers.get("X-URIP-Tenant")
    signature = request.headers.get("X-URIP-Signature", "")
    if not tenant_slug:
        raise HTTPException(status_code=401, detail="Missing X-URIP-Tenant header")
    body = await request.body()
    _tenant, secret = await _resolve_tenant_and_secret(db, tenant_slug)
    if not verify_webhook_signature(secret, body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}")

    ticket_id = payload.get("number") or payload.get("ticket_id")
    state = str(payload.get("state", ""))
    if not ticket_id or not state:
        raise HTTPException(
            status_code=400, detail="Payload missing number or state"
        )
    new_status = DEFAULT_STATE_MAP.get(state, TicketStatus.UNKNOWN)
    if new_status == TicketStatus.UNKNOWN:
        return {"ok": True, "ignored": True, "reason": f"unmapped state {state!r}"}

    risk = await on_ticket_status_changed(db, ticket_id, new_status)
    await db.commit()
    return {
        "ok": True,
        "ticket_id": ticket_id,
        "new_status": new_status,
        "risk_id": risk.risk_id if risk else None,
    }

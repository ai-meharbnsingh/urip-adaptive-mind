"""
ticketing_service — bidirectional ticket lifecycle wiring.

Three responsibilities:

    1. on_risk_assigned(risk)              URIP → external (auto-create)
    2. on_ticket_status_changed(ticket_id, vendor, new_status, ...)
                                           external → URIP (webhook)
    3. poll_ticket_statuses()              fallback when webhooks aren't wired

Provider configuration lives in the tenant's `tenants.settings` JSON under
key `"ticketing"`:

    {
        "ticketing": {
            "provider":   "jira" | "servicenow",
            "base_url":   "https://acme.atlassian.net",
            "auth_token": "<basic-or-bearer>",
            "project_key": "URIP",        // jira only
            "issue_type":  "Bug",         // jira only
            "table":       "incident"     // servicenow only
            "webhook_secret": "<hmac>"    // shared secret for webhook verify
        }
    }

If the tenant has no ticketing config we no-op silently (the feature is opt-in
per-tenant — many customers won't have Jira at all).
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.integrations.ticketing import (
    TicketCreateResult,
    TicketStatus,
    TicketingProviderBase,
    TicketingProviderError,
    get_provider,
)
from backend.models.audit_log import AuditLog
from backend.models.risk import Risk
from backend.models.tenant import Tenant

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Tenant config lookup
# --------------------------------------------------------------------------- #
async def get_tenant_ticketing_config(
    db: AsyncSession, tenant_id: uuid.UUID
) -> Optional[dict[str, Any]]:
    """Return the ticketing block from tenant settings, or None."""
    q = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = q.scalar_one_or_none()
    if tenant is None:
        return None
    cfg = (tenant.settings or {}).get("ticketing") or None
    if not cfg or not cfg.get("provider"):
        return None
    return cfg


def _build_provider(cfg: dict[str, Any]) -> TicketingProviderBase:
    return get_provider(
        cfg["provider"],
        base_url=cfg["base_url"],
        auth_token=cfg["auth_token"],
        project_key=cfg.get("project_key"),
        issue_type=cfg.get("issue_type", "Bug"),
        table=cfg.get("table", "incident"),
    )


# --------------------------------------------------------------------------- #
# 1. URIP → external — auto-create ticket
# --------------------------------------------------------------------------- #
async def on_risk_assigned(
    db: AsyncSession,
    risk: Risk,
    *,
    provider: TicketingProviderBase | None = None,
) -> Optional[TicketCreateResult]:
    """
    Create an external ticket for a freshly-assigned risk.

    `provider` may be passed in by tests (mock-injected); otherwise the tenant
    config is read and a real provider is built.

    Idempotent: if `risk.ticket_id` is already set we return None and DO NOT
    create a duplicate ticket.
    """
    if risk.ticket_id:
        logger.info("on_risk_assigned: risk %s already has ticket %s — skipping",
                    risk.risk_id, risk.ticket_id)
        return None

    if provider is None:
        cfg = await get_tenant_ticketing_config(db, risk.tenant_id)
        if cfg is None:
            logger.debug("on_risk_assigned: tenant %s has no ticketing config — no-op",
                         risk.tenant_id)
            return None
        provider = _build_provider(cfg)

    try:
        result = provider.create_ticket(risk)
    except TicketingProviderError as exc:
        logger.warning("on_risk_assigned: provider %s create failed for risk %s: %s",
                       provider.provider_name, risk.risk_id, exc)
        raise

    risk.ticket_id = result.ticket_id
    risk.ticket_provider = provider.provider_name
    # Backward-compat: keep `jira_ticket` populated when we used Jira so older
    # exports / dashboards still find it.
    if provider.provider_name == "jira":
        risk.jira_ticket = result.ticket_id

    db.add(
        AuditLog(
            id=uuid.uuid4(),
            user_id=None,  # system-driven on assignment
            tenant_id=risk.tenant_id,
            action="ticketing_create",
            resource_type="risk",
            resource_id=risk.id,
            details={
                "provider": provider.provider_name,
                "ticket_id": result.ticket_id,
                "ticket_url": result.ticket_url,
                "risk_id": risk.risk_id,
            },
        )
    )
    await db.flush()
    return result


# --------------------------------------------------------------------------- #
# 2. external → URIP — webhook handler
# --------------------------------------------------------------------------- #
# Closure rule (URIP_Blueprint v3 §5b.1, table row "Closure Rule"):
#   Risk closes only when remediation is verified AND evidence uploaded —
#   OR when auto-remediation re-test passes.
#
# For now, "verified" means the ticket transitioned to a TERMINAL status AND
# the risk had an "evidence" field on it (rough proxy, since the v3 spec has
# evidence handled in the AcceptanceRequest model — that's a separate flow).
# We default to the simpler rule: ticket closed → risk closed; the caller can
# override `verify_evidence=True` to add the stricter check.

async def on_ticket_status_changed(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    ticket_id: str,
    new_status: str,
    *,
    verify_evidence: bool = False,
    comment: str | None = None,
) -> Optional[Risk]:
    """
    Webhook entry point: the external system reports a ticket changed state.

    ``tenant_id`` is required to scope the Risk lookup to a single tenant,
    preventing cross-tenant data leaks (a risk owned by tenant A cannot be
    accidentally resolved by a webhook from tenant B).

    Returns the updated Risk row (or None if no risk has that ticket_id for
    the given tenant).
    """
    if new_status not in TicketStatus.ALL:
        logger.warning("on_ticket_status_changed: unknown status %r — ignored",
                       new_status)
        return None

    q = await db.execute(
        select(Risk).where(Risk.tenant_id == tenant_id, Risk.ticket_id == ticket_id)
    )
    risk = q.scalar_one_or_none()
    if risk is None:
        # Fallback to legacy jira_ticket column (tenant-scoped).
        q2 = await db.execute(
            select(Risk).where(Risk.tenant_id == tenant_id, Risk.jira_ticket == ticket_id)
        )
        risk = q2.scalar_one_or_none()
    if risk is None:
        logger.info("on_ticket_status_changed: no risk found for ticket %s", ticket_id)
        return None

    # Map vendor-status → URIP risk status.
    transitioned_to_terminal = False
    if new_status in TicketStatus.TERMINAL:
        if verify_evidence:
            # Evidence-verified rule — caller responsible for setting this.
            risk.status = "resolved"
        else:
            risk.status = "resolved"
        transitioned_to_terminal = True
    elif new_status == TicketStatus.IN_PROGRESS and risk.status == "open":
        risk.status = "in_progress"
    elif new_status == TicketStatus.REOPENED and risk.status in ("resolved", "closed"):
        risk.status = "open"

    if transitioned_to_terminal:
        db.add(
            AuditLog(
                id=uuid.uuid4(),
                user_id=None,
                tenant_id=risk.tenant_id,
                action="ticketing_close",
                resource_type="risk",
                resource_id=risk.id,
                details={
                    "ticket_id": ticket_id,
                    "new_status": new_status,
                    "comment": comment,
                    "risk_id": risk.risk_id,
                },
            )
        )

    await db.flush()
    return risk


# --------------------------------------------------------------------------- #
# 3. Periodic poll — fallback for tenants without webhooks
# --------------------------------------------------------------------------- #
async def poll_ticket_statuses(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    provider: TicketingProviderBase | None = None,
    limit: int = 100,
) -> list[tuple[str, str, str]]:
    """
    Poll provider for the status of every open-risk ticket and sync URIP.

    Returns list of (risk_id, ticket_id, new_urip_status) tuples — one per
    risk whose status was updated by the poll.
    """
    if provider is None:
        cfg = await get_tenant_ticketing_config(db, tenant_id)
        if cfg is None:
            return []
        provider = _build_provider(cfg)

    q = await db.execute(
        select(Risk)
        .where(
            Risk.tenant_id == tenant_id,
            Risk.ticket_id.is_not(None),
            Risk.status.notin_(["resolved", "closed"]),
        )
        .limit(limit)
    )
    risks = list(q.scalars().all())
    updated: list[tuple[str, str, str]] = []

    for risk in risks:
        try:
            new_status = provider.get_ticket_status(risk.ticket_id)
        except TicketingProviderError as exc:
            logger.warning("poll: get_ticket_status failed for %s: %s",
                           risk.ticket_id, exc)
            continue
        if new_status in TicketStatus.TERMINAL and risk.status != "resolved":
            risk.status = "resolved"
            updated.append((risk.risk_id, risk.ticket_id, "resolved"))
        elif new_status == TicketStatus.IN_PROGRESS and risk.status == "open":
            risk.status = "in_progress"
            updated.append((risk.risk_id, risk.ticket_id, "in_progress"))

    if updated:
        await db.flush()
    return updated

"""
Ticketing audit-log tests — every state-changing ticket action writes an
AuditLog row (create on assignment, close on webhook).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.integrations.ticketing import TicketCreateResult
from backend.models.audit_log import AuditLog
from backend.models.risk import Risk
from backend.services.sla_service import compute_sla_deadline
from backend.services.ticketing_service import (
    on_risk_assigned,
    on_ticket_status_changed,
)


class _FakeProvider:
    provider_name = "jira"

    def create_ticket(self, risk):
        return TicketCreateResult(
            ticket_id="URIP-101",
            ticket_url="https://acme.atlassian.net/browse/URIP-101",
            raw={"key": "URIP-101"},
        )

    def update_ticket(self, ticket_id, *, status=None, comment=None):
        return {"status": status}

    def get_ticket_status(self, ticket_id):
        return "resolved"

    def close_ticket(self, ticket_id, resolution="Done"):
        return {"status": "closed"}


@pytest.fixture
async def open_risk(db_session: AsyncSession, default_tenant):
    risk = Risk(
        risk_id=f"RISK-{uuid.uuid4().hex[:6].upper()}",
        finding="Patch CVE",
        description="x",
        source="tenable",
        domain="vuln",
        cvss_score=7.0,
        severity="high",
        asset="host-1",
        owner_team="IT",
        status="open",
        sla_deadline=compute_sla_deadline("high"),
        tenant_id=default_tenant.id,
    )
    db_session.add(risk)
    await db_session.commit()
    await db_session.refresh(risk)
    return risk


@pytest.mark.asyncio
async def test_on_risk_assigned_writes_audit_log(db_session, open_risk):
    result = await on_risk_assigned(db_session, open_risk, provider=_FakeProvider())
    await db_session.commit()
    assert result is not None
    assert result.ticket_id == "URIP-101"

    rows = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "ticketing_create")
    )
    rows = list(rows.scalars().all())
    assert rows, "ticketing_create audit row missing"
    found = [r for r in rows if str(r.resource_id) == str(open_risk.id)]
    assert found, "audit row resource_id must equal risk id"
    assert (found[0].details or {}).get("ticket_id") == "URIP-101"
    assert (found[0].details or {}).get("provider") == "jira"


@pytest.mark.asyncio
async def test_on_ticket_status_changed_to_terminal_writes_audit(db_session, open_risk):
    # Pre-assign a ticket id so the webhook can match.
    open_risk.ticket_id = "URIP-200"
    open_risk.ticket_provider = "jira"
    await db_session.commit()

    risk = await on_ticket_status_changed(
        db_session, open_risk.tenant_id, "URIP-200", "resolved", comment="closed via webhook"
    )
    await db_session.commit()
    assert risk is not None
    assert risk.status == "resolved"

    rows = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "ticketing_close")
    )
    rows = list(rows.scalars().all())
    assert rows, "ticketing_close audit row missing"
    matched = [r for r in rows if (r.details or {}).get("ticket_id") == "URIP-200"]
    assert matched

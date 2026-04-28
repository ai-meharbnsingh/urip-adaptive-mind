"""ticketing_service — service-layer integration tests against the test DB."""
from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.integrations.ticketing import TicketStatus
from backend.integrations.ticketing.base import TicketCreateResult, TicketingProviderBase
from backend.models.risk import Risk
from backend.models.tenant import Tenant
from backend.services.ticketing_service import (
    on_risk_assigned,
    on_ticket_status_changed,
    poll_ticket_statuses,
)


# --------------------------------------------------------------------------- #
# Mock provider — used by all tests in this module.
# --------------------------------------------------------------------------- #
class MockProvider(TicketingProviderBase):
    provider_name = "mock"

    def __init__(self, status_to_return: str = TicketStatus.OPEN) -> None:
        self.created: list[Any] = []
        self.updates: list[tuple[str, dict[str, Any]]] = []
        self.status_to_return = status_to_return
        self._next_id = 1

    def create_ticket(self, risk):
        ticket_id = f"MOCK-{self._next_id:04d}"
        self._next_id += 1
        self.created.append(risk)
        return TicketCreateResult(ticket_id=ticket_id, ticket_url=None, raw={})

    def update_ticket(self, ticket_id, *, status=None, comment=None):
        self.updates.append((ticket_id, {"status": status, "comment": comment}))
        return {}

    def get_ticket_status(self, ticket_id):
        return self.status_to_return

    def close_ticket(self, ticket_id, resolution="Done"):
        self.updates.append((ticket_id, {"closed": True}))
        return {}


# --------------------------------------------------------------------------- #
@pytest_asyncio.fixture
async def risk_with_tenant(db_session: AsyncSession):
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Test Co",
        slug="test-co",
        domain="test.co",
        is_active=True,
        settings={
            "ticketing": {
                "provider": "jira",
                "base_url": "https://acme.atlassian.net",
                "auth_token": "u:t",
                "project_key": "URIP",
                "webhook_secret": "shh",
            }
        },
    )
    db_session.add(tenant)
    await db_session.commit()

    risk = Risk(
        id=uuid.uuid4(),
        risk_id="RISK-2026-100",
        finding="Test finding",
        description="Test desc",
        source="vapt",
        domain="application",
        cvss_score=8.0,
        severity="high",
        asset="srv-01.test",
        owner_team="AppSec",
        status="open",
        sla_deadline=datetime.now(timezone.utc) + timedelta(days=7),
        tenant_id=tenant.id,
    )
    db_session.add(risk)
    await db_session.commit()
    await db_session.refresh(risk)
    return risk, tenant


# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_on_risk_assigned_creates_ticket_and_persists_id(
    db_session: AsyncSession, risk_with_tenant
):
    risk, _tenant = risk_with_tenant
    provider = MockProvider()
    result = await on_risk_assigned(db_session, risk, provider=provider)
    await db_session.commit()

    assert result is not None
    assert result.ticket_id == "MOCK-0001"
    assert risk.ticket_id == "MOCK-0001"
    assert risk.ticket_provider == "mock"
    assert len(provider.created) == 1


@pytest.mark.asyncio
async def test_on_risk_assigned_idempotent_when_ticket_id_already_set(
    db_session: AsyncSession, risk_with_tenant
):
    risk, _tenant = risk_with_tenant
    risk.ticket_id = "EXISTING-1"
    risk.ticket_provider = "jira"
    await db_session.commit()

    provider = MockProvider()
    result = await on_risk_assigned(db_session, risk, provider=provider)
    assert result is None
    assert len(provider.created) == 0
    # Original ticket_id preserved.
    assert risk.ticket_id == "EXISTING-1"


@pytest.mark.asyncio
async def test_on_ticket_status_changed_resolved_closes_risk(
    db_session: AsyncSession, risk_with_tenant
):
    risk, _ = risk_with_tenant
    risk.ticket_id = "MOCK-9999"
    risk.ticket_provider = "mock"
    await db_session.commit()

    updated = await on_ticket_status_changed(db_session, risk.tenant_id, "MOCK-9999", TicketStatus.RESOLVED)
    await db_session.commit()
    assert updated is not None
    assert updated.status == "resolved"


@pytest.mark.asyncio
async def test_on_ticket_status_changed_in_progress_updates_risk(
    db_session: AsyncSession, risk_with_tenant
):
    risk, _ = risk_with_tenant
    risk.ticket_id = "MOCK-9998"
    await db_session.commit()

    await on_ticket_status_changed(db_session, risk.tenant_id, "MOCK-9998", TicketStatus.IN_PROGRESS)
    await db_session.commit()
    await db_session.refresh(risk)
    assert risk.status == "in_progress"


@pytest.mark.asyncio
async def test_on_ticket_status_changed_unknown_ticket_noop(db_session: AsyncSession):
    dummy_tenant_id = uuid.uuid4()
    out = await on_ticket_status_changed(db_session, dummy_tenant_id, "NEVER-EXISTED", TicketStatus.RESOLVED)
    assert out is None


@pytest.mark.asyncio
async def test_poll_ticket_statuses_picks_up_resolved_in_provider(
    db_session: AsyncSession, risk_with_tenant
):
    risk, tenant = risk_with_tenant
    risk.ticket_id = "MOCK-1"
    await db_session.commit()

    # Provider says: ticket is now Resolved.
    provider = MockProvider(status_to_return=TicketStatus.RESOLVED)
    updates = await poll_ticket_statuses(
        db_session, tenant.id, provider=provider
    )
    await db_session.commit()
    await db_session.refresh(risk)
    assert risk.status == "resolved"
    assert ("RISK-2026-100", "MOCK-1", "resolved") in updates


@pytest.mark.asyncio
async def test_poll_ticket_statuses_skips_already_resolved_risks(
    db_session: AsyncSession, risk_with_tenant
):
    risk, tenant = risk_with_tenant
    risk.ticket_id = "MOCK-1"
    risk.status = "resolved"
    await db_session.commit()

    provider = MockProvider(status_to_return=TicketStatus.RESOLVED)
    updates = await poll_ticket_statuses(db_session, tenant.id, provider=provider)
    assert updates == []

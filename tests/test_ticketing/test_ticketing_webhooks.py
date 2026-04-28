"""Webhook router — HMAC verification + status propagation tests."""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.main import app
from backend.models.risk import Risk
from backend.models.tenant import Tenant
from backend.routers.ticketing_webhook import router as ticketing_router

# Mount the router into the app under /api/ticketing only once across the test
# session — register-then-skip if already registered.
_PREFIX = "/api/ticketing"
if not any(getattr(r, "path", "").startswith(_PREFIX) for r in app.routes):
    app.include_router(ticketing_router, prefix=_PREFIX, tags=["Ticketing Webhooks"])


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest_asyncio.fixture
async def tenant_with_ticketing(db_session: AsyncSession):
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Webhook Co",
        slug="webhook-co",
        domain="webhook.co",
        is_active=True,
        settings={"ticketing": {"provider": "jira", "webhook_secret": "shh-its-a-secret"}},
    )
    db_session.add(tenant)
    await db_session.commit()
    return tenant


@pytest_asyncio.fixture
async def risk_with_jira_ticket(db_session: AsyncSession, tenant_with_ticketing):
    risk = Risk(
        id=uuid.uuid4(),
        risk_id="RISK-WH-001",
        finding="Webhook test risk",
        source="vapt",
        domain="application",
        cvss_score=7.0,
        severity="high",
        asset="srv-01",
        owner_team="AppSec",
        status="open",
        sla_deadline=datetime.now(timezone.utc) + timedelta(days=7),
        tenant_id=tenant_with_ticketing.id,
        ticket_id="URIP-77",
        ticket_provider="jira",
    )
    db_session.add(risk)
    await db_session.commit()
    await db_session.refresh(risk)
    return risk


# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_jira_webhook_resolves_risk_when_done(
    client: AsyncClient,
    tenant_with_ticketing,
    risk_with_jira_ticket,
    db_session: AsyncSession,
):
    body = json.dumps({
        "issue": {"key": "URIP-77", "fields": {"status": {"name": "Done"}}},
        "webhookEvent": "jira:issue_updated",
    }).encode()
    sig = _sign("shh-its-a-secret", body)
    resp = await client.post(
        "/api/ticketing/jira/webhook",
        content=body,
        headers={
            "X-URIP-Tenant": "webhook-co",
            "X-URIP-Signature": sig,
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["new_status"] == "resolved"
    assert data["risk_id"] == "RISK-WH-001"

    await db_session.refresh(risk_with_jira_ticket)
    assert risk_with_jira_ticket.status == "resolved"


@pytest.mark.asyncio
async def test_jira_webhook_rejects_bad_signature(
    client: AsyncClient,
    tenant_with_ticketing,
    risk_with_jira_ticket,
):
    body = json.dumps({"issue": {"key": "URIP-77", "fields": {"status": {"name": "Done"}}}}).encode()
    resp = await client.post(
        "/api/ticketing/jira/webhook",
        content=body,
        headers={
            "X-URIP-Tenant": "webhook-co",
            "X-URIP-Signature": "wrong-signature",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_jira_webhook_rejects_unknown_tenant(client: AsyncClient):
    body = b"{}"
    resp = await client.post(
        "/api/ticketing/jira/webhook",
        content=body,
        headers={
            "X-URIP-Tenant": "no-such-tenant",
            "X-URIP-Signature": _sign("anything", body),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_servicenow_webhook_resolves_on_state_6(
    client: AsyncClient,
    tenant_with_ticketing,
    db_session: AsyncSession,
):
    risk = Risk(
        id=uuid.uuid4(),
        risk_id="RISK-WH-002",
        finding="SN webhook test",
        source="vapt",
        domain="application",
        cvss_score=7.0,
        severity="high",
        asset="srv-02",
        owner_team="AppSec",
        status="open",
        sla_deadline=datetime.now(timezone.utc) + timedelta(days=7),
        tenant_id=tenant_with_ticketing.id,
        ticket_id="INC0010234",
        ticket_provider="servicenow",
    )
    db_session.add(risk)
    await db_session.commit()

    body = json.dumps({"number": "INC0010234", "state": "6"}).encode()
    sig = _sign("shh-its-a-secret", body)
    resp = await client.post(
        "/api/ticketing/servicenow/webhook",
        content=body,
        headers={
            "X-URIP-Tenant": "webhook-co",
            "X-URIP-Signature": sig,
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["new_status"] == "resolved"
    await db_session.refresh(risk)
    assert risk.status == "resolved"


@pytest.mark.asyncio
async def test_servicenow_webhook_unmapped_state_returns_ignored(
    client: AsyncClient, tenant_with_ticketing
):
    body = json.dumps({"number": "INC0010234", "state": "99"}).encode()
    sig = _sign("shh-its-a-secret", body)
    resp = await client.post(
        "/api/ticketing/servicenow/webhook",
        content=body,
        headers={
            "X-URIP-Tenant": "webhook-co",
            "X-URIP-Signature": sig,
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["ignored"] is True

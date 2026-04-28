"""
Auto-remediation audit-log writes — every execute call must produce an
AuditLog row recording approver_user_id and the resulting execution_id.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.audit_log import AuditLog
from backend.models.risk import Risk
from backend.services.sla_service import compute_sla_deadline


@pytest.mark.asyncio
async def test_execute_writes_audit_log(
    client: AsyncClient, db_session: AsyncSession, default_tenant, auth_headers
):
    risk = Risk(
        risk_id=f"RISK-{uuid.uuid4().hex[:6].upper()}",
        finding="Patch CrowdStrike",
        description="x",
        source="crowdstrike",
        domain="endpoint",
        cvss_score=7.0,
        severity="high",
        asset="device-007",
        owner_team="IT",
        status="open",
        sla_deadline=compute_sla_deadline("high"),
        tenant_id=default_tenant.id,
    )
    db_session.add(risk)
    await db_session.commit()

    resp = await client.post(
        f"/api/auto-remediation/{risk.id}/execute",
        json={"dry_run": True, "explicit_approval": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    execution_id = body["id"]

    await db_session.commit()
    rows = await db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "auto_remediation_execute",
            AuditLog.tenant_id == default_tenant.id,
        )
    )
    rows = list(rows.scalars().all())
    assert rows, "auto_remediation_execute audit row missing"
    found = [r for r in rows if str(r.resource_id) == execution_id]
    assert found, "audit row resource_id must match execution id"
    details = found[0].details or {}
    assert details.get("dry_run") is True
    assert "approver_user_id" in details

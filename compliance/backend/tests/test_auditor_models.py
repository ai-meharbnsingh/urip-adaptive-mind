"""
TDD — Auditor Portal models (P2B.10)

Models exercised here:
  - AuditorAccess          — invitation/access record bound to (tenant, framework, period)
  - EvidenceRequest        — auditor-initiated request for additional evidence
  - AuditorActivityLog     — append-only audit trail of every auditor action
  - ComplianceScoreSnapshot (P2B.11) — daily compliance-score snapshot per framework

These tests cover only persistence + tenant isolation. Route/flow tests live elsewhere.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from compliance_backend.models.auditor import (
    AuditorAccess,
    EvidenceRequest,
    AuditorActivityLog,
)
from compliance_backend.models.score_snapshot import ComplianceScoreSnapshot


# ---------------------------------------------------------------------------
# AuditorAccess
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_create_auditor_access_persists_all_fields(db_session):
    now = datetime.utcnow()
    rec = AuditorAccess(
        tenant_id="tenant-aud-1",
        auditor_email="auditor@bigfour.example",
        framework_id=str(uuid.uuid4()),
        audit_period_start=now - timedelta(days=30),
        audit_period_end=now + timedelta(days=30),
        invited_by_user_id="user-admin-1",
        invitation_token_hash="hash-deadbeef",
        expires_at=now + timedelta(days=30),
    )
    db_session.add(rec)
    await db_session.commit()

    found = (await db_session.execute(select(AuditorAccess).where(AuditorAccess.id == rec.id))).scalar_one()
    assert found.auditor_email == "auditor@bigfour.example"
    assert found.tenant_id == "tenant-aud-1"
    assert found.is_revoked is False
    assert found.accepted_at is None
    assert found.invitation_token_hash == "hash-deadbeef"


@pytest.mark.anyio
async def test_auditor_access_tenant_isolation(db_session):
    """A query filtered by tenant must not return another tenant's records."""
    now = datetime.utcnow()
    a = AuditorAccess(
        tenant_id="tenant-iso-A",
        auditor_email="a@x.com",
        framework_id="fw-A",
        audit_period_start=now,
        audit_period_end=now + timedelta(days=30),
        invited_by_user_id="u1",
        invitation_token_hash="h-A",
        expires_at=now + timedelta(days=30),
    )
    b = AuditorAccess(
        tenant_id="tenant-iso-B",
        auditor_email="b@x.com",
        framework_id="fw-B",
        audit_period_start=now,
        audit_period_end=now + timedelta(days=30),
        invited_by_user_id="u2",
        invitation_token_hash="h-B",
        expires_at=now + timedelta(days=30),
    )
    db_session.add_all([a, b])
    await db_session.commit()

    rows = (await db_session.execute(
        select(AuditorAccess).where(AuditorAccess.tenant_id == "tenant-iso-A")
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].auditor_email == "a@x.com"


@pytest.mark.anyio
async def test_auditor_access_revoke(db_session):
    now = datetime.utcnow()
    rec = AuditorAccess(
        tenant_id="t",
        auditor_email="x@x.com",
        framework_id="fw",
        audit_period_start=now,
        audit_period_end=now + timedelta(days=10),
        invited_by_user_id="u",
        invitation_token_hash=f"h-revoke-{uuid.uuid4()}",
        expires_at=now + timedelta(days=10),
    )
    db_session.add(rec)
    await db_session.commit()

    rec.is_revoked = True
    await db_session.commit()

    refreshed = (await db_session.execute(select(AuditorAccess).where(AuditorAccess.id == rec.id))).scalar_one()
    assert refreshed.is_revoked is True


# ---------------------------------------------------------------------------
# EvidenceRequest
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_evidence_request_persists(db_session):
    now = datetime.utcnow()
    access = AuditorAccess(
        tenant_id="t",
        auditor_email="ev@x.com",
        framework_id="fw",
        audit_period_start=now,
        audit_period_end=now + timedelta(days=10),
        invited_by_user_id="u",
        invitation_token_hash=f"h-er-persist-{uuid.uuid4()}",
        expires_at=now + timedelta(days=10),
    )
    db_session.add(access)
    await db_session.commit()

    req = EvidenceRequest(
        auditor_access_id=access.id,
        control_id="ctrl-1",
        description="Need additional log evidence for Q1",
    )
    db_session.add(req)
    await db_session.commit()

    found = (await db_session.execute(select(EvidenceRequest).where(EvidenceRequest.id == req.id))).scalar_one()
    assert found.description == "Need additional log evidence for Q1"
    assert found.fulfilled_at is None
    assert found.fulfillment_evidence_id is None
    assert found.requested_at is not None


@pytest.mark.anyio
async def test_evidence_request_fulfillment(db_session):
    now = datetime.utcnow()
    access = AuditorAccess(
        tenant_id="t",
        auditor_email="ev@x.com",
        framework_id="fw",
        audit_period_start=now,
        audit_period_end=now + timedelta(days=10),
        invited_by_user_id="u",
        invitation_token_hash=f"h-er-fulfill-{uuid.uuid4()}",
        expires_at=now + timedelta(days=10),
    )
    db_session.add(access)
    await db_session.commit()

    req = EvidenceRequest(
        auditor_access_id=access.id,
        control_id="ctrl-1",
        description="X",
    )
    db_session.add(req)
    await db_session.commit()

    req.fulfilled_at = datetime.utcnow()
    req.fulfilled_by_user_id = "user-admin-9"
    req.fulfillment_evidence_id = "ev-uuid-99"
    await db_session.commit()

    refreshed = (await db_session.execute(select(EvidenceRequest).where(EvidenceRequest.id == req.id))).scalar_one()
    assert refreshed.fulfilled_at is not None
    assert refreshed.fulfilled_by_user_id == "user-admin-9"
    assert refreshed.fulfillment_evidence_id == "ev-uuid-99"


# ---------------------------------------------------------------------------
# AuditorActivityLog
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_auditor_activity_log_persists(db_session):
    log = AuditorActivityLog(
        tenant_id="tenant-log",
        auditor_access_id="aa-uuid",
        auditor_email="al@x.com",
        action="list_controls",
        target_type="control",
        target_id=None,
        ip_address="127.0.0.1",
    )
    db_session.add(log)
    await db_session.commit()

    found = (await db_session.execute(select(AuditorActivityLog).where(AuditorActivityLog.id == log.id))).scalar_one()
    assert found.action == "list_controls"
    assert found.tenant_id == "tenant-log"
    assert found.accessed_at is not None
    assert found.target_id is None


# ---------------------------------------------------------------------------
# ComplianceScoreSnapshot (P2B.11)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_score_snapshot_persists(db_session):
    snap = ComplianceScoreSnapshot(
        tenant_id="tenant-snap",
        framework_id="fw-snap",
        snapshot_date=datetime.utcnow(),
        score=85.5,
        pass_count=17,
        fail_count=3,
        inconclusive_count=2,
        total_applicable=20,
    )
    db_session.add(snap)
    await db_session.commit()

    rows = (await db_session.execute(
        select(ComplianceScoreSnapshot).where(ComplianceScoreSnapshot.tenant_id == "tenant-snap")
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].score == 85.5
    assert rows[0].pass_count == 17
    assert rows[0].total_applicable == 20

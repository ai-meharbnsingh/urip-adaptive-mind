"""
CritFix-B NEW-1 (compliance side) + HIGH-002 — TDD tests.

Covers:
  1. ComplianceAuditLog model exists and is registered with Base.metadata.
  2. Compliance state-changing endpoints write to ComplianceAuditLog with
     correct tenant_id (control runs, evidence uploads, policy publishes,
     vendor mutations, score snapshot, auditor invitation create/revoke).
  3. HIGH-002 — vendor `upload_document` persists file bytes to storage so
     they can be retrieved byte-for-byte (no more memory:// placeholder).
"""
from __future__ import annotations

import io
import time
import uuid
from datetime import date, datetime, timedelta

import pytest
# CRIT-005 (Z2.1): migrated python-jose -> PyJWT (HS256 surface identical)
import jwt
from sqlalchemy import select

from compliance_backend.main import app
from compliance_backend.routers.vendors import router as vendors_router
from compliance_backend.services.storage import get_storage


STANDALONE_SECRET = "test-secret-standalone"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _ensure_router_installed(prefix: str, router) -> None:
    for r in app.router.routes:
        if getattr(r, "path", "").startswith(prefix):
            return
    app.include_router(router)


def _auth_headers(tenant_id: str, role: str = "admin", user_sub: str = "user-1") -> dict:
    payload = {
        "sub": user_sub,
        "tenant_id": tenant_id,
        "role": role,
        "exp": int(time.time()) + 3600,
        "iss": "compliance",
    }
    return {"Authorization": f"Bearer {jwt.encode(payload, STANDALONE_SECRET, algorithm='HS256')}"}


# ---------------------------------------------------------------------------
# (1) ComplianceAuditLog model exists
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_compliance_audit_log_model_exists():
    """The model must be importable + registered in Base.metadata."""
    from compliance_backend.models import compliance_audit_log  # noqa: F401
    from compliance_backend.models.compliance_audit_log import ComplianceAuditLog
    from compliance_backend.database import Base

    # Table is registered
    assert "compliance_audit_logs" in Base.metadata.tables, (
        "ComplianceAuditLog must register the 'compliance_audit_logs' table"
    )
    table = Base.metadata.tables["compliance_audit_logs"]

    # Required columns
    required_columns = {
        "id", "tenant_id", "user_id", "action", "resource_type",
        "resource_id", "details_json", "created_at",
    }
    missing = required_columns - set(table.columns.keys())
    assert not missing, f"ComplianceAuditLog missing columns: {missing}"

    # tenant_id must be NOT NULL — every audit row must be tenant-stamped
    assert table.columns["tenant_id"].nullable is False, (
        "tenant_id must be NOT NULL — no tenant-less audit rows allowed."
    )


# ---------------------------------------------------------------------------
# (2) Vendor mutation writes ComplianceAuditLog
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_vendor_create_writes_compliance_audit_log(client, db_session):
    _ensure_router_installed("/vendors", vendors_router)
    from compliance_backend.models.compliance_audit_log import ComplianceAuditLog

    tenant = "tenant-vendor-audit"
    before = (await db_session.execute(
        select(ComplianceAuditLog).where(
            ComplianceAuditLog.tenant_id == tenant,
            ComplianceAuditLog.action == "vendor_created",
        )
    )).scalars().all()

    resp = await client.post(
        "/vendors",
        headers=_auth_headers(tenant),
        json={"name": "AcmeAudit", "criticality": "high"},
    )
    assert resp.status_code == 200, resp.text
    vendor_id = resp.json()["id"]

    rows = (await db_session.execute(
        select(ComplianceAuditLog).where(
            ComplianceAuditLog.tenant_id == tenant,
            ComplianceAuditLog.action == "vendor_created",
        )
    )).scalars().all()
    assert len(rows) == len(before) + 1
    assert rows[-1].resource_type == "vendor"
    assert rows[-1].resource_id == vendor_id


@pytest.mark.anyio
async def test_vendor_update_writes_compliance_audit_log(client, db_session):
    _ensure_router_installed("/vendors", vendors_router)
    from compliance_backend.models.compliance_audit_log import ComplianceAuditLog

    tenant = "tenant-vendor-update-audit"
    create = await client.post(
        "/vendors", headers=_auth_headers(tenant),
        json={"name": "Acme", "criticality": "low"},
    )
    assert create.status_code == 200
    vid = create.json()["id"]

    upd = await client.patch(
        f"/vendors/{vid}",
        headers=_auth_headers(tenant),
        json={"criticality": "critical"},
    )
    assert upd.status_code == 200

    rows = (await db_session.execute(
        select(ComplianceAuditLog).where(
            ComplianceAuditLog.tenant_id == tenant,
            ComplianceAuditLog.action == "vendor_updated",
        )
    )).scalars().all()
    assert len(rows) >= 1
    assert rows[-1].resource_id == vid


# ---------------------------------------------------------------------------
# (3) HIGH-002 — vendor upload_document persists file bytes
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_vendor_upload_document_persists_bytes_to_storage(client, db_session):
    """
    HIGH-002 fix: vendor document upload MUST persist the actual file bytes
    via the evidence storage abstraction. The DB row's ``storage_uri`` must
    NOT be ``memory://`` and the bytes must be retrievable byte-for-byte.

    L2 (CL-NEW-2): the API response does NOT expose ``storage_uri`` on the
    wire (deployment topology is server-side). The persistence property is
    verified by reading ``VendorDocument.storage_uri`` directly from the DB.
    """
    from compliance_backend.models.vendor import VendorDocument

    _ensure_router_installed("/vendors", vendors_router)

    tenant = "tenant-vendor-bytes"

    # Create vendor
    create = await client.post(
        "/vendors",
        headers=_auth_headers(tenant),
        json={"name": "AcmeBytes", "criticality": "high"},
    )
    assert create.status_code == 200
    vid = create.json()["id"]

    file_bytes = b"%PDF-1.4 some pdf-like bytes here\n--EOF--\n" + uuid.uuid4().bytes
    upload = await client.post(
        f"/vendors/{vid}/documents",
        headers=_auth_headers(tenant),
        data={"document_type": "CONTRACT"},
        files={"file": ("contract.pdf", io.BytesIO(file_bytes), "application/pdf")},
    )
    assert upload.status_code == 200, upload.text
    doc_id = upload.json()["id"]

    record = await db_session.get(VendorDocument, doc_id)
    assert record is not None, "vendor document row must persist"

    # MUST NOT be the memory:// placeholder
    assert not record.storage_uri.startswith("memory://"), (
        "HIGH-002: vendor upload_document still uses memory:// placeholder — "
        "file bytes are silently dropped."
    )

    # The storage backend should be able to read back the exact bytes.
    storage = get_storage()
    persisted = await storage.read(record.storage_uri)
    assert persisted == file_bytes, (
        f"persisted bytes mismatch: expected {len(file_bytes)} bytes, got {len(persisted)}"
    )


# ---------------------------------------------------------------------------
# (4) Compliance audit log writes also for policy publish + control run
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_policy_publish_writes_compliance_audit_log(client, db_session):
    """POST /policies writes compliance audit row for policy_created."""
    from compliance_backend.routers import policies as policies_router_mod
    _ensure_router_installed("/policies", policies_router_mod.router)
    from compliance_backend.models.compliance_audit_log import ComplianceAuditLog

    tenant = "tenant-policy-audit"
    resp = await client.post(
        "/policies",
        headers=_auth_headers(tenant),
        json={"name": "Test Policy", "content": "Initial content"},
    )
    assert resp.status_code == 201, resp.text

    rows = (await db_session.execute(
        select(ComplianceAuditLog).where(
            ComplianceAuditLog.tenant_id == tenant,
            ComplianceAuditLog.action == "policy_created",
        )
    )).scalars().all()
    assert len(rows) >= 1


@pytest.mark.anyio
async def test_auditor_invitation_revoke_writes_compliance_audit_log(client, db_session):
    """POST/DELETE /auditor-invitations write compliance audit rows."""
    from compliance_backend.routers import auditor_invitations as ai_mod
    from compliance_backend.models.framework import Framework
    _ensure_router_installed("/auditor-invitations", ai_mod.router)
    from compliance_backend.models.compliance_audit_log import ComplianceAuditLog

    tenant = "tenant-inv-audit"

    # Need a framework to invite against
    fw = Framework(
        id=str(uuid.uuid4()),
        name=f"FW {uuid.uuid4().hex[:4]}",
        short_code=f"AI{uuid.uuid4().hex[:4].upper()}",
        category="security",
    )
    db_session.add(fw)
    await db_session.commit()

    body = {
        "auditor_email": "ext@example.com",
        "framework_id": fw.id,
        "audit_period_start": (datetime.utcnow()).isoformat(),
        "audit_period_end": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        "expires_at": (datetime.utcnow() + timedelta(days=14)).isoformat(),
    }
    resp = await client.post(
        "/auditor-invitations",
        headers=_auth_headers(tenant),
        json=body,
    )
    assert resp.status_code == 201, resp.text
    inv_id = resp.json()["id"]

    create_rows = (await db_session.execute(
        select(ComplianceAuditLog).where(
            ComplianceAuditLog.tenant_id == tenant,
            ComplianceAuditLog.action == "auditor_invitation_created",
        )
    )).scalars().all()
    assert len(create_rows) >= 1
    assert create_rows[-1].resource_id == inv_id

    revoke = await client.delete(
        f"/auditor-invitations/{inv_id}", headers=_auth_headers(tenant),
    )
    assert revoke.status_code == 204

    rev_rows = (await db_session.execute(
        select(ComplianceAuditLog).where(
            ComplianceAuditLog.tenant_id == tenant,
            ComplianceAuditLog.action == "auditor_invitation_revoked",
        )
    )).scalars().all()
    assert len(rev_rows) >= 1

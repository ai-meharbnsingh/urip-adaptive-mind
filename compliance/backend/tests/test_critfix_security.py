"""
CRITICAL SECURITY FIXES — Worker C (compliance backend).

TDD coverage for:
  CRIT-006  POST /controls/{id}/run no longer accepts caller-supplied
            tenant_config / connector_data — engine derives them from
            server-side state ONLY (TenantConfig, ConnectorPull tables).
  CRIT-008  _require_admin matches URIP-side roles (ciso / is_super_admin /
            is_compliance_admin claim) — not the non-existent
            {admin/owner/compliance_admin} legacy set.
  CRIT-009  Evidence carries content_sha256; mismatch on read raises
            EvidenceTamperError; download endpoint returns X-Evidence-Hash.
  NEW-2     Auditor JWT exp claim is correct UTC seconds even on hosts
            with non-UTC TZ (was: int(naive_dt.timestamp()) → local-TZ skew).
  NEW-4     Vendors router is registered in main.py — present in OpenAPI.
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
# CRIT-005 (Z2.1): migrated python-jose -> PyJWT (HS256 surface identical)
import jwt
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.models.evidence import Evidence
from compliance_backend.models.tenant_state import TenantConfig, ConnectorPull
from compliance_backend.services.control_rules import load_builtin_rules

STANDALONE_SECRET = "test-secret-standalone"

load_builtin_rules()


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------


def _make_token(
    tenant_id: str,
    role: str = "admin",
    *,
    is_super_admin: bool = False,
    is_compliance_admin: bool = False,
) -> str:
    payload = {
        "sub": "user-critfix",
        "tenant_id": tenant_id,
        "role": role,
        "is_super_admin": is_super_admin,
        "is_compliance_admin": is_compliance_admin,
        "exp": int(time.time()) + 3600,
        "iss": "compliance",
    }
    return jwt.encode(payload, STANDALONE_SECRET, algorithm="HS256")


def _headers(
    tenant_id: str = "tenant-critfix",
    role: str = "admin",
    *,
    is_super_admin: bool = False,
    is_compliance_admin: bool = False,
) -> dict:
    return {
        "Authorization": "Bearer "
        + _make_token(
            tenant_id,
            role=role,
            is_super_admin=is_super_admin,
            is_compliance_admin=is_compliance_admin,
        )
    }


async def _seed_control(db_session, rule_function: str = "mfa_enforced") -> Control:
    fw = Framework(
        id=str(uuid.uuid4()),
        name=f"FW {uuid.uuid4().hex[:4]}",
        short_code=f"CF{uuid.uuid4().hex[:4].upper()}",
        category="security",
    )
    db_session.add(fw)
    await db_session.flush()
    fv = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=fw.id,
        version="2024",
        is_current=True,
    )
    db_session.add(fv)
    await db_session.flush()
    ctrl = Control(
        id=str(uuid.uuid4()),
        framework_version_id=fv.id,
        control_code=f"CF-{uuid.uuid4().hex[:4].upper()}",
        category="Access",
        description="critfix control",
        rule_function=rule_function,
    )
    db_session.add(ctrl)
    await db_session.commit()
    return ctrl


# ===========================================================================
# CRIT-006 — server-side derivation of tenant_config / connector_data
# ===========================================================================


@pytest.mark.anyio
async def test_critfix_006_route_ignores_caller_tenant_config(client, db_session):
    """
    A caller MUST NOT be able to inject tenant_config in the request body.
    The mfa_enforced rule expects mfa_enabled=True + mfa_enforcement=all_users
    to PASS. With NO server-side TenantConfig row, the rule must FAIL even
    if the caller supplies a "passing" tenant_config in the body — proving
    the body is ignored.
    """
    ctrl = await _seed_control(db_session, rule_function="mfa_enforced")
    tenant = "tenant-crit006-attacker"
    # Attacker tries to forge a passing config in the body
    resp = await client.post(
        f"/controls/{ctrl.id}/run",
        headers=_headers(tenant),
        json={
            "tenant_config": {"mfa_enabled": True, "mfa_enforcement": "all_users"},
            "connector_data": {"aws_iam": {"mfa_enabled": True}},
        },
    )
    # Either 201 (with status != "pass" because body ignored) OR 422 (body field rejected).
    # Both prove the caller cannot influence the result.
    assert resp.status_code in (201, 422), (
        f"Expected 201 or 422, got {resp.status_code}: {resp.text}"
    )
    if resp.status_code == 201:
        body = resp.json()
        assert body["status"] != "pass", (
            "CRIT-006 still exploitable — caller's body produced PASS without server-side config"
        )


@pytest.mark.anyio
async def test_critfix_006_route_uses_server_side_tenant_config(client, db_session):
    """
    With a server-side TenantConfig row that satisfies the rule, the run PASSES.
    Caller body is NEVER consulted — even when omitted entirely.
    """
    ctrl = await _seed_control(db_session, rule_function="mfa_enforced")
    tenant = "tenant-crit006-legit"

    # Admin pre-populates server-side state (this is the correct flow)
    db_session.add(
        TenantConfig(
            tenant_id=tenant,
            settings={"mfa_enabled": True, "mfa_enforcement": "all_users"},
        )
    )
    await db_session.commit()

    resp = await client.post(
        f"/controls/{ctrl.id}/run",
        headers=_headers(tenant),
        # Note: empty JSON body — server derives state itself
        json={},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "pass", (
        f"Expected pass with valid server-side TenantConfig; got {body}"
    )


@pytest.mark.anyio
async def test_critfix_006_request_schema_drops_caller_state_fields(client, db_session):
    """
    The TriggerRunRequest schema must NOT carry tenant_config or connector_data.
    Even if a client sends them, they are silently ignored (Pydantic strips
    unknown fields by default in v2). Verify by inspecting the OpenAPI schema.
    """
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    components = schema.get("components", {}).get("schemas", {})
    # Find TriggerRunRequest (or whatever the body schema is named)
    candidates = [
        name for name in components if "TriggerRun" in name or "ControlRun" in name
    ]
    found_any_state_field = False
    for name in candidates:
        props = (components.get(name, {}) or {}).get("properties", {}) or {}
        if "tenant_config" in props or "connector_data" in props:
            found_any_state_field = True
            break
    assert not found_any_state_field, (
        "CRIT-006 — TriggerRunRequest schema still exposes tenant_config/connector_data"
    )


# ===========================================================================
# CRIT-008 — _require_admin uses URIP-side roles
# ===========================================================================


@pytest.mark.anyio
async def test_critfix_008_ciso_role_is_admin(client, db_session):
    """A user with role=ciso is allowed through compliance _require_admin gates."""
    tenant = "tenant-crit008-ciso"
    # /compliance-score/snapshot is admin-gated
    resp = await client.post(
        "/compliance-score/snapshot",
        headers=_headers(tenant, role="ciso"),
    )
    # Either 201 (admin allowed, even if no frameworks → 0 snapshots) or 5xx for
    # downstream issues — but NOT 403.
    assert resp.status_code != 403, f"ciso must pass admin gate; got 403: {resp.text}"


@pytest.mark.anyio
async def test_critfix_008_executive_role_is_NOT_admin(client):
    """A user with role=executive must be rejected by the admin gate."""
    tenant = "tenant-crit008-exec"
    resp = await client.post(
        "/compliance-score/snapshot",
        headers=_headers(tenant, role="executive"),
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_critfix_008_super_admin_passes_regardless_of_role(client):
    """A user with is_super_admin=True passes regardless of role."""
    tenant = "tenant-crit008-sa"
    resp = await client.post(
        "/compliance-score/snapshot",
        headers=_headers(tenant, role="executive", is_super_admin=True),
    )
    assert resp.status_code != 403, (
        f"is_super_admin must pass admin gate; got 403: {resp.text}"
    )


@pytest.mark.anyio
async def test_critfix_008_compliance_admin_capability_passes(client):
    """A user with is_compliance_admin=True passes regardless of role."""
    tenant = "tenant-crit008-ca"
    resp = await client.post(
        "/compliance-score/snapshot",
        headers=_headers(tenant, role="executive", is_compliance_admin=True),
    )
    assert resp.status_code != 403, (
        f"is_compliance_admin must pass admin gate; got 403: {resp.text}"
    )


@pytest.mark.anyio
async def test_critfix_008_legacy_admin_role_still_works(client):
    """
    Backward-compat: STANDALONE-mode tenants whose JWT carries role=admin
    (compliance issues its own tokens) must continue to pass.
    """
    tenant = "tenant-crit008-legacy"
    resp = await client.post(
        "/compliance-score/snapshot",
        headers=_headers(tenant, role="admin"),
    )
    assert resp.status_code != 403


# ===========================================================================
# CRIT-009 — Evidence content_sha256
# ===========================================================================


@pytest.mark.anyio
async def test_critfix_009_capture_evidence_stores_sha256(db_session):
    from compliance_backend.services.evidence_service import EvidenceService
    import hashlib

    svc = EvidenceService(db=db_session)
    payload = b"crit009 audit payload"
    rec = await svc.capture_evidence(
        control_id=str(uuid.uuid4()),
        tenant_id="tenant-crit009-capture",
        evidence_type="config",
        content=payload,
    )
    assert rec.content_sha256 is not None, "content_sha256 must be stored"
    expected = hashlib.sha256(payload).hexdigest()
    assert rec.content_sha256 == expected


@pytest.mark.anyio
async def test_critfix_009_upload_manual_evidence_stores_sha256(db_session):
    from compliance_backend.services.evidence_service import EvidenceService
    import hashlib

    svc = EvidenceService(db=db_session)
    payload = b"manual upload bytes"
    rec = await svc.upload_manual_evidence(
        file_content=payload,
        filename="report.pdf",
        control_id=str(uuid.uuid4()),
        tenant_id="tenant-crit009-upload",
        evidence_type="document",
    )
    assert rec.content_sha256 is not None
    assert rec.content_sha256 == hashlib.sha256(payload).hexdigest()


@pytest.mark.anyio
async def test_critfix_009_read_detects_tamper(db_session):
    """Mutating the on-disk artifact between write+read must raise EvidenceTamperError."""
    from compliance_backend.services.evidence_service import (
        EvidenceService,
        EvidenceTamperError,
    )

    svc = EvidenceService(db=db_session)
    rec = await svc.capture_evidence(
        control_id=str(uuid.uuid4()),
        tenant_id="tenant-crit009-tamper",
        evidence_type="log",
        content=b"original audit trail",
    )
    await db_session.commit()

    # Corrupt the on-disk file
    assert rec.storage_uri.startswith("file://")
    path = rec.storage_uri[7:]
    with open(path, "wb") as f:
        f.write(b"TAMPERED CONTENT")

    with pytest.raises(EvidenceTamperError):
        await svc.get_evidence_content(rec.id, "tenant-crit009-tamper")


@pytest.mark.anyio
async def test_critfix_009_read_intact_returns_bytes(db_session):
    from compliance_backend.services.evidence_service import EvidenceService

    svc = EvidenceService(db=db_session)
    payload = b"intact evidence body"
    rec = await svc.capture_evidence(
        control_id=str(uuid.uuid4()),
        tenant_id="tenant-crit009-intact",
        evidence_type="config",
        content=payload,
    )
    await db_session.commit()
    out = await svc.get_evidence_content(rec.id, "tenant-crit009-intact")
    assert out == payload


@pytest.mark.anyio
async def test_critfix_009_auditor_download_returns_x_evidence_hash(client, db_session):
    """The auditor download endpoint must include X-Evidence-Hash response header."""
    from compliance_backend.services.evidence_service import EvidenceService
    from compliance_backend.models.auditor import AuditorAccess
    from compliance_backend.services.auditor_service import (
        generate_invitation_token,
        hash_invitation_token,
        AuditorService,
    )

    # Seed framework + control + evidence
    fw = Framework(
        id=str(uuid.uuid4()),
        name="C9-Audit",
        short_code=f"C9{uuid.uuid4().hex[:4].upper()}",
        category="security",
    )
    db_session.add(fw)
    await db_session.flush()
    fv = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=fw.id,
        version="2024",
        is_current=True,
    )
    db_session.add(fv)
    await db_session.flush()
    ctrl = Control(
        id=str(uuid.uuid4()),
        framework_version_id=fv.id,
        control_code="C9-001",
        category="Access",
        description="audit hash",
        rule_function="mfa_enforced",
    )
    db_session.add(ctrl)
    await db_session.flush()

    tenant = "tenant-crit009-aud"
    svc = EvidenceService(db=db_session)
    payload = b"auditor visible bytes"
    ev = await svc.capture_evidence(
        control_id=ctrl.id,
        tenant_id=tenant,
        evidence_type="config",
        content=payload,
        framework_id=fw.id,
    )
    await db_session.commit()

    # Mint auditor JWT for this access
    asvc = AuditorService(db=db_session)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    inv = await asvc.create_invitation(
        tenant_id=tenant,
        auditor_email="auditor@critfix.test",
        framework_id=fw.id,
        audit_period_start=now - timedelta(days=30),
        audit_period_end=now + timedelta(days=30),
        expires_at=now + timedelta(days=30),
        invited_by_user_id="admin-1",
    )
    await db_session.commit()
    accept = await asvc.accept_invitation(inv.raw_token)
    assert accept is not None
    _, jwt_token = accept
    await db_session.commit()

    resp = await client.get(
        f"/auditor/evidence/{ev.id}/download",
        headers={"Authorization": f"Bearer {jwt_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert "x-evidence-hash" in {k.lower() for k in resp.headers.keys()}
    import hashlib
    assert resp.headers.get("X-Evidence-Hash", "").lower() == (
        hashlib.sha256(payload).hexdigest()
    )


# ===========================================================================
# NEW-2 — Auditor JWT exp claim is UTC-correct on non-UTC hosts
# ===========================================================================


@pytest.mark.anyio
async def test_new2_auditor_jwt_exp_is_utc_seconds(db_session, monkeypatch):
    """
    On a host whose local TZ is not UTC, the JWT exp claim must equal the
    integer UTC seconds of expires_at — never offset by local-TZ delta.
    Reproduces the bug: int(naive_utcnow_dt.timestamp()) returns
    epoch_seconds_in_LOCAL_TZ, not epoch_seconds_in_UTC.
    """
    from compliance_backend.services.auditor_service import AuditorService

    # Force a non-UTC local TZ for the duration of this test
    monkeypatch.setenv("TZ", "Asia/Kolkata")
    time.tzset()

    try:
        svc = AuditorService(db=db_session)
        now_utc = datetime.now(timezone.utc).replace(microsecond=0)
        # Note: we pass naive datetimes (DB columns are naive) but representing UTC
        expires_at = now_utc + timedelta(hours=1)
        inv = await svc.create_invitation(
            tenant_id="tenant-new2",
            auditor_email="audit@new2.test",
            framework_id=str(uuid.uuid4()),
            audit_period_start=now_utc.replace(tzinfo=None),
            audit_period_end=(now_utc + timedelta(days=1)).replace(tzinfo=None),
            expires_at=expires_at.replace(tzinfo=None),
            invited_by_user_id="admin",
        )
        await db_session.commit()

        accept = await svc.accept_invitation(inv.raw_token)
        assert accept is not None
        _, token = accept
        await db_session.commit()

        # Decode JWT payload via PyJWT (CRIT-005 Z2.1 migration — was jose).
        # PyJWT (unlike jose) validates the `aud` claim if present in the
        # token; pass audience to satisfy auditor_auth's "compliance-auditor"
        # audience set by _mint_auditor_jwt. (jose ignored aud silently.)
        import jwt as pyjwt_inner
        from compliance_backend.config import settings

        payload = pyjwt_inner.decode(
            token,
            settings.COMPLIANCE_JWT_SECRET,
            algorithms=["HS256"],
            audience="compliance-auditor",
        )
        exp_claim = payload["exp"]

        expected_exp = int(expires_at.timestamp())
        # Both should equal the SAME UTC epoch — within 2 seconds tolerance
        assert abs(exp_claim - expected_exp) <= 2, (
            f"NEW-2 — exp claim drifted by TZ. "
            f"got={exp_claim}, expected={expected_exp}, delta={exp_claim - expected_exp}s"
        )
    finally:
        # Restore TZ
        monkeypatch.delenv("TZ", raising=False)
        time.tzset()


# ===========================================================================
# NEW-4 — Vendors router is registered
# ===========================================================================


@pytest.mark.anyio
async def test_new4_vendors_router_is_registered(client):
    """`GET /vendors` must NOT 404 — proves the router is included in main.py."""
    # No auth header → expect 401, not 404
    resp = await client.get("/vendors")
    assert resp.status_code != 404, (
        "NEW-4 — /vendors returns 404; vendors router is not included in main.py"
    )
    # Any of 200/401/403/422 indicates the route exists
    assert resp.status_code in (200, 401, 403, 422), resp.status_code


@pytest.mark.anyio
async def test_new4_vendors_router_appears_in_openapi(client):
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json().get("paths", {})
    assert any(p.startswith("/vendors") for p in paths.keys()), (
        "NEW-4 — /vendors* paths missing from OpenAPI; router not registered"
    )

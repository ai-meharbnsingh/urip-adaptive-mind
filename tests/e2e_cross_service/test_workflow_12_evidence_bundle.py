"""
WORKFLOW 12 — Evidence bundle export (Compliance service).

Covers:
  1. Accumulate evidence across multiple controls in an audit period.
  2. GET /evidence/bundle?framework_id=...&audit_period=Q4-2025 → returns
     a ZIP file (Content-Type application/zip).
  3. The ZIP contains:
        - one entry per evidence record under  evidence/<id>_<type>.bin
        - a manifest.json mapping evidence to controls.
  4. Bundle filtering works: scoping to a different audit_period returns
     a manifest with zero rows for that scope.
  5. Tenant isolation: another tenant's bundle does not include this
     tenant's evidence (tenant_id filter is enforced server-side).

The bundle endpoint is `GET /evidence/bundle` (per
compliance_backend/routers/evidence.py).  The task description references a
POST /auditor/.../bundle path which does not exist in source today; we use
the actual endpoint and document the deviation.
"""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from datetime import datetime, timedelta

import pytest

from compliance_backend.models.framework import Framework, FrameworkVersion, Control


def _admin_headers(jwt_factory, tenant_id: str) -> dict:
    return {"Authorization": f"Bearer {jwt_factory(tenant_id, role='admin')}"}


async def _seed_framework_with_controls(
    session, n_controls: int = 3
) -> tuple[Framework, list[Control]]:
    fw = Framework(
        id=str(uuid.uuid4()),
        name=f"BundleFw {uuid.uuid4().hex[:4]}",
        short_code=f"BUN{uuid.uuid4().hex[:4].upper()}",
        category="security",
    )
    fv = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=fw.id,
        version="2024",
        is_current=True,
    )
    session.add_all([fw, fv])
    await session.flush()

    controls = []
    for i in range(n_controls):
        c = Control(
            id=str(uuid.uuid4()),
            framework_version_id=fv.id,
            control_code=f"BC-{i:02d}-{uuid.uuid4().hex[:3]}",
            category="Access",
            description=f"Bundle control #{i}",
            rule_function=None,
        )
        controls.append(c)
        session.add(c)
    await session.flush()
    return fw, controls


@pytest.mark.asyncio
async def test_workflow_12_evidence_bundle_zip_with_manifest(
    compliance_client, compliance_session, make_compliance_jwt
):
    tenant_id = "bundle-tenant-e2e"
    h = _admin_headers(make_compliance_jwt, tenant_id)

    fw, controls = await _seed_framework_with_controls(compliance_session, n_controls=3)

    # ── 1) Upload one evidence per control via the public POST /evidence ──
    uploaded_ids = []
    for i, ctrl in enumerate(controls):
        resp = await compliance_client.post(
            "/evidence",
            data={
                "control_id": ctrl.id,
                "evidence_type": "log",
                "framework_id": fw.id,
                "audit_period": "Q4-2025",
            },
            files={
                "file": (
                    f"log-{i}.txt",
                    io.BytesIO(f"log content for control {ctrl.control_code}\n".encode()),
                    "text/plain",
                ),
            },
            headers=h,
        )
        assert resp.status_code == 201, resp.text
        uploaded_ids.append(resp.json()["id"])

    # ── 2) Pull the bundle ─────────────────────────────────────────────────
    bundle_resp = await compliance_client.get(
        f"/evidence/bundle?framework_id={fw.id}&audit_period=Q4-2025",
        headers=h,
    )
    assert bundle_resp.status_code == 200, bundle_resp.text
    assert bundle_resp.headers["content-type"] == "application/zip"
    assert "attachment" in bundle_resp.headers.get("content-disposition", "")

    # ── 3) Validate ZIP structure + manifest.json ──────────────────────────
    with zipfile.ZipFile(io.BytesIO(bundle_resp.content)) as zf:
        names = zf.namelist()
        assert "manifest.json" in names

        # One entry per uploaded evidence
        evidence_entries = [n for n in names if n.startswith("evidence/")]
        assert len(evidence_entries) == len(uploaded_ids), (
            f"Expected {len(uploaded_ids)} evidence entries, got {len(evidence_entries)}"
        )

        manifest_raw = zf.read("manifest.json").decode("utf-8")
        manifest = json.loads(manifest_raw)
        assert isinstance(manifest, list)
        assert len(manifest) == len(uploaded_ids)

        manifest_ids = {row["id"] for row in manifest}
        assert manifest_ids == set(uploaded_ids)

        # Each manifest row maps to a real control_id
        ctrl_id_set = {c.id for c in controls}
        for row in manifest:
            assert row["control_id"] in ctrl_id_set
            assert row["framework_id"] == fw.id
            assert row["audit_period"] == "Q4-2025"
            # The artifact named in manifest exists in the ZIP
            assert row["file_in_bundle"] in names


@pytest.mark.asyncio
async def test_workflow_12_bundle_period_filter_isolates_periods(
    compliance_client, compliance_session, make_compliance_jwt
):
    tenant_id = "bundle-period-tenant"
    h = _admin_headers(make_compliance_jwt, tenant_id)

    fw, [ctrl] = await _seed_framework_with_controls(compliance_session, n_controls=1)

    # Q4-2025 evidence
    r1 = await compliance_client.post(
        "/evidence",
        data={
            "control_id": ctrl.id,
            "evidence_type": "log",
            "framework_id": fw.id,
            "audit_period": "Q4-2025",
        },
        files={"file": ("a.txt", io.BytesIO(b"q4"), "text/plain")},
        headers=h,
    )
    assert r1.status_code == 201, r1.text

    # Bundle for Q4-2026 (different period) → empty manifest
    bundle_resp = await compliance_client.get(
        f"/evidence/bundle?framework_id={fw.id}&audit_period=Q4-2026",
        headers=h,
    )
    assert bundle_resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(bundle_resp.content)) as zf:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert manifest == [], (
            f"Bundle for Q4-2026 must be empty, got {manifest}"
        )


@pytest.mark.asyncio
async def test_workflow_12_bundle_is_tenant_scoped(
    compliance_client, compliance_session, make_compliance_jwt
):
    tenant_a = "bundle-iso-a"
    tenant_b = "bundle-iso-b"
    h_a = _admin_headers(make_compliance_jwt, tenant_a)
    h_b = _admin_headers(make_compliance_jwt, tenant_b)

    fw, [ctrl] = await _seed_framework_with_controls(compliance_session, n_controls=1)

    # A uploads evidence
    r = await compliance_client.post(
        "/evidence",
        data={
            "control_id": ctrl.id,
            "evidence_type": "log",
            "framework_id": fw.id,
            "audit_period": "Q4-2025",
        },
        files={"file": ("a.txt", io.BytesIO(b"data-A"), "text/plain")},
        headers=h_a,
    )
    assert r.status_code == 201
    a_evidence_id = r.json()["id"]

    # B requests a bundle for the same framework + period
    bundle_b = await compliance_client.get(
        f"/evidence/bundle?framework_id={fw.id}&audit_period=Q4-2025",
        headers=h_b,
    )
    assert bundle_b.status_code == 200
    with zipfile.ZipFile(io.BytesIO(bundle_b.content)) as zf:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        leaked = [row for row in manifest if row["id"] == a_evidence_id]
        assert leaked == [], (
            f"Tenant B's bundle leaked tenant A's evidence: {leaked}"
        )

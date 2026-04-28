"""
TDD — Evidence REST endpoint tests (P2B.4)

Tests:
  - POST /evidence — manual upload (multipart)
  - GET /evidence — search returns tenant-scoped results
  - GET /evidence/{id} — download content, 404 for unknown/wrong tenant
  - GET /evidence/bundle — ZIP download
  - Auth enforcement: 401 without token
"""
import io
import json
import os
import time
import uuid
import zipfile
import pytest
# CRIT-005 (Z2.1): migrated python-jose -> PyJWT (HS256 surface identical)
import jwt

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.services.control_rules import load_builtin_rules

STANDALONE_SECRET = "test-secret-standalone"

# Ensure builtins loaded
load_builtin_rules()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _make_token(tenant_id: str = "tenant-ev-route", role: str = "admin") -> str:
    payload = {
        "sub": "user-ev-1",
        "tenant_id": tenant_id,
        "role": role,
        "exp": int(time.time()) + 3600,
        "iss": "compliance",
    }
    return jwt.encode(payload, STANDALONE_SECRET, algorithm="HS256")


def _headers(tenant_id: str = "tenant-ev-route") -> dict:
    return {"Authorization": f"Bearer {_make_token(tenant_id)}"}


# ---------------------------------------------------------------------------
# Helper: insert a control
# ---------------------------------------------------------------------------

async def _seed_control(db_session) -> Control:
    fw = Framework(
        id=str(uuid.uuid4()),
        name=f"FW {uuid.uuid4().hex[:4]}",
        short_code=f"RT{uuid.uuid4().hex[:4].upper()}",
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
        control_code=f"RT-{uuid.uuid4().hex[:4].upper()}",
        category="Route Test",
        description="Test control for route tests",
        rule_function=None,
    )
    db_session.add(ctrl)
    await db_session.flush()
    await db_session.commit()
    return ctrl


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_evidence_upload_requires_auth(client):
    resp = await client.post("/evidence")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_evidence_list_requires_auth(client):
    resp = await client.get("/evidence")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_evidence_bundle_requires_auth(client):
    resp = await client.get("/evidence/bundle")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /evidence — manual upload
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_upload_evidence_success(client, db_session):
    """POST /evidence returns 201 with evidence record."""
    ctrl = await _seed_control(db_session)
    tenant = "tenant-upload-test"

    # Use a realistic PDF body — the upload guard requires a recognised
    # magic prefix when the claim is application/pdf.
    file_bytes = b"%PDF-1.4\nThis is a test policy document.\n%%EOF\n"
    resp = await client.post(
        "/evidence",
        headers=_headers(tenant),
        files={"file": ("policy.pdf", io.BytesIO(file_bytes), "application/pdf")},
        data={
            "control_id": ctrl.id,
            "evidence_type": "document",
        },
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["control_id"] == ctrl.id
    assert body["tenant_id"] == tenant
    assert body["type"] == "document"
    assert body["id"]


@pytest.mark.anyio
async def test_upload_evidence_invalid_type_returns_422(client, db_session):
    ctrl = await _seed_control(db_session)
    resp = await client.post(
        "/evidence",
        headers=_headers(),
        files={"file": ("x.txt", io.BytesIO(b"data"), "text/plain")},
        data={"control_id": ctrl.id, "evidence_type": "INVALID_TYPE"},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_upload_evidence_empty_file_returns_422(client, db_session):
    ctrl = await _seed_control(db_session)
    resp = await client.post(
        "/evidence",
        headers=_headers(),
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
        data={"control_id": ctrl.id, "evidence_type": "document"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /evidence — search
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_get_evidence_returns_tenant_scoped_list(client, db_session):
    """GET /evidence returns only records for the authenticated tenant."""
    ctrl = await _seed_control(db_session)
    tenant = "tenant-list-ev"

    # Upload 2 records for this tenant
    for i in range(2):
        await client.post(
            "/evidence",
            headers=_headers(tenant),
            files={"file": (f"file{i}.txt", io.BytesIO(b"content"), "text/plain")},
            data={"control_id": ctrl.id, "evidence_type": "config"},
        )

    # Upload 1 for a different tenant
    await client.post(
        "/evidence",
        headers=_headers("tenant-other-ev"),
        files={"file": ("other.txt", io.BytesIO(b"other"), "text/plain")},
        data={"control_id": ctrl.id, "evidence_type": "config"},
    )

    resp = await client.get("/evidence", headers=_headers(tenant))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    for item in body["items"]:
        assert item["tenant_id"] == tenant


@pytest.mark.anyio
async def test_get_evidence_filter_by_type(client, db_session):
    ctrl = await _seed_control(db_session)
    tenant = "tenant-filter-type"

    await client.post(
        "/evidence",
        headers=_headers(tenant),
        files={"file": ("cfg.txt", io.BytesIO(b"cfg data"), "text/plain")},
        data={"control_id": ctrl.id, "evidence_type": "config"},
    )
    await client.post(
        "/evidence",
        headers=_headers(tenant),
        files={"file": ("log.txt", io.BytesIO(b"log data"), "text/plain")},
        data={"control_id": ctrl.id, "evidence_type": "log"},
    )

    resp = await client.get("/evidence?type=log", headers=_headers(tenant))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["type"] == "log"


# ---------------------------------------------------------------------------
# GET /evidence/{id} — download single
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_download_evidence_returns_content(client, db_session):
    ctrl = await _seed_control(db_session)
    tenant = "tenant-dl"
    file_bytes = b"downloadable content here"

    upload_resp = await client.post(
        "/evidence",
        headers=_headers(tenant),
        files={"file": ("data.txt", io.BytesIO(file_bytes), "text/plain")},
        data={"control_id": ctrl.id, "evidence_type": "config"},
    )
    assert upload_resp.status_code == 201
    evidence_id = upload_resp.json()["id"]

    dl_resp = await client.get(f"/evidence/{evidence_id}", headers=_headers(tenant))
    assert dl_resp.status_code == 200
    assert dl_resp.content == file_bytes


@pytest.mark.anyio
async def test_download_evidence_wrong_tenant_returns_404(client, db_session):
    """A tenant cannot access another tenant's evidence by ID."""
    ctrl = await _seed_control(db_session)
    tenant_a = "tenant-sec-a"
    tenant_b = "tenant-sec-b"

    upload_resp = await client.post(
        "/evidence",
        headers=_headers(tenant_a),
        files={"file": ("secret.txt", io.BytesIO(b"secret"), "text/plain")},
        data={"control_id": ctrl.id, "evidence_type": "document"},
    )
    assert upload_resp.status_code == 201
    evidence_id = upload_resp.json()["id"]

    # Tenant B tries to access Tenant A's evidence
    resp = await client.get(f"/evidence/{evidence_id}", headers=_headers(tenant_b))
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_download_evidence_not_found(client):
    resp = await client.get(f"/evidence/{uuid.uuid4()}", headers=_headers())
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /evidence/bundle — ZIP download
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_download_bundle_returns_zip(client, db_session):
    ctrl = await _seed_control(db_session)
    tenant = "tenant-bundle-route"

    for i in range(3):
        await client.post(
            "/evidence",
            headers=_headers(tenant),
            files={"file": (f"ev{i}.txt", io.BytesIO(f"content {i}".encode()), "text/plain")},
            data={"control_id": ctrl.id, "evidence_type": "config"},
        )

    resp = await client.get("/evidence/bundle", headers=_headers(tenant))
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("application/zip")

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
        assert "manifest.json" in names
        manifest = json.loads(zf.read("manifest.json"))
        assert len(manifest) == 3


@pytest.mark.anyio
async def test_bundle_empty_for_tenant_with_no_evidence(client):
    """Bundle for a tenant with no evidence returns a valid ZIP with empty manifest."""
    resp = await client.get("/evidence/bundle", headers=_headers("tenant-empty-bundle"))
    assert resp.status_code == 200

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest == []


@pytest.mark.anyio
async def test_bundle_filter_by_audit_period(client, db_session):
    ctrl = await _seed_control(db_session)
    tenant = "tenant-period-bundle"

    await client.post(
        "/evidence",
        headers=_headers(tenant),
        files={"file": ("2025.txt", io.BytesIO(b"2025 data"), "text/plain")},
        data={"control_id": ctrl.id, "evidence_type": "config", "audit_period": "2025"},
    )
    await client.post(
        "/evidence",
        headers=_headers(tenant),
        files={"file": ("2026.txt", io.BytesIO(b"2026 data"), "text/plain")},
        data={"control_id": ctrl.id, "evidence_type": "config", "audit_period": "2026"},
    )

    resp = await client.get("/evidence/bundle?audit_period=2025", headers=_headers(tenant))
    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert len(manifest) == 1
    assert manifest[0]["audit_period"] == "2025"

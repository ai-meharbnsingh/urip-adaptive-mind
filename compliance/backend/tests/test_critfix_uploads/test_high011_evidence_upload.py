"""
HIGH-011 — Evidence upload: no size cap, no content-type check, weak filename
sanitisation.

Required behaviour:
    a. Reject uploads larger than 50 MB with 413.
    b. Allow only the documented Content-Type families
       (image/*, application/pdf, application/json, text/csv, text/plain,
        application/zip). Reject anything else with 422.
    c. Sanitise filenames:
        - strip "/" and "\\" (no directory components)
        - strip ".." (no parent traversal)
        - prefix with a UUID so collisions cannot occur
    d. Same guards on vendor-document upload — see test_high011_vendor_upload.py.
"""
import io
import time
import uuid

import pytest
# CRIT-005 (Z2.1): migrated python-jose -> PyJWT (HS256 surface identical)
import jwt

from compliance_backend.models.framework import Control, Framework, FrameworkVersion
from compliance_backend.services.control_rules import load_builtin_rules

STANDALONE_SECRET = "test-secret-standalone"
load_builtin_rules()


def _make_token(tenant_id: str = "tenant-up-test", role: str = "admin") -> str:
    payload = {
        "sub": "user-up-1",
        "tenant_id": tenant_id,
        "role": role,
        "exp": int(time.time()) + 3600,
        "iss": "compliance",
    }
    return jwt.encode(payload, STANDALONE_SECRET, algorithm="HS256")


def _headers(tenant_id: str = "tenant-up-test") -> dict:
    return {"Authorization": f"Bearer {_make_token(tenant_id)}"}


async def _seed_control(db_session) -> Control:
    fw = Framework(
        id=str(uuid.uuid4()),
        name=f"FW {uuid.uuid4().hex[:4]}",
        short_code=f"UP{uuid.uuid4().hex[:4].upper()}",
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
        control_code=f"UP-{uuid.uuid4().hex[:4].upper()}",
        category="Upload Test",
        description="ctrl",
        rule_function=None,
    )
    db_session.add(ctrl)
    await db_session.flush()
    await db_session.commit()
    return ctrl


# ---------------------------------------------------------------------------
# (a) 50 MB size cap
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_oversize_upload_rejected_413(client, db_session):
    """A 51 MB upload must be rejected with 413."""
    ctrl = await _seed_control(db_session)
    # 51 MB of zero bytes — bytes are constructed lazily by io.BytesIO
    big = b"\0" * (51 * 1024 * 1024)
    resp = await client.post(
        "/evidence",
        headers=_headers(),
        files={"file": ("big.pdf", io.BytesIO(big), "application/pdf")},
        data={"control_id": ctrl.id, "evidence_type": "document"},
    )
    assert resp.status_code == 413, (
        f"51MB upload should be 413, got {resp.status_code}: {resp.text[:200]}"
    )


# Magic-byte prefix per content type — the upload guard checks that bodies
# claiming a recognised binary type actually carry the expected signature.
# Tests must use realistic bodies (production uploads always do).
_MAGIC_PREFIX = {
    "image/png":        b"\x89PNG\r\n\x1a\n",
    "image/jpeg":       b"\xff\xd8\xff\xe0",
    "image/gif":        b"GIF89a",
    "application/pdf":  b"%PDF-1.4\n",
    "application/zip":  b"PK\x03\x04",
}


def _realistic_body(ctype: str, fill: bytes = b"x" * 256) -> bytes:
    """Return ``fill`` bytes prefixed with the magic header for ``ctype``."""
    return _MAGIC_PREFIX.get(ctype, b"") + fill


@pytest.mark.anyio
async def test_under_size_cap_accepted(client, db_session):
    """A 1 MB upload of an allowed type should still succeed."""
    ctrl = await _seed_control(db_session)
    payload = _realistic_body("application/pdf", b"x" * (1 * 1024 * 1024))
    resp = await client.post(
        "/evidence",
        headers=_headers(),
        files={"file": ("ok.pdf", io.BytesIO(payload), "application/pdf")},
        data={"control_id": ctrl.id, "evidence_type": "document"},
    )
    assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# (b) Content-Type allowlist
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_executable_upload_rejected_422(client, db_session):
    ctrl = await _seed_control(db_session)
    resp = await client.post(
        "/evidence",
        headers=_headers(),
        files={
            "file": (
                "evil.exe",
                io.BytesIO(b"MZ\x90\x00fake-pe-header"),
                "application/x-msdownload",
            )
        },
        data={"control_id": ctrl.id, "evidence_type": "document"},
    )
    assert resp.status_code == 422, (
        f".exe upload should be 422, got {resp.status_code}: {resp.text[:200]}"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "ctype,fname",
    [
        ("image/png", "screenshot.png"),
        ("image/jpeg", "photo.jpg"),
        ("application/pdf", "policy.pdf"),
        ("application/json", "config.json"),
        ("text/csv", "data.csv"),
        ("text/plain", "log.txt"),
        ("application/zip", "bundle.zip"),
    ],
)
async def test_allowlisted_content_types_accepted(client, db_session, ctype, fname):
    ctrl = await _seed_control(db_session)
    body = _realistic_body(ctype, b"some-content")
    resp = await client.post(
        "/evidence",
        headers=_headers(),
        files={"file": (fname, io.BytesIO(body), ctype)},
        data={"control_id": ctrl.id, "evidence_type": "document"},
    )
    assert resp.status_code == 201, (
        f"{ctype} should be accepted, got {resp.status_code}: {resp.text[:200]}"
    )


# ---------------------------------------------------------------------------
# (c) Filename sanitisation
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_directory_traversal_filename_sanitised(client, db_session):
    """`../../etc/passwd` must be sanitised to a safe storage path.

    L2 (CL-NEW-2): the API response does NOT expose ``storage_uri`` (deployment
    topology stays server-side). The security property — that the upload guard
    strips traversal and prefixes a UUID — is verified at the storage layer by
    reading the ``Evidence`` record directly via ``db_session``.
    """
    from compliance_backend.models.evidence import Evidence

    ctrl = await _seed_control(db_session)
    resp = await client.post(
        "/evidence",
        headers=_headers(),
        files={
            "file": (
                "../../etc/passwd",
                io.BytesIO(b"root:x:0:0:root:/root:/bin/bash"),
                "text/plain",
            )
        },
        data={"control_id": ctrl.id, "evidence_type": "document"},
    )
    assert resp.status_code == 201, resp.text
    evidence_id = resp.json()["id"]
    record = await db_session.get(Evidence, evidence_id)
    assert record is not None, "evidence row must persist"
    storage_uri = record.storage_uri
    # No directory components, no dot-dot
    assert ".." not in storage_uri
    # The original malicious filename must NOT survive verbatim in the URI
    assert "etc/passwd" not in storage_uri.lower()
    assert "etc%2fpasswd" not in storage_uri.lower()


@pytest.mark.anyio
async def test_filename_uuid_prefix_prevents_collision(client, db_session):
    """Two uploads with the same name must yield distinct storage URIs.

    L2 (CL-NEW-2): the API response does NOT expose ``storage_uri``; the
    UUID-prefix property is verified by reading both ``Evidence`` rows from
    the DB directly.
    """
    from compliance_backend.models.evidence import Evidence

    ctrl = await _seed_control(db_session)
    a = await client.post(
        "/evidence",
        headers=_headers(),
        files={"file": ("dup.pdf", io.BytesIO(_realistic_body("application/pdf", b"first")), "application/pdf")},
        data={"control_id": ctrl.id, "evidence_type": "document"},
    )
    b = await client.post(
        "/evidence",
        headers=_headers(),
        files={"file": ("dup.pdf", io.BytesIO(_realistic_body("application/pdf", b"second")), "application/pdf")},
        data={"control_id": ctrl.id, "evidence_type": "document"},
    )
    assert a.status_code == 201 and b.status_code == 201
    rec_a = await db_session.get(Evidence, a.json()["id"])
    rec_b = await db_session.get(Evidence, b.json()["id"])
    assert rec_a is not None and rec_b is not None
    assert rec_a.storage_uri != rec_b.storage_uri, (
        "two uploads with the same filename must NOT collide on storage URI"
    )

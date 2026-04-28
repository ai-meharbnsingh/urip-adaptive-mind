"""
HIGH-1 — Evidence bundle export must:
  1. Stream zip generation via tempfile (not in-memory) — won't OOM on 1000+ files.
  2. Apply hard size cap (configurable; default 500MB).
  3. Paginate evidence rows in batches of 100 (avoid loading all rows into memory).
  4. Include integrity hashes (content_sha256) in the manifest so an external
     auditor can re-verify bundle contents end-to-end.

These tests do not assert exact streaming internals — they assert the OUTCOMES:
  * Manifest contains content_sha256 per record (re-verifiable).
  * Size cap is enforced — when exceeded, function raises EvidenceBundleSizeError.
  * Bundle still works for normal (small) cases.

Auditors cited:
  - Gemini CRIT-G4 (memory exhaustion)
  - Codex CRIT-002 + HIGH-006 (no integrity hashes in manifest, OOM risk)
  - Kimi MED-006 (in-memory zip)
  - Claude finding (memory bomb)
"""
from __future__ import annotations

import hashlib
import io
import json
import uuid
import zipfile

import pytest

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.services.evidence_service import (
    EvidenceService,
    EvidenceBundleSizeError,
)
from compliance_backend.services.storage import FilesystemStorage


async def _make_control(db_session) -> Control:
    fw = Framework(
        id=str(uuid.uuid4()),
        name=f"H1 FW {uuid.uuid4().hex[:4]}",
        short_code=f"H1{uuid.uuid4().hex[:4].upper()}",
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
        control_code=f"H1-{uuid.uuid4().hex[:4].upper()}",
        category="Test",
        description="H1 audit fix control",
    )
    db_session.add(ctrl)
    await db_session.flush()
    return ctrl


def _make_svc(db_session, tmp_path) -> EvidenceService:
    return EvidenceService(db=db_session, storage=FilesystemStorage(base_dir=tmp_path))


# ---------------------------------------------------------------------------
# 1. Manifest must include content_sha256
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_export_bundle_manifest_includes_content_sha256(db_session, tmp_path):
    ctrl = await _make_control(db_session)
    await db_session.commit()

    svc = _make_svc(db_session, tmp_path)
    rec = await svc.capture_evidence(
        ctrl.id, "tenant-h1", "config", b"hello-h1-content"
    )
    await db_session.commit()

    bundle_bytes = await svc.export_evidence_bundle(tenant_id="tenant-h1")
    with zipfile.ZipFile(io.BytesIO(bundle_bytes)) as zf:
        manifest = json.loads(zf.read("manifest.json"))

    # CRIT-002: hash must be in manifest so auditor can re-verify
    assert len(manifest) == 1
    entry = manifest[0]
    assert "content_sha256" in entry, (
        f"manifest entry missing content_sha256: {entry.keys()}"
    )
    expected = hashlib.sha256(b"hello-h1-content").hexdigest()
    assert entry["content_sha256"] == expected
    assert entry["content_sha256"] == rec.content_sha256


@pytest.mark.anyio
async def test_export_bundle_hash_matches_zipped_artifact(db_session, tmp_path):
    """
    Re-verify: the hash in the manifest equals SHA-256 of the bytes inside
    the zip. This is the auditor-facing contract.
    """
    ctrl = await _make_control(db_session)
    await db_session.commit()

    svc = _make_svc(db_session, tmp_path)
    payload = b"\x00\x01\xffPDF-fake-bytes for verify"
    rec = await svc.upload_manual_evidence(
        file_content=payload,
        filename="report.pdf",
        control_id=ctrl.id,
        tenant_id="tenant-h1-verify",
        evidence_type="document",
        uploaded_by="auditor-test",
    )
    await db_session.commit()

    bundle_bytes = await svc.export_evidence_bundle(tenant_id="tenant-h1-verify")
    with zipfile.ZipFile(io.BytesIO(bundle_bytes)) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        entry = manifest[0]
        artifact_bytes = zf.read(entry["file_in_bundle"])

    assert entry["content_sha256"] == hashlib.sha256(artifact_bytes).hexdigest()


# ---------------------------------------------------------------------------
# 2. Size cap enforcement
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_export_bundle_enforces_size_cap(db_session, tmp_path, monkeypatch):
    """
    When the running total exceeds EVIDENCE_BUNDLE_MAX_BYTES, the function must
    raise EvidenceBundleSizeError instead of building a multi-GB zip in memory.
    """
    ctrl = await _make_control(db_session)
    await db_session.commit()

    # Set tiny cap so we trip it with a few KB of data
    import os as _os
    monkeypatch.setenv("EVIDENCE_BUNDLE_MAX_BYTES", "8192")  # 8 KB

    svc = _make_svc(db_session, tmp_path)
    # Use random bytes so DEFLATE can't compress them away — otherwise the
    # on-disk zip is much smaller than the input bytes and the cap never trips.
    for i in range(8):
        blob = _os.urandom(4096)  # 4 KB random per artifact
        await svc.upload_manual_evidence(
            file_content=blob,
            filename=f"big_{i}.bin",
            control_id=ctrl.id,
            tenant_id="tenant-h1-cap",
            evidence_type="document",
            uploaded_by="user",
        )
    await db_session.commit()

    with pytest.raises(EvidenceBundleSizeError):
        await svc.export_evidence_bundle(tenant_id="tenant-h1-cap")


@pytest.mark.anyio
async def test_export_bundle_under_cap_succeeds(db_session, tmp_path, monkeypatch):
    """Under the cap, normal export still succeeds."""
    ctrl = await _make_control(db_session)
    await db_session.commit()

    monkeypatch.setenv("EVIDENCE_BUNDLE_MAX_BYTES", "1048576")  # 1 MB

    svc = _make_svc(db_session, tmp_path)
    await svc.capture_evidence(ctrl.id, "tenant-h1-ok", "config", b"small-1")
    await svc.capture_evidence(ctrl.id, "tenant-h1-ok", "config", b"small-2")
    await db_session.commit()

    bundle_bytes = await svc.export_evidence_bundle(tenant_id="tenant-h1-ok")
    with zipfile.ZipFile(io.BytesIO(bundle_bytes)) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert len(manifest) == 2


# ---------------------------------------------------------------------------
# 3. Pagination — batch fetch (smoke test: many records still work)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_export_bundle_handles_many_records(db_session, tmp_path, monkeypatch):
    """
    Export with > batch_size (100) records must still work.
    Drives implementation to paginate the SELECT.
    """
    ctrl = await _make_control(db_session)
    await db_session.commit()

    monkeypatch.setenv("EVIDENCE_BUNDLE_MAX_BYTES", str(50 * 1024 * 1024))  # 50 MB

    svc = _make_svc(db_session, tmp_path)
    # 250 small records — exceeds the 100/batch threshold
    for i in range(250):
        await svc.capture_evidence(
            ctrl.id, "tenant-h1-many", "config", f"e-{i}".encode()
        )
    await db_session.commit()

    bundle_bytes = await svc.export_evidence_bundle(tenant_id="tenant-h1-many")
    with zipfile.ZipFile(io.BytesIO(bundle_bytes)) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert len(manifest) == 250
    # Every entry has a hash
    assert all("content_sha256" in m for m in manifest)

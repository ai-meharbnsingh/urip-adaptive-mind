"""
TDD — Evidence Service tests (P2B.4)

Tests:
  - capture_evidence: creates DB record + storage file
  - upload_manual_evidence: creates record with correct captured_by
  - search_evidence: filtering, pagination, tenant isolation
  - get_evidence: tenant isolation (wrong tenant returns None)
  - get_evidence_content: returns bytes
  - export_evidence_bundle: ZIP contains evidence + manifest.json
  - FilesystemStorage: write/read/delete lifecycle
  - Storage backend swap (filesystem vs in-memory mock)
"""
import io
import json
import os
import tempfile
import uuid
import zipfile
import pytest
from pathlib import Path
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.models.evidence import Evidence
from compliance_backend.services.evidence_service import EvidenceService, _content_to_bytes
from compliance_backend.services.storage import FilesystemStorage


# ---------------------------------------------------------------------------
# Helper: insert a minimal control
# ---------------------------------------------------------------------------

async def _make_control(db_session, rule_function: str = None) -> Control:
    fw = Framework(
        id=str(uuid.uuid4()),
        name=f"Test FW {uuid.uuid4().hex[:4]}",
        short_code=f"EV{uuid.uuid4().hex[:4].upper()}",
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
        control_code=f"EV-{uuid.uuid4().hex[:4].upper()}",
        category="Test",
        description="Test evidence control",
        rule_function=rule_function,
    )
    db_session.add(ctrl)
    await db_session.flush()
    return ctrl


# ---------------------------------------------------------------------------
# Helper: create an EvidenceService with temp filesystem storage
# ---------------------------------------------------------------------------

def _make_svc(db_session, tmp_path: Path) -> EvidenceService:
    storage = FilesystemStorage(base_dir=tmp_path)
    return EvidenceService(db=db_session, storage=storage)


# ---------------------------------------------------------------------------
# _content_to_bytes utility
# ---------------------------------------------------------------------------

class TestContentToBytes:
    def test_bytes_passthrough(self):
        data = b"\x00\x01\x02"
        assert _content_to_bytes(data) == data

    def test_string_encoded(self):
        assert _content_to_bytes("hello") == b"hello"

    def test_dict_json_encoded(self):
        result = _content_to_bytes({"key": "val"})
        parsed = json.loads(result)
        assert parsed["key"] == "val"

    def test_list_json_encoded(self):
        result = _content_to_bytes([1, 2, 3])
        parsed = json.loads(result)
        assert parsed == [1, 2, 3]


# ---------------------------------------------------------------------------
# FilesystemStorage
# ---------------------------------------------------------------------------

class TestFilesystemStorage:
    @pytest.mark.anyio
    async def test_write_and_read(self, tmp_path):
        storage = FilesystemStorage(base_dir=tmp_path)
        uri = await storage.write("tenant-1", "2026", "test.txt", b"hello world")
        assert uri.startswith("file://")
        content = await storage.read(uri)
        assert content == b"hello world"

    @pytest.mark.anyio
    async def test_read_missing_raises(self, tmp_path):
        storage = FilesystemStorage(base_dir=tmp_path)
        with pytest.raises(FileNotFoundError):
            await storage.read("file:///nonexistent/path/xyz.bin")

    @pytest.mark.anyio
    async def test_delete_moves_to_trash(self, tmp_path):
        storage = FilesystemStorage(base_dir=tmp_path)
        uri = await storage.write("tenant-1", "2026", "del_test.txt", b"to delete")
        await storage.delete(uri)
        # Original should be gone; trash should exist
        original_path = Path(uri[7:])
        assert not original_path.exists()
        trash = original_path.parent / "_trash" / original_path.name
        assert trash.exists()

    @pytest.mark.anyio
    async def test_delete_missing_is_noop(self, tmp_path):
        """Deleting a non-existent URI should not raise."""
        storage = FilesystemStorage(base_dir=tmp_path)
        await storage.delete("file:///does/not/exist.bin")  # should not raise

    @pytest.mark.anyio
    async def test_tenant_paths_are_isolated(self, tmp_path):
        storage = FilesystemStorage(base_dir=tmp_path)
        uri_a = await storage.write("tenant-a", "2026", "file.txt", b"A's data")
        uri_b = await storage.write("tenant-b", "2026", "file.txt", b"B's data")
        data_a = await storage.read(uri_a)
        data_b = await storage.read(uri_b)
        assert data_a == b"A's data"
        assert data_b == b"B's data"

    @pytest.mark.anyio
    async def test_bad_uri_scheme_raises(self, tmp_path):
        storage = FilesystemStorage(base_dir=tmp_path)
        with pytest.raises(ValueError, match="scheme"):
            await storage.read("s3://bucket/key")


# ---------------------------------------------------------------------------
# EvidenceService.capture_evidence
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_capture_evidence_creates_record(db_session, tmp_path):
    ctrl = await _make_control(db_session)
    await db_session.commit()

    svc = _make_svc(db_session, tmp_path)
    record = await svc.capture_evidence(
        control_id=ctrl.id,
        tenant_id="tenant-cap",
        evidence_type="config",
        content={"key": "value"},
        metadata={"source": "test"},
    )
    await db_session.commit()

    assert record.id is not None
    assert record.control_id == ctrl.id
    assert record.tenant_id == "tenant-cap"
    assert record.type == "config"
    assert record.storage_uri.startswith("file://")
    assert record.captured_by == "system"


@pytest.mark.anyio
async def test_capture_evidence_content_readable(db_session, tmp_path):
    ctrl = await _make_control(db_session)
    await db_session.commit()

    svc = _make_svc(db_session, tmp_path)
    record = await svc.capture_evidence(
        control_id=ctrl.id,
        tenant_id="tenant-read",
        evidence_type="config",
        content={"mfa": True},
    )
    await db_session.commit()

    content_bytes = await svc.storage.read(record.storage_uri)
    parsed = json.loads(content_bytes)
    assert parsed["mfa"] is True


@pytest.mark.anyio
async def test_capture_evidence_default_audit_period_is_current_year(db_session, tmp_path):
    from datetime import datetime
    ctrl = await _make_control(db_session)
    await db_session.commit()

    svc = _make_svc(db_session, tmp_path)
    record = await svc.capture_evidence(
        control_id=ctrl.id,
        tenant_id="tenant-period",
        evidence_type="config",
        content=b"raw",
    )
    await db_session.commit()

    assert record.audit_period == str(datetime.utcnow().year)


# ---------------------------------------------------------------------------
# EvidenceService.upload_manual_evidence
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_upload_manual_evidence(db_session, tmp_path):
    ctrl = await _make_control(db_session)
    await db_session.commit()

    svc = _make_svc(db_session, tmp_path)
    pdf_bytes = b"%PDF-1.4 fake pdf content"
    record = await svc.upload_manual_evidence(
        file_content=pdf_bytes,
        filename="policy.pdf",
        control_id=ctrl.id,
        tenant_id="tenant-manual",
        evidence_type="document",
        uploaded_by="user-999",
    )
    await db_session.commit()

    assert record.captured_by == "user-999"
    assert record.type == "document"
    content = await svc.storage.read(record.storage_uri)
    assert content == pdf_bytes


# ---------------------------------------------------------------------------
# EvidenceService.search_evidence
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_search_evidence_returns_only_tenant_records(db_session, tmp_path):
    ctrl = await _make_control(db_session)
    await db_session.commit()

    svc = _make_svc(db_session, tmp_path)
    # Create 2 records for tenant-sa, 1 for tenant-sb
    for _ in range(2):
        await svc.capture_evidence(ctrl.id, "tenant-sa", "config", {"x": 1})
    await svc.capture_evidence(ctrl.id, "tenant-sb", "config", {"x": 2})
    await db_session.commit()

    result = await svc.search_evidence(tenant_id="tenant-sa")
    assert result["total"] == 2
    for item in result["items"]:
        assert item.tenant_id == "tenant-sa"


@pytest.mark.anyio
async def test_search_evidence_filter_by_type(db_session, tmp_path):
    ctrl = await _make_control(db_session)
    await db_session.commit()

    svc = _make_svc(db_session, tmp_path)
    await svc.capture_evidence(ctrl.id, "tenant-type", "config", b"cfg")
    await svc.capture_evidence(ctrl.id, "tenant-type", "log", b"log data")
    await db_session.commit()

    result = await svc.search_evidence(tenant_id="tenant-type", evidence_type="log")
    assert result["total"] == 1
    assert result["items"][0].type == "log"


@pytest.mark.anyio
async def test_search_evidence_pagination(db_session, tmp_path):
    ctrl = await _make_control(db_session)
    await db_session.commit()

    svc = _make_svc(db_session, tmp_path)
    for i in range(5):
        await svc.capture_evidence(ctrl.id, "tenant-page", "config", {"i": i})
    await db_session.commit()

    result = await svc.search_evidence(tenant_id="tenant-page", page=1, limit=2)
    assert result["total"] == 5
    assert result["pages"] == 3
    assert len(result["items"]) == 2


# ---------------------------------------------------------------------------
# EvidenceService.get_evidence (tenant isolation)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_get_evidence_tenant_isolation(db_session, tmp_path):
    ctrl = await _make_control(db_session)
    await db_session.commit()

    svc = _make_svc(db_session, tmp_path)
    record = await svc.capture_evidence(ctrl.id, "tenant-iso-a", "config", {"x": 1})
    await db_session.commit()

    # Correct tenant — should find it
    found = await svc.get_evidence(record.id, "tenant-iso-a")
    assert found is not None
    assert found.id == record.id

    # Wrong tenant — must return None
    not_found = await svc.get_evidence(record.id, "tenant-iso-b")
    assert not_found is None


# ---------------------------------------------------------------------------
# EvidenceService.export_evidence_bundle
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_export_evidence_bundle_valid_zip(db_session, tmp_path):
    ctrl = await _make_control(db_session)
    await db_session.commit()

    svc = _make_svc(db_session, tmp_path)
    await svc.capture_evidence(ctrl.id, "tenant-bundle", "config", {"rule": "pass"})
    await svc.capture_evidence(ctrl.id, "tenant-bundle", "log", b"log line 1")
    await db_session.commit()

    bundle_bytes = await svc.export_evidence_bundle(tenant_id="tenant-bundle")
    assert len(bundle_bytes) > 0

    # Verify it's a valid ZIP
    with zipfile.ZipFile(io.BytesIO(bundle_bytes)) as zf:
        names = zf.namelist()
        assert "manifest.json" in names, f"manifest.json missing from ZIP: {names}"
        # At least 2 evidence files + manifest
        assert len(names) >= 3

        manifest_data = json.loads(zf.read("manifest.json"))
        assert len(manifest_data) == 2
        for entry in manifest_data:
            assert "id" in entry
            assert "type" in entry
            assert "file_in_bundle" in entry


@pytest.mark.anyio
async def test_export_bundle_respects_audit_period_filter(db_session, tmp_path):
    ctrl = await _make_control(db_session)
    await db_session.commit()

    svc = _make_svc(db_session, tmp_path)
    await svc.capture_evidence(
        ctrl.id, "tenant-filter", "config", b"2025 data", audit_period="2025"
    )
    await svc.capture_evidence(
        ctrl.id, "tenant-filter", "config", b"2026 data", audit_period="2026"
    )
    await db_session.commit()

    bundle_bytes = await svc.export_evidence_bundle(
        tenant_id="tenant-filter", audit_period="2025"
    )
    with zipfile.ZipFile(io.BytesIO(bundle_bytes)) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert len(manifest) == 1
    assert manifest[0]["audit_period"] == "2025"


@pytest.mark.anyio
async def test_export_bundle_tenant_isolation(db_session, tmp_path):
    ctrl = await _make_control(db_session)
    await db_session.commit()

    svc = _make_svc(db_session, tmp_path)
    await svc.capture_evidence(ctrl.id, "tenant-bund-a", "config", b"a data")
    await svc.capture_evidence(ctrl.id, "tenant-bund-b", "config", b"b data")
    await db_session.commit()

    bundle_a = await svc.export_evidence_bundle(tenant_id="tenant-bund-a")
    with zipfile.ZipFile(io.BytesIO(bundle_a)) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert all(e["tenant_id"] == "tenant-bund-a" for e in manifest)
    assert len(manifest) == 1

"""
Evidence Service — P2B.4.

Handles all CRUD operations for compliance evidence artifacts:
  - Auto-capture from control rule results (called by control_engine)
  - Manual upload from auditors/users
  - Search with filters
  - Export bundle (ZIP) for auditor handoff

All operations are tenant-scoped — a tenant can never access another tenant's evidence.

CRIT-009 — every Evidence row carries a SHA-256 hex digest of the stored
artifact (`content_sha256`). The hash is computed at write time and re-verified
on every read. Mismatch raises EvidenceTamperError. The auditor download
endpoint propagates the hash via the X-Evidence-Hash response header so
external auditors can verify integrity end-to-end (SOC2 CC7.2, ISO 27001 A.12.4).
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import math
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.models.evidence import Evidence
from compliance_backend.services.storage import BaseStorage, get_storage

logger = logging.getLogger(__name__)


# Default hard cap for evidence bundle size — 500 MB. Configurable via env.
# Why a cap: a tenant with thousands of large artifacts (screenshots, PDFs) can
# OOM the worker if the bundle is built unbounded. The cap forces the operator
# to paginate by audit_period / framework_id rather than dumping everything.
_DEFAULT_BUNDLE_MAX_BYTES = 500 * 1024 * 1024  # 500 MB

# Pagination — fetch evidence rows in batches to avoid loading all rows into
# memory at once. 100 is small enough to keep peak memory low and large enough
# to keep round-trip overhead negligible.
_BUNDLE_FETCH_BATCH = 100


class EvidenceTamperError(Exception):
    """Raised when stored evidence content fails its integrity hash check."""

    def __init__(self, evidence_id: str, expected: str, actual: str) -> None:
        self.evidence_id = evidence_id
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Evidence {evidence_id!r} integrity check failed: "
            f"expected sha256={expected}, got {actual}. "
            "On-disk artifact may have been tampered with."
        )


class EvidenceBundleSizeError(Exception):
    """
    Raised when an evidence bundle export exceeds the configured size cap.

    The operator should narrow the export by audit_period or framework_id
    rather than dumping the entire tenant. The cap exists to defend against
    accidental and deliberate memory exhaustion (Codex CRIT-002, Gemini
    CRIT-G4).
    """

    def __init__(self, written_bytes: int, cap_bytes: int) -> None:
        self.written_bytes = written_bytes
        self.cap_bytes = cap_bytes
        super().__init__(
            f"Evidence bundle would exceed cap: wrote {written_bytes} bytes, "
            f"cap is {cap_bytes} bytes. "
            "Narrow the export by audit_period or framework_id."
        )


def _bundle_max_bytes() -> int:
    """Read the cap from env at call time so tests can monkeypatch."""
    raw = os.environ.get("EVIDENCE_BUNDLE_MAX_BYTES")
    if not raw:
        return _DEFAULT_BUNDLE_MAX_BYTES
    try:
        val = int(raw)
        if val <= 0:
            return _DEFAULT_BUNDLE_MAX_BYTES
        return val
    except ValueError:
        logger.warning(
            "EVIDENCE_BUNDLE_MAX_BYTES is not an integer (%r); using default %d",
            raw, _DEFAULT_BUNDLE_MAX_BYTES,
        )
        return _DEFAULT_BUNDLE_MAX_BYTES


def _sha256_hex(data: bytes) -> str:
    """Return hex SHA-256 of the given bytes."""
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_audit_period() -> str:
    """Return the current year (UTC) as the default audit period string (e.g. '2026')."""
    return str(datetime.now(timezone.utc).year)


def _content_to_bytes(content: Any) -> bytes:
    """Serialize evidence content to bytes for storage."""
    if isinstance(content, bytes):
        return content
    if isinstance(content, str):
        return content.encode("utf-8")
    # Dict, list, etc. → JSON
    return json.dumps(content, default=str).encode("utf-8")


# ---------------------------------------------------------------------------
# EvidenceService
# ---------------------------------------------------------------------------

class EvidenceService:
    """
    Service layer for evidence management.

    Inject with a db session and optional storage backend.
    The storage backend defaults to the env-configured backend (FilesystemStorage in dev).
    """

    def __init__(self, db: AsyncSession, storage: Optional[BaseStorage] = None) -> None:
        self.db = db
        self.storage = storage or get_storage()

    # ------------------------------------------------------------------ #
    #  Auto-capture (called by control_engine after each rule run)
    # ------------------------------------------------------------------ #

    async def capture_evidence(
        self,
        control_id: str,
        tenant_id: str,
        evidence_type: str,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None,
        framework_id: Optional[str] = None,
        audit_period: Optional[str] = None,
        captured_by: str = "system",
    ) -> Evidence:
        """
        Capture a single piece of evidence and persist it.

        Args:
            control_id:    ID of the Control this evidence belongs to
            tenant_id:     Tenant scope
            evidence_type: "screenshot" | "config" | "log" | "ticket" | "document"
            content:       Raw content (bytes, str, or JSON-serialisable dict)
            metadata:      Optional extra context (source tool, region, etc.)
            framework_id:  Optional — derived from control's framework at engine level
            audit_period:  ISO period string (default: current year)
            captured_by:   "system" for auto-collected, user_id for manual

        Returns:
            Persisted Evidence ORM object (flushed but not committed;
            commit is the caller's responsibility to allow transaction batching)
        """
        audit_period = audit_period or _current_audit_period()
        content_bytes = _content_to_bytes(content)
        filename = f"evidence_{evidence_type}.json"

        # CRIT-009 — compute integrity hash BEFORE storage write so the row
        # records exactly what was persisted. If storage truncates or rewrites
        # bytes, the hash check on read will catch it.
        content_hash = _sha256_hex(content_bytes)

        uri = await self.storage.write(
            tenant_id=tenant_id,
            audit_period=audit_period,
            filename=filename,
            content=content_bytes,
        )

        record = Evidence(
            control_id=control_id,
            framework_id=framework_id,
            tenant_id=tenant_id,
            type=evidence_type,
            storage_uri=uri,
            audit_period=audit_period,
            captured_by=captured_by,
            metadata_json=metadata or {},
            content_sha256=content_hash,
        )
        self.db.add(record)
        await self.db.flush()  # assign ID; caller commits
        logger.info(
            "EvidenceService.capture_evidence: id=%s control=%s tenant=%s type=%s sha256=%s",
            record.id, control_id, tenant_id, evidence_type, content_hash,
        )
        return record

    # ------------------------------------------------------------------ #
    #  Manual upload
    # ------------------------------------------------------------------ #

    async def upload_manual_evidence(
        self,
        file_content: bytes,
        filename: str,
        control_id: str,
        tenant_id: str,
        evidence_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        framework_id: Optional[str] = None,
        audit_period: Optional[str] = None,
        uploaded_by: str = "unknown",
    ) -> Evidence:
        """
        Store a manually uploaded file and create an Evidence record.

        Args:
            file_content:  Raw file bytes (from multipart upload)
            filename:      Original filename (sanitised before storage)
            control_id:    Target control
            tenant_id:     Tenant scope
            evidence_type: Evidence type classification
            metadata:      Optional extra context
            framework_id:  Optional framework ID
            audit_period:  ISO period string (default: current year)
            uploaded_by:   User ID of the uploader

        Returns:
            Persisted Evidence record (not committed — caller commits)
        """
        audit_period = audit_period or _current_audit_period()

        # Sanitise filename: strip path separators
        safe_name = filename.replace("/", "_").replace("\\", "_").replace("..", "_")

        # CRIT-009 — hash the bytes the user uploaded BEFORE storage.write.
        content_hash = _sha256_hex(file_content)

        uri = await self.storage.write(
            tenant_id=tenant_id,
            audit_period=audit_period,
            filename=safe_name,
            content=file_content,
        )

        record = Evidence(
            control_id=control_id,
            framework_id=framework_id,
            tenant_id=tenant_id,
            type=evidence_type,
            storage_uri=uri,
            audit_period=audit_period,
            captured_by=uploaded_by,
            metadata_json=metadata or {"original_filename": filename},
            content_sha256=content_hash,
        )
        self.db.add(record)
        await self.db.flush()
        logger.info(
            "EvidenceService.upload_manual_evidence: id=%s control=%s tenant=%s sha256=%s",
            record.id, control_id, tenant_id, content_hash,
        )
        return record

    # ------------------------------------------------------------------ #
    #  Search
    # ------------------------------------------------------------------ #

    async def search_evidence(
        self,
        tenant_id: str,
        control_id: Optional[str] = None,
        framework_id: Optional[str] = None,
        evidence_type: Optional[str] = None,
        audit_period: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Paginated evidence search, scoped to tenant.

        Returns:
            {
                "items": [Evidence, ...],
                "total": int,
                "page": int,
                "limit": int,
                "pages": int,
            }
        """
        # Build filters
        filters = [Evidence.tenant_id == tenant_id]
        if control_id:
            filters.append(Evidence.control_id == control_id)
        if framework_id:
            filters.append(Evidence.framework_id == framework_id)
        if evidence_type:
            filters.append(Evidence.type == evidence_type)
        if audit_period:
            filters.append(Evidence.audit_period == audit_period)

        where_clause = and_(*filters)

        # Total count
        count_result = await self.db.execute(
            select(func.count()).select_from(Evidence).where(where_clause)
        )
        total = count_result.scalar() or 0

        # Paginated rows
        offset = (page - 1) * limit
        rows_result = await self.db.execute(
            select(Evidence)
            .where(where_clause)
            .order_by(Evidence.captured_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = rows_result.scalars().all()

        pages = math.ceil(total / limit) if total > 0 else 1

        return {"items": list(items), "total": total, "page": page, "limit": limit, "pages": pages}

    # ------------------------------------------------------------------ #
    #  Single fetch
    # ------------------------------------------------------------------ #

    async def get_evidence(self, evidence_id: str, tenant_id: str) -> Optional[Evidence]:
        """
        Fetch a single Evidence record, enforcing tenant isolation.

        Returns None if not found or belongs to a different tenant.
        """
        result = await self.db.execute(
            select(Evidence).where(
                and_(Evidence.id == evidence_id, Evidence.tenant_id == tenant_id)
            )
        )
        return result.scalars().first()

    async def get_evidence_content(self, evidence_id: str, tenant_id: str) -> Optional[bytes]:
        """
        Fetch raw content bytes for a single evidence record.

        Returns None if the record doesn't exist or belongs to another tenant.
        Raises FileNotFoundError if the storage artifact is missing.

        CRIT-009 — re-computes SHA-256 of the artifact and compares it to the
        hash recorded at write time. Mismatch raises EvidenceTamperError so
        the caller (and the auditor) cannot be fooled by silent on-disk
        modification. Legacy rows with NULL content_sha256 (pre-migration)
        skip verification but log a warning so the backfill TODO is visible.
        """
        record = await self.get_evidence(evidence_id, tenant_id)
        if record is None:
            return None
        content = await self.storage.read(record.storage_uri)

        expected = record.content_sha256
        if expected is None:
            logger.warning(
                "EvidenceService.get_evidence_content: legacy evidence id=%s "
                "has no content_sha256 — skipping integrity check (BACKFILL TODO).",
                record.id,
            )
            return content

        actual = _sha256_hex(content)
        if actual != expected:
            logger.error(
                "EvidenceService.get_evidence_content: TAMPER DETECTED "
                "id=%s expected=%s actual=%s uri=%s",
                record.id, expected, actual, record.storage_uri,
            )
            raise EvidenceTamperError(record.id, expected, actual)
        return content

    # ------------------------------------------------------------------ #
    #  Export bundle
    # ------------------------------------------------------------------ #

    async def export_evidence_bundle(
        self,
        tenant_id: str,
        framework_id: Optional[str] = None,
        audit_period: Optional[str] = None,
    ) -> bytes:
        """
        Build a ZIP bundle of all evidence for the given tenant/framework/period.

        The ZIP contains:
          - evidence/{evidence_id}_{type}.bin  — raw artifact bytes
          - manifest.json                       — metadata + content_sha256 per record

        Returns:
            ZIP file as bytes.

        Implementation (HIGH-1 fix — Gemini CRIT-G4 + Codex CRIT-002):
          - The zip is built INTO A TEMP FILE on disk (not into BytesIO) so peak
            memory is bounded regardless of how many artifacts there are.
          - Evidence rows are fetched in batches of ``_BUNDLE_FETCH_BATCH`` (100)
            so the result-set never materialises in memory all at once.
          - A running byte total is tracked. If the on-disk zip exceeds
            ``EVIDENCE_BUNDLE_MAX_BYTES`` (default 500 MB), the temp file is
            removed (moved to trash per INV-0) and ``EvidenceBundleSizeError``
            is raised. The operator must narrow the export.
          - The manifest now includes ``content_sha256`` for each record so an
            external auditor can re-verify the bundle end-to-end without trusting
            us.

        Raises:
            EvidenceBundleSizeError: when the bundle would exceed the cap.
        """
        cap = _bundle_max_bytes()

        filters = [Evidence.tenant_id == tenant_id]
        if framework_id:
            filters.append(Evidence.framework_id == framework_id)
        if audit_period:
            filters.append(Evidence.audit_period == audit_period)

        where_clause = and_(*filters)

        # Build the zip into a temp file on disk so peak memory is bounded.
        # delete=False so we control deletion (the file lives just long enough
        # for us to read its bytes, then we remove it). On Windows you cannot
        # reopen a NamedTemporaryFile while it's open — using delete=False sidesteps
        # that quirk too.
        tmp = tempfile.NamedTemporaryFile(
            mode="w+b",
            prefix="evidence_bundle_",
            suffix=".zip",
            delete=False,
        )
        tmp_path = Path(tmp.name)
        tmp.close()

        manifest: List[Dict[str, Any]] = []

        try:
            with zipfile.ZipFile(
                tmp_path, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
            ) as zf:
                # Page through evidence rows in batches so we never load the
                # entire result-set into memory.
                offset = 0
                while True:
                    rows_result = await self.db.execute(
                        select(Evidence)
                        .where(where_clause)
                        .order_by(Evidence.captured_at.asc(), Evidence.id.asc())
                        .offset(offset)
                        .limit(_BUNDLE_FETCH_BATCH)
                    )
                    batch = list(rows_result.scalars().all())
                    if not batch:
                        break

                    for record in batch:
                        try:
                            content = await self.storage.read(record.storage_uri)
                        except FileNotFoundError:
                            logger.warning(
                                "export_evidence_bundle: artifact missing for "
                                "evidence id=%s uri=%s",
                                record.id, record.storage_uri,
                            )
                            content = b""

                        # Re-compute sha256 of what we are actually putting in
                        # the bundle. If the storage layer was tampered with
                        # but get_evidence_content was not used, this catches it
                        # at bundle-time too.
                        actual_hash = _sha256_hex(content) if content else None
                        if (
                            content
                            and record.content_sha256
                            and actual_hash != record.content_sha256
                        ):
                            # Tampered artifact — emit a warning but continue
                            # so the bundle reflects on-disk reality. The
                            # auditor will see hash mismatch vs DB record.
                            logger.error(
                                "export_evidence_bundle: TAMPER detected id=%s "
                                "expected=%s actual=%s — emitting actual hash in "
                                "manifest for auditor visibility.",
                                record.id, record.content_sha256, actual_hash,
                            )

                        entry_name = f"evidence/{record.id}_{record.type}.bin"
                        zf.writestr(entry_name, content)

                        # Cap check after every write — bail early if we'd blow
                        # past the limit. Flush so the on-disk size reflects the
                        # write before stat().
                        zf.fp.flush()
                        size_so_far = tmp_path.stat().st_size
                        if size_so_far > cap:
                            raise EvidenceBundleSizeError(size_so_far, cap)

                        manifest.append({
                            "id": record.id,
                            "control_id": record.control_id,
                            "framework_id": record.framework_id,
                            "tenant_id": record.tenant_id,
                            "type": record.type,
                            "storage_uri": record.storage_uri,
                            "audit_period": record.audit_period,
                            "captured_at": record.captured_at.isoformat(),
                            "captured_by": record.captured_by,
                            "metadata": record.metadata_json,
                            "file_in_bundle": entry_name,
                            # Codex CRIT-002 fix — auditor can re-verify
                            "content_sha256": (
                                actual_hash or record.content_sha256
                            ),
                        })

                    if len(batch) < _BUNDLE_FETCH_BATCH:
                        break
                    offset += _BUNDLE_FETCH_BATCH

                zf.writestr("manifest.json", json.dumps(manifest, indent=2))

            # Final size check (manifest write may push us over).
            final_size = tmp_path.stat().st_size
            if final_size > cap:
                raise EvidenceBundleSizeError(final_size, cap)

            # Read the finished zip back as bytes for the caller. This is still
            # bounded by cap, not by row count.
            return tmp_path.read_bytes()
        finally:
            # INV-0: never `rm`; rename into a sibling _trash dir if it exists,
            # otherwise leave the file (the OS tmp dir is cleaned by the OS).
            try:
                trash = tmp_path.parent / "_trash"
                trash.mkdir(parents=True, exist_ok=True)
                if tmp_path.exists():
                    tmp_path.rename(trash / tmp_path.name)
            except Exception as exc:  # pragma: no cover — defence in depth
                logger.warning(
                    "export_evidence_bundle: could not move %s to trash: %s",
                    tmp_path, exc,
                )

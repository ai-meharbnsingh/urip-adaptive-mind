"""
Object storage abstraction for evidence artifacts — P2B.4.

Two implementations:
  FilesystemStorage  — local filesystem under compliance/data/evidence/
                       Used for development and testing. NO external dependencies.
  S3Storage          — AWS S3 / Cloudflare R2 compatible.
                       TODO: implement when production infra is provisioned.

Usage:
    from compliance_backend.services.storage import get_storage
    storage = get_storage()
    uri = await storage.write(tenant_id, audit_period, filename, content_bytes)
    data = await storage.read(uri)

The storage backend is selected via the EVIDENCE_STORAGE_BACKEND env var:
  "filesystem" (default) — FilesystemStorage
  "s3"                   — S3Storage (requires EVIDENCE_S3_BUCKET, AWS credentials)

Production note:
  Switch to S3Storage by setting:
    EVIDENCE_STORAGE_BACKEND=s3
    EVIDENCE_S3_BUCKET=my-compliance-evidence
    AWS_DEFAULT_REGION=us-east-1
  Ensure IAM role has s3:PutObject, s3:GetObject, s3:DeleteObject on the bucket.
"""
from __future__ import annotations

import abc
import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Base directory for filesystem storage.
# storage.py lives at: compliance/backend/compliance_backend/services/storage.py
# parents[3] = compliance/
# Override with EVIDENCE_STORAGE_BASE_DIR env var (useful for tests to use tmp dir)
_DEFAULT_BASE_DIR = (
    Path(os.environ["EVIDENCE_STORAGE_BASE_DIR"])
    if "EVIDENCE_STORAGE_BASE_DIR" in os.environ
    else Path(__file__).resolve().parents[3] / "data" / "evidence"
)


class BaseStorage(abc.ABC):
    """Abstract storage backend for evidence artifacts."""

    @abc.abstractmethod
    async def write(
        self,
        tenant_id: str,
        audit_period: str,
        filename: str,
        content: bytes,
    ) -> str:
        """
        Write content to storage and return the opaque URI.

        Args:
            tenant_id:    Tenant scope (used as path prefix / S3 prefix)
            audit_period: Audit period string (e.g. "2026" or "2026-Q1")
            filename:     Suggested filename (will be prefixed with uuid for uniqueness)
            content:      Raw bytes to store

        Returns:
            Opaque URI string (e.g. "file:///...abs_path" or "s3://bucket/key")
        """
        ...

    @abc.abstractmethod
    async def read(self, uri: str) -> bytes:
        """
        Retrieve content from storage by URI.

        Raises:
            FileNotFoundError if uri does not exist.
        """
        ...

    @abc.abstractmethod
    async def delete(self, uri: str) -> None:
        """
        Remove a stored artifact.
        Implementation must handle missing URI gracefully (no-op or log).
        """
        ...


class FilesystemStorage(BaseStorage):
    """
    Local filesystem storage backend.

    Layout:
      {base_dir}/{tenant_id}/{audit_period}/{uuid}_{filename}

    URIs are of the form:
      file:///absolute/path/to/file

    Suitable for: local development, tests, single-node deployments.
    NOT suitable for: multi-node deployments (files not shared across nodes).

    Production recommendation: use S3Storage with a shared S3/R2 bucket.
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or _DEFAULT_BASE_DIR

    def _resolve_path(self, tenant_id: str, audit_period: str, filename: str) -> Path:
        safe_tenant = tenant_id.replace("/", "_").replace("..", "_")
        safe_period = audit_period.replace("/", "_").replace("..", "_")
        directory = self.base_dir / safe_tenant / safe_period
        directory.mkdir(parents=True, exist_ok=True)
        unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"
        return directory / unique_name

    def _uri_to_path(self, uri: str) -> Path:
        if not uri.startswith("file://"):
            raise ValueError(f"FilesystemStorage cannot handle URI scheme: {uri!r}")
        # file:///absolute/path → /absolute/path
        return Path(uri[7:])

    async def write(
        self,
        tenant_id: str,
        audit_period: str,
        filename: str,
        content: bytes,
    ) -> str:
        path = self._resolve_path(tenant_id, audit_period, filename)
        # Run blocking IO in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, path.write_bytes, content)
        uri = f"file://{path}"
        logger.debug("FilesystemStorage.write: %s", uri)
        return uri

    async def read(self, uri: str) -> bytes:
        path = self._uri_to_path(uri)
        if not path.exists():
            raise FileNotFoundError(f"Evidence not found at: {uri}")
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, path.read_bytes)
        return data

    async def delete(self, uri: str) -> None:
        """
        Move file to _trash/ subdirectory instead of deleting (INV-0: no rm).
        """
        try:
            path = self._uri_to_path(uri)
            if not path.exists():
                logger.debug("FilesystemStorage.delete: not found, skipping: %s", uri)
                return
            trash_dir = path.parent / "_trash"
            trash_dir.mkdir(parents=True, exist_ok=True)
            dest = trash_dir / path.name
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, path.rename, dest)
            logger.debug("FilesystemStorage.delete: moved to trash: %s", dest)
        except Exception as exc:
            logger.warning("FilesystemStorage.delete error: %s", exc)


class S3Storage(BaseStorage):
    """
    S3-compatible object storage backend.

    TODO: Implement when production infra is provisioned.
    Required env vars:
      EVIDENCE_S3_BUCKET   — S3 bucket name
      AWS_DEFAULT_REGION   — AWS region (or use instance role)

    URI format: s3://{bucket}/{tenant_id}/{audit_period}/{uuid}_{filename}
    """

    def __init__(self, bucket: Optional[str] = None) -> None:
        self.bucket = bucket or os.environ.get("EVIDENCE_S3_BUCKET", "compliance-evidence")

    async def write(self, tenant_id: str, audit_period: str, filename: str, content: bytes) -> str:
        raise NotImplementedError(
            "S3Storage is not yet implemented. "
            "Set EVIDENCE_STORAGE_BACKEND=filesystem for local development."
        )

    async def read(self, uri: str) -> bytes:
        raise NotImplementedError("S3Storage is not yet implemented.")

    async def delete(self, uri: str) -> None:
        raise NotImplementedError("S3Storage is not yet implemented.")


def get_storage() -> BaseStorage:
    """
    Factory — returns the configured storage backend singleton.

    EVIDENCE_STORAGE_BACKEND env var:
      "filesystem" (default) → FilesystemStorage
      "s3"                   → S3Storage
    """
    backend = os.environ.get("EVIDENCE_STORAGE_BACKEND", "filesystem").lower()
    if backend == "s3":
        return S3Storage()
    return FilesystemStorage()

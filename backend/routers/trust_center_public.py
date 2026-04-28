"""
trust_center_public — buyer-facing endpoints (no auth on landing/request, but
download is gated by the time-bound access token).

Mounted at /trust (NOT /api) so URLs are buyer-friendly:

    GET  /trust/{tenant_slug}                          — landing page metadata
    POST /trust/{tenant_slug}/request-access           — buyer submits request
    POST /trust/{tenant_slug}/sign-nda                 — sign NDA electronically
    GET  /trust/access/{access_token}/download/{doc_id} — token-gated download

The download endpoint streams real bytes:
  - file://...  → opens the local file with a 64-KiB chunk iterator
  - s3://...    → boto3 get_object().Body iter_chunks
  - http(s)://  → httpx streaming proxy (handy for R2 / pre-signed URLs)

Range requests (HTTP 206) are honoured for filesystem and S3 paths so the
buyer's PDF reader can do byte-range fetches.
"""
from __future__ import annotations

import logging
import mimetypes
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.audit_log import AuditLog
from backend.models.tenant import Tenant
from backend.models.trust_center import TrustCenterAccessRequest, TrustCenterDocument
from backend.services.trust_center_service import (
    download_document,
    list_published_documents,
    request_access,
    sign_nda,
)

logger = logging.getLogger(__name__)

# 64-KiB chunk: balances syscall overhead vs memory residency in the worker.
DEFAULT_CHUNK = 64 * 1024


# Indirect lookup so tests can monkey-patch a fake boto3 client without
# requiring the real package to be installed in the test env.
def _boto3_client(service_name: str, **kwargs):  # pragma: no cover - real prod path
    import boto3  # type: ignore[import-not-found]
    return boto3.client(service_name, **kwargs)


# ---- mime-type sniffing -------------------------------------------------- #
_MIME_MAGIC_HEADERS: list[tuple[bytes, str]] = [
    (b"%PDF-", "application/pdf"),
    (b"PK\x03\x04", "application/zip"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
]


def _sniff_content_type(header: bytes, fallback_path: str | None) -> str:
    for magic, ct in _MIME_MAGIC_HEADERS:
        if header.startswith(magic):
            return ct
    if fallback_path:
        guessed, _ = mimetypes.guess_type(fallback_path)
        if guessed:
            return guessed
    return "application/octet-stream"


def _safe_filename(doc: TrustCenterDocument) -> str:
    """Sanitise a download filename — keep alnum / dot / dash / underscore."""
    parsed = urlparse(doc.file_storage_uri)
    base = Path(parsed.path).name or f"document-{doc.id}"
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    if "." not in safe:
        # Append a sensible extension based on doc_type so PDF readers open it.
        if doc.doc_type in ("SOC2_REPORT", "PEN_TEST_SUMMARY", "ISO_CERT"):
            safe += ".pdf"
    return safe


# ---- Range header parsing ------------------------------------------------ #
_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


def _parse_range(range_header: str | None, file_size: int) -> tuple[int, int] | None:
    """
    Returns (start, end) inclusive or None when no/invalid range.
    Per RFC 7233 we tolerate `bytes=0-` (open-ended) and `bytes=-N` (suffix).
    """
    if not range_header:
        return None
    m = _RANGE_RE.match(range_header.strip())
    if not m:
        return None
    start_s, end_s = m.group(1), m.group(2)
    if not start_s and not end_s:
        return None
    if not start_s:
        # suffix range: last N bytes
        n = int(end_s)
        if n <= 0:
            return None
        return max(0, file_size - n), file_size - 1
    start = int(start_s)
    end = int(end_s) if end_s else file_size - 1
    if start > end or start >= file_size:
        return None
    end = min(end, file_size - 1)
    return start, end


# ---- streaming generators ------------------------------------------------ #
def _stream_file(path: str, start: int, end: int, chunk: int = DEFAULT_CHUNK) -> Iterator[bytes]:
    """Yield bytes [start..end] from a filesystem path."""
    remaining = end - start + 1
    with open(path, "rb") as fh:
        if start:
            fh.seek(start)
        while remaining > 0:
            data = fh.read(min(chunk, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


def _stream_s3(s3_client, bucket: str, key: str, range_header: str | None) -> tuple[Iterator[bytes], dict[str, str], int | None]:
    """Pull an S3 object and yield its Body bytes."""
    kwargs: dict[str, Any] = {"Bucket": bucket, "Key": key}
    if range_header:
        kwargs["Range"] = range_header
    obj = s3_client.get_object(**kwargs)
    body = obj["Body"]
    headers: dict[str, str] = {}
    if obj.get("ContentType"):
        headers["content-type"] = obj["ContentType"]
    content_length = obj.get("ContentLength")
    content_range = obj.get("ContentRange")
    if content_range:
        headers["content-range"] = content_range

    def _gen() -> Iterator[bytes]:
        try:
            iterator = body.iter_chunks(chunk_size=DEFAULT_CHUNK) if hasattr(body, "iter_chunks") else None
            if iterator is not None:
                for chunk in iterator:
                    if chunk:
                        yield chunk
            else:
                while True:
                    data = body.read(DEFAULT_CHUNK)
                    if not data:
                        break
                    yield data
        finally:
            close = getattr(body, "close", None)
            if callable(close):
                close()

    return _gen(), headers, content_length

router = APIRouter()


# --------------------------------------------------------------------------- #
class PublicDocOut(BaseModel):
    id: str
    doc_type: str
    title: str
    description: str | None
    valid_until: datetime | None
    requires_nda: bool


class TenantBrandOut(BaseModel):
    name: str
    slug: str
    logo_url: str | None = None
    primary_color: str | None = None


class TrustCenterLandingOut(BaseModel):
    tenant: TenantBrandOut
    documents: list[PublicDocOut]


class RequestAccessIn(BaseModel):
    doc_id: uuid.UUID
    requester_email: EmailStr
    requester_name: str | None = None
    requester_company: str | None = None
    requester_purpose: str | None = Field(default=None, max_length=2000)


class RequestAccessOut(BaseModel):
    request_id: str
    status: str
    nda_required: bool


class SignNdaIn(BaseModel):
    request_id: uuid.UUID
    signature_text: str = Field(min_length=2, max_length=255)


# --------------------------------------------------------------------------- #
async def _get_tenant_by_slug(db: AsyncSession, slug: str) -> Tenant:
    q = await db.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = q.scalar_one_or_none()
    if tenant is None or not tenant.is_active:
        raise HTTPException(status_code=404, detail="Trust Center not found")
    return tenant


# --------------------------------------------------------------------------- #
# Landing — public, no auth.
# --------------------------------------------------------------------------- #
@router.get("/{tenant_slug}", response_model=TrustCenterLandingOut)
async def landing(
    tenant_slug: str, db: AsyncSession = Depends(get_db)
) -> TrustCenterLandingOut:
    tenant = await _get_tenant_by_slug(db, tenant_slug)
    docs = await list_published_documents(db, tenant.id)
    branding = (tenant.settings or {}).get("branding") or {}
    return TrustCenterLandingOut(
        tenant=TenantBrandOut(
            name=tenant.name,
            slug=tenant.slug,
            logo_url=branding.get("logo_url"),
            primary_color=branding.get("primary_color"),
        ),
        documents=[
            PublicDocOut(
                id=str(d.id),
                doc_type=d.doc_type,
                title=d.title,
                description=d.description,
                valid_until=d.valid_until,
                requires_nda=d.requires_nda,
            )
            for d in docs
        ],
    )


# --------------------------------------------------------------------------- #
@router.post("/{tenant_slug}/request-access", response_model=RequestAccessOut)
async def request_access_endpoint(
    tenant_slug: str,
    payload: RequestAccessIn,
    db: AsyncSession = Depends(get_db),
) -> RequestAccessOut:
    tenant = await _get_tenant_by_slug(db, tenant_slug)
    try:
        req = await request_access(
            db,
            tenant.id,
            payload.doc_id,
            requester_email=payload.requester_email,
            requester_name=payload.requester_name,
            requester_company=payload.requester_company,
            requester_purpose=payload.requester_purpose,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    # Look up doc.requires_nda for client UI hint.
    from backend.models.trust_center import TrustCenterDocument
    doc_q = await db.execute(
        select(TrustCenterDocument).where(TrustCenterDocument.id == payload.doc_id)
    )
    doc = doc_q.scalar_one()
    return RequestAccessOut(
        request_id=str(req.id),
        status=req.status,
        nda_required=doc.requires_nda,
    )


# --------------------------------------------------------------------------- #
@router.post("/{tenant_slug}/sign-nda")
async def sign_nda_endpoint(
    tenant_slug: str,
    payload: SignNdaIn,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    tenant = await _get_tenant_by_slug(db, tenant_slug)
    # Confirm the request belongs to this tenant before signing — prevents
    # cross-tenant request-id guessing.
    q = await db.execute(
        select(TrustCenterAccessRequest).where(
            TrustCenterAccessRequest.id == payload.request_id,
            TrustCenterAccessRequest.tenant_id == tenant.id,
        )
    )
    if q.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Request not found")
    try:
        req = await sign_nda(db, payload.request_id, signature_text=payload.signature_text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"ok": True, "nda_signed_at": req.nda_signed_at}


# --------------------------------------------------------------------------- #
async def _write_download_audit(
    db: AsyncSession, doc: TrustCenterDocument, request_row: TrustCenterAccessRequest, ip: str | None
) -> None:
    db.add(
        AuditLog(
            id=uuid.uuid4(),
            user_id=None,  # buyer is not a tenant-side user
            tenant_id=doc.tenant_id,
            action="trust_center_download",
            resource_type="trust_center_document",
            resource_id=doc.id,
            details={
                "request_id": str(request_row.id),
                "requester_email": request_row.requester_email,
                "doc_title": doc.title,
                "download_count": int(request_row.download_count or 0),
            },
            ip_address=ip,
        )
    )
    await db.commit()


@router.get("/access/{access_token}/download/{doc_id}")
async def download(
    access_token: str,
    doc_id: uuid.UUID,
    request: Request,
    range: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    handle = await download_document(db, access_token, doc_id)
    if handle is None:
        raise HTTPException(status_code=403, detail="Invalid, expired, or revoked access token")
    await db.commit()

    uri = handle.file_storage_uri
    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()
    filename = _safe_filename(handle.document)
    client_ip = request.client.host if request.client else None

    # ---------- filesystem ---------- #
    if scheme in ("file", ""):
        local_path = parsed.path if scheme == "file" else uri
        if not local_path or not os.path.isfile(local_path):
            raise HTTPException(status_code=404, detail="Document file not available on storage")
        file_size = os.path.getsize(local_path)
        # Sniff content type from file header.
        with open(local_path, "rb") as fh:
            header_bytes = fh.read(16)
        content_type = _sniff_content_type(header_bytes, local_path)

        rng = _parse_range(range, file_size)
        await _write_download_audit(db, handle.document, handle.request, client_ip)
        if rng is None:
            headers = {
                "content-disposition": f'attachment; filename="{filename}"',
                "accept-ranges": "bytes",
                "content-length": str(file_size),
            }
            return StreamingResponse(
                _stream_file(local_path, 0, file_size - 1),
                media_type=content_type,
                headers=headers,
                status_code=200,
            )
        start, end = rng
        length = end - start + 1
        headers = {
            "content-disposition": f'attachment; filename="{filename}"',
            "accept-ranges": "bytes",
            "content-range": f"bytes {start}-{end}/{file_size}",
            "content-length": str(length),
        }
        return StreamingResponse(
            _stream_file(local_path, start, end),
            media_type=content_type,
            headers=headers,
            status_code=206,
        )

    # ---------- s3 ---------- #
    if scheme == "s3":
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        if not bucket or not key:
            raise HTTPException(status_code=500, detail="Malformed s3 URI")
        try:
            s3 = _boto3_client("s3")
        except Exception as exc:  # pragma: no cover - real prod path
            logger.exception("Failed to construct boto3 client")
            raise HTTPException(status_code=500, detail="Object store unavailable") from exc
        try:
            stream, s3_headers, content_length = _stream_s3(s3, bucket, key, range)
        except Exception as exc:
            logger.warning("S3 get_object failed for s3://%s/%s: %s", bucket, key, exc)
            raise HTTPException(status_code=502, detail="Could not fetch object from S3")
        await _write_download_audit(db, handle.document, handle.request, client_ip)
        media_type = s3_headers.pop("content-type", None) or _sniff_content_type(b"", key)
        is_partial = "content-range" in s3_headers
        out_headers: dict[str, str] = {
            "content-disposition": f'attachment; filename="{filename}"',
            "accept-ranges": "bytes",
        }
        if content_length is not None:
            out_headers["content-length"] = str(content_length)
        out_headers.update(s3_headers)
        return StreamingResponse(
            stream,
            media_type=media_type,
            headers=out_headers,
            status_code=206 if is_partial else 200,
        )

    # ---------- http / https proxy ---------- #
    if scheme in ("http", "https"):
        import httpx  # local import keeps the cold path light
        try:
            with httpx.Client(timeout=30.0) as cli:
                req_headers = {"Range": range} if range else {}
                upstream = cli.get(uri, headers=req_headers)
        except httpx.HTTPError as exc:
            logger.warning("HTTP storage fetch failed: %s", exc)
            raise HTTPException(status_code=502, detail="Could not fetch object from storage")
        if upstream.status_code not in (200, 206):
            raise HTTPException(status_code=502, detail=f"Storage upstream HTTP {upstream.status_code}")
        await _write_download_audit(db, handle.document, handle.request, client_ip)
        media_type = upstream.headers.get("content-type") or _sniff_content_type(upstream.content[:16], uri)
        out_headers = {
            "content-disposition": f'attachment; filename="{filename}"',
            "accept-ranges": "bytes",
            "content-length": str(len(upstream.content)),
        }
        if "content-range" in upstream.headers:
            out_headers["content-range"] = upstream.headers["content-range"]
        return StreamingResponse(
            iter([upstream.content]),
            media_type=media_type,
            headers=out_headers,
            status_code=upstream.status_code,
        )

    # Unknown scheme → 500.
    raise HTTPException(status_code=500, detail=f"Unsupported storage URI scheme: {scheme!r}")

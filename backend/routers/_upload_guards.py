"""
Upload validation guards (backend) — P33a.

Mirrors the compliance-side guard (compliance_backend.routers._upload_guards)
but lives inside the URIP backend package so backend stays self-contained.

Enforced policy:
  - MAX_UPLOAD_BYTES = 50 MB → 413 on overrun
  - Content-Type allowlist: image/*, application/pdf, application/json,
    text/csv, text/plain, application/zip → 422 on disallowed
  - Magic-byte sniff for image/* / pdf / zip — claimed type must match
    detected magic (catches PHP-as-PNG style uploads) → 422 on mismatch
  - Filename sanitisation: strip directory separators + parent traversal,
    prefix with UUID4 hex, cap to 200 chars; falls back to ``upload.bin``
    if the sanitised base ends up empty.

Returns (content_bytes, safe_filename, original_filename) or raises
HTTPException with the right status code.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Tuple

from fastapi import HTTPException, UploadFile, status

logger = logging.getLogger(__name__)


# ── Limits ─────────────────────────────────────────────────────────
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB

ALLOWED_CONTENT_TYPE_FAMILIES = {
    "application/pdf",
    "application/json",
    "application/zip",
    "text/csv",
    "text/plain",
}
ALLOWED_CONTENT_TYPE_PREFIXES = ("image/",)


# ── Filename sanitisation ──────────────────────────────────────────

_FORBIDDEN_NAME_CHARS = re.compile(r"[\\/]+")
_DOTDOT = re.compile(r"\.\.+")


def _is_content_type_allowed(content_type: str | None) -> bool:
    if not content_type:
        return False
    ct = content_type.strip().lower().split(";", 1)[0].strip()
    if ct in ALLOWED_CONTENT_TYPE_FAMILIES:
        return True
    return any(ct.startswith(p) for p in ALLOWED_CONTENT_TYPE_PREFIXES)


def sanitise_filename(raw: str | None) -> Tuple[str, str]:
    original = raw or ""
    base = original
    base = _FORBIDDEN_NAME_CHARS.sub("_", base)
    base = _DOTDOT.sub("_", base)
    base = base.strip(" .")
    base = base[:200]
    if not base:
        base = "upload.bin"
    safe = f"{uuid.uuid4().hex}__{base}"
    return safe, original


# ── Magic-byte sniffing ────────────────────────────────────────────

_MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"RIFF", "image/webp__riff_header"),
    (b"BM", "image/bmp"),
    (b"%PDF-", "application/pdf"),
    (b"PK\x03\x04", "application/zip"),
    (b"PK\x05\x06", "application/zip"),
    (b"PK\x07\x08", "application/zip"),
]


def _detect_magic(data: bytes) -> str | None:
    if not data:
        return None
    for sig, ct in _MAGIC_SIGNATURES:
        if data.startswith(sig):
            if ct == "image/webp__riff_header":
                if len(data) >= 12 and data[8:12] == b"WEBP":
                    return "image/webp"
                return None
            return ct
    return None


_COMPATIBLE_FAMILIES: dict[str, set[str]] = {
    "image/png":  {"image/png"},
    "image/jpeg": {"image/jpeg", "image/jpg"},
    "image/gif":  {"image/gif"},
    "image/webp": {"image/webp"},
    "image/bmp":  {"image/bmp"},
    "application/pdf": {"application/pdf"},
    "application/zip": {
        "application/zip",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    },
}

_BINARY_MIME_PREFIXES = ("image/",)
_BINARY_MIME_EXACT = {"application/pdf", "application/zip"}


def _claimed_matches_magic(claimed: str | None, magic_ct: str | None) -> bool:
    if not claimed:
        return False
    cl = claimed.strip().lower().split(";", 1)[0].strip()

    requires_magic = (
        cl in _BINARY_MIME_EXACT
        or any(cl.startswith(p) for p in _BINARY_MIME_PREFIXES)
    )

    if magic_ct is None:
        return not requires_magic

    families = _COMPATIBLE_FAMILIES.get(magic_ct, {magic_ct})
    return cl in families


async def read_and_validate_upload(file: UploadFile) -> Tuple[bytes, str, str]:
    """
    Read ``file`` end-to-end, validate, return (body, safe_filename, original).
    Raises HTTPException on policy violation.
    """
    content_type = file.content_type
    if not _is_content_type_allowed(content_type):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Unsupported content_type {content_type!r}. Allowed: "
                f"image/*, application/pdf, application/json, text/csv, "
                f"text/plain, application/zip"
            ),
        )

    chunks: list[bytes] = []
    total = 0
    cap = MAX_UPLOAD_BYTES
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > cap:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"Uploaded file exceeds the {cap // (1024 * 1024)} MB limit."
                ),
            )

    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty.",
        )

    body = b"".join(chunks)

    magic_ct = _detect_magic(body[:32])
    if not _claimed_matches_magic(content_type, magic_ct):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Uploaded file content does not match declared "
                f"Content-Type {content_type!r}: detected {magic_ct!r}. "
                "Refusing to store."
            ),
        )

    safe_name, original = sanitise_filename(file.filename)
    return body, safe_name, original

"""
HIGH-011 — Upload validation guards (size, content-type, filename sanitisation).

Used by:
  - routers/evidence.py        (manual evidence upload)
  - routers/vendors.py         (vendor document upload)

Why a router-level helper (and not service-level)?
--------------------------------------------------
The CritFix-D scope explicitly excludes
``compliance_backend/services/evidence_service.py`` (CritFix-B's territory),
so all input validation must happen BEFORE the service is called. This module
is the boundary.

What's enforced
---------------
- ``MAX_UPLOAD_BYTES`` = 50 MB. Anything larger → 413.
- Content-Type allowlist: image/*, application/pdf, application/json,
  text/csv, text/plain, application/zip. Anything else → 422.
- Filename sanitisation:
    * strip ``/`` and ``\\`` (no directory components)
    * strip ``..`` (no parent traversal)
    * collapse repeated path separators
    * prefix with a UUID4 hex so two uploads of "report.pdf" cannot collide
      on disk
- ``read_and_validate_upload(file)`` returns ``(content_bytes, safe_filename,
  original_filename)`` or raises HTTPException with the right status.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Tuple

from fastapi import HTTPException, UploadFile, status

logger = logging.getLogger(__name__)


# ── Limits ──────────────────────────────────────────────────────────
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB

# Order matters for clarity; image/* is matched as a family below.
ALLOWED_CONTENT_TYPE_FAMILIES = {
    "application/pdf",
    "application/json",
    "application/zip",
    "text/csv",
    "text/plain",
}
ALLOWED_CONTENT_TYPE_PREFIXES = ("image/",)


# ── Filename sanitisation ───────────────────────────────────────────

_FORBIDDEN_NAME_CHARS = re.compile(r"[\\/]+")  # / or \ (one or more)
_DOTDOT = re.compile(r"\.\.+")  # one or more consecutive dots when len > 1


def _is_content_type_allowed(content_type: str | None) -> bool:
    if not content_type:
        return False
    ct = content_type.strip().lower().split(";", 1)[0].strip()
    if ct in ALLOWED_CONTENT_TYPE_FAMILIES:
        return True
    return any(ct.startswith(p) for p in ALLOWED_CONTENT_TYPE_PREFIXES)


def sanitise_filename(raw: str | None) -> Tuple[str, str]:
    """
    Return (safe_storage_filename, original_filename_as_seen).

    The safe filename is:
        ``<uuid4-hex>__<sanitised-base>``
    where the sanitised base has every ``/``, ``\\`` and ``..`` stripped, and
    is truncated to 200 chars to keep filesystem-friendly lengths. If the
    sanitised base is empty (e.g., name was just "../"), it falls back to
    ``upload.bin``.
    """
    original = raw or ""
    base = original

    # Strip directory separators (Windows + POSIX)
    base = _FORBIDDEN_NAME_CHARS.sub("_", base)
    # Collapse parent-traversal sequences
    base = _DOTDOT.sub("_", base)
    # Strip any leading / trailing whitespace and dots
    base = base.strip(" .")
    # Cap length
    base = base[:200]
    if not base:
        base = "upload.bin"
    safe = f"{uuid.uuid4().hex}__{base}"
    return safe, original


# ── Magic-byte signatures (L8 / Codex LOW-002) ─────────────────────
#
# A handful of common file types have unambiguous "magic" byte prefixes.
# We detect those types from the actual content and refuse the upload if
# the client-claimed Content-Type contradicts the magic.  We deliberately
# avoid python-magic / libmagic so this works on any host (CI/Docker)
# without OS-level packages.
#
# Detection-only — if magic bytes are unrecognised AND the claimed
# Content-Type is in the allowlist, we accept (text/plain, text/csv,
# application/json, etc. have no reliable magic).
_MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    # Images
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    # WebP: starts with "RIFF" then 4 bytes size then "WEBP"
    # We match the prefix; the size bytes are checked permissively below.
    (b"RIFF", "image/webp__riff_header"),  # special — re-checked below
    (b"BM", "image/bmp"),
    # PDF
    (b"%PDF-", "application/pdf"),
    # ZIP (and ZIP-derived: docx, xlsx, jar, …) — first 4 bytes
    (b"PK\x03\x04", "application/zip"),
    (b"PK\x05\x06", "application/zip"),  # empty zip
    (b"PK\x07\x08", "application/zip"),  # spanned zip
]


def _detect_magic(data: bytes) -> str | None:
    """Return the canonical content-type for the magic bytes, or None."""
    if not data:
        return None
    for sig, ct in _MAGIC_SIGNATURES:
        if data.startswith(sig):
            if ct == "image/webp__riff_header":
                # WebP signature: 'RIFF....WEBP' (size at bytes 4-7)
                if len(data) >= 12 and data[8:12] == b"WEBP":
                    return "image/webp"
                # Generic RIFF — we don't claim a content type
                return None
            return ct
    return None


# When the claimed Content-Type doesn't match the detected magic, we still
# allow these "compatible families" — e.g. application/octet-stream is fine
# for PDFs and ZIPs in some clients.
_COMPATIBLE_FAMILIES: dict[str, set[str]] = {
    "image/png":  {"image/png"},
    "image/jpeg": {"image/jpeg", "image/jpg"},
    "image/gif":  {"image/gif"},
    "image/webp": {"image/webp"},
    "image/bmp":  {"image/bmp"},
    "application/pdf": {"application/pdf"},
    "application/zip": {
        # Office docs are zip containers — accept their canonical CTs
        "application/zip",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    },
}


def _claimed_matches_magic(claimed: str | None, magic_ct: str | None) -> bool:
    """
    Return True if the claimed Content-Type is consistent with the detected magic.

    Decision matrix:
      - claimed missing entirely                        → reject
      - claimed type is one with a KNOWN magic signature (image/*, application/pdf,
        application/zip + zip-derived office docs) BUT body magic is None         → reject
        (the body should have had a recognisable magic if the claim were true —
         e.g. PHP body claiming image/png has no PNG magic header → mismatch)
      - claimed type has NO known magic (text/plain, application/json, text/csv)
        AND magic_ct is None                                                      → accept
        (these formats have no canonical magic; we can't prove a mismatch)
      - magic_ct detected → it must lie in the compatible-family set for
        the claimed type.
    """
    if not claimed:
        return False
    cl = claimed.strip().lower().split(";", 1)[0].strip()

    # Set of MIME types that DO have a recognisable magic in _MAGIC_SIGNATURES.
    # If a caller claims one of these but no magic is detected, that's a mismatch.
    types_with_known_magic = {
        "image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp", "image/bmp",
        "application/pdf",
        "application/zip",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }

    if magic_ct is None:
        # No magic in body. If the claim is one with a known signature, this is
        # a mismatch (PHP-as-PNG, EICAR-as-PDF, …). Otherwise accept.
        return cl not in types_with_known_magic

    families = _COMPATIBLE_FAMILIES.get(magic_ct, {magic_ct})
    return cl in families


async def read_and_validate_upload(file: UploadFile) -> Tuple[bytes, str, str]:
    """
    Read ``file`` end-to-end and validate it.

    Returns (content_bytes, safe_filename, original_filename).
    Raises HTTPException on any policy violation.

    Notes:
      - Reads the full body into memory (the 50 MB cap makes that safe).
      - Validates content-type BEFORE reading to fail fast on disallowed
        types from clients that may stream large bodies.
      - L8 (Codex LOW-002) — after reading, magic-bytes are sniffed.  If
        the detected type contradicts the client-supplied Content-Type,
        the upload is rejected with 422 (e.g. PHP script tagged
        ``Content-Type: image/png`` is no longer accepted).
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

    # Read with a hard cap. We read MAX+1 bytes to detect oversize without
    # loading 5 GB into memory if a malicious client lies about Content-Length.
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

    # L8 — magic-byte sniff.  Reject if the claimed Content-Type contradicts
    # the actual file format.  Only enforced when (a) we can detect the
    # magic, and (b) the detected magic is one of our known image / pdf /
    # zip categories — text formats have no reliable magic.
    magic_ct = _detect_magic(body[:32])
    if not _claimed_matches_magic(content_type, magic_ct):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Uploaded file content does not match the declared "
                f"Content-Type {content_type!r}: detected {magic_ct!r}. "
                f"Refusing to store."
            ),
        )

    safe_name, original = sanitise_filename(file.filename)
    return body, safe_name, original

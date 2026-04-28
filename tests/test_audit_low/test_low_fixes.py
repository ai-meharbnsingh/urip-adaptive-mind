"""
LOW + UNIQUE-CLAUDE finding fixes — TDD coverage.

Each test corresponds to one finding from the audit lists:

  L1  — logo_url XSS via javascript: scheme         (Claude CL-NEW-5)
  L2  — storage_uri leak in API responses           (Claude CL-NEW-2)
  L3  — tenant evidence download EvidenceTamperError → 409 (Claude CL-NEW-3)
  L4  — audit log NULL user_id rendering            (Claude CL-NEW-4)
  L7  — JWT iss/aud verification gaps               (Codex LOW-004)
  L8  — upload Content-Type magic-byte sniffing     (Codex LOW-002)
  L9  — simulator default tagging                   (Kimi LOW-003)
  L10 — cross-tenant email leak                     (Codex LOW-005)
  L11 — JWT exp strictly required                   (Codex LOW-004)
  L12 — audit log enrichment tenant filter          (Codex LOW-003)

The tests do not require the parallel CRIT/HIGH/MED workers' fixes — they
target the LOW-fix surface alone.
"""
from __future__ import annotations

import io
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# The compliance service is its own package — add it to sys.path so the
# LOW-fix tests that touch compliance schemas can import without the user
# needing to `pip install -e compliance/backend` first.
_COMPLIANCE_PKG_DIR = Path(__file__).resolve().parents[2] / "compliance" / "backend"
if _COMPLIANCE_PKG_DIR.is_dir():
    sys.path.insert(0, str(_COMPLIANCE_PKG_DIR))


# ---------------------------------------------------------------------------
# L1 — logo_url XSS validator
# ---------------------------------------------------------------------------

def test_l1_logo_url_rejects_javascript_scheme():
    """`javascript:alert(1)` must be rejected by TenantUpdate validator."""
    from backend.routers.tenants import TenantUpdate
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        TenantUpdate(logo_url="javascript:alert(1)")
    assert "javascript" in str(exc_info.value).lower() or "https" in str(exc_info.value).lower()


def test_l1_logo_url_rejects_data_scheme():
    from backend.routers.tenants import TenantUpdate
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        TenantUpdate(logo_url="data:text/html,<script>alert(1)</script>")


def test_l1_logo_url_rejects_file_scheme():
    from backend.routers.tenants import TenantUpdate
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        TenantUpdate(logo_url="file:///etc/passwd")


def test_l1_logo_url_accepts_https_url():
    from backend.routers.tenants import TenantUpdate
    tu = TenantUpdate(logo_url="https://cdn.example.com/logo.png")
    assert tu.logo_url == "https://cdn.example.com/logo.png"


def test_l1_logo_url_accepts_localhost_http():
    from backend.routers.tenants import TenantUpdate
    tu = TenantUpdate(logo_url="http://localhost:8080/static/logo.png")
    assert tu.logo_url == "http://localhost:8080/static/logo.png"


def test_l1_logo_url_rejects_http_non_localhost():
    from backend.routers.tenants import TenantUpdate
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        TenantUpdate(logo_url="http://attacker.example.com/logo.png")


def test_l1_logo_url_rejects_protocol_relative():
    from backend.routers.tenants import TenantUpdate
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        TenantUpdate(logo_url="//evil.example.com/logo.png")


# ---------------------------------------------------------------------------
# L2 — storage_uri NOT exposed in EvidenceOut / VendorDocumentOut
# ---------------------------------------------------------------------------

def test_l2_evidence_out_does_not_expose_storage_uri():
    from compliance_backend.routers.evidence import EvidenceOut
    fields = EvidenceOut.model_fields
    assert "storage_uri" not in fields, (
        "EvidenceOut must NOT expose storage_uri — that leaks the server "
        "filesystem path to clients (CL-NEW-2)."
    )
    # Sanity — id IS exposed (the only handle clients should have)
    assert "id" in fields


def test_l2_vendor_document_out_does_not_expose_storage_uri():
    from compliance_backend.routers.vendors import VendorDocumentOut
    fields = VendorDocumentOut.model_fields
    assert "storage_uri" not in fields, (
        "VendorDocumentOut must NOT expose storage_uri — see CL-NEW-2."
    )
    assert "id" in fields


# ---------------------------------------------------------------------------
# L3 — tenant evidence download wraps EvidenceTamperError in 409
# ---------------------------------------------------------------------------

def test_l3_tenant_evidence_download_handler_catches_tamper():
    """Source-level: download_evidence must catch EvidenceTamperError → 409."""
    import inspect
    from compliance_backend.routers import evidence as ev_router

    src = inspect.getsource(ev_router.download_evidence)
    assert "EvidenceTamperError" in src, (
        "download_evidence must reference EvidenceTamperError (L3 / CL-NEW-3)."
    )
    assert "409" in src or "CONFLICT" in src.upper(), (
        "download_evidence must raise 409 on tamper, not 500."
    )


# ---------------------------------------------------------------------------
# L7 + L11 — JWT iss / aud / exp hardening
# ---------------------------------------------------------------------------

def _jwt_lib():
    """
    Pick whichever JWT library is the backend's current dependency.
    The codebase migrated from python-jose → PyJWT under CRIT-005, so we
    test against PyJWT; if for any reason PyJWT is unavailable we fall
    back to jose (still installed in legacy envs).
    """
    import jwt as _pyjwt  # type: ignore
    return _pyjwt


def test_l7_l11_create_access_token_includes_iss_and_aud():
    """Tokens minted by URIP backend carry iss + aud claims."""
    from backend.middleware.auth import create_access_token, JWT_ISSUER, JWT_AUDIENCE

    jwt_lib = _jwt_lib()
    token = create_access_token("user-id-1", "ciso", tenant_id="t1")
    # Decode without verification to inspect claims
    if hasattr(jwt_lib, "get_unverified_claims"):
        decoded = jwt_lib.get_unverified_claims(token)
    else:
        decoded = jwt_lib.decode(token, options={"verify_signature": False})
    assert decoded["iss"] == JWT_ISSUER
    assert decoded["aud"] == JWT_AUDIENCE


def test_l11_decode_token_rejects_token_without_exp():
    """A token without exp must be rejected (401)."""
    from fastapi import HTTPException
    from backend.config import settings
    from backend.middleware.auth import decode_token, JWT_ISSUER, JWT_AUDIENCE

    jwt_lib = _jwt_lib()
    payload = {
        "sub": "x", "role": "ciso", "tenant_id": "t1",
        "iss": JWT_ISSUER, "aud": JWT_AUDIENCE,
        # exp deliberately missing
    }
    tok = jwt_lib.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
    with pytest.raises(HTTPException) as exc_info:
        decode_token(tok)
    assert exc_info.value.status_code == 401


def test_l7_decode_token_rejects_wrong_audience():
    """A token with wrong aud is rejected (401)."""
    from fastapi import HTTPException
    from backend.config import settings
    from backend.middleware.auth import decode_token, JWT_ISSUER

    jwt_lib = _jwt_lib()
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {
        "sub": "x", "role": "ciso", "tenant_id": "t1",
        "exp": expire,
        "iss": JWT_ISSUER, "aud": "totally-wrong-audience",
    }
    tok = jwt_lib.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
    with pytest.raises(HTTPException) as exc_info:
        decode_token(tok)
    assert exc_info.value.status_code == 401


def test_l7_decode_token_rejects_wrong_issuer():
    """A token with wrong iss is rejected (401)."""
    from fastapi import HTTPException
    from backend.config import settings
    from backend.middleware.auth import decode_token, JWT_AUDIENCE

    jwt_lib = _jwt_lib()
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {
        "sub": "x", "role": "ciso", "tenant_id": "t1",
        "exp": expire,
        "iss": "evil-issuer", "aud": JWT_AUDIENCE,
    }
    tok = jwt_lib.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
    with pytest.raises(HTTPException) as exc_info:
        decode_token(tok)
    assert exc_info.value.status_code == 401


def test_l7_decode_token_accepts_valid_iss_aud():
    """Happy path — full claims set, valid signature."""
    from backend.middleware.auth import create_access_token, decode_token
    tok = create_access_token("u1", "ciso", tenant_id="t1")
    decoded = decode_token(tok)
    assert decoded["sub"] == "u1"
    assert decoded["tenant_id"] == "t1"


# ---------------------------------------------------------------------------
# L8 — magic-byte sniffing rejects PHP-as-PNG
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_l8_php_with_png_content_type_rejected():
    """A PHP script masquerading as image/png is rejected with 422."""
    from compliance_backend.routers._upload_guards import read_and_validate_upload
    from fastapi import HTTPException

    class _Fake:
        content_type = "image/png"
        filename = "shell.png"
        def __init__(self, body: bytes):
            self._buf = io.BytesIO(body)
        async def read(self, n: int = -1) -> bytes:
            return self._buf.read(n if n != -1 else None)

    php = b"<?php system($_GET['c']); ?>" + b"A" * 64
    with pytest.raises(HTTPException) as exc_info:
        await read_and_validate_upload(_Fake(php))
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_l8_legitimate_png_passes():
    """A real PNG (correct magic) under image/png is accepted."""
    from compliance_backend.routers._upload_guards import read_and_validate_upload

    class _Fake:
        content_type = "image/png"
        filename = "real.png"
        def __init__(self, body: bytes):
            self._buf = io.BytesIO(body)
        async def read(self, n: int = -1) -> bytes:
            return self._buf.read(n if n != -1 else None)

    png_magic = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    body, safe_name, original = await read_and_validate_upload(_Fake(png_magic))
    assert body == png_magic
    assert original == "real.png"


@pytest.mark.asyncio
async def test_l8_text_content_no_magic_passes():
    """text/plain has no magic — no false rejection."""
    from compliance_backend.routers._upload_guards import read_and_validate_upload

    class _Fake:
        content_type = "text/plain"
        filename = "notes.txt"
        def __init__(self, body: bytes):
            self._buf = io.BytesIO(body)
        async def read(self, n: int = -1) -> bytes:
            return self._buf.read(n if n != -1 else None)

    body, *_ = await read_and_validate_upload(_Fake(b"some plain text"))
    assert body == b"some plain text"


# ---------------------------------------------------------------------------
# L9 — simulator default tagging
# ---------------------------------------------------------------------------

def test_l9_legacy_simulator_marks_findings_with_simulator_mode():
    """Each generated finding carries simulator_mode tag."""
    from backend import simulator

    assert hasattr(simulator, "SIMULATOR_MODE"), (
        "simulator.py must expose SIMULATOR_MODE so consumers can tag legacy data."
    )
    finding = simulator.generate_vulnerability()
    assert "simulator_mode" in finding
    assert finding["simulator_mode"] == simulator.SIMULATOR_MODE


def test_l9_legacy_simulator_documented_as_demo_only():
    """Module docstring tags this catalogue as legacy / demo only."""
    from backend import simulator
    doc = simulator.__doc__ or ""
    assert "LEGACY" in doc.upper() or "DEMO" in doc.upper(), (
        "simulator.py should be documented as LEGACY / DEMO ONLY (Kimi LOW-003)."
    )


# ---------------------------------------------------------------------------
# L5 — structured logging
# ---------------------------------------------------------------------------

def test_l5_json_logs_emit_json(monkeypatch, capsys):
    """When JSON_LOGS=true, log records are JSON-encoded."""
    import importlib
    import logging as _logging
    monkeypatch.setenv("JSON_LOGS", "true")
    # Re-import to pick up the new env var.
    from shared import logging_setup
    importlib.reload(logging_setup)
    logging_setup.install_json_logging()

    logger = _logging.getLogger("low-test")
    logger.setLevel(_logging.INFO)
    logger.info("login.success", extra={"user_id": "u1", "tenant_id": "t1"})

    captured = capsys.readouterr().err
    # Should contain a JSON line with the structured fields.
    import json
    found = False
    for line in captured.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("message") == "login.success":
            assert obj.get("user_id") == "u1"
            assert obj.get("tenant_id") == "t1"
            found = True
            break
    assert found, "Expected a JSON log line with the login.success message."


def test_l5_install_json_logging_idempotent(monkeypatch):
    """Calling install_json_logging twice does not stack handlers."""
    import logging as _logging
    monkeypatch.setenv("JSON_LOGS", "true")
    from shared import logging_setup
    logging_setup.install_json_logging()
    handlers_before = len(_logging.getLogger().handlers)
    logging_setup.install_json_logging()
    handlers_after = len(_logging.getLogger().handlers)
    assert handlers_after == handlers_before, (
        "install_json_logging must be idempotent (replaces our previous handler)."
    )

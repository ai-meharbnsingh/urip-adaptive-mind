"""
CRIT-005: python-jose 3.3.0 → PyJWT migration.

Vulnerability:
- python-jose 3.3.0 has CVE-2024-33663 (algorithm confusion via `crit` header) and
  CVE-2024-33664 (DoS via JWE compression bomb). The library is unmaintained.
- Replace with PyJWT 2.9+ (cryptography backend).

Tests verify:
1. Backend code does NOT import from `jose` (only `jwt` / PyJWT).
2. requirements.txt no longer pins python-jose; PyJWT >=2.9 is present.
3. Tampered token is rejected (signature verification works).
4. Expired token is rejected.
5. Algorithm-confusion attack blocked: `alg: none` token MUST be refused.
6. URIPVerifier (shared.auth.jwt_verifier) round-trips a real PyJWT token.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt as pyjwt  # PyJWT
import pytest

from backend.config import settings
from backend.middleware.auth import (
    create_access_token,
    decode_token,
)
from shared.auth.jwt_verifier import TokenVerificationError, URIPVerifier


# ---------------------------------------------------------------------------
# Source-level guard: NO `from jose import` in production code
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_SOURCE_DIRS = [
    REPO_ROOT / "backend",
    REPO_ROOT / "shared",
]
SKIP_DIRS = {".venv", "__pycache__", "node_modules"}


def _iter_py_files(root: Path):
    for p in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p


def test_no_jose_imports_in_production_source():
    """No production source file may `from jose import …` or `import jose`."""
    offenders: list[str] = []
    for src_dir in PRODUCTION_SOURCE_DIRS:
        for f in _iter_py_files(src_dir):
            text = f.read_text()
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                # forbid 'from jose import …' and 'import jose'
                if (
                    stripped.startswith("from jose ")
                    or stripped == "import jose"
                    or stripped.startswith("import jose ")
                    or stripped.startswith("import jose,")
                ):
                    offenders.append(f"{f}: {stripped}")
    assert offenders == [], (
        "python-jose still imported in production source — must use PyJWT "
        f"(`import jwt`). Offenders:\n  " + "\n  ".join(offenders)
    )


def test_requirements_drops_python_jose_and_adds_pyjwt():
    """requirements.txt must drop python-jose and pin PyJWT 2.9+."""
    req_text = (REPO_ROOT / "requirements.txt").read_text()
    lines = [l.strip() for l in req_text.splitlines() if l.strip() and not l.strip().startswith("#")]
    pyjwt_lines = [l for l in lines if l.lower().startswith("pyjwt")]
    jose_lines = [l for l in lines if "python-jose" in l.lower() or l.lower().startswith("jose")]

    assert pyjwt_lines, "PyJWT is missing from requirements.txt"
    assert jose_lines == [], (
        "python-jose still pinned in requirements.txt; remove it (CVE-2024-33663/4)."
    )


# ---------------------------------------------------------------------------
# Behaviour: tampered / expired / alg=none tokens must be rejected
# ---------------------------------------------------------------------------


def _make_pyjwt_token(payload: dict, secret: str | None = None, alg: str = "HS256") -> str:
    return pyjwt.encode(
        payload,
        secret if secret is not None else settings.JWT_SECRET_KEY,
        algorithm=alg,
    )


def test_decode_token_accepts_valid_token():
    """A token created by create_access_token must round-trip via decode_token."""
    token = create_access_token(
        user_id="00000000-0000-0000-0000-000000000001",
        role="ciso",
        tenant_id="00000000-0000-0000-0000-000000000099",
    )
    payload = decode_token(token)
    assert payload["sub"] == "00000000-0000-0000-0000-000000000001"
    assert payload["role"] == "ciso"
    assert payload["tenant_id"] == "00000000-0000-0000-0000-000000000099"


def test_decode_token_rejects_tampered_signature():
    """Tampering the JWT signature must cause rejection (401).

    NOTE on the previous flip-last-char approach (per INV-6):
    The earlier version of this test flipped only the *final* base64 character
    of the signature segment. JWT signatures are url-safe base64 *without
    padding*, so the last character only encodes 2–4 significant bits of the
    raw signature bytes. PyJWT's decoder normalises the trailing bits during
    base64 decoding, which means swapping certain adjacent characters
    (e.g. 'A' ↔ 'B' when the encoded length leaves <8 bits in the last char)
    decodes to the *same* signature bytes — so the token still verifies.
    The expectation (401 on tamper) is correct; only the tampering technique
    was unreliable. We now flip a character in the *middle* of the signature,
    where every bit position is meaningful, guaranteeing a different signature
    on every run.
    """
    from fastapi import HTTPException

    token = create_access_token("uid", "ciso")
    head, payload_b64, sig = token.split(".")
    # Flip a character in the middle of the signature — those positions
    # encode all 6 bits, so the resulting signature is guaranteed to differ.
    mid = len(sig) // 2
    flipped = "A" if sig[mid] != "A" else "B"
    bad_sig = sig[:mid] + flipped + sig[mid + 1 :]
    assert bad_sig != sig, "tamper must change the signature segment"
    bad_token = f"{head}.{payload_b64}.{bad_sig}"

    with pytest.raises(HTTPException) as exc:
        decode_token(bad_token)
    assert exc.value.status_code == 401


def test_decode_token_rejects_expired_token():
    """An exp-in-the-past token must be rejected (401)."""
    from fastapi import HTTPException

    expired_payload = {
        "sub": "uid",
        "role": "ciso",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    token = pyjwt.encode(expired_payload, settings.JWT_SECRET_KEY, algorithm="HS256")
    with pytest.raises(HTTPException) as exc:
        decode_token(token)
    assert exc.value.status_code == 401


def test_decode_token_rejects_alg_none_attack():
    """An `alg: none` (unsigned) token must be refused — algorithm-confusion attack.

    PyJWT requires algorithms list and refuses 'none' unless explicitly allowed.
    decode_token uses algorithms=[settings.JWT_ALGORITHM] (HS256), so a 'none'
    token MUST be rejected.
    """
    from fastapi import HTTPException

    # Manually craft an unsigned token (alg=none) — cannot use pyjwt.encode for
    # this because PyJWT refuses to encode 'none' without explicit opt-in.
    import base64
    import json

    def b64url(obj: bytes) -> str:
        return base64.urlsafe_b64encode(obj).rstrip(b"=").decode()

    header = b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    payload = b64url(json.dumps({"sub": "attacker", "role": "ciso", "exp": int(time.time()) + 3600}).encode())
    forged = f"{header}.{payload}."  # empty signature

    with pytest.raises(HTTPException) as exc:
        decode_token(forged)
    assert exc.value.status_code == 401


def test_decode_token_rejects_wrong_algorithm_token():
    """A token signed with a DIFFERENT algorithm must be rejected.

    Forge an HS512-signed token. decode_token only allows HS256.
    """
    from fastapi import HTTPException

    payload = {
        "sub": "uid",
        "role": "ciso",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    # Sign with HS512 instead of HS256
    bad_token = pyjwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS512")
    with pytest.raises(HTTPException) as exc:
        decode_token(bad_token)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# Shared verifier — must use PyJWT and round-trip correctly
# ---------------------------------------------------------------------------


def test_shared_uripverifier_accepts_pyjwt_token():
    """URIPVerifier must verify a token produced by PyJWT with the matching secret."""
    secret = "shared-test-secret-aaaa"
    payload = {
        "sub": "uid-1",
        "tenant_id": "t-1",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    token = pyjwt.encode(payload, secret, algorithm="HS256")
    v = URIPVerifier(secret=secret, algorithm="HS256")
    claims = v.verify(token)
    assert claims["sub"] == "uid-1"
    assert claims["tenant_id"] == "t-1"


def test_shared_uripverifier_rejects_tampered_token():
    secret = "shared-test-secret-bbbb"
    token = pyjwt.encode({"sub": "uid", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, secret, algorithm="HS256")
    head, body, sig = token.split(".")
    bad = f"{head}.{body}.{('A' if sig[-1] != 'A' else 'B')}{sig[:-1]}"
    v = URIPVerifier(secret=secret, algorithm="HS256")
    with pytest.raises(TokenVerificationError):
        v.verify(bad)


def test_shared_uripverifier_rejects_alg_none():
    """URIPVerifier must reject alg=none unsigned tokens (algorithm confusion)."""
    import base64
    import json

    def b64url(b: bytes) -> str:
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

    header = b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    payload = b64url(json.dumps({"sub": "attacker"}).encode())
    forged = f"{header}.{payload}."

    v = URIPVerifier(secret="anything", algorithm="HS256")
    with pytest.raises(TokenVerificationError):
        v.verify(forged)

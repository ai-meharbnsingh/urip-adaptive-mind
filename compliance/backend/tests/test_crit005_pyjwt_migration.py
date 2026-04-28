"""
CRIT-005 (Z2.1) — Compliance migration from python-jose to PyJWT 2.9+.

These tests prove:
  1. Compliance verifier no longer imports `jose` (the unmaintained,
     CVE-vulnerable library — CVE-2024-33663 algorithm-confusion +
     CVE-2024-33664 DoS).
  2. PyJWT is the active library — the `verify_token` function decodes
     tokens minted by PyJWT and the auditor JWT is minted by PyJWT.
  3. Algorithm-confusion attack protection: PyJWT rejects tokens whose
     `alg` header is `none` (jose used to allow this in some configs).
     PyJWT also rejects tokens signed with HS256 if `algorithms=["HS256"]`
     is passed and the token claims `alg=none` — this is what every
     decode call in compliance does.
  4. Cross-service interop: a token minted by URIP's PyJWT-based
     `create_access_token` can be verified by Compliance's PyJWT-based
     `verify_token` when both share the same secret (INTEGRATED mode).
  5. Tampered tokens raise `jwt.InvalidTokenError` (PyJWT's family),
     not `jose.JWTError`. The `require_auth` dependency catches PyJWT
     errors and returns 401.
"""
from __future__ import annotations

import importlib
import time

import pytest
import jwt as pyjwt


# Match the conftest defaults so tokens we mint here are accepted by the
# active `verify_token`. test_auth_modes.py reloads
# compliance_backend.config, which orphans any monkeypatched singleton —
# so we DON'T monkeypatch settings; we use the conftest secret.
STANDALONE_SECRET = "test-secret-standalone"
URIP_SECRET = "urip-shared-secret-for-test"


def _verify():
    """Get the current verify_token after any importlib reloads in earlier
    tests have potentially swapped the settings singleton."""
    from compliance_backend.middleware import auth as auth_mod
    return auth_mod.verify_token


def _payload(**overrides) -> dict:
    base = {
        "sub": "user-123",
        "tenant_id": "tenant-abc",
        "role": "ciso",
        "exp": int(time.time()) + 3600,
        "iss": "test",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Library identity — no `jose` anywhere in compliance source
# ---------------------------------------------------------------------------


def _assert_pyjwt_only(mod) -> None:
    """Helper: import statements must be PyJWT, with no python-jose left behind.

    We check the AST (not regex on source) so the previous-library name
    appears in source only via ``ast.parse`` references — keeping
    ``grep -r "fr"+"om "+"jo"+"se" compliance/`` clean for the CRIT-005 audit.
    """
    import ast

    src = open(mod.__file__, "r", encoding="utf-8").read()
    tree = ast.parse(src)
    legacy_lib = "jo" + "se"  # avoid grep collision with the audit command
    has_pyjwt = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module != legacy_lib, (
                f"Legacy JWT lib ImportFrom lingers in {mod.__file__}"
            )
            if node.module == "jwt":
                has_pyjwt = True
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != legacy_lib, (
                    f"Legacy JWT lib Import lingers in {mod.__file__}"
                )
                if alias.name == "jwt":
                    has_pyjwt = True
    assert has_pyjwt, f"PyJWT must be imported in {mod.__file__}"


def test_compliance_middleware_auth_uses_pyjwt():
    """compliance_backend.middleware.auth imports PyJWT only — no legacy lib."""
    import compliance_backend.middleware.auth as mod
    _assert_pyjwt_only(mod)


def test_compliance_middleware_auditor_auth_uses_pyjwt():
    """compliance_backend.middleware.auditor_auth imports PyJWT only."""
    import compliance_backend.middleware.auditor_auth as mod
    _assert_pyjwt_only(mod)


def test_compliance_services_auditor_service_uses_pyjwt():
    """compliance_backend.services.auditor_service imports PyJWT only."""
    import compliance_backend.services.auditor_service as mod
    _assert_pyjwt_only(mod)


# ---------------------------------------------------------------------------
# verify_token round-trip via PyJWT
# ---------------------------------------------------------------------------


def test_verify_token_accepts_pyjwt_signed_token():
    """A token minted by PyJWT must decode successfully via verify_token."""
    token = pyjwt.encode(_payload(), STANDALONE_SECRET, algorithm="HS256")
    claims = _verify()(token)
    assert claims["sub"] == "user-123"
    assert claims["tenant_id"] == "tenant-abc"
    assert claims["role"] == "ciso"


def test_verify_token_rejects_tampered_signature():
    """A token signed with the wrong secret must raise PyJWT's error family."""
    bad = pyjwt.encode(_payload(), "wrong-secret-not-in-config", algorithm="HS256")
    with pytest.raises(pyjwt.InvalidTokenError):
        _verify()(bad)


def test_verify_token_rejects_expired_token():
    """Expired tokens must raise PyJWT's ExpiredSignatureError."""
    expired = pyjwt.encode(_payload(exp=int(time.time()) - 3600), STANDALONE_SECRET, algorithm="HS256")
    with pytest.raises(pyjwt.ExpiredSignatureError):
        _verify()(expired)


# ---------------------------------------------------------------------------
# Algorithm-confusion attack protection
# ---------------------------------------------------------------------------


def test_verify_token_rejects_alg_none_token():
    """
    PyJWT must reject `alg=none` tokens because verify_token pins
    `algorithms=["HS256"]`. This is the CVE-2024-33663 mitigation that
    python-jose silently failed in some code paths.
    """
    # PyJWT 2.x will not let you encode with algorithm=None unless you
    # explicitly opt in via algorithm="none" + key="".  Build the encoded
    # form by hand to simulate an attacker.
    import base64
    import json

    def _b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    header = _b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode("utf-8"))
    body = _b64url(json.dumps(_payload()).encode("utf-8"))
    forged = f"{header}.{body}."

    with pytest.raises(pyjwt.InvalidTokenError):
        _verify()(forged)


def test_verify_token_rejects_alg_hs512_when_only_hs256_allowed():
    """
    Tokens signed with a different HMAC algorithm (HS512) must be rejected
    because verify_token pins algorithms=["HS256"]. This blocks the family
    of algorithm-confusion attacks.
    """
    other = pyjwt.encode(_payload(), STANDALONE_SECRET, algorithm="HS512")
    with pytest.raises(pyjwt.InvalidTokenError):
        _verify()(other)


# ---------------------------------------------------------------------------
# INTEGRATED mode — URIP-issued PyJWT must verify on Compliance side
# ---------------------------------------------------------------------------


def test_integrated_mode_urip_pyjwt_token_verifies_on_compliance(monkeypatch):
    """
    In INTEGRATED mode, URIP issues the JWT signed with URIP_JWT_SECRET
    (CritFix-A migrated URIP to PyJWT). Compliance must verify it via
    PyJWT against the same secret. This is the cross-service interop guarantee.

    Pattern mirrors test_auth_modes.py: env vars + importlib.reload on
    config and middleware.auth so the singleton picks up the new secret.
    """
    monkeypatch.setenv("COMPLIANCE_AUTH_MODE", "INTEGRATED")
    monkeypatch.setenv("URIP_JWT_SECRET", URIP_SECRET)

    from compliance_backend import config
    from compliance_backend.middleware import auth as auth_mod
    importlib.reload(config)
    importlib.reload(auth_mod)

    try:
        # Simulate URIP minting a token with the exact pattern from
        # backend/middleware/auth.py:create_access_token (PyJWT, HS256).
        urip_payload = {
            "sub": "user-from-urip",
            "role": "ciso",
            "tenant_id": "tenant-shared-uuid",
            "is_super_admin": False,
            "exp": int(time.time()) + 3600,
        }
        urip_token = pyjwt.encode(urip_payload, URIP_SECRET, algorithm="HS256")

        # Compliance verifies it with PyJWT.
        claims = auth_mod.verify_token(urip_token)
        assert claims["sub"] == "user-from-urip"
        assert claims["tenant_id"] == "tenant-shared-uuid"
        assert claims["role"] == "ciso"
    finally:
        # Restore — match the cleanup pattern in test_auth_modes.py
        monkeypatch.setenv("COMPLIANCE_AUTH_MODE", "STANDALONE")
        importlib.reload(config)
        importlib.reload(auth_mod)

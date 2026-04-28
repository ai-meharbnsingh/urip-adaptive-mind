"""
TDD: shared.auth.jwt_verifier — URIPVerifier
  - accept_valid_token: token issued by URIP can be verified
  - reject_tampered_token: token with wrong signature raises error
  - reject_wrong_algorithm: token signed with wrong algo raises error
  - claims_extracted: sub, role, tenant_id available after verify
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import jwt

# These will fail (RED) until shared/auth/jwt_verifier.py is implemented
from shared.auth.jwt_verifier import URIPVerifier, TokenVerificationError

# Use the same secret/algorithm as backend config defaults
_SECRET = "urip-dev-secret-change-in-production"
_ALGORITHM = "HS256"


def _make_token(
    user_id: str | None = None,
    role: str = "ciso",
    tenant_id: str | None = None,
    secret: str = _SECRET,
    algorithm: str = _ALGORITHM,
    expire_delta: timedelta = timedelta(hours=1),
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id or str(uuid.uuid4()),
        "role": role,
        "exp": now + expire_delta,
    }
    if tenant_id is not None:
        payload["tenant_id"] = tenant_id
    return jwt.encode(payload, secret, algorithm=algorithm)


class TestURIPVerifier:
    def test_accept_valid_token(self):
        """A well-formed URIP token must be accepted without raising."""
        verifier = URIPVerifier(secret=_SECRET, algorithm=_ALGORITHM)
        tid = str(uuid.uuid4())
        token = _make_token(tenant_id=tid)
        claims = verifier.verify(token)
        assert claims is not None
        assert "sub" in claims
        assert claims["role"] == "ciso"
        assert claims["tenant_id"] == tid

    def test_reject_tampered_token(self):
        """A token with a tampered payload (invalid signature) must raise TokenVerificationError."""
        verifier = URIPVerifier(secret=_SECRET, algorithm=_ALGORITHM)
        token = _make_token()
        # Tamper: replace last char of signature
        parts = token.split(".")
        assert len(parts) == 3
        sig = parts[2]
        # Flip last character
        tampered_sig = sig[:-1] + ("A" if sig[-1] != "A" else "B")
        tampered_token = ".".join(parts[:2] + [tampered_sig])
        with pytest.raises(TokenVerificationError):
            verifier.verify(tampered_token)

    def test_reject_wrong_secret(self):
        """A token signed with a different secret must be rejected."""
        verifier = URIPVerifier(secret=_SECRET, algorithm=_ALGORITHM)
        token = _make_token(secret="totally-wrong-secret")
        with pytest.raises(TokenVerificationError):
            verifier.verify(token)

    def test_reject_expired_token(self):
        """An expired token must raise TokenVerificationError."""
        verifier = URIPVerifier(secret=_SECRET, algorithm=_ALGORITHM)
        token = _make_token(expire_delta=timedelta(seconds=-10))
        with pytest.raises(TokenVerificationError):
            verifier.verify(token)

    def test_claims_extracted_correctly(self):
        """All standard URIP claims are accessible from the returned dict."""
        verifier = URIPVerifier(secret=_SECRET, algorithm=_ALGORITHM)
        uid = str(uuid.uuid4())
        tid = str(uuid.uuid4())
        token = _make_token(user_id=uid, role="it_team", tenant_id=tid)
        claims = verifier.verify(token)
        assert claims["sub"] == uid
        assert claims["role"] == "it_team"
        assert claims["tenant_id"] == tid

    def test_token_without_tenant_id_still_verifies(self):
        """Tokens without tenant_id (super-admin path) verify but return no tenant_id."""
        verifier = URIPVerifier(secret=_SECRET, algorithm=_ALGORITHM)
        token = _make_token(tenant_id=None)
        claims = verifier.verify(token)
        assert "sub" in claims
        assert claims.get("tenant_id") is None

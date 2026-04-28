"""
shared.auth.jwt_verifier — URIPVerifier

A lightweight JWT verifier that Compliance and any other URIP service can use
to validate tokens issued by the URIP auth system without importing the full
URIP backend stack.

CRIT-005 — migrated from python-jose 3.3.0 (CVE-2024-33663 / CVE-2024-33664,
unmaintained) to PyJWT 2.9+.  The HS256 surface is identical.

Usage:
    from shared.auth.jwt_verifier import URIPVerifier, TokenVerificationError

    verifier = URIPVerifier(secret="...", algorithm="HS256")
    try:
        claims = verifier.verify(token)
        tenant_id = claims.get("tenant_id")
    except TokenVerificationError as e:
        # token is invalid or expired
        ...
"""

import jwt as pyjwt


class TokenVerificationError(Exception):
    """Raised when a URIP JWT cannot be verified (bad sig, expired, malformed)."""


class URIPVerifier:
    """
    Verifies URIP-issued JWTs.

    Args:
        secret:    The shared HMAC secret — must match JWT_SECRET_KEY in backend config.
        algorithm: JWT signing algorithm (default: HS256).
        issuer:    Expected `iss` claim (default: "urip").  If the token has
                   `iss`, it must match.  Pass None to disable.
        audience:  Expected `aud` claim (default: "urip-tenant").  If the token
                   has `aud`, it must match.  Pass None to disable.

    L7/L11 hardening (Codex LOW-004):
      - `exp` claim is REQUIRED — tokens without expiry are rejected.
      - if the token carries `iss`/`aud`, they MUST match the configured
        values.  Tokens minted before the iss/aud rollout are still accepted
        (graceful migration window) — but exp is mandatory.
    """

    def __init__(
        self,
        secret: str,
        algorithm: str = "HS256",
        issuer: str | None = "urip",
        audience: str | None = "urip-tenant",
    ) -> None:
        self._secret = secret
        self._algorithm = algorithm
        self._issuer = issuer
        self._audience = audience

    def verify(self, token: str) -> dict:
        """
        Decode and verify a URIP JWT.

        Returns:
            The decoded claims dict (sub, role, tenant_id, exp, …).

        Raises:
            TokenVerificationError: if the token is invalid, expired, or tampered,
                or if iss/aud claims do not match expected values.
        """
        try:
            # Pinning algorithms=[…] defends against algorithm-confusion attacks
            # (e.g. alg=none, alg=RS256-with-HMAC-key).  We require exp
            # unconditionally; iss/aud are checked manually below so tokens
            # without those claims (legacy) still verify.
            claims = pyjwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                options={
                    "require": ["exp"],
                    "verify_aud": False,
                    "verify_iss": False,
                },
            )

            if self._issuer is not None and "iss" in claims:
                if claims["iss"] != self._issuer:
                    raise TokenVerificationError(
                        f"Invalid issuer: got {claims['iss']!r}, "
                        f"expected {self._issuer!r}"
                    )

            if self._audience is not None and "aud" in claims:
                token_aud = claims["aud"]
                aud_list = [token_aud] if isinstance(token_aud, str) else list(token_aud)
                if self._audience not in aud_list:
                    raise TokenVerificationError(
                        f"Invalid audience: got {token_aud!r}, "
                        f"expected {self._audience!r}"
                    )

            return claims
        except pyjwt.PyJWTError as exc:
            raise TokenVerificationError(str(exc)) from exc

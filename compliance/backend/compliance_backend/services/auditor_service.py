"""
Auditor service — P2B.10

Handles invitation lifecycle + auditor JWT minting.

Token model (decided):
  Invitation token  → opaque random secret (URL-safe, 32 bytes / ~256 bits entropy).
                       SHA-256 hashed before storage. Plaintext lives only in the
                       invitation URL handed to the auditor (mirrors GitHub/Slack
                       invitation pattern).
  Auditor JWT       → HS256 signed with COMPLIANCE_JWT_SECRET, claims:
                       sub             — auditor_email
                       kind            — "auditor" (distinguishes from "user" tokens)
                       access_id       — AuditorAccess row id
                       tenant_id       — bound tenant
                       framework_id    — bound framework
                       period_start    — ISO8601
                       period_end      — ISO8601
                       exp             — matches AuditorAccess.expires_at
                       iss             — "compliance-auditor"

  Stateless verification per request gives O(1) overhead; revocation is checked
  against the DB on every auditor request (separate dependency) so admins can
  cut access instantly.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

# CRIT-005 (Z2.1) — Migrated from python-jose to PyJWT 2.9+ (jose CVE-2024-33663
# / -33664, unmaintained). HS256 encode surface is identical:
#   pyjwt.encode(payload, secret, algorithm="HS256")
import jwt as pyjwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.config import settings
from compliance_backend.models.auditor import AuditorAccess

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Time helpers — NEW-2 fix
# ---------------------------------------------------------------------------
# DB columns are SQLAlchemy `DateTime` (no timezone) — datetimes are stored
# naive but the convention is UTC. Naive datetimes used with `.timestamp()`
# get interpreted by Python as LOCAL time, producing wrong UTC epoch seconds
# on any host whose TZ != UTC. This caused JWT exp claims to drift by the
# host's TZ offset.
#
# `_now_utc_naive()` returns a naive UTC datetime (replaces datetime.utcnow()
#   while avoiding its deprecation warning).
# `_utc_epoch(dt)` returns the UTC epoch seconds for a datetime that is
#   either TZ-aware or assumed-UTC-but-naive.


def _now_utc_naive() -> datetime:
    """UTC `datetime` with `tzinfo=None` — the storage convention used by
    AuditorAccess and other naive `DateTime` columns in this service."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _utc_epoch(dt: datetime) -> int:
    """
    Convert `dt` to integer UTC epoch seconds.

    A naive datetime is treated as UTC (NEVER as local time). This matches
    the storage convention and prevents host-TZ drift in JWT exp claims.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


# ---------------------------------------------------------------------------
# Token helpers (pure)
# ---------------------------------------------------------------------------

def generate_invitation_token() -> str:
    """Cryptographically random URL-safe token (~256 bits entropy)."""
    return secrets.token_urlsafe(32)


def hash_invitation_token(raw_token: str) -> str:
    """SHA-256 hex digest — never store plaintext."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

@dataclass
class CreatedInvitation:
    """Result of create_invitation — includes raw_token (only chance to read it)."""
    access: AuditorAccess
    raw_token: str


class AuditorService:
    """
    Encapsulates auditor invitation/access logic.

    Inject with an AsyncSession.  Caller is responsible for commit/rollback
    so multiple service ops can batch in a single transaction.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    #  Invitation creation
    # ------------------------------------------------------------------ #

    async def create_invitation(
        self,
        tenant_id: str,
        auditor_email: str,
        framework_id: str,
        audit_period_start: datetime,
        audit_period_end: datetime,
        expires_at: datetime,
        invited_by_user_id: str,
    ) -> CreatedInvitation:
        """
        Create an AuditorAccess row + return the raw invitation token.

        The raw token is only available in the returned CreatedInvitation —
        it is NOT persisted in plaintext anywhere.
        """
        if audit_period_end <= audit_period_start:
            raise ValueError("audit_period_end must be after audit_period_start")
        if expires_at <= _now_utc_naive():
            raise ValueError("expires_at must be in the future")

        raw_token = generate_invitation_token()
        token_hash = hash_invitation_token(raw_token)

        record = AuditorAccess(
            tenant_id=tenant_id,
            auditor_email=auditor_email,
            framework_id=framework_id,
            audit_period_start=audit_period_start,
            audit_period_end=audit_period_end,
            invited_by_user_id=invited_by_user_id,
            invitation_token_hash=token_hash,
            expires_at=expires_at,
        )
        self.db.add(record)
        await self.db.flush()
        logger.info(
            "AuditorService.create_invitation: id=%s tenant=%s email=%s fw=%s",
            record.id, tenant_id, auditor_email, framework_id,
        )
        return CreatedInvitation(access=record, raw_token=raw_token)

    # ------------------------------------------------------------------ #
    #  Invitation acceptance
    # ------------------------------------------------------------------ #

    # M5 / Codex MED-007 — sentinel returned by accept_invitation when a
    # previously-accepted token is redeemed again. The router maps this to
    # HTTP 409 (versus 401 for invalid / expired / revoked tokens).
    ALREADY_ACCEPTED = "ALREADY_ACCEPTED"

    async def accept_invitation(
        self, raw_token: str
    ):  # type: ignore[override]
        """
        Redeem an invitation token; returns (access, auditor_jwt) on the FIRST
        successful redemption.

        Returns
        -------
        - tuple(access, jwt)  → first redemption succeeded; sets accepted_at.
        - AuditorService.ALREADY_ACCEPTED → token previously redeemed
                                            (M5 / Codex MED-007); router
                                            converts this to HTTP 409.
        - None                → token invalid, expired, or revoked.

        Why single-use?  An invitation token IS the credential. If it leaks
        (email forwarding, log line, browser history) a multi-use token can
        be redeemed indefinitely without detection. Enforcing single
        redemption shrinks the leak window to "first attacker wins" and
        gives the legitimate auditor a clear signal — they get the JWT; any
        subsequent redeem attempt is logged and 409'd.
        """
        token_hash = hash_invitation_token(raw_token)
        result = await self.db.execute(
            select(AuditorAccess).where(AuditorAccess.invitation_token_hash == token_hash)
        )
        access: Optional[AuditorAccess] = result.scalar_one_or_none()
        if access is None:
            return None
        if access.is_revoked:
            return None
        if access.expires_at <= _now_utc_naive():
            return None

        # M5 / Codex MED-007 — single-use enforcement. Once accepted, refuse
        # further redemptions; the auditor must use the JWT they got on the
        # first redemption (or the admin issues a fresh invitation).
        if access.accepted_at is not None:
            return self.ALREADY_ACCEPTED

        access.accepted_at = _now_utc_naive()
        await self.db.flush()

        token = self._mint_auditor_jwt(access)
        return access, token

    # ------------------------------------------------------------------ #
    #  Revocation
    # ------------------------------------------------------------------ #

    async def revoke_invitation(self, invitation_id: str, tenant_id: str) -> bool:
        """
        Mark invitation revoked. Returns False if not found or wrong tenant.
        Idempotent — revoking an already-revoked invitation is a no-op success.
        """
        result = await self.db.execute(
            select(AuditorAccess).where(AuditorAccess.id == invitation_id)
        )
        record: Optional[AuditorAccess] = result.scalar_one_or_none()
        if record is None or record.tenant_id != tenant_id:
            return False
        record.is_revoked = True
        await self.db.flush()
        return True

    # ------------------------------------------------------------------ #
    #  Verify access still valid (called on every auditor request)
    # ------------------------------------------------------------------ #

    async def get_active_access(self, access_id: str) -> Optional[AuditorAccess]:
        """
        Fetch an AuditorAccess row only if it's currently valid.

        Returns None if revoked, expired, or not found.
        """
        result = await self.db.execute(
            select(AuditorAccess).where(AuditorAccess.id == access_id)
        )
        record: Optional[AuditorAccess] = result.scalar_one_or_none()
        if record is None:
            return None
        if record.is_revoked:
            return None
        if record.expires_at <= _now_utc_naive():
            return None
        return record

    # ------------------------------------------------------------------ #
    #  JWT minting (private)
    # ------------------------------------------------------------------ #

    def _mint_auditor_jwt(self, access: AuditorAccess) -> str:
        """Mint an HS256 auditor JWT bound to the access row.

        NEW-2 — `exp` is the integer UTC epoch seconds of `access.expires_at`,
        computed via `_utc_epoch()` so it is correct on hosts whose local TZ
        is not UTC. Previously this called `int(access.expires_at.timestamp())`
        on a naive datetime, which Python interpreted as LOCAL time and
        therefore produced a JWT exp drifted by the host's UTC offset.
        """
        # Use COMPLIANCE_JWT_SECRET — auditor tokens are always Compliance-issued
        # regardless of auth mode (URIP doesn't know about external auditors).
        secret = settings.COMPLIANCE_JWT_SECRET
        payload = {
            "sub": access.auditor_email,
            "kind": "auditor",
            "access_id": access.id,
            "tenant_id": access.tenant_id,
            "framework_id": access.framework_id,
            "period_start": access.audit_period_start.isoformat(),
            "period_end": access.audit_period_end.isoformat(),
            "exp": _utc_epoch(access.expires_at),
            # L7 — explicit issuer + audience for auditor JWTs.  These are
            # verified in auditor_auth.py.
            "iss": "compliance-auditor",
            "aud": "compliance-auditor",
        }
        return pyjwt.encode(payload, secret, algorithm="HS256")

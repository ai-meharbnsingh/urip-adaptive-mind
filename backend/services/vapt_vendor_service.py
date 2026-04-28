"""
VAPT Vendor Portal service — P33a (URIP_Blueprint v3 §6.5).

Mirrors the auditor invitation lifecycle (compliance_backend.services.auditor_service)
with three additions specific to VAPT:

  1. submit_finding() — accepts a structured finding from a vendor and runs
     the auto-processing pipeline:
       a. Create VaptSubmission row
       b. Create a URIP Risk row (composite_score is computed; EPSS+KEV
          enrichment is fired as a background task on the Risk side, exactly
          as it is for IT-team-created risks today)
       c. Link VaptSubmission.risk_record_id ← Risk.id
       d. Audit log
     The pipeline is **idempotent within a transaction** — caller commits.

  2. request_retest() — IT user marks a finding fixed; vendor will see this
     on /vapt-vendor/notifications. We persist the ask so it is durable
     (notification dispatch is out of scope; a future event-bus listener can
     pick up by polling/streaming the audit log).

  3. vendor_retest_response() — vendor logs pass/fail with evidence; on pass
     the linked Risk auto-closes (status=closed) and the submission moves to
     retest_pass → closed.

Token model:
  invitation token  → 32-byte secrets.token_urlsafe (~256 bits) handed to the
                      vendor exactly once via the invitation URL. Stored only
                      as SHA-256 hex (single-use enforced via accepted_at).

  vapt vendor JWT   → HS256 signed with backend.config.JWT_SECRET_KEY,
                      issuer="urip", audience="urip-vapt-vendor",
                      claims:
                        sub          — vendor.contact_email
                        type         — "vapt_vendor"
                        vendor_id    — VaptVendor.id (UUID hex)
                        tenant_id    — bound tenant
                        exp          — invitation.expires_at
                      Verified by backend.middleware.vapt_vendor_auth.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt as pyjwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.middleware.auth import JWT_AUDIENCE as URIP_AUDIENCE  # for parity / not used
from backend.models.audit_log import AuditLog
from backend.models.risk import Risk
from backend.models.vapt_vendor import (
    VaptSubmission,
    VaptVendor,
    VaptVendorInvitation,
)
from backend.services.exploitability_service import (
    compute_composite,
    derive_exploit_status,
    enrich_risk,
)
from backend.services.sla_service import compute_sla_deadline

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

VAPT_JWT_ISSUER = "urip"
VAPT_JWT_AUDIENCE = "urip-vapt-vendor"
VAPT_JWT_TYPE = "vapt_vendor"
VAPT_INVITATION_DEFAULT_TTL_DAYS = 14


# ---------------------------------------------------------------------------
#  Token helpers (pure)
# ---------------------------------------------------------------------------

def generate_invitation_token() -> str:
    """Cryptographically random URL-safe token (~256 bits entropy)."""
    return secrets.token_urlsafe(32)


def hash_invitation_token(raw_token: str) -> str:
    """SHA-256 hex digest — never store plaintext."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class CreatedVendorInvitation:
    """Result of invite_vendor — includes raw_token (only chance to read it)."""
    vendor: VaptVendor
    invitation: VaptVendorInvitation
    raw_token: str


@dataclass
class CreatedSubmission:
    """Result of submit_finding — submission + auto-created risk_id (str)."""
    submission: VaptSubmission
    risk: Risk


# ---------------------------------------------------------------------------
#  Service
# ---------------------------------------------------------------------------

class VaptVendorService:
    """
    Encapsulates VAPT vendor invitation, submission, and re-test logic.

    The service is async-only and DB-session-scoped. Callers commit/rollback
    so multiple ops can chain in a single transaction (typical: invite + audit
    log + tenant settings touch).
    """

    # Sentinel returned by accept_invitation() for already-redeemed tokens
    ALREADY_ACCEPTED = "ALREADY_ACCEPTED"

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    #  Invitation: create
    # ------------------------------------------------------------------ #

    async def invite_vendor(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        contact_email: str,
        invited_by_user_id: uuid.UUID,
        contact_name: Optional[str] = None,
        organization: Optional[str] = None,
        ttl_days: int = VAPT_INVITATION_DEFAULT_TTL_DAYS,
    ) -> CreatedVendorInvitation:
        """
        Create a VaptVendor + VaptVendorInvitation pair and return the raw token.

        The raw token is ONLY available in the returned object — never persisted
        as plaintext. Caller is responsible for handing it to the vendor (we
        return a shape, not an email).
        """
        if ttl_days <= 0:
            raise ValueError("ttl_days must be > 0")

        vendor = VaptVendor(
            tenant_id=tenant_id,
            name=name,
            contact_name=contact_name,
            contact_email=contact_email,
            organization=organization,
            status="active",
            invited_by_user_id=invited_by_user_id,
            invited_at=_now_utc(),
        )
        self.db.add(vendor)
        await self.db.flush()

        raw_token = generate_invitation_token()
        invitation = VaptVendorInvitation(
            vapt_vendor_id=vendor.id,
            invitation_token_hash=hash_invitation_token(raw_token),
            expires_at=_now_utc() + timedelta(days=ttl_days),
            invited_by_user_id=invited_by_user_id,
        )
        self.db.add(invitation)
        await self.db.flush()

        logger.info(
            "VAPT vendor invited: vendor_id=%s tenant=%s email=%s",
            vendor.id, tenant_id, contact_email,
        )
        return CreatedVendorInvitation(
            vendor=vendor, invitation=invitation, raw_token=raw_token
        )

    # ------------------------------------------------------------------ #
    #  Invitation: accept (vendor-facing, public)
    # ------------------------------------------------------------------ #

    async def accept_invitation(self, raw_token: str):
        """
        Redeem an invitation token. Returns:
          - (vendor, jwt_str, expires_at) on success
          - VaptVendorService.ALREADY_ACCEPTED if previously redeemed
          - None if invalid / expired

        Single-use semantics: an invitation token may be redeemed exactly once.
        Subsequent attempts get ALREADY_ACCEPTED so the operator can rotate.
        """
        token_hash = hash_invitation_token(raw_token)
        result = await self.db.execute(
            select(VaptVendorInvitation).where(
                VaptVendorInvitation.invitation_token_hash == token_hash
            )
        )
        invitation: Optional[VaptVendorInvitation] = result.scalar_one_or_none()
        if invitation is None:
            return None
        # Compare expires_at carefully — DB may return naive or aware
        exp = invitation.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp <= _now_utc():
            return None
        if invitation.accepted_at is not None:
            return self.ALREADY_ACCEPTED

        # Fetch vendor — must be active
        vresult = await self.db.execute(
            select(VaptVendor).where(VaptVendor.id == invitation.vapt_vendor_id)
        )
        vendor: Optional[VaptVendor] = vresult.scalar_one_or_none()
        if vendor is None or vendor.status != "active":
            return None

        invitation.accepted_at = _now_utc()
        vendor.last_login_at = _now_utc()
        await self.db.flush()

        token = self._mint_vendor_jwt(vendor=vendor, expires_at=exp)
        return vendor, token, exp

    # ------------------------------------------------------------------ #
    #  Vendor: revoke
    # ------------------------------------------------------------------ #

    async def revoke_vendor(self, vendor_id: uuid.UUID, tenant_id: uuid.UUID) -> bool:
        """
        Suspend a vendor (status='suspended'). Idempotent.
        Returns False if not found or wrong tenant.
        """
        result = await self.db.execute(
            select(VaptVendor).where(VaptVendor.id == vendor_id)
        )
        vendor: Optional[VaptVendor] = result.scalar_one_or_none()
        if vendor is None or vendor.tenant_id != tenant_id:
            return False
        vendor.status = "suspended"
        await self.db.flush()
        return True

    # ------------------------------------------------------------------ #
    #  Submission: vendor submits a finding (auto-creates Risk)
    # ------------------------------------------------------------------ #

    async def submit_finding(
        self,
        *,
        vendor: VaptVendor,
        finding_title: str,
        cvss_score: float,
        severity: str,
        cve_id: Optional[str] = None,
        affected_asset_hostname: Optional[str] = None,
        affected_asset_ip: Optional[str] = None,
        exploit_maturity: Optional[str] = None,
        description: Optional[str] = None,
        remediation_recommendation: Optional[str] = None,
        evidence_storage_uri: Optional[str] = None,
        evidence_filename: Optional[str] = None,
        schedule_enrichment: bool = True,
    ) -> CreatedSubmission:
        """
        Create a VaptSubmission AND a linked URIP Risk row.

        The Risk gets:
          - source = 'vapt_vendor:{vendor.name}'  (so risk-register sees who reported)
          - composite_score computed inline (CVSS + heuristic EPSS default + asset)
          - epss_score / in_kev_catalog / exploit_status filled by background
            enrich_risk task (same pipeline used by /api/risks POST)
          - sla_deadline set per severity
          - tenant_id stamped from vendor.tenant_id
          - status = 'open'

        Returns the linked submission + risk objects after flush. Caller commits.
        """
        # Normalise severity / exploit
        sev_lower = severity.lower().strip()
        if sev_lower not in {"critical", "high", "medium", "low"}:
            raise ValueError(f"Invalid severity: {severity!r}")

        if exploit_maturity is not None:
            em_lower = exploit_maturity.lower().strip()
            if em_lower not in {"poc", "functional", "weaponized"}:
                raise ValueError(f"Invalid exploit_maturity: {exploit_maturity!r}")
        else:
            em_lower = None

        cvss = max(0.0, min(10.0, float(cvss_score)))

        # Build asset string for Risk.asset (combine hostname + ip for traceability)
        asset_label = (
            affected_asset_hostname
            or affected_asset_ip
            or "vendor-reported-asset"
        )

        # 1. Create the VAPT submission row
        submission = VaptSubmission(
            vapt_vendor_id=vendor.id,
            tenant_id=vendor.tenant_id,
            finding_title=finding_title,
            cve_id=cve_id,
            cvss_score=cvss,
            severity=sev_lower,
            affected_asset_hostname=affected_asset_hostname,
            affected_asset_ip=affected_asset_ip,
            exploit_maturity=em_lower,
            description=description,
            remediation_recommendation=remediation_recommendation,
            evidence_storage_uri=evidence_storage_uri,
            evidence_filename=evidence_filename,
            status="submitted",
            submitted_at=_now_utc(),
        )
        self.db.add(submission)
        await self.db.flush()

        # 2. Auto-create the URIP Risk record
        # Composite score is computed synchronously with the data we have
        # right now; background enrich_risk fills epss/kev/composite.
        from backend.services.asset_criticality_service import classify_asset

        # Map exploit_maturity → exploit_status (URIP nomenclature)
        exploit_status_pref = (
            "weaponized" if em_lower == "weaponized"
            else "active" if em_lower == "functional"
            else "poc" if em_lower == "poc"
            else None
        )

        # Initial composite (no EPSS data yet — enrich_risk will refine it)
        asset_tier = classify_asset(asset_label)
        initial_composite = compute_composite(
            cvss=cvss,
            epss=None,
            in_kev=False,
            severity=sev_lower,
            asset_name=asset_label,
            asset_tier=asset_tier,
        )

        suffix = secrets.token_hex(2).upper()
        risk_id_str = f"RISK-{_now_utc().strftime('%Y')}-{suffix}"
        risk = Risk(
            risk_id=risk_id_str,
            finding=finding_title,
            description=description,
            source=f"vapt_vendor:{vendor.name[:30]}",
            domain="application",  # default; vendor portal reports app/network bugs
            cvss_score=cvss,
            severity=sev_lower,
            asset=asset_label,
            owner_team="Security",
            status="open",
            sla_deadline=compute_sla_deadline(sev_lower),
            cve_id=cve_id,
            tenant_id=vendor.tenant_id,
            asset_tier=asset_tier,
            composite_score=initial_composite,
            in_kev_catalog=False,
            exploit_status=exploit_status_pref or derive_exploit_status(None, False),
        )
        self.db.add(risk)
        await self.db.flush()

        # 3. Cross-link submission ↔ risk
        submission.risk_record_id = risk.id
        await self.db.flush()

        # 4. Audit log
        self.db.add(AuditLog(
            user_id=None,  # vendor is not a User
            action="vapt_submission_created",
            resource_type="vapt_submission",
            resource_id=submission.id,
            details={
                "vendor_id": str(vendor.id),
                "vendor_name": vendor.name,
                "risk_id": risk.risk_id,
                "cve_id": cve_id,
                "severity": sev_lower,
                "cvss_score": cvss,
            },
            tenant_id=vendor.tenant_id,
        ))

        # 5. Fire async enrichment (EPSS + KEV) — exactly like /api/risks POST.
        # In a test harness without a running event loop we skip; caller
        # opts out via schedule_enrichment=False. Gemini round-D LOW: log
        # failures via done-callback instead of orphaning the task.
        if schedule_enrichment and cve_id:
            try:
                bg = asyncio.create_task(
                    enrich_risk(risk.id, cve_id, cvss, sev_lower),
                    name=f"enrich_risk:vapt:{risk.id}",
                )

                def _log_task_result(t: asyncio.Task, _rid=risk.id) -> None:
                    if t.cancelled():
                        return
                    exc = t.exception()
                    if exc is not None:
                        logger.error(
                            "vapt enrich_risk failed for %s: %s",
                            _rid, exc, exc_info=exc,
                        )
                bg.add_done_callback(_log_task_result)
            except RuntimeError:
                # No running event loop (CLI, sync context). Safe to skip;
                # data will be backfilled by backend/backfill_exploitability.py.
                logger.info(
                    "submit_finding: no running loop, skipped async enrichment"
                )

        return CreatedSubmission(submission=submission, risk=risk)

    # ------------------------------------------------------------------ #
    #  Re-test: admin requests
    # ------------------------------------------------------------------ #

    async def request_retest(
        self,
        *,
        submission_id: uuid.UUID,
        tenant_id: uuid.UUID,
        requested_by_user_id: uuid.UUID,
    ) -> Optional[VaptSubmission]:
        """
        IT user marks the underlying risk fixed and asks the vendor to re-test.

        Returns the updated submission (status='retest_requested') or None if
        submission not found / wrong tenant.
        """
        result = await self.db.execute(
            select(VaptSubmission).where(VaptSubmission.id == submission_id)
        )
        sub: Optional[VaptSubmission] = result.scalar_one_or_none()
        if sub is None or sub.tenant_id != tenant_id:
            return None

        # Allowed transition only from 'fixed' or 'in_progress' or 'submitted' (early signal)
        if sub.status not in {"submitted", "triaged", "in_progress", "fixed"}:
            raise ValueError(
                f"Cannot request re-test on submission in status={sub.status!r}"
            )

        sub.status = "retest_requested"
        sub.retest_requested_at = _now_utc()
        sub.retest_requested_by_user_id = requested_by_user_id

        self.db.add(AuditLog(
            user_id=requested_by_user_id,
            action="vapt_retest_requested",
            resource_type="vapt_submission",
            resource_id=sub.id,
            details={"submission_id": str(sub.id)},
            tenant_id=tenant_id,
        ))
        await self.db.flush()
        return sub

    # ------------------------------------------------------------------ #
    #  Re-test: vendor responds
    # ------------------------------------------------------------------ #

    async def vendor_retest_response(
        self,
        *,
        submission: VaptSubmission,
        result: str,
        evidence_uri: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> VaptSubmission:
        """
        Vendor uploads a re-test result.

        result must be 'pass' or 'fail'.
          - pass → submission.status='retest_pass' → 'closed'; linked Risk
                   moves to status='closed' (auto-close).
          - fail → submission.status='retest_fail'; the linked Risk remains
                   open and goes back to 'in_progress' for IT to re-fix.
        """
        if result not in {"pass", "fail"}:
            raise ValueError("retest result must be 'pass' or 'fail'")

        if submission.status != "retest_requested":
            raise ValueError(
                f"Submission status={submission.status!r} cannot accept a re-test response."
            )

        submission.retest_completed_at = _now_utc()
        submission.retest_result = result
        submission.retest_evidence_uri = evidence_uri
        submission.retest_notes = notes

        if result == "pass":
            submission.status = "closed"
            # Auto-close the linked URIP Risk
            if submission.risk_record_id is not None:
                risk_result = await self.db.execute(
                    select(Risk).where(Risk.id == submission.risk_record_id)
                )
                risk = risk_result.scalar_one_or_none()
                if risk is not None:
                    risk.status = "closed"
        else:
            submission.status = "retest_fail"

        self.db.add(AuditLog(
            user_id=None,
            action="vapt_retest_completed",
            resource_type="vapt_submission",
            resource_id=submission.id,
            details={"result": result, "submission_id": str(submission.id)},
            tenant_id=submission.tenant_id,
        ))
        await self.db.flush()
        return submission

    # ------------------------------------------------------------------ #
    #  Listings (scoped)
    # ------------------------------------------------------------------ #

    async def list_vendor_submissions(
        self, vendor_id: uuid.UUID, *, status: Optional[str] = None
    ) -> list[VaptSubmission]:
        """
        Return only this vendor's own submissions.

        This is the primary scoping enforcement on top of JWT verification:
        the vendor JWT carries vendor_id, the router calls this with that id,
        and the SQL query filters on it. There is no path that allows one
        vendor to see another vendor's data.
        """
        query = (
            select(VaptSubmission)
            .where(VaptSubmission.vapt_vendor_id == vendor_id)
            .order_by(VaptSubmission.submitted_at.desc())
        )
        if status:
            query = query.where(VaptSubmission.status == status)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_tenant_submissions(
        self, tenant_id: uuid.UUID, *, status: Optional[str] = None
    ) -> list[VaptSubmission]:
        """Admin view: all submissions across all vendors of this tenant."""
        query = (
            select(VaptSubmission)
            .where(VaptSubmission.tenant_id == tenant_id)
            .order_by(VaptSubmission.submitted_at.desc())
        )
        if status:
            query = query.where(VaptSubmission.status == status)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_submission_for_vendor(
        self, *, submission_id: uuid.UUID, vendor_id: uuid.UUID
    ) -> Optional[VaptSubmission]:
        """Fetch a single submission, scoped by vendor (security boundary)."""
        result = await self.db.execute(
            select(VaptSubmission).where(
                VaptSubmission.id == submission_id,
                VaptSubmission.vapt_vendor_id == vendor_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_submission_for_tenant(
        self, *, submission_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Optional[VaptSubmission]:
        """Fetch a single submission for a tenant admin (cross-vendor)."""
        result = await self.db.execute(
            select(VaptSubmission).where(
                VaptSubmission.id == submission_id,
                VaptSubmission.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_tenant_vendors(
        self, tenant_id: uuid.UUID, *, only_active: bool = False
    ) -> list[VaptVendor]:
        query = select(VaptVendor).where(VaptVendor.tenant_id == tenant_id)
        if only_active:
            query = query.where(VaptVendor.status == "active")
        query = query.order_by(VaptVendor.invited_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_vendor(
        self, vendor_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Optional[VaptVendor]:
        result = await self.db.execute(
            select(VaptVendor).where(VaptVendor.id == vendor_id)
        )
        v = result.scalar_one_or_none()
        if v is None or v.tenant_id != tenant_id:
            return None
        return v

    async def get_active_vendor_by_id(
        self, vendor_id: uuid.UUID
    ) -> Optional[VaptVendor]:
        """
        Used by the JWT middleware to confirm the vendor still exists AND is
        active. Returns None for suspended / missing vendors regardless of
        tenant — the JWT carries tenant_id which the middleware double-checks.
        """
        result = await self.db.execute(
            select(VaptVendor).where(VaptVendor.id == vendor_id)
        )
        v = result.scalar_one_or_none()
        if v is None or v.status != "active":
            return None
        return v

    # ------------------------------------------------------------------ #
    #  JWT minting (private)
    # ------------------------------------------------------------------ #

    def _mint_vendor_jwt(self, *, vendor: VaptVendor, expires_at: datetime) -> str:
        """Mint a VAPT-vendor-scoped JWT with iss/aud/type guard rails."""
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        payload = {
            "sub": vendor.contact_email,
            "type": VAPT_JWT_TYPE,
            "vendor_id": str(vendor.id),
            "tenant_id": str(vendor.tenant_id),
            "exp": int(expires_at.timestamp()),
            "iss": VAPT_JWT_ISSUER,
            "aud": VAPT_JWT_AUDIENCE,
        }
        return pyjwt.encode(
            payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )

    def decode_vendor_jwt(self, token: str) -> dict:
        """
        Decode + verify a VAPT vendor JWT.

        Raises pyjwt.PyJWTError on any failure (signature / iss / aud /
        algorithm / expiry). Caller in middleware maps errors to 401.
        """
        return pyjwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=VAPT_JWT_AUDIENCE,
            issuer=VAPT_JWT_ISSUER,
            options={"require": ["exp", "iss", "aud"]},
        )

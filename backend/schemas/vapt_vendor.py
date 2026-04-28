"""
Pydantic schemas for the VAPT Vendor Portal — P33a (URIP_Blueprint v3 §6.5).
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# CVE-YYYY-NNNNN+   (4 digits year, 4-7 digit serial)
_CVE_PATTERN = re.compile(r"^CVE-\d{4}-\d{4,7}$")
_VALID_SEVERITY = {"critical", "high", "medium", "low"}
_VALID_EXPLOIT_MATURITY = {"poc", "functional", "weaponized"}
_VALID_RETEST_RESULT = {"pass", "fail"}


# ---------------------------------------------------------------------------
#  Admin: invite / list / revoke
# ---------------------------------------------------------------------------

class VaptVendorInviteCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    contact_email: EmailStr
    contact_name: Optional[str] = Field(default=None, max_length=255)
    organization: Optional[str] = Field(default=None, max_length=255)
    ttl_days: int = Field(default=14, ge=1, le=90)


class VaptVendorOut(BaseModel):
    id: str
    name: str
    contact_email: str
    contact_name: Optional[str] = None
    organization: Optional[str] = None
    status: str
    invited_at: datetime
    last_login_at: Optional[datetime] = None
    submission_count: Optional[int] = None
    invitation_url: Optional[str] = None  # populated only on create


class VaptVendorListResponse(BaseModel):
    items: list[VaptVendorOut]
    total: int


# ---------------------------------------------------------------------------
#  Vendor portal: invitation accept
# ---------------------------------------------------------------------------

class VaptInvitationAccept(BaseModel):
    token: str = Field(..., min_length=10)


class VaptInvitationAcceptResponse(BaseModel):
    vapt_vendor_jwt: str
    expires_at: datetime
    vendor: VaptVendorOut


# ---------------------------------------------------------------------------
#  Submissions
# ---------------------------------------------------------------------------

class VaptSubmissionCreate(BaseModel):
    """Used in tests / programmatic invocations. Multipart layer wraps this."""
    finding_title: str = Field(..., min_length=1, max_length=500)
    cve_id: Optional[str] = Field(default=None, max_length=30)
    cvss_score: float = Field(..., ge=0.0, le=10.0)
    severity: str
    affected_asset_hostname: Optional[str] = Field(default=None, max_length=255)
    affected_asset_ip: Optional[str] = Field(default=None, max_length=45)
    exploit_maturity: Optional[str] = None
    description: Optional[str] = None
    remediation_recommendation: Optional[str] = None

    @field_validator("severity")
    @classmethod
    def _check_severity(cls, v: str) -> str:
        if v.lower() not in _VALID_SEVERITY:
            raise ValueError(
                f"severity must be one of {sorted(_VALID_SEVERITY)}; got {v!r}"
            )
        return v.lower()

    @field_validator("exploit_maturity")
    @classmethod
    def _check_exploit(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if v.lower() not in _VALID_EXPLOIT_MATURITY:
            raise ValueError(
                f"exploit_maturity must be one of "
                f"{sorted(_VALID_EXPLOIT_MATURITY)}; got {v!r}"
            )
        return v.lower()

    @field_validator("cve_id")
    @classmethod
    def _check_cve(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        if not _CVE_PATTERN.match(v):
            raise ValueError(
                "cve_id must match CVE-YYYY-NNNNN format (e.g. CVE-2024-3400)"
            )
        return v


class VaptSubmissionOut(BaseModel):
    id: str
    vapt_vendor_id: str
    tenant_id: str
    finding_title: str
    cve_id: Optional[str] = None
    cvss_score: float
    severity: str
    affected_asset_hostname: Optional[str] = None
    affected_asset_ip: Optional[str] = None
    exploit_maturity: Optional[str] = None
    description: Optional[str] = None
    remediation_recommendation: Optional[str] = None
    evidence_filename: Optional[str] = None
    submitted_at: datetime
    status: str
    risk_record_id: Optional[str] = None
    risk_id_label: Optional[str] = None  # e.g. "RISK-2026-A1B2"
    retest_requested_at: Optional[datetime] = None
    retest_completed_at: Optional[datetime] = None
    retest_result: Optional[str] = None


class VaptSubmissionListResponse(BaseModel):
    items: list[VaptSubmissionOut]
    total: int


# ---------------------------------------------------------------------------
#  Re-test
# ---------------------------------------------------------------------------

class VaptRetestRequest(BaseModel):
    """Admin → vendor: please re-test."""
    note: Optional[str] = None


class VaptRetestResponse(BaseModel):
    """Vendor → admin: re-test result."""
    result: str
    notes: Optional[str] = None

    @field_validator("result")
    @classmethod
    def _check_result(cls, v: str) -> str:
        if v.lower() not in _VALID_RETEST_RESULT:
            raise ValueError(
                f"result must be one of {sorted(_VALID_RETEST_RESULT)}"
            )
        return v.lower()


# ---------------------------------------------------------------------------
#  Vendor profile
# ---------------------------------------------------------------------------

class VaptVendorProfile(BaseModel):
    id: str
    name: str
    contact_email: str
    contact_name: Optional[str] = None
    organization: Optional[str] = None
    status: str
    tenant_id: str
    invited_at: datetime
    last_login_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
#  Notifications
# ---------------------------------------------------------------------------

class VaptVendorNotification(BaseModel):
    submission_id: str
    finding_title: str
    risk_id_label: Optional[str] = None
    requested_at: datetime
    note: Optional[str] = None


class VaptVendorNotificationListResponse(BaseModel):
    items: list[VaptVendorNotification]
    total: int

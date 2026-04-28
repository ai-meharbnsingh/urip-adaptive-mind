import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


# M2 (Kimi MED-001) — Soft email-format validator at API boundary.
# We intentionally do NOT use pydantic.EmailStr because it rejects RFC 6761
# special-use TLDs (.test, .localhost, .invalid, .example) which the URIP
# test fixtures use heavily.  This regex covers the obvious malformed cases
# (no @, multiple @, missing local-part / domain) while preserving the
# convenience of testdomain emails.  RFC 5321 / 5322 has more permissive
# grammar, but for an API-boundary check this catches >99% of typos.
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def _validate_email(v: str) -> str:
    if not isinstance(v, str) or not _EMAIL_RE.match(v):
        raise ValueError("value is not a valid email address")
    return v.lower()


# Annotated type usable across schema modules.
EmailField = Annotated[str, AfterValidator(_validate_email)]


class LoginRequest(BaseModel):
    # M2 (Kimi MED-001) — Reject malformed emails at the API boundary so
    # they never reach the auth handler.
    email: EmailField
    # M1 — bcrypt silently truncates anything past 72 bytes; reject at
    # entry. Floor of 1 (not 12) here because we still need to authenticate
    # legacy users whose password met the older policy. UserCreate enforces
    # 12+ for NEW credentials.
    password: str = Field(..., min_length=1, max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserProfile"


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    team: str | None = None
    is_super_admin: bool = False
    tenant_slug: str | None = None

    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1)
    email: EmailField
    full_name: str = Field(..., min_length=1, max_length=150)
    password: str = Field(..., min_length=12, max_length=72)
    role: str = Field("it_team", min_length=1, max_length=20)
    team: str | None = Field(None, max_length=100)


class ForgotPasswordRequest(BaseModel):
    email: EmailField


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=200)
    new_password: str = Field(..., min_length=12, max_length=72)


class MFAEnrollResponse(BaseModel):
    provisioning_uri: str
    qr_payload: str


class MFAVerifyRequest(BaseModel):
    code: str = Field(..., pattern=r"^[0-9]{6}$")

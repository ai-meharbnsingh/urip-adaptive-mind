"""
Pydantic v2 models for Okta Core API response shapes.

These models are used to validate and type raw JSON from the Okta API
before the connector processes it.  They are intentionally lenient
(extra fields are ignored) so new Okta API fields do not break parsing.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


# ─────────────────────────────────────────────────────────────────────────────
# Sub-models
# ─────────────────────────────────────────────────────────────────────────────


class OktaUserProfile(BaseModel):
    """Okta user profile sub-object."""

    model_config = {"extra": "ignore"}

    email: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    login: Optional[str] = None
    displayName: Optional[str] = None


class OktaOutcome(BaseModel):
    """Outcome block inside a System Log event."""

    model_config = {"extra": "ignore"}

    result: Optional[str] = None
    reason: Optional[str] = None


class OktaActor(BaseModel):
    """Actor block inside a System Log event."""

    model_config = {"extra": "ignore"}

    id: Optional[str] = None
    type: Optional[str] = None
    alternateId: Optional[str] = None
    displayName: Optional[str] = None


class OktaTarget(BaseModel):
    """One entry in the ``target`` list of a System Log event."""

    model_config = {"extra": "ignore"}

    id: Optional[str] = None
    type: Optional[str] = None
    alternateId: Optional[str] = None
    displayName: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Top-level models
# ─────────────────────────────────────────────────────────────────────────────


class OktaUser(BaseModel):
    """
    Okta User object as returned by GET /api/v1/users.

    https://developer.okta.com/docs/reference/api/users/#user-object
    """

    model_config = {"extra": "ignore"}

    id: str
    status: Optional[str] = None
    profile: Optional[OktaUserProfile] = None
    lastLogin: Optional[str] = None
    lastUpdated: Optional[str] = None
    created: Optional[str] = None
    activated: Optional[str] = None

    @property
    def email(self) -> str | None:
        return self.profile.email if self.profile else None

    @property
    def display_name(self) -> str:
        if self.profile:
            parts = [self.profile.firstName, self.profile.lastName]
            name = " ".join(p for p in parts if p).strip()
            return name or self.profile.email or self.id
        return self.id


class OktaAppAssignment(BaseModel):
    """
    Okta AppLink object returned by GET /api/v1/users/{id}/appLinks,
    OR a simplified view of an Application from GET /api/v1/apps.

    https://developer.okta.com/docs/reference/api/users/#get-assigned-app-links
    """

    model_config = {"extra": "ignore"}

    id: Optional[str] = None
    label: Optional[str] = None
    # appLink fields
    appName: Optional[str] = None
    # apps endpoint fields
    name: Optional[str] = None
    status: Optional[str] = None
    lastUpdated: Optional[str] = None

    @property
    def app_name(self) -> str | None:
        """Normalize: appName (appLinks) or name (apps endpoint)."""
        return self.appName or self.name


class OktaFactor(BaseModel):
    """
    Okta Factor object as returned by GET /api/v1/users/{id}/factors.

    https://developer.okta.com/docs/reference/api/factors/#factor-object
    """

    model_config = {"extra": "ignore"}

    id: str
    factorType: Optional[str] = None
    provider: Optional[str] = None
    status: Optional[str] = None
    created: Optional[str] = None
    lastUpdated: Optional[str] = None


class OktaSystemLogEvent(BaseModel):
    """
    Okta System Log event as returned by GET /api/v1/logs.

    https://developer.okta.com/docs/reference/api/system-log/#logevent-object
    """

    model_config = {"extra": "ignore"}

    uuid: str
    published: str
    eventType: str
    severity: Optional[str] = None
    displayMessage: Optional[str] = None
    actor: Optional[OktaActor] = None
    target: Optional[list[OktaTarget]] = Field(default_factory=list)
    outcome: Optional[OktaOutcome] = None
    client: Optional[dict[str, Any]] = None
    request: Optional[dict[str, Any]] = None
    securityContext: Optional[dict[str, Any]] = None
    debugContext: Optional[dict[str, Any]] = None
    legacyEventType: Optional[str] = None

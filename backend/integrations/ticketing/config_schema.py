"""
backend.integrations.ticketing.config_schema — tenant-side ticketing config validator.

Used by the admin UI when a tenant pastes their Jira / ServiceNow API token.
Two helpers:
    validate_ticketing_config(raw: dict) -> TicketingConfig
        Pydantic-validates the raw dict.  Normalises (lower-case provider,
        trim trailing slashes, upper-case Jira project_key).

    preflight_ticketing_config(cfg, http_client=None) -> PreflightResult
        Hits the live API to verify auth + that project_key / table actually
        exist.  Returns a `PreflightResult(ok=bool, message=str)` so the UI can
        render the exact remediation step.

The HTTP client is injectable so tests don't need network access.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import httpx
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


PROVIDERS = {"jira", "servicenow"}


class TicketingConfig(BaseModel):
    """Tenant ticketing configuration block (lives in tenants.settings.ticketing)."""

    provider: str
    base_url: str
    auth_token: str = Field(min_length=1)
    # Jira-only:
    project_key: Optional[str] = None
    issue_type: str = "Bug"
    # ServiceNow-only:
    table: str = "incident"
    # Shared:
    webhook_secret: str = ""

    # ----- normalisation ----- #
    @field_validator("provider", mode="before")
    @classmethod
    def _norm_provider(cls, v: str) -> str:
        if not v:
            raise ValueError("provider required")
        v = str(v).strip().lower()
        if v in {"snow", "service_now"}:
            v = "servicenow"
        if v not in PROVIDERS:
            raise ValueError(f"provider must be one of {sorted(PROVIDERS)}, got {v!r}")
        return v

    @field_validator("base_url", mode="before")
    @classmethod
    def _norm_base_url(cls, v: str) -> str:
        if not v:
            raise ValueError("base_url required")
        v = str(v).strip().rstrip("/")
        if not (v.startswith("https://") or v.startswith("http://localhost")):
            # We allow http://localhost for local dev; otherwise require HTTPS.
            raise ValueError("base_url must use https:// (http://localhost permitted for dev)")
        return v

    @field_validator("project_key", mode="before")
    @classmethod
    def _norm_project_key(cls, v):
        if v is None:
            return v
        return str(v).strip().upper()

    @model_validator(mode="after")
    def _check_provider_specific(self) -> "TicketingConfig":
        if self.provider == "jira" and not self.project_key:
            raise ValueError("project_key is required for provider=jira")
        if self.provider == "servicenow" and not self.table:
            raise ValueError("table is required for provider=servicenow")
        return self


def validate_ticketing_config(raw: dict) -> TicketingConfig:
    """Wrap Pydantic.model_validate so callers see a uniform exception type."""
    return TicketingConfig.model_validate(raw)


# --------------------------------------------------------------------------- #
# Pre-flight ping
# --------------------------------------------------------------------------- #
@dataclass
class PreflightResult:
    ok: bool
    message: str = ""


def _jira_headers(auth_token: str) -> dict[str, str]:
    import base64
    if ":" in auth_token:
        encoded = base64.b64encode(auth_token.encode("utf-8")).decode("ascii")
        auth = f"Basic {encoded}"
    else:
        auth = f"Bearer {auth_token}"
    return {"Authorization": auth, "Accept": "application/json"}


def _servicenow_headers(auth_token: str) -> dict[str, str]:
    if ":" in auth_token:
        import base64
        encoded = base64.b64encode(auth_token.encode("utf-8")).decode("ascii")
        auth = f"Basic {encoded}"
    else:
        auth = f"Bearer {auth_token}"
    return {"Authorization": auth, "Accept": "application/json"}


def _ping_jira(cfg: TicketingConfig, client: httpx.Client) -> PreflightResult:
    headers = _jira_headers(cfg.auth_token)
    # 1. /myself — verifies auth token is valid.
    try:
        me = client.get(f"{cfg.base_url}/rest/api/3/myself", headers=headers, timeout=15)
    except httpx.HTTPError as exc:
        return PreflightResult(False, f"Network error contacting Jira: {exc}")
    if me.status_code == 401:
        return PreflightResult(False, "Jira returned HTTP 401 — auth token invalid")
    if me.status_code == 403:
        return PreflightResult(False, "Jira returned HTTP 403 — token lacks REST scopes")
    if me.status_code >= 500:
        return PreflightResult(False, f"Jira returned HTTP {me.status_code} — service down")
    if me.status_code != 200:
        return PreflightResult(False, f"Unexpected Jira HTTP {me.status_code} on /myself")

    # 2. /project/<KEY> — verifies project_key exists.
    try:
        pr = client.get(
            f"{cfg.base_url}/rest/api/3/project/{cfg.project_key}",
            headers=headers, timeout=15,
        )
    except httpx.HTTPError as exc:
        return PreflightResult(False, f"Network error contacting Jira project endpoint: {exc}")
    if pr.status_code == 404:
        return PreflightResult(False, f"Jira project_key {cfg.project_key!r} not found (HTTP 404)")
    if pr.status_code != 200:
        return PreflightResult(False, f"Jira project lookup returned HTTP {pr.status_code}")
    body = pr.json() if pr.content else {}
    return PreflightResult(True, f"Jira project {cfg.project_key} reachable — id={body.get('id')}")


def _ping_servicenow(cfg: TicketingConfig, client: httpx.Client) -> PreflightResult:
    headers = _servicenow_headers(cfg.auth_token)
    url = f"{cfg.base_url}/api/now/table/{cfg.table}?sysparm_limit=1"
    try:
        resp = client.get(url, headers=headers, timeout=15)
    except httpx.HTTPError as exc:
        return PreflightResult(False, f"Network error contacting ServiceNow: {exc}")
    if resp.status_code == 401:
        return PreflightResult(False, "ServiceNow returned HTTP 401 — auth token invalid")
    if resp.status_code == 403:
        return PreflightResult(False, "ServiceNow returned HTTP 403 — user lacks role")
    if resp.status_code >= 500:
        return PreflightResult(False, f"ServiceNow returned HTTP {resp.status_code} — service down")
    if resp.status_code != 200:
        return PreflightResult(False, f"ServiceNow HTTP {resp.status_code}")
    return PreflightResult(True, f"ServiceNow table {cfg.table} reachable")


def preflight_ticketing_config(
    cfg: TicketingConfig,
    *,
    http_client: httpx.Client | None = None,
) -> PreflightResult:
    own_client = http_client is None
    client = http_client or httpx.Client(timeout=15.0)
    try:
        if cfg.provider == "jira":
            return _ping_jira(cfg, client)
        if cfg.provider == "servicenow":
            return _ping_servicenow(cfg, client)
        return PreflightResult(False, f"Unsupported provider: {cfg.provider}")
    finally:
        if own_client:
            client.close()

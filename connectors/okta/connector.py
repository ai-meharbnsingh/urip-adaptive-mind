"""
Okta Workforce Identity connector for URIP.

Implements the BaseConnector contract:
  authenticate   → SSWS token verification via GET /api/v1/users/me
  fetch_findings → pulls System Log events matching the configured filter
  normalize      → maps Okta log event → URIPRiskRecord (severity by event type)
  health_check   → operational status via healthcheck probe

Out of scope (not implemented):
  push / create action — Okta Workflows handles automated responses (IF/THEN
  policies); URIP does not push tickets back to Okta.

References
----------
Okta Core API: https://developer.okta.com/docs/reference/core-okta-api/
System Log API: https://developer.okta.com/docs/reference/api/system-log/
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _run_async(coro: Any) -> Any:
    """
    Run a coroutine from synchronous code.

    Uses asyncio.run() which always creates a new event loop, ensuring
    compatibility with Python 3.10+ where get_event_loop() is deprecated
    in non-async contexts and raises in 3.12+ when there is no current loop.
    """
    return asyncio.run(coro)


from connectors.base.connector import (
    BaseConnector,
    ConnectorAuthError,
    ConnectorFetchError,
    ConnectorHealth,
    ConnectorSession,
    CredentialFieldSpec,
    RawFinding,
    URIPRiskRecord,
)
from connectors.base.registry import register_connector
from connectors.base.setup_guides_data import SETUP_GUIDES
from connectors.okta.api_client import OktaAPIClient
from connectors.okta.schemas import OktaSystemLogEvent


# ─────────────────────────────────────────────────────────────────────────────
# Severity mapping helpers
# ─────────────────────────────────────────────────────────────────────────────

# Event types that carry a direct severity classification
_HIGH_EVENT_TYPES: frozenset[str] = frozenset({
    "user.account.lock",
    "user.session.access_admin_app",
    "application.user_membership.add",
    "application.user_membership.remove",
})

_DEFAULT_LOG_FILTER = (
    'eventType eq "user.account.lock" or '
    'eventType eq "user.session.access_admin_app" or '
    'eventType eq "policy.evaluate_sign_on"'
)


def _parse_event_types_from_filter(filter_expr: str) -> list[str]:
    """
    Extract a list of event-type strings from an Okta filter expression.

    Handles the pattern:
        eventType eq "user.account.lock" or eventType eq "policy.evaluate_sign_on"

    Returns an empty list if no event types can be parsed (caller falls back
    to default list).
    """
    return re.findall(r'eventType\s+eq\s+"([^"]+)"', filter_expr)


def _map_severity(event: OktaSystemLogEvent) -> str:
    """
    Map an Okta System Log event to a URIP severity string.

    Rules (in priority order):
      1. user.account.lock                  → high   (credential abuse / brute-force)
      2. user.session.access_admin_app      → high   (admin-app access — privilege escalation risk)
      3. application.user_membership.add/
         application.user_membership.remove → high   (lateral movement signal)
      4. policy.evaluate_sign_on with
         outcome.result == "DENY"           → medium (policy block — suspicious sign-in)
      5. Any other event                    → low
    """
    etype = event.eventType or ""

    if etype in _HIGH_EVENT_TYPES:
        return "high"

    if etype == "policy.evaluate_sign_on":
        outcome_result = (
            event.outcome.result.upper()
            if event.outcome and event.outcome.result
            else ""
        )
        if outcome_result == "DENY":
            return "medium"
        return "low"

    return "low"


# ─────────────────────────────────────────────────────────────────────────────
# Connector class
# ─────────────────────────────────────────────────────────────────────────────


@register_connector("okta")
class OktaConnector(BaseConnector):
    """
    Live connector for Okta Workforce Identity Cloud.

    Data flow
    ---------
    1. Authenticate via GET /api/v1/users/me (SSWS token probe).
    2. Pull System Log events using the configured Okta filter expression.
    3. Normalize each event to URIPRiskRecord with severity-by-event-type logic.
    4. health_check() re-probes /api/v1/users/me.

    Supported products
    ------------------
    - Okta Workforce Identity Cloud (all editions)
    - Okta Standard / Premier / Enterprise / FedRAMP High

    Auth
    ----
    SSWS token — generated in Okta Admin Console:
        Security → API → Tokens → Create Token
    Token requires Read-Only Administrator role or Org Administrator role.
    """

    NAME = "okta"
    RISK_INDEX_DOMAIN = "identity"

    # Catalog metadata
    DISPLAY_NAME = "Okta Workforce Identity"
    CATEGORY = "IDENTITY"
    SHORT_DESCRIPTION = (
        "Universal SSO + adaptive MFA + lifecycle management. "
        "Pulls user posture, app assignments, MFA enrollment, and System Log "
        "events for cross-domain risk correlation."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://developer.okta.com/docs/reference/core-okta-api/"
    SUPPORTED_PRODUCTS = [
        "Okta Workforce Identity Cloud",
        "Okta Standard / Premier / Enterprise / FedRAMP High",
    ]
    MODULE_CODE = "IDENTITY"

    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="domain",
            label="Okta Domain",
            type="url",
            required=True,
            placeholder="your-org.okta.com",
            help_text=(
                "Your Okta tenant domain. "
                "NO https://, NO trailing slash."
            ),
        ),
        CredentialFieldSpec(
            name="api_token",
            label="API Token",
            type="password",
            required=True,
            secret=True,
            help_text=(
                "Okta admin → Security → API → Tokens → Create Token. "
                "Token is shown ONCE."
            ),
        ),
        CredentialFieldSpec(
            name="log_event_filter",
            label='System Log event filter (Okta filter syntax)',
            type="text",
            required=True,
            default=_DEFAULT_LOG_FILTER,
            help_text=(
                "Okta filter expression for System Log events to ingest. "
                'Example: eventType eq "user.account.lock" or '
                'eventType eq "policy.evaluate_sign_on"'
            ),
        ),
    ]

    # Inline onboarding content
    SETUP_GUIDE = SETUP_GUIDES.get("okta")

    # ─────────────────────────────────────────────────────────────────────────
    # Constructor
    # ─────────────────────────────────────────────────────────────────────────

    def __init__(self) -> None:
        self._client: OktaAPIClient | None = None
        self._domain: str = ""
        self._log_event_filter: str = _DEFAULT_LOG_FILTER
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    # ─────────────────────────────────────────────────────────────────────────
    # BaseConnector contract
    # ─────────────────────────────────────────────────────────────────────────

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate Okta SSWS credentials by calling GET /api/v1/users/me.

        Required credential keys:
            - domain    : Okta tenant domain (e.g. "your-org.okta.com")
            - api_token : SSWS API token
        Optional:
            - log_event_filter : Okta filter expression for System Log events
            - tenant_id        : scoped into ConnectorSession

        Returns
        -------
        ConnectorSession

        Raises
        ------
        ConnectorAuthError
            If credentials are missing or Okta rejects the token.
        """
        domain = tenant_credentials.get("domain", "").strip().rstrip("/")
        api_token = tenant_credentials.get("api_token", "").strip()

        if not domain:
            raise ConnectorAuthError(
                "Okta credentials must include 'domain' (e.g. your-org.okta.com)."
            )
        if not api_token:
            raise ConnectorAuthError(
                "Okta credentials must include 'api_token'."
            )

        self._domain = domain
        self._log_event_filter = tenant_credentials.get(
            "log_event_filter", _DEFAULT_LOG_FILTER
        )

        self._client = OktaAPIClient(domain=domain, api_token=api_token)

        try:
            me = _run_async(self._client.healthcheck())
        except ConnectorAuthError:
            raise
        except Exception as exc:
            raise ConnectorAuthError(
                f"Okta authentication probe failed: {exc}"
            ) from exc

        user_id = me.get("id", "unknown")
        login = me.get("login") or me.get("profile", {}).get("login", "unknown")
        logger.info(
            "Okta authenticated: userId=%s login=%s domain=%s",
            user_id,
            login,
            domain,
        )

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token="okta-ssws-****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
            extra={"userId": user_id, "login": login},
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull System Log events from Okta matching the configured filter.

        Parameters
        ----------
        since : datetime
            Fetch only events published after this timestamp.
        tenant_id : str, optional
            Scoped into RawFinding.tenant_id.

        Returns
        -------
        list[RawFinding]

        Raises
        ------
        ConnectorFetchError
            If the connector is not authenticated or the API call fails.
        """
        if self._client is None:
            raise ConnectorFetchError(
                "Okta connector not authenticated. Call authenticate() first."
            )

        tenant_id: str = kwargs.get("tenant_id", "unknown")

        # Parse event types from the configured filter expression
        event_types = _parse_event_types_from_filter(self._log_event_filter)

        try:
            raw_events = _run_async(
                self._client.list_system_log(
                    since=since,
                    types=event_types if event_types else None,
                )
            )

            findings: list[RawFinding] = []
            for event in raw_events:
                # Use the Okta event UUID as the stable finding ID
                event_id = event.get("uuid", "")
                findings.append(
                    RawFinding(
                        id=event_id,
                        source=self.NAME,
                        raw_data=event,
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            logger.info(
                "Okta: fetched %d System Log events for tenant %s (since %s)",
                len(findings),
                tenant_id,
                since.isoformat(),
            )
            self._last_run = datetime.now(timezone.utc)
            return findings

        except (ConnectorAuthError, ConnectorFetchError):
            raise
        except Exception as exc:
            self._error_count += 1
            msg = str(exc)
            self._last_error = msg
            logger.exception("Okta fetch_findings failed")
            raise ConnectorFetchError(f"Okta fetch_findings failed: {msg}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map an Okta System Log RawFinding to a URIPRiskRecord.

        Severity mapping:
            user.account.lock                           → high
            user.session.access_admin_app               → high
            application.user_membership.add/remove      → high
            policy.evaluate_sign_on + outcome.DENY      → medium
            policy.evaluate_sign_on + other outcome     → low
            all other event types                       → low

        The external_id (Okta event UUID) and source_url are embedded in
        the description field for traceability.
        """
        event = OktaSystemLogEvent.model_validate(raw.raw_data)

        severity = _map_severity(event)

        # Build a human-readable finding title
        actor_name = (
            event.actor.displayName
            if event.actor and event.actor.displayName
            else "unknown actor"
        )
        actor_email = (
            event.actor.alternateId
            if event.actor and event.actor.alternateId
            else None
        )

        display_msg = event.displayMessage or event.eventType
        finding_title = f"Okta: {display_msg} ({event.eventType})"

        # Source URL for direct navigation in Okta admin
        source_url = (
            f"https://{self._domain}/admin/logs?eventId={event.uuid}"
            if self._domain
            else None
        )

        # Outcome info
        outcome_result = (
            event.outcome.result
            if event.outcome and event.outcome.result
            else "unknown"
        )

        description = (
            f"Okta System Log event {event.uuid}: {display_msg}. "
            f"Event type: {event.eventType}. "
            f"Severity: {event.severity or 'N/A'}. "
            f"Actor: {actor_name}"
            + (f" <{actor_email}>" if actor_email else "")
            + f". Outcome: {outcome_result}. "
            f"Published: {event.published}. "
            f"URL: {source_url or 'N/A'}."
        )

        # Derive asset from first target if available
        asset = "okta-tenant"
        if event.target:
            first_target = event.target[0]
            asset = (
                first_target.displayName
                or first_target.alternateId
                or first_target.id
                or "okta-tenant"
            )

        return URIPRiskRecord(
            finding=finding_title,
            description=description,
            source=self.NAME,
            domain="identity",
            cvss_score=0.0,
            severity=severity,
            asset=asset,
            owner_team="Identity & Access Management",
            cve_id=None,
            exploit_status=None,
        )

    def health_check(self) -> ConnectorHealth:
        """Return connector operational status. Never raises."""
        if self._client is None:
            return ConnectorHealth(
                connector_name=self.NAME,
                status="ok",
                last_run=None,
                error_count=0,
                last_error=None,
            )

        try:
            _run_async(self._client.healthcheck())
            error_count = self._error_count
            status = "ok" if error_count == 0 else (
                "degraded" if error_count < 5 else "error"
            )
            return ConnectorHealth(
                connector_name=self.NAME,
                status=status,
                last_run=self._last_run,
                error_count=error_count,
                last_error=self._last_error,
            )
        except Exception as exc:
            return ConnectorHealth(
                connector_name=self.NAME,
                status="degraded",
                last_run=self._last_run,
                error_count=self._error_count + 1,
                last_error=str(exc),
            )

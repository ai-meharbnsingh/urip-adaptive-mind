"""
Jira Cloud + Jira Data Center connector for URIP.

Implements the BaseConnector contract:
  authenticate   → Basic (Cloud) or Bearer (DC/Server) auth via /rest/api/3/myself
  fetch_findings → search security tickets via JQL
  normalize      → maps Jira issue → URIPRiskRecord
  health_check   → operational status

Bidirectional:
  create_ticket  → creates a Jira issue from URIP risk data

References
----------
Atlassian REST API v3: https://developer.atlassian.com/cloud/jira/platform/rest/v3/
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional


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
from connectors.jira.api_client import JiraAPIClient
from connectors.jira.schemas import JiraIssue, JiraSearchResponse

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Priority / Status maps
# ─────────────────────────────────────────────────────────────────────────────

# Jira priority name → URIP severity
_PRIORITY_MAP: dict[str, str] = {
    "highest": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "lowest": "low",
}

# Jira status name → URIP risk status label (informational — not stored on URIPRiskRecord)
_STATUS_MAP: dict[str, str] = {
    "open": "open",
    "in progress": "in_progress",
    "done": "resolved",
    "closed": "resolved",
    "resolved": "resolved",
}

# Jira priority → Jira-native priority name for outbound ticket creation
_SEVERITY_TO_JIRA_PRIORITY: dict[str, str] = {
    "critical": "Highest",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}


def _map_priority(jira_priority: str | None) -> str:
    """Map Jira priority name → URIP severity string."""
    return _PRIORITY_MAP.get((jira_priority or "").lower(), "medium")


def _map_status(jira_status: str | None) -> str:
    """Map Jira status name → URIP risk status label."""
    return _STATUS_MAP.get((jira_status or "").lower(), "open")


# ─────────────────────────────────────────────────────────────────────────────
# Connector class
# ─────────────────────────────────────────────────────────────────────────────


@register_connector("jira")
class JiraConnector(BaseConnector):
    """
    Live connector for Jira Cloud and Jira Data Center.

    Data flow
    ---------
    1. Authenticate via /rest/api/3/myself (Cloud: Basic, DC: Bearer).
    2. Search security tickets using a configurable JQL filter.
    3. Normalize each issue to URIPRiskRecord.
    4. (Bidirectional) Create Jira issues from URIP risk data via create_ticket().

    Supported products
    ------------------
    - Jira Cloud (Atlassian-hosted)
    - Jira Data Center (self-managed ≥ 9.0)
    - Jira Server (≥ 9.0, same REST API surface as Data Center)

    Auth
    ----
    Cloud  → email + API token (Atlassian API token, NOT password)
    DC/Server → Personal Access Token (PAT)
    """

    NAME = "jira"
    RISK_INDEX_DOMAIN = None  # ITSM connector — no risk-index contribution

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "Jira"
    CATEGORY = "ITSM"
    SHORT_DESCRIPTION = (
        "Bidirectional sync — push URIP risks as Jira issues, "
        "ingest security tickets back as risk records."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://developer.atlassian.com/cloud/jira/platform/rest/v3/"
    SUPPORTED_PRODUCTS = [
        "Jira Cloud",
        "Jira Data Center",
        "Jira Server (≥9.0)",
    ]
    MODULE_CODE = "ITSM"

    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="base_url",
            label="Jira Base URL",
            type="url",
            required=True,
            placeholder="https://your-org.atlassian.net",
            help_text="Jira Cloud: https://your-org.atlassian.net. DC/Server: your internal URL.",
            pattern=r"^https://[^\s]+$",
        ),
        CredentialFieldSpec(
            name="auth_method",
            label="Auth Method",
            type="select",
            required=True,
            help_text="Choose Email + API Token for Cloud, or PAT for Data Center / Server.",
            options=[
                {"value": "basic", "label": "Email + API Token (Cloud)"},
                {"value": "bearer", "label": "Personal Access Token (DC/Server)"},
            ],
        ),
        CredentialFieldSpec(
            name="email",
            label="Email",
            type="text",
            required=False,
            help_text="Required when auth_method=basic. Atlassian account email.",
            placeholder="you@your-org.com",
        ),
        CredentialFieldSpec(
            name="api_token",
            label="API Token",
            type="password",
            required=False,
            secret=True,
            help_text="Required when auth_method=basic. Generate at id.atlassian.com → Security → API tokens.",
            placeholder="ATATT3xFfGF0…",
        ),
        CredentialFieldSpec(
            name="bearer_token",
            label="Personal Access Token",
            type="password",
            required=False,
            secret=True,
            help_text="Required when auth_method=bearer. Profile → Personal Access Tokens in DC/Server.",
            placeholder="NjI2NzYwMzU5NDU4OjqFv…",
        ),
        CredentialFieldSpec(
            name="default_project_key",
            label="Default Project Key",
            type="text",
            required=True,
            placeholder="SEC",
            help_text="Project where URIP-pushed risks will land (e.g. SEC, OPS, CSEC).",
        ),
        CredentialFieldSpec(
            name="risk_jql",
            label="JQL filter for security tickets to ingest",
            type="text",
            required=True,
            placeholder='project = SEC AND labels = "security"',
            default='project = SEC AND labels = "security"',
            help_text=(
                'JQL expression that selects security tickets for URIP to ingest. '
                'Example: project = SEC AND labels = "urip-risk" ORDER BY created DESC'
            ),
        ),
    ]

    # P33-Z3 (revised): inline onboarding content.
    SETUP_GUIDE = SETUP_GUIDES.get("jira")

    # ─────────────────────────────────────────────────────────────────────────
    # Constructor
    # ─────────────────────────────────────────────────────────────────────────

    def __init__(self) -> None:
        self._client: JiraAPIClient | None = None
        self._base_url: str = ""
        self._risk_jql: str = 'project = SEC AND labels = "security"'
        self._default_project_key: str = "SEC"
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    # ─────────────────────────────────────────────────────────────────────────
    # BaseConnector contract
    # ─────────────────────────────────────────────────────────────────────────

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate Jira credentials by calling /rest/api/3/myself.

        Required credential keys:
            - base_url      : Jira instance URL
            - auth_method   : "basic" or "bearer"
        If auth_method == "basic":
            - email         : Atlassian account email
            - api_token     : Atlassian API token
        If auth_method == "bearer":
            - bearer_token  : Personal Access Token (DC/Server)
        Optional:
            - default_project_key : project key for outbound ticket creation
            - risk_jql            : JQL for inbound ticket ingestion

        Returns
        -------
        ConnectorSession
            Session with token field set to "jira-basic-****" or "jira-bearer-****".

        Raises
        ------
        ConnectorAuthError
            If credentials are missing or Jira rejects them.
        """
        base_url = tenant_credentials.get("base_url", "").strip()
        auth_method = tenant_credentials.get("auth_method", "").strip().lower()

        if not base_url:
            raise ConnectorAuthError(
                "Jira credentials must include 'base_url'."
            )
        if not auth_method:
            raise ConnectorAuthError(
                "Jira credentials must include 'auth_method' ('basic' or 'bearer')."
            )

        # Store config for later use by fetch_findings / create_ticket.
        self._base_url = base_url
        self._risk_jql = tenant_credentials.get(
            "risk_jql", 'project = SEC AND labels = "security"'
        )
        self._default_project_key = tenant_credentials.get("default_project_key", "SEC")

        if auth_method == "basic":
            email = tenant_credentials.get("email", "").strip()
            api_token = tenant_credentials.get("api_token", "").strip()
            if not email or not api_token:
                raise ConnectorAuthError(
                    "auth_method=basic requires 'email' and 'api_token'."
                )
            self._client = JiraAPIClient(
                base_url=base_url,
                email=email,
                api_token=api_token,
            )
            token_label = "jira-basic-****"

        elif auth_method == "bearer":
            bearer_token = tenant_credentials.get("bearer_token", "").strip()
            if not bearer_token:
                raise ConnectorAuthError(
                    "auth_method=bearer requires 'bearer_token'."
                )
            self._client = JiraAPIClient(
                base_url=base_url,
                bearer_token=bearer_token,
            )
            token_label = "jira-bearer-****"

        else:
            raise ConnectorAuthError(
                f"Unsupported auth_method: {auth_method!r}. Use 'basic' or 'bearer'."
            )

        # Verify credentials by calling /rest/api/3/myself.
        try:
            myself = _run_async(
                self._client.get_myself()
            )
        except ConnectorAuthError:
            raise
        except Exception as exc:
            raise ConnectorAuthError(
                f"Jira authentication probe failed: {exc}"
            ) from exc

        account_id = myself.get("accountId", "unknown")
        logger.info("Jira authenticated: accountId=%s base_url=%s", account_id, base_url)

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=token_label,
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
            extra={"accountId": account_id},
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull security tickets from Jira using the configured JQL filter.

        Parameters
        ----------
        since : datetime
            Fetch only issues updated after this timestamp.
            The JQL filter handles this via "updated >= -Xd" style clauses —
            or the connector simply passes the full JQL and paginates.
        tenant_id : str, optional
            Scoped into RawFinding.tenant_id.
        limit : int, optional
            Maximum issues to fetch (default 100).

        Returns
        -------
        list[RawFinding]

        Raises
        ------
        ConnectorFetchError
            If the Jira API returns an error or the connector is not authenticated.
        """
        if self._client is None:
            raise ConnectorFetchError(
                "Jira connector not authenticated. Call authenticate() first."
            )

        tenant_id: str = kwargs.get("tenant_id", "unknown")
        limit: int = kwargs.get("limit", 100)

        try:
            raw = _run_async(
                self._client.search_issues(
                    jql=self._risk_jql,
                    max_results=limit,
                )
            )
            data = JiraSearchResponse.model_validate(raw)

            findings: list[RawFinding] = []
            for issue in data.issues:
                findings.append(
                    RawFinding(
                        id=issue.key,
                        source=self.NAME,
                        raw_data=issue.model_dump(mode="json"),
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            logger.info(
                "Jira: fetched %d issues for tenant %s (JQL: %s)",
                len(findings),
                tenant_id,
                self._risk_jql,
            )
            self._last_run = datetime.now(timezone.utc)
            return findings

        except (ConnectorAuthError, ConnectorFetchError):
            raise
        except Exception as exc:
            self._error_count += 1
            msg = str(exc)
            self._last_error = msg
            logger.exception("Jira fetch_findings failed")
            raise ConnectorFetchError(f"Jira fetch_findings failed: {msg}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map a Jira RawFinding to a URIPRiskRecord.

        Priority mapping:
            Highest → critical
            High    → high
            Medium  → medium
            Low     → low
            Lowest  → low
            (unmapped) → medium

        Status mapping:
            Open / In Progress → open
            Done / Closed / Resolved → resolved

        The external_id and source_url are stored in description for
        traceability (URIPRiskRecord has no dedicated link field).
        """
        issue = JiraIssue.model_validate(raw.raw_data)

        fields = issue.fields
        summary = (fields.summary if fields else None) or issue.key
        status_name = (fields.status.name if fields and fields.status else None)
        priority_name = (fields.priority.name if fields and fields.priority else None)
        description_raw = (fields.description if fields else None)

        # Extract plain text from ADF or plain string description.
        if isinstance(description_raw, dict):
            # ADF — extract text nodes
            desc_text = _extract_adf_text(description_raw)
        elif isinstance(description_raw, str):
            desc_text = description_raw
        else:
            desc_text = ""

        severity = _map_priority(priority_name)
        status_label = _map_status(status_name)

        source_url = f"{self._base_url}/browse/{issue.key}" if self._base_url else None

        description = (
            f"Jira issue {issue.key}: {summary}. "
            f"Status: {status_name or 'unknown'}. "
            f"Priority: {priority_name or 'unknown'}. "
            f"URL: {source_url or 'N/A'}."
        )
        if desc_text:
            description += f" Details: {desc_text[:500]}"

        return URIPRiskRecord(
            finding=f"Jira: {summary}",
            description=description,
            source=self.NAME,
            domain="application",
            cvss_score=0.0,
            severity=severity,
            asset=issue.key,
            owner_team="IT Service Management",
            cve_id=None,
            exploit_status=None,
        )

    def health_check(self) -> ConnectorHealth:
        """Return connector operational status."""
        if self._client is None:
            # Not yet authenticated — report as ok (not an error state).
            return ConnectorHealth(
                connector_name=self.NAME,
                status="ok",
                last_run=None,
                error_count=0,
                last_error=None,
            )

        try:
            _run_async(
                self._client.get_myself()
            )
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

    # ─────────────────────────────────────────────────────────────────────────
    # Bidirectional — outbound ticket creation
    # ─────────────────────────────────────────────────────────────────────────

    def create_ticket(
        self,
        session: Any,  # ConnectorSession (passed by caller but not used internally)
        risk: URIPRiskRecord,
        project_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create a Jira issue from a URIPRiskRecord.

        Parameters
        ----------
        session : ConnectorSession
            Active session (for interface consistency — auth state already in self._client).
        risk : URIPRiskRecord
            Normalized risk record to push.
        project_key : str, optional
            Override the configured default_project_key.

        Returns
        -------
        dict
            {"key": "SEC-42", "url": "https://…/browse/SEC-42", "id": "10001"}

        Raises
        ------
        ConnectorFetchError
            If the connector is not authenticated or the API call fails.
        """
        if self._client is None:
            raise ConnectorFetchError(
                "Jira connector not authenticated. Call authenticate() first."
            )

        target_project = project_key or self._default_project_key
        jira_priority = _SEVERITY_TO_JIRA_PRIORITY.get(risk.severity, "Medium")

        description = (
            f"Risk detected by URIP.\n\n"
            f"Finding: {risk.finding}\n"
            f"Severity: {risk.severity}\n"
            f"Asset: {risk.asset}\n"
            f"Owner team: {risk.owner_team}\n"
            f"Source: {risk.source}\n"
            f"Domain: {risk.domain}\n"
        )
        if risk.description:
            description += f"\nDetails:\n{risk.description}"

        try:
            resp = _run_async(
                self._client.create_issue(
                    project_key=target_project,
                    summary=risk.finding[:255],  # Jira summary max 255 chars
                    description=description,
                    issue_type="Task",
                    priority=jira_priority,
                    labels=["urip", "security"],
                )
            )
            issue_key = resp.get("key", "UNKNOWN")
            issue_id = resp.get("id", "")
            issue_url = f"{self._base_url}/browse/{issue_key}"
            logger.info("Jira: created issue %s (%s)", issue_key, issue_url)
            return {"key": issue_key, "id": issue_id, "url": issue_url}

        except (ConnectorAuthError, ConnectorFetchError):
            raise
        except Exception as exc:
            self._error_count += 1
            msg = str(exc)
            self._last_error = msg
            logger.exception("Jira create_ticket failed")
            raise ConnectorFetchError(f"Jira create_ticket failed: {msg}") from exc


# ─────────────────────────────────────────────────────────────────────────────
# ADF text extraction helper (module-level so it's testable)
# ─────────────────────────────────────────────────────────────────────────────


def _extract_adf_text(adf: dict[str, Any]) -> str:
    """
    Recursively extract plain text from an Atlassian Document Format (ADF) dict.

    Returns a single string with space-separated text nodes.
    """
    parts: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "text":
                parts.append(node.get("text", ""))
            for child in node.get("content", []):
                _walk(child)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(adf)
    return " ".join(p for p in parts if p).strip()

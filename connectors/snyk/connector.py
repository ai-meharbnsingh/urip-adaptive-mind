"""
connectors/snyk/connector.py — Snyk SCA / Container / IaC / Code connector for URIP.

Implements the BaseConnector contract:
  authenticate   → verify org access via GET /rest/orgs/{org_id}
  fetch_findings → pull vulnerability issues via GET /rest/orgs/{org_id}/issues
  normalize      → maps SnykIssue → URIPRiskRecord
  health_check   → operational status

Snyk REST API reference (v2024-10-15):
  https://apidocs.snyk.io/?version=2024-10-15
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

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
from connectors.snyk.api_client import SnykAPIClient
from connectors.snyk.schemas import SnykIssue

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _run_async(coro: Any) -> Any:
    """
    Run a coroutine from synchronous code using asyncio.run().

    Matches the canonical pattern from connectors/jira/connector.py:
    asyncio.run() always creates a fresh event loop — compatible with
    Python 3.10+ where get_event_loop() raises in non-async contexts.
    """
    return asyncio.run(coro)


# Snyk effective_severity_level → URIP severity
_SEVERITY_MAP: dict[str, str] = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
}

# Snyk scan type (project/issue type) → URIP source tag
_SOURCE_TYPE_MAP: dict[str, str] = {
    # Open Source (SCA)
    "npm": "snyk:open_source",
    "maven": "snyk:open_source",
    "gradle": "snyk:open_source",
    "pip": "snyk:open_source",
    "poetry": "snyk:open_source",
    "pipenv": "snyk:open_source",
    "yarn": "snyk:open_source",
    "nuget": "snyk:open_source",
    "rubygems": "snyk:open_source",
    "composer": "snyk:open_source",
    "gomodules": "snyk:open_source",
    "govendor": "snyk:open_source",
    "golang": "snyk:open_source",
    "hex": "snyk:open_source",
    "sbt": "snyk:open_source",
    "paket": "snyk:open_source",
    "open_source": "snyk:open_source",
    # Container
    "docker": "snyk:container",
    "apk": "snyk:container",
    "deb": "snyk:container",
    "rpm": "snyk:container",
    "container": "snyk:container",
    # IaC
    "k8sconfig": "snyk:iac",
    "helmconfig": "snyk:iac",
    "terraformconfig": "snyk:iac",
    "cloudformationconfig": "snyk:iac",
    "armconfig": "snyk:iac",
    "iac": "snyk:iac",
    # Snyk Code (SAST)
    "sast": "snyk:code",
    "code": "snyk:code",
}

# Snyk app base URL (used to build source_url for issue deep-links)
_SNYK_APP_URL = "https://app.snyk.io"


def _map_severity(snyk_severity: str | None) -> str:
    """Map Snyk effective_severity_level → URIP severity string."""
    return _SEVERITY_MAP.get((snyk_severity or "").lower(), "medium")


def _map_source_type(issue_type: str | None) -> str:
    """Map Snyk issue/project type → URIP source tag."""
    return _SOURCE_TYPE_MAP.get((issue_type or "").lower(), "snyk:open_source")


def _extract_cve(problems: list[Any]) -> Optional[str]:
    """Return the first CVE ID from an issue's problems list, or None."""
    for problem in problems:
        pid = (problem.id if hasattr(problem, "id") else problem.get("id", "")) or ""
        if pid.upper().startswith("CVE-"):
            return pid.upper()
    return None


def _extract_package(coordinates: list[Any]) -> Optional[str]:
    """Return the first package_name from coordinates[].representations[], or None."""
    for coord in coordinates:
        reps = coord.representations if hasattr(coord, "representations") else []
        for rep in reps:
            dep = rep.dependency if hasattr(rep, "dependency") else None
            if dep:
                pkg = (
                    dep.package_name
                    if hasattr(dep, "package_name")
                    else dep.get("package_name")
                )
                if pkg:
                    return pkg
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Connector class
# ─────────────────────────────────────────────────────────────────────────────


@register_connector("snyk")
class SnykConnector(BaseConnector):
    """
    Live connector for Snyk Open Source, Container, IaC, and Code scanning.

    Data flow
    ---------
    1. Authenticate via GET /rest/orgs/{org_id} (verifies token + org access).
    2. Fetch vulnerability issues using GET /rest/orgs/{org_id}/issues with
       cursor-based pagination and optional severity filter.
    3. Normalize each SnykIssue to a URIPRiskRecord.

    Supported products
    ------------------
    - Snyk Open Source (SCA — dependency vulnerabilities)
    - Snyk Container (container image SCA)
    - Snyk IaC (infrastructure-as-code misconfiguration)
    - Snyk Code — Standard / Enterprise (SAST)

    Auth
    ----
    API token from Snyk → Account Settings → API Token.
    Bearer token format: ``Authorization: token {api_token}``
    """

    NAME = "snyk"
    DISPLAY_NAME = "Snyk"
    CATEGORY = "DAST"
    STATUS = "live"
    MODULE_CODE = "DAST"
    RISK_INDEX_DOMAIN = "application"

    SHORT_DESCRIPTION = (
        "Open-source dependency scanning + container image SCA + IaC scanning. "
        "Pulls vulnerability findings from your monitored projects."
    )
    VENDOR_DOCS_URL = "https://docs.snyk.io/snyk-api/snyk-rest-api"
    SUPPORTED_PRODUCTS = [
        "Snyk Open Source",
        "Snyk Container",
        "Snyk IaC",
        "Snyk Code (Standard / Enterprise)",
    ]

    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="org_id",
            label="Snyk Organization ID (UUID)",
            type="text",
            required=True,
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            help_text="Snyk → Settings → General → Organization ID",
        ),
        CredentialFieldSpec(
            name="api_token",
            label="API Token",
            type="password",
            required=True,
            secret=True,
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            help_text="Snyk → Account Settings → API Token",
        ),
        CredentialFieldSpec(
            name="api_url",
            label="API URL",
            type="url",
            required=True,
            default="https://api.snyk.io",
            placeholder="https://api.snyk.io",
            help_text=(
                "Override for Snyk EU (api.eu.snyk.io) or Snyk AU "
                "(api.au.snyk.io)"
            ),
        ),
        CredentialFieldSpec(
            name="severity_filter",
            label="Minimum severity to ingest (comma-sep)",
            type="text",
            required=True,
            default="critical,high",
            placeholder="critical,high",
            help_text="Snyk severities: critical|high|medium|low",
        ),
    ]

    SETUP_GUIDE = SETUP_GUIDES.get("snyk")

    # ─────────────────────────────────────────────────────────────────────────
    # Constructor
    # ─────────────────────────────────────────────────────────────────────────

    def __init__(self) -> None:
        self._client: SnykAPIClient | None = None
        self._org_id: str = ""
        self._api_url: str = "https://api.snyk.io"
        self._severity_filter: list[str] = ["critical", "high"]
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    # ─────────────────────────────────────────────────────────────────────────
    # BaseConnector contract
    # ─────────────────────────────────────────────────────────────────────────

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate Snyk credentials by calling GET /rest/orgs/{org_id}.

        Required credential keys:
            - org_id    : Snyk organization UUID
            - api_token : Snyk API token
        Optional:
            - api_url         : Override for non-US tenants (default https://api.snyk.io)
            - severity_filter : Comma-separated severity levels (default "critical,high")

        Returns
        -------
        ConnectorSession

        Raises
        ------
        ConnectorAuthError
            If credentials are missing or Snyk rejects them.
        """
        org_id = tenant_credentials.get("org_id", "").strip()
        api_token = tenant_credentials.get("api_token", "").strip()

        if not org_id:
            raise ConnectorAuthError(
                "Snyk credentials must include 'org_id' (Organization UUID)."
            )
        if not api_token:
            raise ConnectorAuthError(
                "Snyk credentials must include 'api_token'."
            )

        api_url = tenant_credentials.get("api_url", "https://api.snyk.io").strip()
        severity_raw = tenant_credentials.get("severity_filter", "critical,high").strip()
        severity_filter = [s.strip() for s in severity_raw.split(",") if s.strip()]

        self._org_id = org_id
        self._api_url = api_url
        self._severity_filter = severity_filter or ["critical", "high"]

        self._client = SnykAPIClient(
            org_id=org_id,
            api_token=api_token,
            api_url=api_url,
        )

        # Verify access by calling healthcheck (GET /rest/orgs/{org_id}).
        try:
            org_data = _run_async(self._client.healthcheck())
        except ConnectorAuthError:
            raise
        except Exception as exc:
            raise ConnectorAuthError(
                f"Snyk authentication probe failed: {exc}"
            ) from exc

        org_name = (
            (org_data.get("data") or {})
            .get("attributes", {})
            .get("name", "unknown")
        )
        logger.info(
            "Snyk authenticated: org_id=%s org_name=%s api_url=%s",
            org_id,
            org_name,
            api_url,
        )

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token="snyk-token-****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
            extra={"org_id": org_id, "org_name": org_name},
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull vulnerability findings from Snyk for the configured organization.

        Parameters
        ----------
        since : datetime
            Fetch only issues created/updated after this timestamp.
        tenant_id : str, optional
            Scoped into RawFinding.tenant_id.
        limit : int, optional
            Per-page limit (default 100, max 1000 total due to cap).

        Returns
        -------
        list[RawFinding]

        Raises
        ------
        ConnectorFetchError
            If the Snyk API returns an error or the connector is not authenticated.
        """
        if self._client is None:
            raise ConnectorFetchError(
                "Snyk connector not authenticated. Call authenticate() first."
            )

        tenant_id: str = kwargs.get("tenant_id", "unknown")
        limit: int = kwargs.get("limit", 100)

        try:
            raw_issues = _run_async(
                self._client.list_issues(
                    since=since,
                    severity=self._severity_filter,
                    limit=limit,
                )
            )

            findings: list[RawFinding] = []
            for item in raw_issues:
                issue = SnykIssue.model_validate(item)
                findings.append(
                    RawFinding(
                        id=issue.id,
                        source=self.NAME,
                        raw_data=item,
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            logger.info(
                "Snyk: fetched %d findings for tenant %s (org=%s severity=%s)",
                len(findings),
                tenant_id,
                self._org_id,
                self._severity_filter,
            )
            self._last_run = datetime.now(timezone.utc)
            return findings

        except (ConnectorAuthError, ConnectorFetchError):
            raise
        except Exception as exc:
            self._error_count += 1
            msg = str(exc)
            self._last_error = msg
            logger.exception("Snyk fetch_findings failed")
            raise ConnectorFetchError(f"Snyk fetch_findings failed: {msg}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map a Snyk RawFinding to a URIPRiskRecord.

        Severity mapping:
            critical → critical
            high     → high
            medium   → medium
            low      → low
            (unmapped) → medium

        Source mapping (by issue/project type):
            open_source / npm / pip / maven / … → "snyk:open_source"
            docker / apk / deb / rpm / …        → "snyk:container"
            k8sconfig / terraformconfig / …     → "snyk:iac"
            sast / code                          → "snyk:code"

        CVE: extracted from attributes.problems[].id where id starts with "CVE-".

        source_url: deep-link to the Snyk issue in the UI.
        """
        issue = SnykIssue.model_validate(raw.raw_data)
        attrs = issue.attributes

        title = attrs.title or issue.id
        severity = _map_severity(attrs.effective_severity_level)
        source_tag = _map_source_type(attrs.type)
        cve_id = _extract_cve(attrs.problems)
        package_name = _extract_package(attrs.coordinates)

        # Build project_id from relationships if present.
        project_id: Optional[str] = None
        relationships = issue.relationships or {}
        project_rel = relationships.get("scan_item") or relationships.get("project") or {}
        project_data = project_rel.get("data") or {}
        if isinstance(project_data, dict):
            project_id = project_data.get("id")

        # Deep-link to the Snyk issue UI.
        source_url: Optional[str] = None
        if project_id:
            source_url = (
                f"{_SNYK_APP_URL}/org/{self._org_id}"
                f"/project/{project_id}#issue-{issue.id}"
            )

        # Build asset label from package name if available.
        asset = package_name or issue.id

        description_parts = [
            f"Snyk issue {issue.id}: {title}.",
            f"Severity: {attrs.effective_severity_level or 'unknown'}.",
        ]
        if cve_id:
            description_parts.append(f"CVE: {cve_id}.")
        if package_name:
            description_parts.append(f"Package: {package_name}.")
        if source_url:
            description_parts.append(f"URL: {source_url}.")

        return URIPRiskRecord(
            finding=f"Snyk: {title}",
            description=" ".join(description_parts),
            source=source_tag,
            domain="application",
            cvss_score=0.0,
            severity=severity,
            asset=asset,
            owner_team="Application Security",
            cve_id=cve_id,
            exploit_status=None,
        )

    def health_check(self) -> ConnectorHealth:
        """Return connector operational status."""
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

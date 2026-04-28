"""
Burp Suite Enterprise connector for URIP.

Implements the BaseConnector contract:
  authenticate   → validates API key
  fetch_findings → pulls scan findings (XSS, SQLi, etc.) per application target
  normalize      → maps Burp findings → URIPRiskRecord
  health_check   → returns operational status
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

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
from connectors.burp_enterprise.api_client import BurpEnterpriseAPIClient
from connectors.burp_enterprise.schemas import (
    BurpIssue,
    BurpListResponse,
    BurpScan,
)

logger = logging.getLogger(__name__)

SEVERITY_MAP = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "info": "low",
}


def _map_severity(raw: str | None) -> str:
    return SEVERITY_MAP.get((raw or "").lower(), "medium")


@register_connector("burp_enterprise")
class BurpEnterpriseConnector(BaseConnector):
    """
    Live connector for Burp Suite Enterprise (DAST).

    Data flow
    ---------
    1. Authenticate with base_url + api_key.
    2. Fetch scans (/api/v2/scans).
    3. For each scan, fetch issues (/api/v2/scans/{id}/issues).
    4. Normalize each to URIPRiskRecord.
    """

    NAME = "burp_enterprise"
    # DAST connector — feeds the Applications domain bucket but is NOT in one
    # of the 3 Cyber Risk Index sub-indexes per task spec.
    RISK_INDEX_DOMAIN = None

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "Burp Suite Enterprise"
    CATEGORY = "DAST"
    SHORT_DESCRIPTION = (
        "DAST scan findings including XSS, SQLi, and other application vulnerabilities from Burp Suite Enterprise."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://portswigger.net/burp/documentation/enterprise/api"
    SUPPORTED_PRODUCTS = None
    MODULE_CODE = "DAST"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="base_url", label="API Endpoint", type="url",
            required=True,
            placeholder="https://burp-enterprise.example.com",
            help_text="Burp Suite Enterprise server URL.",
            pattern=r"^https://[^\s]+$",
        ),
        CredentialFieldSpec(
            name="api_key", label="API Key", type="password",
            required=True, secret=True,
            placeholder="key-abc123…",
            help_text="Burp Enterprise API key from Settings → API.",
        ),
        CredentialFieldSpec(
            name="max_requests_per_hour", label="Max requests / hour",
            type="number", required=False, default=1000,
            help_text="Burp Enterprise API rate-limit ceiling.",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["burp_enterprise"]

    def __init__(self) -> None:
        self._client: BurpEnterpriseAPIClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate Burp Suite Enterprise credentials.

        Required credential keys:
            - base_url
            - api_key
        """
        base_url = tenant_credentials.get("base_url")
        api_key = tenant_credentials.get("api_key")

        if not base_url:
            raise ConnectorAuthError("Burp Enterprise credentials must include 'base_url'")
        if not api_key:
            raise ConnectorAuthError("Burp Enterprise credentials must include 'api_key'")

        max_requests_per_hour = tenant_credentials.get("max_requests_per_hour", 1000)
        self._client = BurpEnterpriseAPIClient(
            base_url=str(base_url),
            api_key=str(api_key),
            max_requests_per_hour=int(max_requests_per_hour),
        )

        if not self._client.validate_auth():
            raise ConnectorAuthError(
                "Burp Enterprise authentication failed: invalid API key or insufficient permissions"
            )

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"burp-{str(api_key)[:4]}****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull DAST scan findings.

        Parameters
        ----------
        since : datetime
            Fetch only findings created/updated after this time.
        tenant_id : str, optional
            Scoped into RawFinding.tenant_id.
        max_scans : int, optional
            Cap the number of scans inspected per tick (default 10).
        """
        if self._client is None:
            raise ConnectorFetchError(
                "Connector not authenticated. Call authenticate() first."
            )

        tenant_id: str = kwargs.get("tenant_id", "unknown")
        max_scans: int = kwargs.get("max_scans", 10)
        findings: list[RawFinding] = []

        try:
            # ── Scans ───────────────────────────────────────────────────
            scans_resp = self._client.list_scans(limit=max_scans, offset=0)
            scans_data = BurpListResponse.model_validate(scans_resp)

            # ── Per-scan issues ─────────────────────────────────────────
            for scan_item in scans_data.data:
                scan_id = scan_item.get("id")
                if not scan_id:
                    continue
                issues_resp = self._client.list_issues(scan_id=scan_id)
                issues_data = BurpListResponse.model_validate(issues_resp)
                for issue_item in issues_data.data:
                    issue_item["scan_id"] = scan_id
                    issue_item["target_url"] = scan_item.get("target_url")
                    raw_id = f"{scan_id}:{issue_item.get('id', 'unknown')}"
                    findings.append(
                        RawFinding(
                            id=raw_id,
                            source=self.NAME,
                            raw_data={**issue_item, "category": "issue"},
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )

            logger.info(
                "Burp Enterprise: fetched %d findings for tenant %s",
                len(findings),
                tenant_id,
            )
            self._last_run = datetime.now(timezone.utc)
            return findings

        except Exception as exc:
            self._error_count += 1
            msg = str(exc)
            if hasattr(exc, "response") and exc.response is not None:
                try:
                    body = exc.response.json()
                    if isinstance(body, dict) and "error" in body:
                        msg = f"{msg} — {body['error']}"
                except Exception:
                    pass
            self._last_error = msg
            logger.exception("Burp Enterprise fetch_findings failed")
            raise ConnectorFetchError(f"Burp Enterprise fetch failed: {msg}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map a Burp Enterprise RawFinding to URIPRiskRecord.
        """
        data = raw.raw_data
        issue = BurpIssue.model_validate(data)

        severity = _map_severity(issue.severity)
        finding = f"DAST: {issue.issue_type or 'Unknown Issue'}"
        description = (
            f"Burp Suite Enterprise detected {issue.issue_type or 'unknown'} "
            f"at {issue.url or 'unknown URL'} (path: {issue.path or 'unknown'}). "
            f"Confidence: {issue.confidence or 'unknown'}."
        )
        if issue.description:
            description += f" Details: {issue.description}"

        asset = issue.url or issue.scan_id or "unknown"

        return URIPRiskRecord(
            finding=finding,
            description=description,
            source=self.NAME,
            domain="application",
            cvss_score=0.0,
            severity=severity,
            asset=asset,
            owner_team="Application Security",
            cve_id=None,
            exploit_status=None,
        )

    def health_check(self) -> ConnectorHealth:
        """Return connector operational status."""
        status = "ok"
        if self._error_count > 0:
            status = "degraded" if self._error_count < 5 else "error"

        return ConnectorHealth(
            connector_name=self.NAME,
            status=status,
            last_run=self._last_run,
            error_count=self._error_count,
            last_error=self._last_error,
        )

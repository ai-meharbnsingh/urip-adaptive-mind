"""
Bug Bounty connector for URIP (HackerOne + Bugcrowd).

Implements the BaseConnector contract:
  authenticate   → API token validation per platform
  fetch_findings → pull reports with severity P1/P2/P3/P4
  normalize      → maps report → URIPRiskRecord
  health_check   → returns operational status

Also exposes webhook ingest:
  ingest_webhook(payload, tenant_id) → URIPRiskRecord
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
from connectors.bug_bounty.api_client import BugcrowdAPIClient, HackerOneAPIClient

logger = logging.getLogger(__name__)

# HackerOne severity: critical / high / medium / low
# Bugcrowd priority: 1 (P1) / 2 (P2) / 3 (P3) / 4 (P4)
SEVERITY_MAP = {
    "critical": ("critical", 9.0),
    "high": ("high", 7.0),
    "medium": ("medium", 5.0),
    "low": ("low", 3.0),
    1: ("critical", 9.0),
    2: ("high", 7.0),
    3: ("medium", 5.0),
    4: ("low", 3.0),
    "p1": ("critical", 9.0),
    "p2": ("high", 7.0),
    "p3": ("medium", 5.0),
    "p4": ("low", 3.0),
}


def _map_bug_bounty_severity(native: Any) -> tuple[str, float]:
    if isinstance(native, str):
        native = native.lower().strip()
    return SEVERITY_MAP.get(native, ("medium", 5.0))


@register_connector("bug_bounty")
class BugBountyConnector(BaseConnector):
    """
    Live connector for Bug Bounty (HackerOne + Bugcrowd).

    Data flow
    ---------
    1. authenticate → validate API token.
    2. fetch_findings → pull reports/submissions.
    3. normalize → map each report to URIPRiskRecord.
    4. ingest_webhook → real-time push creates Risk record directly.
    """

    NAME = "bug_bounty"
    # Bug bounty findings feed the Application domain bucket but are NOT in
    # one of the 3 Cyber Risk Index sub-indexes per task spec.
    RISK_INDEX_DOMAIN = None

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["bug_bounty"]
    DISPLAY_NAME = "Bug Bounty"
    # CATEGORY must be in CONNECTOR_CATEGORIES (connectors/base/connector.py).
    # Bug bounty connectors ship under the BUG_BOUNTY bucket in the Tool Catalog.
    CATEGORY = "BUG_BOUNTY"
    SHORT_DESCRIPTION = (
        "Ingests vulnerability reports from HackerOne and Bugcrowd via API and webhooks."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://api.hackerone.com/customer-resources"
    SUPPORTED_PRODUCTS = ["HackerOne", "Bugcrowd", "Generic webhook (Intigriti / YesWeHack / inbound)"]
    MODULE_CODE = "BUG_BOUNTY"
    CREDENTIAL_FIELDS: list[CredentialFieldSpec] = [
        CredentialFieldSpec(
            name="platform",
            label="Platform",
            type="select",
            required=True,
            options=[
                {"value": "hackerone", "label": "HackerOne"},
                {"value": "bugcrowd", "label": "Bugcrowd"},
                {"value": "webhook", "label": "Generic webhook"},
            ],
        ),
        CredentialFieldSpec(name="api_token", label="API token (HackerOne / Bugcrowd)", type="password", required=False, secret=True),
        CredentialFieldSpec(name="program_handle", label="Program handle / slug", type="text", required=False),
        CredentialFieldSpec(name="webhook_secret", label="Webhook HMAC secret (generic webhook mode)", type="password", required=False, secret=True),
    ]

    def __init__(self) -> None:
        self._client: HackerOneAPIClient | BugcrowdAPIClient | None = None
        self._platform: str = ""
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate Bug Bounty credentials based on platform.

        Required credential keys:
            - platform  (hackerone | bugcrowd)
        Per-platform:
            - HackerOne: api_token + optional program_handle
            - Bugcrowd: api_token
        Optional:
            - tenant_id
        """
        platform = (tenant_credentials.get("platform") or "").lower()
        if not platform:
            raise ConnectorAuthError("Bug Bounty credentials must include 'platform'")
        if platform not in {"hackerone", "bugcrowd"}:
            raise ConnectorAuthError(f"Unsupported bug_bounty platform: {platform}")

        self._platform = platform

        if platform == "hackerone":
            api_token = tenant_credentials.get("api_token")
            if not api_token:
                raise ConnectorAuthError("HackerOne credentials require 'api_token'")
            program_handle = tenant_credentials.get("program_handle")
            self._client = HackerOneAPIClient(
                api_token=str(api_token),
                program_handle=program_handle,
            )
            if not self._client.validate_auth():
                raise ConnectorAuthError("HackerOne authentication failed")

        elif platform == "bugcrowd":
            api_token = tenant_credentials.get("api_token")
            if not api_token:
                raise ConnectorAuthError("Bugcrowd credentials require 'api_token'")
            self._client = BugcrowdAPIClient(api_token=str(api_token))
            if not self._client.validate_auth():
                raise ConnectorAuthError("Bugcrowd authentication failed")

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"bug_bounty-{platform}",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull bug bounty reports since `since`.

        Parameters
        ----------
        since : datetime
            Fetch only reports submitted after this timestamp.
        tenant_id : str, optional
            Scoped into RawFinding.tenant_id.
        """
        if self._client is None:
            raise ConnectorFetchError(
                "Connector not authenticated. Call authenticate() first."
            )

        tenant_id: str = kwargs.get("tenant_id", "unknown")
        since_iso = since.isoformat() if since else None
        findings: list[RawFinding] = []

        try:
            if self._platform == "hackerone":
                reports = self._client.list_reports(since=since_iso)
                for report in reports:
                    report["platform"] = "hackerone"
                    findings.append(
                        RawFinding(
                            id=report.get("id") or str(hash(str(report))),
                            source=self.NAME,
                            raw_data=report,
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )
            elif self._platform == "bugcrowd":
                submissions = self._client.list_submissions(since=since_iso)
                for sub in submissions:
                    sub["platform"] = "bugcrowd"
                    findings.append(
                        RawFinding(
                            id=sub.get("id") or str(hash(str(sub))),
                            source=self.NAME,
                            raw_data=sub,
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )

            logger.info(
                "Bug Bounty (%s): fetched %d findings for tenant %s",
                self._platform,
                len(findings),
                tenant_id,
            )
            self._last_run = datetime.now(timezone.utc)
            return findings

        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("Bug Bounty fetch_findings failed")
            raise ConnectorFetchError(f"Bug Bounty fetch failed: {exc}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map a Bug Bounty RawFinding to URIPRiskRecord.

        Mappings
        --------
        platform                → source suffix
        HackerOne severity      → severity + cvss_score
        Bugcrowd priority       → severity + cvss_score
        remediation_recommendation → included in description
        """
        data = raw.raw_data
        platform = data.get("platform", "unknown")

        if platform == "hackerone":
            attrs = data.get("attributes", {})
            title = attrs.get("title", "HackerOne Report")
            severity_rating = attrs.get("severity", {}).get("rating") if isinstance(attrs.get("severity"), dict) else attrs.get("severity")
            state = attrs.get("state", "unknown")
            weakness = attrs.get("weakness", {}).get("name") if isinstance(attrs.get("weakness"), dict) else attrs.get("weakness")
            scope = attrs.get("structured_scope", {})
            asset = scope.get("asset_identifier") if isinstance(scope, dict) else None
            remediation = None

        elif platform == "bugcrowd":
            attrs = data.get("attributes", {})
            title = attrs.get("title", "Bugcrowd Submission")
            severity_rating = attrs.get("priority")
            state = attrs.get("state", "unknown")
            weakness = attrs.get("vrt_lineage", [None])[0] if isinstance(attrs.get("vrt_lineage"), list) else attrs.get("vrt_lineage")
            target = attrs.get("target", {})
            asset = target.get("name") if isinstance(target, dict) else None
            remediation = attrs.get("remediation_recommendation")

        else:
            title = "Bug Bounty Report"
            severity_rating = "medium"
            state = "unknown"
            weakness = None
            asset = None
            remediation = None

        sev, cvss = _map_bug_bounty_severity(severity_rating)

        description_parts = [f"Bug Bounty {platform} report — State: {state}"]
        if weakness:
            description_parts.append(f"Weakness: {weakness}")
        if remediation:
            description_parts.append(f"Remediation: {remediation}")
        description = "\n".join(description_parts)

        return URIPRiskRecord(
            finding=title,
            description=description,
            source=f"bug_bounty:{platform}",
            domain="application",
            cvss_score=cvss,
            severity=sev,
            asset=asset or "Unknown Asset",
            owner_team="Bug Bounty",
            cve_id=None,
            exploit_status=None,
        )

    def ingest_webhook(self, payload: dict[str, Any], tenant_id: str = "unknown") -> URIPRiskRecord:
        """
        Ingest a real-time webhook payload from HackerOne or Bugcrowd.

        Expected payload shape:
        {
            "platform": "hackerone" | "bugcrowd",
            "report": { ...raw report object... }
        }
        """
        platform = (payload.get("platform") or "").lower()
        if platform not in {"hackerone", "bugcrowd"}:
            raise ConnectorFetchError(f"Webhook ingest unsupported platform: {platform}")

        report = payload.get("report", {})
        report["platform"] = platform

        raw = RawFinding(
            id=report.get("id") or str(hash(str(report))),
            source=self.NAME,
            raw_data=report,
            fetched_at=datetime.now(timezone.utc),
            tenant_id=tenant_id,
        )
        return self.normalize(raw)

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

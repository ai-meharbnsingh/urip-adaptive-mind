"""
GitHub Advanced Security (GHAS) connector for URIP.

Implements the BaseConnector contract:
  authenticate   → Verify PAT + org access via GET /orgs/{org}
  fetch_findings → Pull code-scanning + secret-scanning + Dependabot alerts
  normalize      → Map each alert type → URIPRiskRecord
  health_check   → Operational status

GHAS covers three distinct security surfaces:
  - Code Scanning  (SAST — CodeQL + 3rd-party tools)
  - Secret Scanning (credentials + tokens committed to repos)
  - Dependabot     (SCA — vulnerable dependencies)

All three are surfaced as separate source types so the URIP dashboard can
split or aggregate them:
  source: "ghas:code"      — code scanning
  source: "ghas:secret"    — secret scanning
  source: "ghas:dependabot" — Dependabot SCA

Category mapping note:
  GHAS is SAST + secret-scanning + SCA.  URIP does not yet have a dedicated
  "AppSec" module, so we map to CATEGORY="DAST" / MODULE_CODE="DAST" as the
  closest existing module (application-layer security findings).

References
----------
GitHub REST API: https://docs.github.com/en/rest
GHAS features:   https://docs.github.com/en/code-security/getting-started/github-security-features
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
from connectors.ghas.api_client import GhasAPIClient
from connectors.ghas.schemas import (
    GhasCodeScanningAlert,
    GhasDependabotAlert,
    GhasSecretScanningAlert,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Severity mapping
# ─────────────────────────────────────────────────────────────────────────────

# GHAS rule.security_severity_level → URIP severity
_SECURITY_SEVERITY_MAP: dict[str, str] = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
}

# GHAS rule.severity (tool/linter level) → URIP severity (fallback when
# security_severity_level is absent — e.g. informational/style rules)
_RULE_SEVERITY_MAP: dict[str, str] = {
    "error": "high",
    "warning": "medium",
    "note": "low",
    "none": "low",
}


def _map_code_scanning_severity(
    security_severity_level: str | None,
    rule_severity: str | None,
) -> str:
    """
    Derive URIP severity from a code-scanning alert's rule metadata.

    Priority:
    1. rule.security_severity_level  ("critical" | "high" | "medium" | "low")
    2. rule.severity                 ("error" | "warning" | "note")
    3. fallback → "medium"
    """
    if security_severity_level:
        mapped = _SECURITY_SEVERITY_MAP.get(security_severity_level.lower())
        if mapped:
            return mapped
    if rule_severity:
        mapped = _RULE_SEVERITY_MAP.get(rule_severity.lower())
        if mapped:
            return mapped
    return "medium"


# ─────────────────────────────────────────────────────────────────────────────
# Connector class
# ─────────────────────────────────────────────────────────────────────────────


@register_connector("ghas")
class GhasConnector(BaseConnector):
    """
    Live connector for GitHub Advanced Security (GHAS).

    Data flow
    ---------
    1. Authenticate via GET /orgs/{org} (verifies token + org access).
    2. Fetch code-scanning + secret-scanning + Dependabot alerts in parallel.
    3. Normalize each alert to URIPRiskRecord.
       - Code scanning:  severity from rule.security_severity_level or rule.severity.
       - Secret scanning: always severity="critical" (any leaked secret is critical).
       - Dependabot:     severity from security_advisory.severity.

    Supported products
    ------------------
    - GitHub Advanced Security on GitHub Enterprise Cloud
    - GHAS on GitHub Enterprise Server (>=3.7)

    Auth
    ----
    Bearer token — classic PAT or fine-grained PAT.
    Required scopes: security_events, read:org
    """

    NAME = "ghas"

    # ── Tool Catalog metadata ───────────────────────────────────────────────
    DISPLAY_NAME = "GitHub Advanced Security"
    CATEGORY = "DAST"
    SHORT_DESCRIPTION = (
        "Code scanning + secret scanning + Dependabot SCA across your GitHub organization. "
        "Cross-correlate code vulnerabilities with runtime exposure."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://docs.github.com/en/code-security/getting-started/github-security-features"
    SUPPORTED_PRODUCTS = [
        "GitHub Advanced Security on GitHub Enterprise Cloud",
        "GHAS on GitHub Enterprise Server (>=3.7)",
    ]
    MODULE_CODE = "DAST"
    RISK_INDEX_DOMAIN = "application"

    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="org",
            label="GitHub Organization",
            type="text",
            required=True,
            placeholder="your-org",
            help_text=(
                "GitHub organization slug — the name that appears in your org URL "
                "(e.g. 'acme-corp' from https://github.com/acme-corp)."
            ),
        ),
        CredentialFieldSpec(
            name="token",
            label="Personal Access Token or GitHub App token",
            type="password",
            required=True,
            secret=True,
            placeholder="ghp_…",
            help_text=(
                "Required scopes: security_events, read:org. "
                "Classic PAT: Settings → Developer settings → Personal access tokens. "
                "Fine-grained PAT: ensure 'Code scanning alerts', 'Secret scanning alerts', "
                "and 'Dependabot alerts' read permissions are granted."
            ),
        ),
        CredentialFieldSpec(
            name="api_url",
            label="GitHub API URL",
            type="url",
            required=True,
            default="https://api.github.com",
            placeholder="https://api.github.com",
            help_text=(
                "Leave as default for GitHub.com. "
                "For GitHub Enterprise Server, use: https://github.your-company.com/api/v3"
            ),
        ),
    ]

    # Inline onboarding content
    SETUP_GUIDE = SETUP_GUIDES.get("ghas")

    # ─────────────────────────────────────────────────────────────────────────
    # Constructor
    # ─────────────────────────────────────────────────────────────────────────

    def __init__(self) -> None:
        self._client: GhasAPIClient | None = None
        self._org: str = ""
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    # ─────────────────────────────────────────────────────────────────────────
    # BaseConnector contract
    # ─────────────────────────────────────────────────────────────────────────

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate GHAS credentials by calling GET /orgs/{org}.

        Required credential keys:
            - org      : GitHub organization name
            - token    : PAT or GitHub App token
            - api_url  : GitHub API root URL (default https://api.github.com)

        Returns
        -------
        ConnectorSession
            Session with token set to "ghas-bearer-****".

        Raises
        ------
        ConnectorAuthError
            If credentials are missing, the token is invalid, or the org does
            not exist / is not accessible.
        """
        org = tenant_credentials.get("org", "").strip()
        token = tenant_credentials.get("token", "").strip()
        api_url = tenant_credentials.get("api_url", "https://api.github.com").strip()

        if not org:
            raise ConnectorAuthError("GHAS credentials must include 'org'.")
        if not token:
            raise ConnectorAuthError("GHAS credentials must include 'token'.")
        if not api_url:
            api_url = "https://api.github.com"

        self._org = org
        self._client = GhasAPIClient(org=org, token=token, api_url=api_url)

        try:
            org_data = _run_async(self._client.healthcheck())
        except ConnectorAuthError:
            raise
        except ConnectorFetchError:
            raise
        except Exception as exc:
            raise ConnectorAuthError(
                f"GHAS authentication probe failed: {exc}"
            ) from exc

        org_login = org_data.get("login", org)
        logger.info("GHAS authenticated: org=%s api_url=%s", org_login, api_url)

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token="ghas-bearer-****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
            extra={"org": org_login},
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull all three GHAS alert types.

        Parameters
        ----------
        since : datetime
            Fetch only alerts updated at or after this timestamp.
        tenant_id : str, optional
            Scoped into RawFinding.tenant_id.

        Returns
        -------
        list[RawFinding]
            Combined code-scanning + secret-scanning + Dependabot findings.

        Raises
        ------
        ConnectorFetchError
            If the connector is not authenticated or any GitHub API call fails.
        """
        if self._client is None:
            raise ConnectorFetchError(
                "GHAS connector not authenticated. Call authenticate() first."
            )

        tenant_id: str = kwargs.get("tenant_id", "unknown")

        try:
            code_alerts = _run_async(
                self._client.list_code_scanning_alerts(since=since)
            )
            secret_alerts = _run_async(
                self._client.list_secret_scanning_alerts(since=since)
            )
            dependabot_alerts = _run_async(
                self._client.list_dependabot_alerts(since=since)
            )
        except (ConnectorAuthError, ConnectorFetchError):
            raise
        except Exception as exc:
            self._error_count += 1
            msg = str(exc)
            self._last_error = msg
            logger.exception("GHAS fetch_findings failed")
            raise ConnectorFetchError(f"GHAS fetch_findings failed: {msg}") from exc

        findings: list[RawFinding] = []
        now = datetime.now(timezone.utc)

        for alert in code_alerts:
            findings.append(
                RawFinding(
                    id=f"ghas:code:{alert.get('number', 'unknown')}",
                    source="ghas:code",
                    raw_data=alert,
                    fetched_at=now,
                    tenant_id=tenant_id,
                )
            )

        for alert in secret_alerts:
            findings.append(
                RawFinding(
                    id=f"ghas:secret:{alert.get('number', 'unknown')}",
                    source="ghas:secret",
                    raw_data=alert,
                    fetched_at=now,
                    tenant_id=tenant_id,
                )
            )

        for alert in dependabot_alerts:
            findings.append(
                RawFinding(
                    id=f"ghas:dependabot:{alert.get('number', 'unknown')}",
                    source="ghas:dependabot",
                    raw_data=alert,
                    fetched_at=now,
                    tenant_id=tenant_id,
                )
            )

        logger.info(
            "GHAS: fetched %d code-scanning, %d secret-scanning, %d dependabot alerts "
            "for tenant %s (org=%s)",
            len(code_alerts),
            len(secret_alerts),
            len(dependabot_alerts),
            tenant_id,
            self._org,
        )
        self._last_run = now
        return findings

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map a GHAS RawFinding to a URIPRiskRecord.

        Source routing:
          "ghas:code"       → GhasCodeScanningAlert
          "ghas:secret"     → GhasSecretScanningAlert  (always critical)
          "ghas:dependabot" → GhasDependabotAlert      (advisory.severity)
        """
        source = raw.source
        if source == "ghas:code":
            return self._normalize_code_scanning(raw)
        elif source == "ghas:secret":
            return self._normalize_secret_scanning(raw)
        elif source == "ghas:dependabot":
            return self._normalize_dependabot(raw)
        else:
            # Fallback — unknown sub-source, normalize as generic GHAS finding.
            logger.warning("GHAS normalize: unknown source '%s' — normalizing as code-scanning", source)
            return self._normalize_code_scanning(raw)

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

    # ─────────────────────────────────────────────────────────────────────────
    # Private normalization helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _normalize_code_scanning(self, raw: RawFinding) -> URIPRiskRecord:
        """Normalize a code-scanning alert → URIPRiskRecord."""
        alert = GhasCodeScanningAlert.model_validate(raw.raw_data)

        rule = alert.rule
        rule_id = (rule.id if rule else None) or "unknown-rule"
        security_severity = rule.security_severity_level if rule else None
        rule_severity = rule.severity if rule else None
        severity = _map_code_scanning_severity(security_severity, rule_severity)

        # File path from most recent instance
        file_path = None
        if alert.most_recent_instance and alert.most_recent_instance.location:
            file_path = alert.most_recent_instance.location.path

        asset = file_path or f"org:{self._org}"
        source_url = alert.html_url or ""

        finding = f"Code scanning: {rule_id}"
        description = (
            f"GitHub code-scanning alert #{alert.number} ({alert.state}). "
            f"Rule: {rule_id}. "
            f"Severity: {security_severity or rule_severity or 'unknown'}. "
            f"File: {file_path or 'unknown'}. "
            f"URL: {source_url}"
        )

        return URIPRiskRecord(
            finding=finding,
            description=description,
            source=raw.source,
            domain="application",
            cvss_score=0.0,
            severity=severity,
            asset=asset,
            owner_team="Application Security",
            cve_id=None,
            exploit_status=None,
        )

    def _normalize_secret_scanning(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Normalize a secret-scanning alert → URIPRiskRecord.

        Always severity="critical" — any leaked secret must be rotated immediately.
        """
        alert = GhasSecretScanningAlert.model_validate(raw.raw_data)

        secret_type = alert.secret_type_display_name or alert.secret_type or "Unknown secret type"
        source_url = alert.html_url or ""

        finding = f"Secret leaked: {secret_type}"
        description = (
            f"GitHub secret-scanning alert #{alert.number} ({alert.state}). "
            f"Secret type: {secret_type}. "
            f"This secret must be rotated immediately. "
            f"URL: {source_url}"
        )

        return URIPRiskRecord(
            finding=finding,
            description=description,
            source=raw.source,
            domain="application",
            cvss_score=0.0,
            severity="critical",   # always critical — leaked secrets are P0
            asset=f"org:{self._org}",
            owner_team="Application Security",
            cve_id=None,
            exploit_status="active",  # treat as actively exploitable until rotated
        )

    def _normalize_dependabot(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Normalize a Dependabot (SCA) alert → URIPRiskRecord.

        Severity comes from security_advisory.severity.
        """
        alert = GhasDependabotAlert.model_validate(raw.raw_data)

        advisory = alert.security_advisory
        vuln = alert.security_vulnerability

        advisory_severity = (advisory.severity if advisory else None) or "medium"
        severity = _SECURITY_SEVERITY_MAP.get(advisory_severity.lower(), "medium")

        package_name = (
            vuln.package.name if (vuln and vuln.package) else "unknown-package"
        )
        vuln_range = (vuln.vulnerable_version_range if vuln else None) or "unknown"
        advisory_summary = (advisory.summary if advisory else None) or ""
        cve_id = (advisory.cve_id if advisory else None)
        source_url = alert.html_url or ""

        asset = f"dep:{package_name}"
        finding = f"Dependabot: {package_name} ({vuln_range})"
        description = (
            f"GitHub Dependabot alert #{alert.number} ({alert.state}). "
            f"Package: {package_name}. "
            f"Vulnerable range: {vuln_range}. "
            f"Advisory severity: {advisory_severity}. "
            f"{advisory_summary + '. ' if advisory_summary else ''}"
            f"URL: {source_url}"
        )

        return URIPRiskRecord(
            finding=finding,
            description=description,
            source=raw.source,
            domain="application",
            cvss_score=advisory.cvss_score if (advisory and advisory.cvss_score) else 0.0,
            severity=severity,
            asset=asset,
            owner_team="Application Security",
            cve_id=cve_id,
            exploit_status=None,
        )

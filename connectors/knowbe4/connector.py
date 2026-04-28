"""
KnowBe4 connector for URIP.

Implements the BaseConnector contract:
  authenticate   → validates API key via /v1/account
  fetch_findings → pulls training enrollments + phishing simulation recipients;
                   emits a finding for each user whose training is incomplete OR
                   who clicked a phishing simulation.
  normalize      → maps a KnowBe4 raw finding → URIPRiskRecord. Adds the
                   compliance-citation phrase ("ISO 27001 A.6.3 / SOC 2 CC1.4")
                   to the description so the compliance module can cross-link
                   the finding to the right control without a second lookup.
  health_check   → returns operational status

Why this connector treats incomplete training as a control failure:
  - ISO 27001:2022 Annex A.6.3 — Information security awareness, education
    and training requires ALL personnel to be trained on org policies +
    threats. An incomplete training enrollment means a user has not met that
    obligation.
  - SOC 2 Trust Services Criteria CC1.4 — The entity demonstrates a
    commitment to attract, develop, and RETAIN COMPETENT individuals in
    alignment with objectives. Security training is the primary evidence
    for CC1.4.

A failed phishing simulation (clicked, did not report) is a separate signal:
the user is currently susceptible. That's a higher-severity finding because it
indicates *current* risky behaviour, not just missing paperwork.
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
from connectors.knowbe4.api_client import KnowBe4APIClient, DEFAULT_BASE_URL

logger = logging.getLogger(__name__)


# Status values that count as INCOMPLETE training (i.e., still a finding).
INCOMPLETE_TRAINING_STATUSES = {"in_progress", "past_due", "not_started", "enrolled"}

# Compliance citation block — appended to every URIPRiskRecord description so
# the compliance module + auditor portal can show it without a second query.
COMPLIANCE_CITATION = (
    "Maps to compliance controls: ISO 27001:2022 A.6.3 (Awareness, education "
    "and training); SOC 2 CC1.4 (Demonstrate commitment to competent personnel)."
)


@register_connector("knowbe4")
class KnowBe4Connector(BaseConnector):
    """
    Live connector for KnowBe4 (security awareness training + phishing simulations).

    Data flow
    ---------
    1. authenticate → validate API key with GET /v1/account.
    2. fetch_findings → pull training enrollments + phishing recipients;
       emit a finding for each user whose training is incomplete or who
       clicked a phishing simulation.
    3. normalize → map each finding to URIPRiskRecord with compliance citations.
    """

    NAME = "knowbe4"
    RISK_INDEX_DOMAIN = None  # Compliance / awareness signal, not Cyber Risk Index.

    DISPLAY_NAME = "KnowBe4 Security Awareness"
    CATEGORY = "LMS"
    SHORT_DESCRIPTION = (
        "Pulls training completion + phishing simulation results from "
        "KnowBe4 to evidence ISO 27001 A.6.3 / SOC 2 CC1.4 controls."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://developer.knowbe4.com/reference/getting-started"
    SUPPORTED_PRODUCTS = ["KnowBe4 Reporting API"]
    MODULE_CODE = "CORE"

    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="api_key",
            label="API Key",
            type="password",
            required=True,
            secret=True,
            help_text=(
                "KnowBe4 → Account Settings → API Access → Generate New Token."
            ),
        ),
        CredentialFieldSpec(
            name="api_base",
            label="API Base URL",
            type="url",
            required=False,
            default=DEFAULT_BASE_URL,
            placeholder=DEFAULT_BASE_URL,
            help_text=(
                "https://us.api.knowbe4.com (default) or "
                "https://eu.api.knowbe4.com for the EU pod."
            ),
            pattern=r"^https://[^\s]+$",
        ),
    ]

    SETUP_GUIDE = SETUP_GUIDES["knowbe4"]

    def __init__(self) -> None:
        self._client: KnowBe4APIClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    # ─────────────────────────────────────────────────────────────────────
    # authenticate
    # ─────────────────────────────────────────────────────────────────────

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        api_key = tenant_credentials.get("api_key") or tenant_credentials.get(
            "knowbe4_api_key"
        )
        if not api_key:
            raise ConnectorAuthError("KnowBe4 credentials must include 'api_key'")

        base_url = tenant_credentials.get("api_base", DEFAULT_BASE_URL)
        self._client = KnowBe4APIClient(api_key=str(api_key), base_url=str(base_url))

        if not self._client.validate_auth():
            raise ConnectorAuthError(
                "KnowBe4 authentication failed: invalid API key or insufficient tier"
            )

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"knowbe4-{str(api_key)[:4]}****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    # ─────────────────────────────────────────────────────────────────────
    # fetch_findings
    # ─────────────────────────────────────────────────────────────────────

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        if self._client is None:
            raise ConnectorFetchError(
                "Connector not authenticated. Call authenticate() first."
            )

        tenant_id: str = kwargs.get("tenant_id", "unknown")
        since_iso: str | None = since.isoformat() if since else None
        findings: list[RawFinding] = []

        try:
            # Training enrollments — emit ONLY incomplete ones.
            enrollments = self._client.list_training_enrollments(since_iso)
            for enr in enrollments:
                status = (enr.get("status") or "").lower()
                if status in INCOMPLETE_TRAINING_STATUSES:
                    enr["_kind"] = "training_incomplete"
                    findings.append(
                        RawFinding(
                            id=str(enr.get("id", "")),
                            source=self.NAME,
                            raw_data=enr,
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )

            # Phishing recipients — emit users who CLICKED but did NOT report.
            recipients = self._client.list_phishing_recipients(since_iso)
            for r in recipients:
                if r.get("clicked") and not r.get("reported"):
                    r["_kind"] = "phishing_failed"
                    findings.append(
                        RawFinding(
                            id=str(r.get("id", "")),
                            source=self.NAME,
                            raw_data=r,
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )

            self._last_run = datetime.now(timezone.utc)
            logger.info(
                "KnowBe4: fetched %d findings (incomplete training + failed phishing) "
                "for tenant %s",
                len(findings),
                tenant_id,
            )
            return findings

        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("KnowBe4 fetch_findings failed")
            raise ConnectorFetchError(f"KnowBe4 fetch failed: {exc}") from exc

    # ─────────────────────────────────────────────────────────────────────
    # normalize
    # ─────────────────────────────────────────────────────────────────────

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        kind = raw.raw_data.get("_kind", "")
        data = raw.raw_data

        if kind == "phishing_failed":
            user = data.get("user", {})
            email = user.get("email") or data.get("user_email", "unknown")
            campaign = data.get("campaign_name") or data.get("campaign", "")
            finding = f"Failed phishing simulation: {campaign or 'unnamed campaign'}"
            description = (
                f"User {email} clicked a phishing simulation email and did not "
                f"report it. Campaign: {campaign}. {COMPLIANCE_CITATION}"
            )
            severity = "high"
            cvss = 6.5
        else:
            # training_incomplete (default)
            user = data.get("user", {})
            email = user.get("email") or data.get("user_email", "unknown")
            module = data.get("module_name", "unnamed module")
            status = data.get("status", "incomplete")
            finding = f"Incomplete security awareness training: {module}"
            description = (
                f"User {email} has training status '{status}' for module "
                f"'{module}'. {COMPLIANCE_CITATION}"
            )
            # past_due is medium; in_progress is low. Default medium.
            severity = "medium" if status == "past_due" else "low" if status == "in_progress" else "medium"
            cvss = 4.0

        return URIPRiskRecord(
            finding=finding,
            description=description,
            source=self.NAME,
            domain="identity",
            cvss_score=cvss,
            severity=severity,
            asset=email,
            owner_team="Compliance",
        )

    # ─────────────────────────────────────────────────────────────────────
    # health_check
    # ─────────────────────────────────────────────────────────────────────

    def health_check(self) -> ConnectorHealth:
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

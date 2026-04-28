"""
Hoxhunt connector for URIP.

Hoxhunt is a phishing-training competitor to KnowBe4 with a behaviour-change
score (0.0–1.0) per user. URIP treats:
  - training_status != "active" as a finding (low engagement → ISO 27001 A.6.3)
  - simulation outcome == "clicked" as a finding (failed phishing test → high)

Compliance citations identical to KnowBe4 (ISO 27001 A.6.3 / SOC 2 CC1.4).
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
from connectors.hoxhunt.api_client import DEFAULT_BASE_URL, HoxhuntAPIClient

logger = logging.getLogger(__name__)


COMPLIANCE_CITATION = (
    "Maps to compliance controls: ISO 27001:2022 A.6.3 (Awareness, education "
    "and training); SOC 2 CC1.4 (Demonstrate commitment to competent personnel)."
)

# Hoxhunt training statuses that count as INACTIVE / low engagement.
INACTIVE_TRAINING_STATUSES = {"inactive", "paused", "lapsed"}


@register_connector("hoxhunt")
class HoxhuntConnector(BaseConnector):
    NAME = "hoxhunt"
    RISK_INDEX_DOMAIN = None

    DISPLAY_NAME = "Hoxhunt Phishing Training"
    CATEGORY = "LMS"
    SHORT_DESCRIPTION = (
        "Pulls phishing-training engagement + behaviour-change scores from "
        "Hoxhunt to evidence ISO 27001 A.6.3 / SOC 2 CC1.4."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://help.hoxhunt.com/en/articles/api-overview"
    SUPPORTED_PRODUCTS = ["Hoxhunt"]
    MODULE_CODE = "CORE"

    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="api_token",
            label="API Token",
            type="password",
            required=True,
            secret=True,
            help_text="Hoxhunt → Settings → Integrations → API Tokens → Create.",
        ),
        CredentialFieldSpec(
            name="api_base",
            label="API Base URL",
            type="url",
            required=False,
            default=DEFAULT_BASE_URL,
            placeholder=DEFAULT_BASE_URL,
            help_text="Override only for region-specific Hoxhunt pods.",
            pattern=r"^https://[^\s]+$",
        ),
    ]

    SETUP_GUIDE = SETUP_GUIDES["hoxhunt"]

    def __init__(self) -> None:
        self._client: HoxhuntAPIClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    # ─────────────────────────────────────────────────────────────────────

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        token = tenant_credentials.get("api_token") or tenant_credentials.get(
            "hoxhunt_api_token"
        )
        if not token:
            raise ConnectorAuthError("Hoxhunt credentials must include 'api_token'")
        base_url = tenant_credentials.get("api_base", DEFAULT_BASE_URL)
        self._client = HoxhuntAPIClient(api_token=str(token), base_url=str(base_url))
        if not self._client.validate_auth():
            raise ConnectorAuthError(
                "Hoxhunt authentication failed: invalid token or insufficient scope"
            )
        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"hoxhunt-{str(token)[:4]}****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    # ─────────────────────────────────────────────────────────────────────

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        if self._client is None:
            raise ConnectorFetchError(
                "Connector not authenticated. Call authenticate() first."
            )
        tenant_id = kwargs.get("tenant_id", "unknown")
        since_iso = since.isoformat() if since else None
        findings: list[RawFinding] = []

        try:
            users = self._client.list_users(since_iso)
            for u in users:
                status = (u.get("training_status") or "").lower()
                if status in INACTIVE_TRAINING_STATUSES:
                    u["_kind"] = "training_inactive"
                    findings.append(
                        RawFinding(
                            id=str(u.get("id", "")),
                            source=self.NAME,
                            raw_data=u,
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )

            sims = self._client.list_simulation_responses(since_iso)
            for s in sims:
                if s.get("outcome") == "clicked":
                    s["_kind"] = "phishing_failed"
                    findings.append(
                        RawFinding(
                            id=str(s.get("id", "")),
                            source=self.NAME,
                            raw_data=s,
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )

            self._last_run = datetime.now(timezone.utc)
            return findings

        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("Hoxhunt fetch_findings failed")
            raise ConnectorFetchError(f"Hoxhunt fetch failed: {exc}") from exc

    # ─────────────────────────────────────────────────────────────────────

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        kind = raw.raw_data.get("_kind", "")
        data = raw.raw_data

        if kind == "phishing_failed":
            email = data.get("user_email", "unknown")
            campaign = data.get("campaign", "")
            finding = f"Failed phishing simulation: {campaign or 'unnamed campaign'}"
            description = (
                f"User {email} clicked a Hoxhunt simulation. Campaign: {campaign}. "
                f"{COMPLIANCE_CITATION}"
            )
            severity = "high"
            cvss = 6.5
        else:
            email = data.get("email", "unknown")
            score = data.get("behaviour_score", 0.0)
            status = data.get("training_status", "inactive")
            finding = f"Inactive security awareness training (Hoxhunt)"
            description = (
                f"User {email} has training status '{status}' and behaviour score "
                f"{score}. {COMPLIANCE_CITATION}"
            )
            severity = "medium" if score < 0.3 else "low"
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

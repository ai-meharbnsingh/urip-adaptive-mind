"""
AuthBridge connector for URIP.

AuthBridge is an Indian background-verification (BGV) provider. URIP treats
incomplete BGV (status != "completed") as a control failure for:

  HIPAA — 45 CFR § 164.308(a)(1)(ii)(B) — Risk management standard requires
          implementing security measures sufficient to reduce risks to a
          reasonable level. Workforce screening (BGV) is one such measure
          per § 164.308(a)(3) (Workforce security).

The connector emits a finding for every verification whose status is NOT
"completed" — both pending and explicitly failed verifications surface as
risks, with failed BGVs at higher severity.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from connectors.authbridge.api_client import AuthBridgeAPIClient, DEFAULT_BASE_URL
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

logger = logging.getLogger(__name__)


COMPLIANCE_CITATION = (
    "Maps to compliance controls: HIPAA 45 CFR §164.308(a)(1)(ii)(B) (Risk "
    "management) and §164.308(a)(3) (Workforce security / sanction policy). "
    "Incomplete BGV indicates the workforce-screening safeguard has not been "
    "fully implemented for this employee."
)


@register_connector("authbridge")
class AuthBridgeConnector(BaseConnector):
    NAME = "authbridge"
    RISK_INDEX_DOMAIN = None

    DISPLAY_NAME = "AuthBridge BGV"
    CATEGORY = "BGV"
    SHORT_DESCRIPTION = (
        "Pulls per-employee Background Verification (BGV) status from "
        "AuthBridge. Incomplete BGV cited as a HIPAA §164.308 finding."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://www.authbridge.com/products/api/"
    SUPPORTED_PRODUCTS = ["AuthBridge BGV"]
    MODULE_CODE = "CORE"

    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="api_token",
            label="API Token",
            type="password",
            required=True,
            secret=True,
            help_text="Issued by your AuthBridge account manager.",
        ),
        CredentialFieldSpec(
            name="api_base",
            label="API Base URL",
            type="url",
            required=False,
            default=DEFAULT_BASE_URL,
            placeholder=DEFAULT_BASE_URL,
            pattern=r"^https://[^\s]+$",
        ),
    ]

    SETUP_GUIDE = SETUP_GUIDES["authbridge"]

    def __init__(self) -> None:
        self._client: AuthBridgeAPIClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    # ─────────────────────────────────────────────────────────────────────

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        token = tenant_credentials.get("api_token") or tenant_credentials.get(
            "authbridge_api_token"
        )
        if not token:
            raise ConnectorAuthError(
                "AuthBridge credentials must include 'api_token'"
            )
        base_url = tenant_credentials.get("api_base", DEFAULT_BASE_URL)
        self._client = AuthBridgeAPIClient(api_token=str(token), base_url=str(base_url))
        if not self._client.validate_auth():
            raise ConnectorAuthError(
                "AuthBridge authentication failed: invalid token or IP not allow-listed"
            )
        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"authbridge-{str(token)[:4]}****",
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
            verifications = self._client.list_verifications(since_iso)
            for v in verifications:
                status = (v.get("status") or "").lower()
                # Anything that is NOT completed surfaces as a finding.
                if status != "completed":
                    findings.append(
                        RawFinding(
                            id=str(v.get("id", "")),
                            source=self.NAME,
                            raw_data=v,
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )

            self._last_run = datetime.now(timezone.utc)
            logger.info(
                "AuthBridge: fetched %d incomplete-BGV findings for tenant %s",
                len(findings),
                tenant_id,
            )
            return findings

        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("AuthBridge fetch_findings failed")
            raise ConnectorFetchError(f"AuthBridge fetch failed: {exc}") from exc

    # ─────────────────────────────────────────────────────────────────────

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        data = raw.raw_data
        email = data.get("employee_email", "unknown")
        name = data.get("employee_name", email)
        status = (data.get("status") or "").lower()

        if status == "failed":
            finding = f"Failed background verification: {name}"
            description = (
                f"BGV for {name} ({email}) returned status FAILED. "
                f"{COMPLIANCE_CITATION}"
            )
            severity = "high"
            cvss = 7.0
        else:
            pending = data.get("checks_pending") or []
            pending_str = ", ".join(pending) if pending else "in progress"
            finding = f"Incomplete background verification: {name}"
            description = (
                f"BGV for {name} ({email}) is incomplete (status={status!r}). "
                f"Outstanding checks: {pending_str}. {COMPLIANCE_CITATION}"
            )
            severity = "medium"
            cvss = 5.0

        return URIPRiskRecord(
            finding=finding,
            description=description,
            source=self.NAME,
            domain="identity",
            cvss_score=cvss,
            severity=severity,
            asset=email,
            owner_team="HR / Compliance",
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

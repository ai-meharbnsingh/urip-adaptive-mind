"""
OnGrid connector for URIP — alternative BGV provider to AuthBridge.

OnGrid provides Aadhaar / PAN / address / criminal verification. URIP treats
verification_status != "verified" as a control failure for HIPAA §164.308.
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
from connectors.ongrid.api_client import DEFAULT_BASE_URL, OnGridAPIClient

logger = logging.getLogger(__name__)


COMPLIANCE_CITATION = (
    "Maps to compliance controls: HIPAA 45 CFR §164.308(a)(1)(ii)(B) (Risk "
    "management) and §164.308(a)(3) (Workforce security). Incomplete BGV "
    "indicates the workforce-screening safeguard has not been fully "
    "implemented for this employee."
)


@register_connector("ongrid")
class OnGridConnector(BaseConnector):
    NAME = "ongrid"
    RISK_INDEX_DOMAIN = None

    DISPLAY_NAME = "OnGrid BGV"
    CATEGORY = "BGV"
    SHORT_DESCRIPTION = (
        "Pulls per-candidate Background Verification status from OnGrid. "
        "Incomplete BGV cited as a HIPAA §164.308 finding."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://docs.ongrid.in/"
    SUPPORTED_PRODUCTS = ["OnGrid Verifications"]
    MODULE_CODE = "CORE"

    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="api_key",
            label="API Key",
            type="password",
            required=True,
            secret=True,
            help_text="OnGrid console → Settings → API → Generate new key.",
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

    SETUP_GUIDE = SETUP_GUIDES["ongrid"]

    def __init__(self) -> None:
        self._client: OnGridAPIClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    # ─────────────────────────────────────────────────────────────────────

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        api_key = tenant_credentials.get("api_key") or tenant_credentials.get(
            "ongrid_api_key"
        )
        if not api_key:
            raise ConnectorAuthError("OnGrid credentials must include 'api_key'")
        base_url = tenant_credentials.get("api_base", DEFAULT_BASE_URL)
        self._client = OnGridAPIClient(api_key=str(api_key), base_url=str(base_url))
        if not self._client.validate_auth():
            raise ConnectorAuthError(
                "OnGrid authentication failed: invalid API key or insufficient tier"
            )
        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"ongrid-{str(api_key)[:4]}****",
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
            checks = self._client.list_checks(since_iso)
            for c in checks:
                vs = (c.get("verification_status") or "").lower()
                # Anything except "verified" is a finding.
                if vs != "verified":
                    findings.append(
                        RawFinding(
                            id=str(c.get("id", "")),
                            source=self.NAME,
                            raw_data=c,
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )

            self._last_run = datetime.now(timezone.utc)
            logger.info(
                "OnGrid: fetched %d incomplete-BGV findings for tenant %s",
                len(findings),
                tenant_id,
            )
            return findings

        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("OnGrid fetch_findings failed")
            raise ConnectorFetchError(f"OnGrid fetch failed: {exc}") from exc

    # ─────────────────────────────────────────────────────────────────────

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        data = raw.raw_data
        email = data.get("candidate_email", "unknown")
        name = data.get("candidate_name", email)
        status = (data.get("verification_status") or "").lower()

        if status == "rejected":
            reason = data.get("rejection_reason", "")
            finding = f"Rejected background verification: {name}"
            description = (
                f"BGV for {name} ({email}) was REJECTED. Reason: {reason}. "
                f"{COMPLIANCE_CITATION}"
            )
            severity = "high"
            cvss = 7.0
        else:
            remaining = data.get("checks_remaining") or []
            remaining_str = ", ".join(remaining) if remaining else "in progress"
            finding = f"Incomplete background verification: {name}"
            description = (
                f"BGV for {name} ({email}) is incomplete "
                f"(verification_status={status!r}). Outstanding checks: "
                f"{remaining_str}. {COMPLIANCE_CITATION}"
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

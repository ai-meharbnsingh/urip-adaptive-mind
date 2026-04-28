"""
Microsoft Entra ID (Azure AD) connector for URIP.

Implements the BaseConnector contract:
  authenticate   → OAuth2 client credentials flow
  fetch_findings → pulls riskyUsers, riskDetections, riskySignIns, CA policy results
  normalize      → maps Entra findings → URIPRiskRecord (with Identity Risk severity map)
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
from connectors.ms_entra.api_client import MsEntraAPIClient
from connectors.ms_entra.schemas import (
    MsEntraCAPolicyResult,
    MsEntraGraphListResponse,
    MsEntraRiskDetection,
    MsEntraRiskySignIn,
    MsEntraRiskyUser,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Identity Risk severity mapping (MASTER_BLUEPRINT Identity Risk carry-forward)
# ─────────────────────────────────────────────────────────────────────────────

IDENTITY_RISK_SEVERITY_MAP = {
    # critical
    "leakedcredentials": "critical",
    "leakedCredentials": "critical",
    "maliciousipaddress": "critical",
    "maliciousIPAddress": "critical",
    # high
    "mfafatigue": "high",
    "mfaFatigue": "high",
    "atypicaltravel": "high",
    "atypicalTravel": "high",
    # medium
    "anonymizedipaddress": "medium",
    "anonymizedIPAddress": "medium",
    "suspiciousapitraffic": "medium",
    "suspiciousAPITraffic": "medium",
}


def _map_risk_detection_severity(risk_event_type: str | None) -> str:
    """Map Entra riskEventType to URIP severity per Identity Risk table."""
    if not risk_event_type:
        return "medium"
    return IDENTITY_RISK_SEVERITY_MAP.get(risk_event_type, "medium")


def _map_generic_severity(raw: str | None) -> str:
    mapping = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}
    return mapping.get((raw or "").lower(), "medium")


@register_connector("ms_entra")
class MsEntraConnector(BaseConnector):
    """
    Live connector for Microsoft Entra ID (Identity Protection).

    Data flow
    ---------
    1. Authenticate with tenant_id + client_id + client_secret (OAuth2).
    2. Fetch risky users (/identityProtection/riskyUsers).
    3. Fetch risk detections (/identityProtection/riskDetections).
    4. Fetch risky sign-ins (/auditLogs/signIns?$filter=...).
    5. Fetch CA policy results (/identityProtection/conditionalAccessPolicyResults).
    6. Normalize each to URIPRiskRecord.
    """

    NAME = "ms_entra"
    RISK_INDEX_DOMAIN = "attack"

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "Microsoft Entra ID"
    CATEGORY = "IDENTITY"
    SHORT_DESCRIPTION = (
        "Risky users, sign-in detections, conditional-access drift from Entra Identity Protection."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = (
        "https://learn.microsoft.com/en-us/graph/api/resources/identityprotectionroot"
    )
    SUPPORTED_PRODUCTS = ["Identity Protection", "Conditional Access", "Sign-in Logs"]
    MODULE_CODE = "IDENTITY"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="tenant_id", label="Azure AD Tenant ID", type="uuid",
            required=True,
            placeholder="00000000-0000-0000-0000-000000000000",
            help_text="Azure portal → Microsoft Entra ID → Overview → Tenant ID.",
        ),
        CredentialFieldSpec(
            name="client_id", label="Application (Client) ID", type="uuid",
            required=True,
            placeholder="00000000-0000-0000-0000-000000000000",
            help_text="App registration's Application (client) ID.",
        ),
        CredentialFieldSpec(
            name="client_secret", label="Client Secret", type="password",
            required=True, secret=True,
            help_text="App registration → Certificates & secrets → Client secret.",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["ms_entra"]

    def __init__(self) -> None:
        self._client: MsEntraAPIClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate Microsoft Entra OAuth2 credentials.

        Required credential keys:
            - tenant_id
            - client_id
            - client_secret
        """
        tenant_id = tenant_credentials.get("tenant_id")
        client_id = tenant_credentials.get("client_id")
        client_secret = tenant_credentials.get("client_secret")

        if not tenant_id:
            raise ConnectorAuthError("MS Entra credentials must include 'tenant_id'")
        if not client_id:
            raise ConnectorAuthError("MS Entra credentials must include 'client_id'")
        if not client_secret:
            raise ConnectorAuthError("MS Entra credentials must include 'client_secret'")

        self._client = MsEntraAPIClient(
            tenant_id=str(tenant_id),
            client_id=str(client_id),
            client_secret=str(client_secret),
        )

        if not self._client.authenticate():
            raise ConnectorAuthError(
                "MS Entra authentication failed: invalid credentials or insufficient permissions"
            )

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=str(tenant_id),
            token=f"entra-{str(client_id)[:4]}****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull risky users, risk detections, risky sign-ins, and CA policy results.

        Parameters
        ----------
        since : datetime
            Fetch only findings created/updated after this time.
        tenant_id : str, optional
            Scoped into RawFinding.tenant_id.
        """
        if self._client is None:
            raise ConnectorFetchError(
                "Connector not authenticated. Call authenticate() first."
            )

        tenant_id: str = kwargs.get("tenant_id", "unknown")
        findings: list[RawFinding] = []

        try:
            # ── Risky users ─────────────────────────────────────────────
            users_resp = self._client.list_risky_users()
            users_data = MsEntraGraphListResponse.model_validate(users_resp)
            for item in users_data.value:
                findings.append(
                    RawFinding(
                        id=item.get("id", "unknown"),
                        source=self.NAME,
                        raw_data={**item, "category": "risky_user"},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            # ── Risk detections ─────────────────────────────────────────
            detections_resp = self._client.list_risk_detections()
            detections_data = MsEntraGraphListResponse.model_validate(detections_resp)
            for item in detections_data.value:
                findings.append(
                    RawFinding(
                        id=item.get("id", "unknown"),
                        source=self.NAME,
                        raw_data={**item, "category": "risk_detection"},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            # ── Risky sign-ins ──────────────────────────────────────────
            signins_resp = self._client.list_risky_signins()
            signins_data = MsEntraGraphListResponse.model_validate(signins_resp)
            for item in signins_data.value:
                findings.append(
                    RawFinding(
                        id=item.get("id", "unknown"),
                        source=self.NAME,
                        raw_data={**item, "category": "risky_signin"},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            # ── CA policy results ───────────────────────────────────────
            ca_resp = self._client.list_ca_policy_results()
            ca_data = MsEntraGraphListResponse.model_validate(ca_resp)
            for item in ca_data.value:
                findings.append(
                    RawFinding(
                        id=item.get("id", "unknown"),
                        source=self.NAME,
                        raw_data={**item, "category": "ca_policy"},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            logger.info(
                "MS Entra: fetched %d findings for tenant %s",
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
            logger.exception("MS Entra fetch_findings failed")
            raise ConnectorFetchError(f"MS Entra fetch failed: {msg}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map an MS Entra RawFinding to URIPRiskRecord.

        Handles four categories:
          1. risky_user     → identity domain, IAM owner
          2. risk_detection → identity domain, IAM owner, severity from riskEventType
          3. risky_signin   → identity domain, IAM owner
          4. ca_policy      → identity domain, IAM owner
        """
        data = raw.raw_data
        category = data.get("category", "risk_detection")
        upn = data.get("userPrincipalName") or "unknown-user"

        if category == "risky_user":
            user = MsEntraRiskyUser.model_validate(data)
            severity = _map_generic_severity(user.riskLevel)
            finding = f"Risky User: {upn}"
            description = (
                f"Microsoft Entra Identity Protection flagged user {upn} "
                f"as risky (state: {user.riskState or 'unknown'})."
            )

        elif category == "risk_detection":
            detection = MsEntraRiskDetection.model_validate(data)
            severity = _map_risk_detection_severity(detection.riskEventType)
            finding = f"Risk Detection: {detection.riskEventType or 'Unknown'}"
            description = (
                f"Microsoft Entra risk detection: {detection.riskEventType or 'Unknown'} "
                f"for user {upn}. Detected: {detection.detectedDateTime or 'N/A'}."
            )

        elif category == "risky_signin":
            signin = MsEntraRiskySignIn.model_validate(data)
            severity = _map_generic_severity(signin.riskLevelDuringSignIn)
            finding = f"Risky Sign-In: {upn}"
            description = (
                f"Microsoft Entra risky sign-in for user {upn}. "
                f"Risk level during sign-in: {signin.riskLevelDuringSignIn or 'unknown'}."
            )

        elif category == "ca_policy":
            ca = MsEntraCAPolicyResult.model_validate(data)
            severity = "high" if (ca.result or "").lower() == "failure" else "medium"
            finding = f"CA Policy Failure: {ca.policyName or 'Unknown'}"
            description = (
                f"Microsoft Entra Conditional Access policy '{ca.policyName or 'Unknown'}' "
                f"resulted in {ca.result or 'unknown'} for user {upn}."
            )

        else:
            finding = "Entra Identity Finding"
            description = "Unknown Entra finding category."
            severity = "medium"

        return URIPRiskRecord(
            finding=finding,
            description=description,
            source=self.NAME,
            domain="identity",
            cvss_score=0.0,
            severity=severity,
            asset=upn,
            owner_team="IAM",
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

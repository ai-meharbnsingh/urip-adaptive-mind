"""
CERT-In Advisories connector for URIP.

Implements the BaseConnector contract:
  authenticate   → no-op (public source); validate connectivity
  fetch_findings → advisories newer than 'since' via RSS + HTML fallback
  normalize      → maps CERT-In advisory → URIPRiskRecord
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
from connectors.cert_in.api_client import CertInAPIClient
from connectors.cert_in.schemas import CertInAdvisory

logger = logging.getLogger(__name__)

SEVERITY_MAP = {
    "Critical": ("critical", 9.0),
    "High": ("high", 7.5),
    "Medium": ("medium", 5.0),
    "Low": ("low", 3.0),
}


@register_connector("cert_in")
class CertInConnector(BaseConnector):
    """
    Live connector for CERT-In (India Computer Emergency Response Team) advisories.

    Data flow
    ---------
    1. authenticate → check CERT-In site connectivity (public, no credentials).
    2. fetch_findings → try RSS feed first; fall back to HTML scrape if empty/fails.
    3. normalize → map each advisory to URIPRiskRecord.
    """

    NAME = "cert_in"
    # Advisory feed — informational, not a sub-index source per task spec.
    RISK_INDEX_DOMAIN = None

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["cert_in"]
    DISPLAY_NAME = "CERT-In Advisories"
    # CATEGORY must be in CONNECTOR_CATEGORIES (connectors/base/connector.py).
    # CERT-In publishes advisory bulletins → ADVISORY is the matching slot.
    CATEGORY = "ADVISORY"
    SHORT_DESCRIPTION = (
        "Ingests public security advisories from India's CERT-In, including CVE mappings."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://www.cert-in.org.in/"
    SUPPORTED_PRODUCTS = ["CERT-In Vulnerability Notes", "CERT-In Advisory RSS Feed"]
    MODULE_CODE = "ADVISORY"
    CREDENTIAL_FIELDS: list[CredentialFieldSpec] = [
        CredentialFieldSpec(
            name="base_url",
            label="CERT-In base URL",
            type="url",
            required=False,
            default="https://www.cert-in.org.in",
            help_text="Override only if you mirror CERT-In internally.",
        ),
    ]

    def __init__(self) -> None:
        self._client: CertInAPIClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate connectivity to CERT-In (public source, no credentials required).

        Optional credential keys:
            - base_url    (default https://www.cert-in.org.in)
            - tenant_id
        """
        base_url = tenant_credentials.get("base_url", "https://www.cert-in.org.in")
        self._client = CertInAPIClient(base_url=str(base_url))

        if not self._client.validate_connectivity():
            raise ConnectorAuthError(
                "CERT-In connectivity check failed: site unreachable"
            )

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token="public",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull advisories newer than `since`.

        Strategy:
          1. Try RSS feed.
          2. If RSS returns empty or fails, fall back to HTML scrape.
          3. Filter by `since` locally.

        Parameters
        ----------
        since : datetime
            Only advisories published after this timestamp.
        tenant_id : str, optional
            Scoped into RawFinding.tenant_id.
        force_scrape : bool, optional
            Skip RSS and go straight to HTML scrape.
        """
        if self._client is None:
            raise ConnectorFetchError(
                "Connector not authenticated. Call authenticate() first."
            )

        tenant_id: str = kwargs.get("tenant_id", "unknown")
        force_scrape: bool = kwargs.get("force_scrape", False)
        findings: list[RawFinding] = []

        try:
            advisories: list[CertInAdvisory] = []

            if not force_scrape:
                try:
                    advisories = self._client.fetch_rss()
                    logger.info("CERT-In: fetched %d advisories from RSS", len(advisories))
                except Exception as exc:
                    logger.warning("CERT-In RSS fetch failed, falling back to scrape: %s", exc)
                    advisories = []

            if force_scrape or not advisories:
                advisories = self._client.fetch_scrape()
                logger.info("CERT-In: fetched %d advisories from scrape", len(advisories))

            for adv in advisories:
                # Time filter
                if adv.published_at and since.tzinfo is not None and adv.published_at.tzinfo is None:
                    adv.published_at = adv.published_at.replace(tzinfo=timezone(offset=__import__("datetime").timedelta(hours=5, minutes=30)))
                if adv.published_at and adv.published_at < since:
                    continue

                findings.append(
                    RawFinding(
                        id=adv.cert_in_id,
                        source=self.NAME,
                        raw_data=adv.model_dump(mode="json"),
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            self._last_run = datetime.now(timezone.utc)
            return findings

        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("CERT-In fetch_findings failed")
            raise ConnectorFetchError(f"CERT-In fetch failed: {exc}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map a CERT-In RawFinding to URIPRiskRecord.

        Mappings
        --------
        cert_in_id       → finding prefix
        severity         → severity + cvss_score via SEVERITY_MAP
        domain           → 'advisory'
        cve_refs[0]      → cve_id
        mitigation       → appended to description
        """
        data = raw.raw_data
        adv = CertInAdvisory.model_validate(data)

        severity_label, cvss = SEVERITY_MAP.get(adv.severity, ("medium", 5.0))

        description = adv.description or adv.title
        if adv.mitigation:
            description += f"\nMitigation: {adv.mitigation}"
        description += "\n[Indian regulatory provenance — CERT-In]"

        cve_id = adv.cve_refs[0] if adv.cve_refs else None

        return URIPRiskRecord(
            finding=adv.title,
            description=description,
            source=self.NAME,
            domain="advisory",
            cvss_score=cvss,
            severity=severity_label,
            asset=adv.affected_products[0] if adv.affected_products else "N/A",
            owner_team="Security Operations",
            cve_id=cve_id,
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

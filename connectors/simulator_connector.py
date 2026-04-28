"""
connectors/simulator_connector.py — Default (RE-flavored) simulator connector.

P1.6: Refactor backend/simulator.py to USE the connector framework.

Design decisions
----------------
- The original simulator.py is NOT moved (INV-0: no rm); it continues to work
  as a standalone CLI tool (--bulk, --continuous, --batch) for seeding data.
- This module registers as "simulator" in the global connector registry and
  exposes the same REAL_CVES data through the normalized URIPRiskRecord interface.
- REAL_CVES is imported from backend.simulator to avoid duplication (single source
  of truth).  Both paths — legacy CLI and new connector framework — use the same data.
- fetch_findings() accepts `count` kwarg (default: random 5–15) and `tenant_id` kwarg
  so the scheduler can scope data correctly.
- Backwards compatibility: simulator behavior is IDENTICAL — same CVEs, same domains,
  same asset lists.  Tests that check source names like "crowdstrike" continue to pass.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone
from typing import Optional

from connectors.base.connector import (
    BaseConnector,
    ConnectorHealth,
    ConnectorSession,
    CredentialFieldSpec,
    RawFinding,
    URIPRiskRecord,
)
from connectors.base.registry import register_connector
from connectors.base.setup_guides_data import SETUP_GUIDES

# Import REAL_CVES and ASSETS from the canonical simulator to avoid duplication
from backend.simulator import REAL_CVES, ASSETS, DOMAIN_TEAM


@register_connector("simulator")
class SimulatorConnector(BaseConnector):
    """
    Default RE-flavored simulator connector.

    Wraps backend.simulator's REAL_CVES dict through the connector framework
    contract.  Source labels match the original: crowdstrike, easm, cnapp,
    armis, vapt, threat_intel, cert_in, bug_bounty, soc.
    """

    NAME = "simulator"

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "Default Simulator"
    CATEGORY = "SIMULATOR"
    SHORT_DESCRIPTION = (
        "Synthetic finding stream covering 9 source labels — used for demos and tests."
    )
    STATUS = "simulated"
    VENDOR_DOCS_URL = None
    SUPPORTED_PRODUCTS = None
    MODULE_CODE = "CORE"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="tenant_id", label="Tenant Label", type="text", required=False,
            placeholder="default",
            help_text="Optional label attached to simulator runs (no real auth needed).",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["simulator"]

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "default"),
            token="simulator-no-auth-needed",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs) -> list[RawFinding]:
        count: int = kwargs.get("count", random.randint(5, 15))
        tenant_id: str = kwargs.get("tenant_id", "default")

        findings: list[RawFinding] = []
        for _ in range(count):
            source = random.choice(list(REAL_CVES.keys()))
            cve_id, title, cvss, severity, domain = random.choice(REAL_CVES[source])
            asset = random.choice(ASSETS[domain])
            owner = DOMAIN_TEAM[domain]

            raw_id = str(uuid.uuid4())
            findings.append(RawFinding(
                id=raw_id,
                source=source,
                raw_data={
                    "cve_id": cve_id,
                    "title": title,
                    "cvss": cvss,
                    "severity": severity,
                    "domain": domain,
                    "asset": asset,
                    "owner_team": owner,
                },
                fetched_at=datetime.now(timezone.utc),
                tenant_id=tenant_id,
            ))
        return findings

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        d = raw.raw_data
        cve_id = d["cve_id"]
        # Preserve original logic: custom IDs (EASM-*, CNAPP-*, etc.) → cve_id=None
        if cve_id and any(
            cve_id.startswith(pfx)
            for pfx in ("EASM-", "CNAPP-", "ARMIS-", "VAPT-", "TI-", "BB-", "SOC-")
        ):
            cve_id = None

        return URIPRiskRecord(
            finding=d["title"],
            description=(
                f"[{d['cve_id']}] {d['title']}. "
                f"Detected by {raw.source} connector. "
                f"Asset: {d['asset']}. Requires immediate triage."
            ),
            source=raw.source,
            domain=d["domain"],
            cvss_score=d["cvss"],
            severity=d["severity"],
            asset=d["asset"],
            owner_team=d["owner_team"],
            cve_id=cve_id,
        )

    def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_name=self.NAME,
            status="ok",
            last_run=datetime.now(timezone.utc),
            error_count=0,
        )

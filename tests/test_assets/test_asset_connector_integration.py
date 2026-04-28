"""
End-to-end integration tests:
connector finding → asset upsert → risk linked → asset_risk_score updated.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from connectors.base.connector import RawFinding, URIPRiskRecord

from backend.models.asset import Asset
from backend.models.risk import Risk
from backend.models.tenant import Tenant
from backend.services import asset_service
from backend.services.connector_runner import preprocess_connector_record


async def _make_tenant(db: AsyncSession, slug: str) -> Tenant:
    t = Tenant(
        id=uuid.uuid4(),
        name=f"Tenant {slug}",
        slug=slug,
        domain=f"{slug}.test",
        is_active=True,
        settings={},
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


def _build_finding(
    *,
    asset_label: str = "integ-host",
    cve: str | None = "CVE-2026-1000",
    mac: str | None = "aa:bb:cc:dd:ee:01",
    ip: str | None = "10.5.0.1",
    cvss: float = 7.5,
) -> tuple[RawFinding, URIPRiskRecord]:
    raw = RawFinding(
        id=str(uuid.uuid4()),
        source="vapt",
        raw_data={
            "hostname": asset_label,
            "ip": ip,
            "mac": mac,
            "device_type": "server",
            "device_category": "IT",
            "os_name": "Linux",
        },
        fetched_at=datetime.now(timezone.utc),
        tenant_id="placeholder",
    )
    record = URIPRiskRecord(
        finding=f"Vuln on {asset_label}",
        source="vapt",
        domain="endpoint",
        cvss_score=cvss,
        severity="high",
        asset=asset_label,
        owner_team="Infrastructure",
        description="Integration test vuln",
        cve_id=cve,
    )
    return raw, record


class TestConnectorIntegration:
    async def test_finding_creates_asset_and_links_new_risk(
        self, db_session: AsyncSession
    ):
        tenant = await _make_tenant(db_session, "integ-1")
        raw, record = _build_finding(asset_label="integ-host-1")

        existing, enriched = await preprocess_connector_record(
            db_session,
            tenant_id=tenant.id,
            raw=raw,
            record=record,
        )
        assert existing is None
        assert "asset_id" in enriched
        assert enriched["asset_id"] is not None

        # Asset row exists
        asset_row = (
            await db_session.execute(
                select(Asset).where(Asset.id == enriched["asset_id"])
            )
        ).scalar_one_or_none()
        assert asset_row is not None
        assert asset_row.tenant_id == tenant.id
        assert asset_row.hostname == "integ-host-1"
        assert asset_row.device_category == "IT"
        assert "vapt" in asset_row.source_connectors

    async def test_second_finding_dedupes_to_same_asset(
        self, db_session: AsyncSession
    ):
        tenant = await _make_tenant(db_session, "integ-2")

        raw1, record1 = _build_finding(asset_label="dedupe-host", cve="CVE-2026-2001")
        _existing1, enriched1 = await preprocess_connector_record(
            db_session, tenant_id=tenant.id, raw=raw1, record=record1
        )
        asset_id_1 = enriched1["asset_id"]
        await db_session.commit()

        raw2, record2 = _build_finding(asset_label="dedupe-host", cve="CVE-2026-2002")
        _existing2, enriched2 = await preprocess_connector_record(
            db_session, tenant_id=tenant.id, raw=raw2, record=record2
        )
        asset_id_2 = enriched2["asset_id"]
        await db_session.commit()

        # Both findings hit the SAME asset row
        assert asset_id_1 == asset_id_2

        # Only one asset for this tenant
        rows = (
            await db_session.execute(
                select(Asset).where(Asset.tenant_id == tenant.id)
            )
        ).scalars().all()
        assert len(rows) == 1

    async def test_full_round_trip_asset_risk_score(
        self, db_session: AsyncSession
    ):
        """
        Connector finds two CVEs on the same asset → asset row is created,
        two Risks are persisted with asset_id set → refresh_asset_risk_score
        rolls up max() of composite_score.
        """
        tenant = await _make_tenant(db_session, "integ-3")

        # Persist Risk 1 the way connectors.py does it
        async def _ingest(cve: str, score: float) -> Risk:
            raw, record = _build_finding(
                asset_label="rt-host", cve=cve, cvss=score
            )
            existing, enriched = await preprocess_connector_record(
                db_session, tenant_id=tenant.id, raw=raw, record=record
            )
            if existing is not None:
                # de-duped → existing was already mutated; commit and return.
                await db_session.commit()
                return existing

            risk = Risk(
                id=uuid.uuid4(),
                risk_id=f"RISK-RT-{cve}",
                finding=record.finding,
                description=record.description,
                source=record.source,
                domain=record.domain,
                cvss_score=float(enriched["cvss_score"]),
                severity=record.severity,
                asset=record.asset,
                owner_team=record.owner_team,
                status="open",
                sla_deadline=datetime.now(timezone.utc),
                cve_id=cve,
                fingerprint_key=enriched["fingerprint_key"],
                sources_attributed=enriched["sources_attributed"],
                advisory_status=enriched.get("advisory_status"),
                remediation_steps=enriched["remediation_steps"],
                asset_id=enriched["asset_id"],
                tenant_id=tenant.id,
                composite_score=score,
            )
            db_session.add(risk)
            await db_session.commit()
            await db_session.refresh(risk)
            return risk

        r1 = await _ingest("CVE-2026-3000", 6.0)
        r2 = await _ingest("CVE-2026-3001", 8.7)

        assert r1.asset_id is not None
        assert r1.asset_id == r2.asset_id

        # Refresh the rollup
        asset_row = (
            await db_session.execute(
                select(Asset).where(Asset.id == r1.asset_id)
            )
        ).scalar_one()
        await asset_service.refresh_asset_risk_score(db_session, asset_row)
        await db_session.commit()
        await db_session.refresh(asset_row)

        assert asset_row.asset_risk_score == 8.7

    async def test_connector_runner_does_not_break_when_asset_metadata_minimal(
        self, db_session: AsyncSession
    ):
        """
        Some connectors only emit a hostname; we should still get an Asset
        row keyed by the hostname-only fingerprint.
        """
        tenant = await _make_tenant(db_session, "integ-min")
        raw = RawFinding(
            id=str(uuid.uuid4()),
            source="cert_in",
            raw_data={"asset_name": "min-host"},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="placeholder",
        )
        record = URIPRiskRecord(
            finding="Advisory",
            source="cert_in",
            domain="application",
            cvss_score=5.0,
            severity="medium",
            asset="min-host",
            owner_team="AppSec",
            cve_id="CVE-2026-9999",
        )
        _existing, enriched = await preprocess_connector_record(
            db_session, tenant_id=tenant.id, raw=raw, record=record
        )
        assert enriched["asset_id"] is not None

        asset = (
            await db_session.execute(
                select(Asset).where(Asset.id == enriched["asset_id"])
            )
        ).scalar_one()
        assert asset.hostname == "min-host"

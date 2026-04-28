from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from connectors.base.connector import RawFinding, URIPRiskRecord

from backend.models.risk import Risk
from backend.services.advisory_applicability_service import AdvisoryRecord, AssetState, classify_advisory
from backend.services.asset_fingerprint_service import compute_asset_fingerprint, find_existing_risk, merge_risk
from backend.services import asset_service
from backend.services.remediation_fetcher import NormalizedFinding, fetch_remediation
from backend.services.severity_normalizer import SeverityNormalizer

logger = logging.getLogger(__name__)


async def preprocess_connector_record(
    db: AsyncSession,
    *,
    tenant_id: Any,
    raw: RawFinding,
    record: URIPRiskRecord,
) -> tuple[Risk | None, dict[str, Any]]:
    """
    Universal Intelligence Engine wiring point.

    Runs AFTER connector.normalize() and BEFORE persistence / scoring.

    Returns:
      - (existing_risk, {}) if de-duped/merged
      - (None, enriched_fields) if caller should create a new Risk row
    """
    source = (record.source or "").strip().lower()

    # 1) Severity normalization → cvss_score (0-10)
    cvss = SeverityNormalizer().normalize(record.cvss_score, source)

    # 2) Asset fingerprint
    mac, hostname, ip = _extract_identity(raw, record)
    fingerprint = compute_asset_fingerprint(mac=mac, hostname=hostname, ip=ip)

    # 3) De-dup lookup
    existing: Risk | None = None
    if record.cve_id:
        existing = await find_existing_risk(
            tenant_id=tenant_id,
            fingerprint=fingerprint,
            cve_id=record.cve_id,
            db=db,
        )

    # 6) Advisory applicability
    advisory_status: str | None = None
    if record.cve_id:
        asset_state = _extract_asset_state(raw)
        try:
            advisory_status = await classify_advisory(
                AdvisoryRecord(
                    tenant_id=str(tenant_id),
                    cve_id=record.cve_id,
                    fingerprint_key=fingerprint,
                ),
                asset_state=asset_state,
                db=db,
            )
        except Exception:
            logger.exception("Advisory applicability classification failed for %s", record.cve_id)

    # 7) Remediation steps
    remediation_steps = fetch_remediation(_to_normalized_finding(record, raw))

    # 8) Asset upsert — every connector finding establishes/refreshes an Asset row.
    # We do this BEFORE the merge/new-risk branches so the FK target exists for both.
    asset_row = None
    try:
        raw_data_with_asset = dict(raw.raw_data or {})
        # Make sure asset metadata is present in raw_data — connectors that put
        # the asset name on URIPRiskRecord.asset still need it bridged.
        if not (
            raw_data_with_asset.get("hostname")
            or raw_data_with_asset.get("asset")
            or raw_data_with_asset.get("device_name")
        ):
            raw_data_with_asset["asset"] = record.asset
        # Bridge the normalized owner_team and asset_tier so a fresh asset starts
        # with sensible classification.
        raw_data_with_asset.setdefault("owner_team", record.owner_team)
        if record.asset_tier is not None and "asset_tier" not in raw_data_with_asset:
            raw_data_with_asset["asset_tier"] = record.asset_tier

        asset_row = await asset_service.upsert_asset(
            db,
            tenant_id=tenant_id,
            raw_data=raw_data_with_asset,
            source_connector=source,
        )
    except Exception:
        # Asset upsert is best-effort — never break risk ingestion if it fails.
        logger.exception("Asset upsert failed for tenant=%s record=%s", tenant_id, record.cve_id)

    asset_id = asset_row.id if asset_row is not None else None

    # 4) Merge if existing
    if existing is not None:
        incoming = SimpleNamespace(
            source=source,
            composite_score=record.composite_score,
            remediation_steps=remediation_steps,
        )
        merge_risk(existing, incoming)
        existing.fingerprint_key = fingerprint
        existing.advisory_status = advisory_status
        existing.cvss_score = max(float(existing.cvss_score), float(cvss)) if existing.cvss_score is not None else cvss
        # Backfill asset_id on de-duped row if it was previously NULL.
        if existing.asset_id is None and asset_id is not None:
            existing.asset_id = asset_id
        db.add(existing)
        return existing, {}

    # New risk fields for persistence
    return None, {
        "cvss_score": cvss,
        "fingerprint_key": fingerprint,
        "sources_attributed": [source] if source else [],
        "advisory_status": advisory_status,
        "remediation_steps": remediation_steps,
        "asset_id": asset_id,
    }


def _extract_identity(raw: RawFinding, record: URIPRiskRecord) -> tuple[str | None, str | None, str | None]:
    data = raw.raw_data or {}
    mac = data.get("mac") or data.get("mac_address") or data.get("macAddress")
    hostname = data.get("hostname") or data.get("host") or data.get("device_name") or data.get("asset_name")
    ip = data.get("ip") or data.get("ip_address") or data.get("ipAddress")

    # Fallback: if hostname missing, use normalized asset label.
    if not hostname:
        hostname = record.asset
    return mac, hostname, ip


def _extract_asset_state(raw: RawFinding) -> AssetState | None:
    data = raw.raw_data or {}
    installed_version = data.get("installed_version") or data.get("version")
    patched_versions = data.get("patched_versions") or data.get("patchedVersions") or []
    if installed_version is None and not patched_versions:
        return None
    if not isinstance(patched_versions, list):
        patched_versions = [patched_versions]
    return AssetState(installed_version=str(installed_version) if installed_version is not None else None,
                      patched_versions=[str(v) for v in patched_versions if v is not None])


def _to_normalized_finding(record: URIPRiskRecord, raw: RawFinding) -> NormalizedFinding:
    source = (record.source or "").strip().lower()
    data = raw.raw_data or {}

    if record.cve_id:
        return NormalizedFinding(
            source=source,
            finding_type="cve",
            cve_id=record.cve_id,
            advisory_text=_pick_text(record, data),
        )

    if source in {"cert_in", "certin", "cert-in"}:
        return NormalizedFinding(
            source=source,
            finding_type="cert_in",
            advisory_text=_pick_text(record, data),
        )

    if source == "vapt":
        return NormalizedFinding(
            source=source,
            finding_type="vapt",
            remediation_recommendation=data.get("remediation_recommendation") or data.get("remediation"),
        )

    if source == "bug_bounty":
        return NormalizedFinding(
            source=source,
            finding_type="bug_bounty",
            researcher_recommendation=data.get("researcher_recommendation") or data.get("recommendation"),
        )

    if source in {"soc", "soc_alert"}:
        return NormalizedFinding(
            source=source,
            finding_type="soc_alert",
            alert_type=data.get("alert_type") or data.get("type"),
        )

    # Heuristic: IOC-ish records
    if data.get("indicator_type") or data.get("ioc_type"):
        return NormalizedFinding(
            source=source,
            finding_type="ioc_match",
            indicator_type=data.get("indicator_type") or data.get("ioc_type"),
            indicator_value=data.get("indicator_value") or data.get("ioc_value"),
        )

    return NormalizedFinding(source=source, finding_type="generic", remediation_steps=[])


def _pick_text(record: URIPRiskRecord, data: dict[str, Any]) -> str | None:
    return record.description or data.get("advisory_text") or data.get("description") or data.get("details")


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point for the Celery worker (P33-Z6)
# ─────────────────────────────────────────────────────────────────────────────


async def run_connector(tenant_id: str, connector_name: str) -> dict[str, Any]:
    """
    Authenticate, fetch, normalize, and persist findings for a single
    (tenant, connector) pair.

    This is the convenience entry point for the Celery
    ``connector_pull_task`` worker — it opens its own DB session, instantiates
    the connector via the registry, and reuses ``preprocess_connector_record``
    for de-dup + enrichment.  Exists as a thin alias over
    ``backend.services._connector_pull_runner.run_connector_pull`` so callers
    can import a single, stable name from ``connector_runner``.

    Returns a status dict — never raises for per-finding errors so a single
    bad payload does not abort the entire pull.
    """
    # Import here to avoid a top-level cycle (the helper imports back from
    # this module via ``preprocess_connector_record``).
    from backend.services._connector_pull_runner import run_connector_pull

    return await run_connector_pull(tenant_id, connector_name)

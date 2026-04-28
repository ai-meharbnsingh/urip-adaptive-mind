"""
Risk Index Service — TrendAI-style 0-100 Cyber Risk Index.

Purpose
-------
The Trend Micro Vision One dashboard surfaces a single 0-100 "Cyber Risk Index"
plus three sub-indexes (Exposure / Attack / Security Configuration) and a
five-bucket per-asset-type breakdown (Devices / Internet-Facing / Accounts /
Applications / Cloud Assets).  This service computes the same data shape from
the URIP risk register so the cockpit frontend can render an equivalent KPI
strip without changing any of the existing 0-10 composite scoring infrastructure.

Design decisions
----------------
- 0-100 is a DERIVED VIEW, not a replacement.  The 0-10 ``Risk.composite_score``
  field is unchanged — it is what every existing exploitability and aggregate
  service relies on.
- The score formula is intentionally simple, so it is auditable end-to-end:
      base       = mean(composite_score for open risks) * 10        -> 0..100
      crit_bonus = critical_count * 0.5                              -> additive
      high_bonus = high_count     * 0.2                              -> additive
      kev_bonus  = kev_active_count * 1.0                            -> additive
      score      = min(100, base + crit_bonus + high_bonus + kev_bonus)
- Closed risks NEVER contribute — the index is a posture-of-now signal.
- Connector → sub-index mapping is declared on each connector as the class
  attribute ``RISK_INDEX_DOMAIN``.  The service maps Risk.source → connector
  class → RISK_INDEX_DOMAIN.  This keeps the contract on the connector side so
  adding a new connector is a one-line change in its module, not a fork in
  this service.
- Domain breakdown prefers ``Risk.domain`` when it cleanly maps to one of the
  five buckets ("cloud" -> cloud_assets, "endpoint" -> devices, …).  If the
  domain field does not map, we fall back to the connector category resolved
  from Risk.source.
- Trade-off: ``cloudsek`` connector ships both XVigil (active dark-web threat
  alerts -> ATTACK signal) and BeVigil (mobile app exposure -> EXPOSURE signal)
  but Risk.source is just "cloudsek".  We map the connector as a whole to
  "attack" because XVigil is the dominant signal.  When the connector grows
  per-product source values ("cloudsek_xvigil", "cloudsek_bevigil") we can
  split the mapping.

Usage
-----
    svc = RiskIndexService(db_session)
    idx = await svc.compute_risk_index_0_100(tenant_id)
    subs = await svc.compute_subindexes(tenant_id)
    bk   = await svc.compute_domain_breakdown(tenant_id)
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Iterable, Literal, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.risk import Risk

# ─────────────────────────────────────────────────────────────────────────────
# Domain ↔ source mapping helpers
# ─────────────────────────────────────────────────────────────────────────────

#: One source of truth.  Frontend mirrors these via /api/risk-index payload.
SUBINDEX_NAMES: tuple[str, ...] = ("exposure", "attack", "security_config")
DOMAIN_NAMES: tuple[str, ...] = (
    "devices",
    "internet_facing",
    "accounts",
    "applications",
    "cloud_assets",
)
LevelLiteral = Literal["low", "medium", "high", "critical"]
SubindexNameLiteral = Literal["exposure", "attack", "security_config"]
DomainNameLiteral = Literal[
    "devices", "internet_facing", "accounts", "applications", "cloud_assets"
]


# Source → sub-index mapping is the canonical lookup. Built by importing
# the connector classes lazily inside helper functions to avoid pulling
# heavy connector modules into the import graph for every test that
# imports this service.
def _build_source_to_subindex() -> dict[str, str]:
    """
    Combine the static (canonical) table with whatever the connector
    registry exposes, so the service works in both:
      - Full app boot (registry has every connector class) — registry wins.
      - Lightweight pytest sessions (only a subset of connector modules are
        imported via backend.connector_loader) — static table fills the gaps.

    Returns ``{Risk.source NAME → "exposure"|"attack"|"security_config"}``.
    """
    # Start with the static canonical table
    mapping: dict[str, str] = dict(_STATIC_SOURCE_TO_SUBINDEX)

    try:
        # Lazy import — avoids circular boot-time hits from the test suite.
        import backend.connector_loader  # noqa: F401  side-effect: registers
        from connectors.base.registry import _global_registry
    except Exception:  # pragma: no cover — defensive fallback
        return mapping

    try:
        for name in _global_registry.list_names():
            cls = _global_registry.get(name)
            domain = getattr(cls, "RISK_INDEX_DOMAIN", None)
            if domain in SUBINDEX_NAMES:
                mapping[name] = domain
    except Exception:  # pragma: no cover
        pass

    return mapping


# Static fallback table — kept in sync with the connector class attrs.
# This is the same mapping the connectors declare; duplicated here so the
# service still works in pruned test environments where the connector
# registry is not loaded.  See test_risk_index_service.py for the contract
# tests that pin both directions.
_STATIC_SOURCE_TO_SUBINDEX: dict[str, str] = {
    # exposure
    "tenable": "exposure",
    "easm": "exposure",
    # attack
    "sentinelone": "attack",
    "crowdstrike": "attack",
    "ms_entra": "attack",
    "siem": "attack",
    "gtb": "attack",
    "cloudsek": "attack",
    "netskope": "attack",
    # security_config
    "aws_cspm": "security_config",
    "azure_cspm": "security_config",
    "gcp_cspm": "security_config",
    "manageengine_ec": "security_config",
    "manageengine_mdm": "security_config",
    "fortiguard_fw": "security_config",
}


# Domain bucket mapping — first try Risk.domain, then connector category.
# Risk.domain values come from the connector layer.  Common values are:
#   endpoint, cloud, network, application, identity, ot, iot
_DOMAIN_FIELD_TO_BUCKET: dict[str, str] = {
    "endpoint": "devices",
    "device": "devices",
    "iot": "devices",
    "cloud": "cloud_assets",
    "application": "applications",
    "identity": "accounts",
    "internet_facing": "internet_facing",
    "external": "internet_facing",
}


# Source → bucket fallback (used when Risk.domain is blank or unknown).
# Reflects the URIP_Blueprint v3 §6 connector-category to bucket mapping.
_SOURCE_TO_BUCKET: dict[str, str] = {
    # Devices: VM / EDR / UEM / MDM
    "tenable": "devices",
    "crowdstrike": "devices",
    "sentinelone": "devices",
    "manageengine_ec": "devices",
    "manageengine_mdm": "devices",
    "armis_ot": "devices",
    # Internet-facing: EASM
    "easm": "internet_facing",
    "cloudsek": "internet_facing",
    # Accounts: Identity / PAM
    "ms_entra": "accounts",
    "cyberark_pam": "accounts",
    # Applications: DAST / Bug bounty / Application
    "burp_enterprise": "applications",
    "bug_bounty": "applications",
    # Cloud assets: CSPM
    "aws_cspm": "cloud_assets",
    "azure_cspm": "cloud_assets",
    "gcp_cspm": "cloud_assets",
}


# ─────────────────────────────────────────────────────────────────────────────
# Pure helpers
# ─────────────────────────────────────────────────────────────────────────────


def classify_level(score: float) -> LevelLiteral:
    """
    Cut score into one of four bands.

    Cutoffs (inclusive on the lower bound):
        0   <= score < 30  -> low
        30  <= score < 60  -> medium
        60  <= score < 80  -> high
        80  <= score       -> critical
    """
    if score >= 80.0:
        return "critical"
    if score >= 60.0:
        return "high"
    if score >= 30.0:
        return "medium"
    return "low"


_LEVEL_TO_COLOR: dict[str, str] = {
    "low": "green",
    "medium": "yellow",
    "high": "orange",
    "critical": "red",
}


def color_for_level(level: LevelLiteral) -> str:
    """Map level → frontend-rendered traffic-light color."""
    return _LEVEL_TO_COLOR[level]


def _resolve_domain_bucket(risk_domain: Optional[str], source: Optional[str]) -> Optional[str]:
    """
    Map a (Risk.domain, Risk.source) pair to one of the 5 dashboard buckets.

    Returns None if the pair cannot be classified — caller drops the row.
    """
    if risk_domain:
        bucket = _DOMAIN_FIELD_TO_BUCKET.get(risk_domain.strip().lower())
        if bucket is not None:
            return bucket
    if source:
        return _SOURCE_TO_BUCKET.get(source.strip().lower())
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic-free dataclasses (consumed by the router which serialises them)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RiskIndex:
    """Top-of-dashboard 0-100 risk index."""
    score: float
    level: LevelLiteral
    color_code: str


@dataclass(frozen=True)
class Subindex:
    """One sub-index — exposure, attack, or security_config."""
    score: float
    level: LevelLiteral
    contributing_count: int


@dataclass(frozen=True)
class Subindexes:
    """All three sub-indexes bundled together."""
    exposure: Subindex
    attack: Subindex
    security_config: Subindex


@dataclass(frozen=True)
class DomainBucket:
    """One row in the 5-bucket per-asset-type breakdown."""
    name: DomainNameLiteral
    total: int
    critical_count: int
    high_count: int
    mean_score: float          # 0..10 scale (re-expresses composite_score mean)
    level: LevelLiteral        # derived from mean_score * 10


@dataclass(frozen=True)
class DomainBreakdown:
    """All five domain buckets."""
    devices: DomainBucket
    internet_facing: DomainBucket
    accounts: DomainBucket
    applications: DomainBucket
    cloud_assets: DomainBucket


@dataclass(frozen=True)
class TopRisk:
    """Drill-down row used by sub-index / domain detail endpoints."""
    risk_id: str
    finding: str
    source: str
    severity: str
    composite_score: Optional[float]
    asset: str
    domain: Optional[str]


# ─────────────────────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────────────────────


class RiskIndexService:
    """
    Stateless service — accepts an AsyncSession and computes the dashboard
    payload sections.  Mirrors RiskAggregateService construction style.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._source_to_subindex: dict[str, str] | None = None

    # ------------------------------------------------------------------ #
    #  Lazy mapping accessor — pulls from connector registry on first use.
    # ------------------------------------------------------------------ #
    def _subindex_for_source(self, source: Optional[str]) -> Optional[str]:
        if not source:
            return None
        if self._source_to_subindex is None:
            self._source_to_subindex = _build_source_to_subindex()
        return self._source_to_subindex.get(source)

    # ------------------------------------------------------------------ #
    #  Common open-risks fetch
    # ------------------------------------------------------------------ #
    async def _open_risks(self, tenant_id: uuid.UUID) -> list[Risk]:
        rows = (await self.db.execute(
            select(Risk).where(
                Risk.tenant_id == tenant_id,
                Risk.status == "open",
            )
        )).scalars().all()
        return list(rows)

    # ------------------------------------------------------------------ #
    #  PART 1 — single 0-100 cyber risk index
    # ------------------------------------------------------------------ #
    async def compute_risk_index_0_100(self, tenant_id: uuid.UUID) -> RiskIndex:
        """
        Single 0-100 score for the dashboard top-strip.

        Empty tenant → score=0, level=low.
        """
        risks = await self._open_risks(tenant_id)

        if not risks:
            return RiskIndex(score=0.0, level="low", color_code="green")

        # Base = mean(composite_score) * 10. Risks with NULL composite_score
        # are excluded from the average (otherwise None would zero the mean).
        scored = [float(r.composite_score) for r in risks if r.composite_score is not None]
        base = (sum(scored) / len(scored)) * 10.0 if scored else 0.0

        critical_count = sum(1 for r in risks if r.severity == "critical")
        high_count = sum(1 for r in risks if r.severity == "high")
        kev_count = sum(1 for r in risks if r.in_kev_catalog)

        bonus = (critical_count * 0.5) + (high_count * 0.2) + (kev_count * 1.0)
        raw = base + bonus
        score = round(min(100.0, max(0.0, raw)), 2)
        level = classify_level(score)
        return RiskIndex(score=score, level=level, color_code=color_for_level(level))

    # ------------------------------------------------------------------ #
    #  PART 2 — three sub-indexes
    # ------------------------------------------------------------------ #
    async def compute_subindexes(self, tenant_id: uuid.UUID) -> Subindexes:
        """
        Compute Exposure / Attack / Security Configuration sub-indexes.

        Each is a weighted-mean 0-100 score over the open risks whose source
        maps to that sub-index via the connector RISK_INDEX_DOMAIN attribute.
        """
        risks = await self._open_risks(tenant_id)

        buckets: dict[str, list[Risk]] = {
            "exposure": [],
            "attack": [],
            "security_config": [],
        }
        for r in risks:
            sub = self._subindex_for_source(r.source)
            if sub in buckets:
                buckets[sub].append(r)

        def _mean_to_subindex(rows: list[Risk]) -> Subindex:
            scored = [float(r.composite_score) for r in rows if r.composite_score is not None]
            mean = sum(scored) / len(scored) if scored else 0.0
            score = round(min(100.0, max(0.0, mean * 10.0)), 2)
            level = classify_level(score)
            return Subindex(score=score, level=level, contributing_count=len(rows))

        return Subindexes(
            exposure=_mean_to_subindex(buckets["exposure"]),
            attack=_mean_to_subindex(buckets["attack"]),
            security_config=_mean_to_subindex(buckets["security_config"]),
        )

    # ------------------------------------------------------------------ #
    #  PART 3 — five-bucket domain breakdown
    # ------------------------------------------------------------------ #
    async def compute_domain_breakdown(self, tenant_id: uuid.UUID) -> DomainBreakdown:
        """
        Bucket open risks into 5 dashboard buckets and aggregate per-bucket
        counts + mean score.
        """
        risks = await self._open_risks(tenant_id)

        buckets: dict[str, list[Risk]] = {n: [] for n in DOMAIN_NAMES}
        for r in risks:
            bucket = _resolve_domain_bucket(r.domain, r.source)
            if bucket in buckets:
                buckets[bucket].append(r)

        def _bucket_to_obj(name: DomainNameLiteral, rows: list[Risk]) -> DomainBucket:
            scored = [float(r.composite_score) for r in rows if r.composite_score is not None]
            mean = sum(scored) / len(scored) if scored else 0.0
            mean = round(mean, 2)
            level = classify_level(mean * 10.0)
            return DomainBucket(
                name=name,
                total=len(rows),
                critical_count=sum(1 for r in rows if r.severity == "critical"),
                high_count=sum(1 for r in rows if r.severity == "high"),
                mean_score=mean,
                level=level,
            )

        return DomainBreakdown(
            devices=_bucket_to_obj("devices", buckets["devices"]),
            internet_facing=_bucket_to_obj("internet_facing", buckets["internet_facing"]),
            accounts=_bucket_to_obj("accounts", buckets["accounts"]),
            applications=_bucket_to_obj("applications", buckets["applications"]),
            cloud_assets=_bucket_to_obj("cloud_assets", buckets["cloud_assets"]),
        )

    # ------------------------------------------------------------------ #
    #  Drill-down helpers
    # ------------------------------------------------------------------ #
    async def top_risks_for_subindex(
        self, tenant_id: uuid.UUID, name: SubindexNameLiteral, limit: int = 10,
    ) -> list[TopRisk]:
        risks = await self._open_risks(tenant_id)
        matched = [r for r in risks if self._subindex_for_source(r.source) == name]
        matched.sort(
            key=lambda r: float(r.composite_score) if r.composite_score is not None else 0.0,
            reverse=True,
        )
        return [self._risk_to_top(r) for r in matched[:limit]]

    async def top_risks_for_domain(
        self, tenant_id: uuid.UUID, name: DomainNameLiteral, limit: int = 10,
    ) -> list[TopRisk]:
        risks = await self._open_risks(tenant_id)
        matched = [
            r for r in risks
            if _resolve_domain_bucket(r.domain, r.source) == name
        ]
        matched.sort(
            key=lambda r: float(r.composite_score) if r.composite_score is not None else 0.0,
            reverse=True,
        )
        return [self._risk_to_top(r) for r in matched[:limit]]

    @staticmethod
    def _risk_to_top(r: Risk) -> TopRisk:
        return TopRisk(
            risk_id=r.risk_id,
            finding=r.finding,
            source=r.source,
            severity=r.severity,
            composite_score=float(r.composite_score) if r.composite_score is not None else None,
            asset=r.asset,
            domain=r.domain,
        )

"""
Threat Intelligence API Router.

Endpoints for threat pulses, IOCs, APT groups, dark web alerts,
and geo-stats. All endpoints require authentication.
"""
from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.middleware.auth import get_current_user
from backend.middleware.module_gate import require_any_module
from backend.models.user import User
from backend.services.threat_intel_service import (
    APT_SECTOR_MAP,
    CVE_APT_MAP,
    get_apt_groups,
    get_dark_web_alerts,
    get_geo_stats,
    get_otx_pulses,
)

# CRIT-007 — threat intel feeds matter for any tenant running a security
# detection module (vuln management, EDR, or network).  At least one of those
# must be active.  Super-admins bypass.
router = APIRouter(dependencies=[Depends(require_any_module(["VM", "EDR", "NETWORK"]))])


# Threat-intel payloads come from external data sources (OTX, MITRE) with
# loosely-typed shapes that vary by feed.  We expose them with `dict[str, Any]`
# inside a typed envelope so callers always know the response is a Pydantic
# model with `items` + `total` keys, even if the per-item shape is heterogeneous.
class ThreatIntelEnvelope(BaseModel):
    items: list[dict[str, Any]]
    total: int


class IocMatchEnvelope(ThreatIntelEnvelope):
    total_iocs_checked: int
    match_rate: float


@router.get("/pulses", response_model=ThreatIntelEnvelope)
async def list_threat_pulses(
    limit: int = Query(default=50, ge=1, le=200),
    min_relevance: float = Query(default=0.0, ge=0.0, le=100.0),
    current_user: User = Depends(get_current_user),
):
    """Return recent threat pulses with IOCs and relevance scores."""
    pulses = await get_otx_pulses(limit=limit)
    if min_relevance > 0:
        pulses = [p for p in pulses if p.get("relevance_score", 0) >= min_relevance]
    # Sort by relevance descending
    pulses.sort(key=lambda p: p.get("relevance_score", 0), reverse=True)
    return ThreatIntelEnvelope(items=pulses, total=len(pulses))


@router.get("/apt-groups", response_model=ThreatIntelEnvelope)
async def list_apt_groups(
    country: str | None = Query(default=None),
    sector: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    """Return APT groups from MITRE ATT&CK."""
    groups = await get_apt_groups()
    if country:
        groups = [g for g in groups if g.get("country", "").lower() == country.lower()]
    if sector:
        groups = [
            g
            for g in groups
            if any(sector.lower() in s.lower() for s in g.get("targeting", []))
        ]
    return ThreatIntelEnvelope(items=groups, total=len(groups))


@router.get("/iocs", response_model=ThreatIntelEnvelope)
async def list_iocs(
    ioc_type: str | None = Query(default=None, alias="type"),
    current_user: User = Depends(get_current_user),
):
    """Return all IOCs from recent pulses (IPs, domains, hashes)."""
    pulses = await get_otx_pulses()
    iocs: list[dict] = []
    for pulse in pulses:
        for indicator in pulse.get("indicators", []):
            ioc_entry = {
                "type": indicator.get("type", ""),
                "indicator": indicator.get("indicator", ""),
                "description": indicator.get("description", ""),
                "source_pulse": pulse.get("name", ""),
                "pulse_id": pulse.get("id", ""),
                "tlp": pulse.get("tlp", "white"),
                "relevance_score": pulse.get("relevance_score", 0),
            }
            iocs.append(ioc_entry)

    if ioc_type:
        iocs = [i for i in iocs if i["type"].lower() == ioc_type.lower()]

    # Sort by relevance
    iocs.sort(key=lambda i: i.get("relevance_score", 0), reverse=True)
    return ThreatIntelEnvelope(items=iocs, total=len(iocs))


@router.get("/iocs/match", response_model=IocMatchEnvelope)
async def match_iocs(
    current_user: User = Depends(get_current_user),
):
    """Check IOCs against risks in our DB (simulated matching).

    In production, this would correlate IOCs with SIEM data, firewall logs,
    and asset inventory. For demo, we return simulated match results.
    """
    pulses = await get_otx_pulses()
    matches: list[dict] = []

    # Simulated matches — IOCs that "matched" against RE infrastructure
    simulated_hits = {
        "185.174.101.42": {
            "matched_in": "Firewall Logs",
            "match_count": 3,
            "first_seen": "2026-04-01T14:22:00Z",
            "last_seen": "2026-04-07T09:15:00Z",
            "action_taken": "Blocked",
        },
        "royal-enfield-hr.com": {
            "matched_in": "Email Gateway",
            "match_count": 12,
            "first_seen": "2026-03-28T08:00:00Z",
            "last_seen": "2026-04-06T16:30:00Z",
            "action_taken": "Quarantined",
        },
        "royalenfield-warranty.in": {
            "matched_in": "DNS Logs",
            "match_count": 47,
            "first_seen": "2026-04-02T10:00:00Z",
            "last_seen": "2026-04-08T22:45:00Z",
            "action_taken": "Sinkholed",
        },
        "139.180.199.55": {
            "matched_in": "IDS/IPS",
            "match_count": 156,
            "first_seen": "2026-03-15T00:00:00Z",
            "last_seen": "2026-04-08T18:00:00Z",
            "action_taken": "Blocked",
        },
        "invoice-royalenfield.com": {
            "matched_in": "Email Gateway",
            "match_count": 8,
            "first_seen": "2026-04-04T06:00:00Z",
            "last_seen": "2026-04-07T14:00:00Z",
            "action_taken": "Quarantined",
        },
    }

    for pulse in pulses:
        for indicator in pulse.get("indicators", []):
            ioc_val = indicator.get("indicator", "")
            if ioc_val in simulated_hits:
                hit = simulated_hits[ioc_val]
                matches.append(
                    {
                        "ioc": ioc_val,
                        "ioc_type": indicator.get("type", ""),
                        "description": indicator.get("description", ""),
                        "source_pulse": pulse.get("name", ""),
                        "adversary": pulse.get("adversary", "Unknown"),
                        "tlp": pulse.get("tlp", "white"),
                        "matched_in": hit["matched_in"],
                        "match_count": hit["match_count"],
                        "first_seen": hit["first_seen"],
                        "last_seen": hit["last_seen"],
                        "action_taken": hit["action_taken"],
                    }
                )

    total_iocs = sum(len(p.get("indicators", [])) for p in pulses)
    return IocMatchEnvelope(
        items=matches,
        total=len(matches),
        total_iocs_checked=total_iocs,
        match_rate=round(len(matches) / max(1, total_iocs) * 100, 1),
    )


@router.get("/geo-stats", response_model=ThreatIntelEnvelope)
async def geo_stats(
    current_user: User = Depends(get_current_user),
):
    """Return threat data aggregated by country for map visualization."""
    stats = await get_geo_stats()
    return ThreatIntelEnvelope(items=stats, total=len(stats))


@router.get("/dark-web", response_model=ThreatIntelEnvelope)
async def dark_web_alerts(
    severity: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    """Return dark web monitoring alerts (simulated but realistic)."""
    alerts = get_dark_web_alerts()
    if severity:
        alerts = [a for a in alerts if a.get("severity", "").lower() == severity.lower()]
    return ThreatIntelEnvelope(items=alerts, total=len(alerts))


# --------------------------------------------------------------------------- #
# Word-cloud aggregation — supplies frontend/threat-map.html D3 visualisation.
# --------------------------------------------------------------------------- #
class WordCloudEntry(BaseModel):
    term: str
    count: int


class WordCloudResponse(BaseModel):
    apt_groups: list[WordCloudEntry]
    ttps: list[WordCloudEntry]
    sectors: list[WordCloudEntry]


def _frequency_to_entries(counter: Counter, top_n: int = 30) -> list[WordCloudEntry]:
    return [
        WordCloudEntry(term=term, count=count)
        for term, count in counter.most_common(top_n)
    ]


@router.get("/word-cloud", response_model=WordCloudResponse)
async def threat_word_cloud(
    current_user: User = Depends(get_current_user),
) -> WordCloudResponse:
    """
    Aggregate counts for the three word-cloud canvases on the threat map.

    Sources:
      - apt_groups: CVE→APT static map + adversary names from OTX pulses
      - ttps:       OTX pulse tags (lower-cased, deduped per pulse)
      - sectors:    APT_SECTOR_MAP entries hit by APT names appearing in pulses
    """
    apt_counter: Counter[str] = Counter()
    ttp_counter: Counter[str] = Counter()
    sector_counter: Counter[str] = Counter()

    # 1. APT groups from the static CVE map (each CVE counts as one mention).
    for groups in CVE_APT_MAP.values():
        for g in groups:
            name = g.get("name") or ""
            if name and name.lower() != "multiple":
                apt_counter[name] += 1

    # 2. APT groups + sectors + tags from live (or synthetic) OTX pulses.
    pulses = await get_otx_pulses(limit=200)
    for pulse in pulses:
        adversary = (pulse.get("adversary") or "").split("(")[0].strip()
        if adversary and adversary.lower() != "unknown":
            apt_counter[adversary] += 1
            # Map back to sectors via APT_SECTOR_MAP.
            sector_info = APT_SECTOR_MAP.get(adversary, {})
            for sector in sector_info.get("sectors", []):
                if sector and sector.lower() != "various":
                    sector_counter[sector] += 1

        for tag in pulse.get("tags", []) or []:
            if isinstance(tag, str) and tag:
                ttp_counter[tag.lower()] += 1

    # 3. Top-up sector counts from APT_SECTOR_MAP for each APT in apt_counter.
    for apt_name, mentions in apt_counter.items():
        info = APT_SECTOR_MAP.get(apt_name, {})
        for sector in info.get("sectors", []):
            if sector and sector.lower() != "various":
                sector_counter[sector] += mentions

    return WordCloudResponse(
        apt_groups=_frequency_to_entries(apt_counter),
        ttps=_frequency_to_entries(ttp_counter),
        sectors=_frequency_to_entries(sector_counter),
    )

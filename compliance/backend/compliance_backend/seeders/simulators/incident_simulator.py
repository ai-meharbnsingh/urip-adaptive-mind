"""
incident_simulator — generate Incident records with realistic lifecycles.

Behavior:
  - Draws from INCIDENT_SCENARIOS in _common.py for narrative content.
  - Severity drives SLA hours: critical=1, high=4, medium=24, low=72.
  - Mix: ~60% closed, ~25% in active phases (triaged/contained/etc.), ~15% open.
  - SLA breach rate ~10-15% (realistic for a mature SOC).
  - incident_number is monotonic per tenant: INC-2026-0001, INC-2026-0002, ...

Idempotency: skip if any incidents exist for tenant.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.seeders.simulators.sim_models import Incident
from compliance_backend.seeders.simulators._common import (
    INCIDENT_SCENARIOS,
    make_rng,
    stable_uuid,
    now_utc,
)


SLA_HOURS_BY_SEVERITY = {"critical": 1, "high": 4, "medium": 24, "low": 72}

# Distribution of statuses across the population
STATUS_WEIGHTS = [
    ("closed", 0.55),
    ("recovered", 0.10),
    ("eradicated", 0.05),
    ("contained", 0.08),
    ("triaged", 0.12),
    ("detected", 0.10),
]


def _choose_status(rng: random.Random) -> str:
    statuses, weights = zip(*STATUS_WEIGHTS)
    return rng.choices(statuses, weights=weights)[0]


def _build_lifecycle(
    detected_at: datetime, severity: str, status: str, rng: random.Random
) -> dict:
    """
    Compute timestamps for each lifecycle phase up to `status`.
    Returns dict of {triaged_at, contained_at, eradicated_at, recovered_at, closed_at, sla_breached}.
    """
    sla = SLA_HOURS_BY_SEVERITY[severity]
    out = {
        "triaged_at": None,
        "contained_at": None,
        "eradicated_at": None,
        "recovered_at": None,
        "closed_at": None,
        "sla_breached": False,
    }

    phases = ["detected", "triaged", "contained", "eradicated", "recovered", "closed"]
    if status not in phases:
        return out
    target_idx = phases.index(status)

    # Triage timing — most respect SLA, ~12% breach
    triage_hours = (
        sla * rng.uniform(0.3, 0.95) if rng.random() > 0.12 else sla * rng.uniform(1.2, 3.0)
    )
    out["sla_breached"] = triage_hours > sla
    cur = detected_at
    if target_idx >= 1:
        cur = detected_at + timedelta(hours=triage_hours)
        out["triaged_at"] = cur
    if target_idx >= 2:
        cur = cur + timedelta(hours=rng.uniform(0.5, sla * 1.5))
        out["contained_at"] = cur
    if target_idx >= 3:
        cur = cur + timedelta(hours=rng.uniform(2, sla * 4))
        out["eradicated_at"] = cur
    if target_idx >= 4:
        cur = cur + timedelta(hours=rng.uniform(2, 24))
        out["recovered_at"] = cur
    if target_idx >= 5:
        cur = cur + timedelta(hours=rng.uniform(24, 168))  # post-mortem 1-7 days
        out["closed_at"] = cur
    return out


def _assignee_for(category: str, rng: random.Random) -> str:
    pools = {
        "phishing": ["soc-team@adverb.in", "vikram.mehta@adverb.in"],
        "ransomware": ["incident-response@adverb.in", "cisco.team@adverb.in"],
        "malware": ["soc-team@adverb.in", "endpoint-team@adverb.in"],
        "data_loss": ["dlp-team@adverb.in", "compliance@adverb.in"],
        "credential_compromise": ["iam-team@adverb.in", "soc-team@adverb.in"],
        "insider_threat": ["hr-team@adverb.in", "compliance@adverb.in"],
        "misconfiguration": ["platform-eng@adverb.in", "cloudops@adverb.in"],
        "ddos": ["network-team@adverb.in", "soc-team@adverb.in"],
        "third_party": ["vendor-mgmt@adverb.in", "compliance@adverb.in"],
        "physical": ["facilities@adverb.in", "soc-team@adverb.in"],
    }
    return rng.choice(pools.get(category, ["soc-team@adverb.in"]))


async def simulate_incidents(
    session: AsyncSession,
    *,
    tenant_id: str,
    count: int = 25,
    seed: int = 42,
    skip_if_existing: bool = True,
) -> dict[str, int]:
    """
    Generate `count` Incident records for a tenant.

    Args:
        tenant_id:        Tenant scope.
        count:            Number of incidents to create.
        seed:             RNG seed.
        skip_if_existing: No-op if any incidents exist.

    Returns:
        Summary counts.
    """
    rng = make_rng(seed)

    if skip_if_existing:
        existing = (await session.execute(
            select(func.count()).select_from(Incident).where(Incident.tenant_id == tenant_id)
        )).scalar() or 0
        if existing > 0:
            return {"created": 0, "skipped": existing, "tenant_id": tenant_id}

    created = 0
    closed_count = 0

    # Force at least one of each severity in the first 4
    forced_severities = ["low", "medium", "high", "critical"]

    now = now_utc()
    for i in range(count):
        scenario = rng.choice(INCIDENT_SCENARIOS)

        if i < len(forced_severities):
            severity = forced_severities[i]
        else:
            severity = scenario["severity"]

        # Detection time: anywhere in last 180 days
        detected_at = now - timedelta(days=rng.randint(0, 180), hours=rng.randint(0, 23))
        status = _choose_status(rng)
        lifecycle = _build_lifecycle(detected_at, severity, status, rng)

        # If status >= recovered, force RCA + lessons
        if status in ("recovered", "closed"):
            rca = scenario.get("rca", "")
            lessons = scenario.get("lessons", "")
        else:
            rca = None
            lessons = None

        if status == "closed":
            closed_count += 1

        incident_number = f"INC-{detected_at.year}-{(i + 1):04d}"

        inc = Incident(
            id=stable_uuid(tenant_id, "incident", str(i)),
            tenant_id=tenant_id,
            incident_number=incident_number,
            title=scenario["title"],
            description=scenario["description"],
            category=scenario["category"],
            severity=severity,
            status=status,
            detected_at=detected_at,
            triaged_at=lifecycle["triaged_at"],
            contained_at=lifecycle["contained_at"],
            eradicated_at=lifecycle["eradicated_at"],
            recovered_at=lifecycle["recovered_at"],
            closed_at=lifecycle["closed_at"],
            assigned_to=_assignee_for(scenario["category"], rng),
            affected_assets=scenario.get("affected_assets", []),
            rca_summary=rca,
            lessons_learned=lessons,
            sla_breached=lifecycle["sla_breached"],
        )
        session.add(inc)
        created += 1

    await session.flush()
    return {
        "created": created,
        "closed": closed_count,
        "skipped": 0,
        "tenant_id": tenant_id,
    }

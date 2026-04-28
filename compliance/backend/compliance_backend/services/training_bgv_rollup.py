"""
Training + BGV completion roll-up service.

Aggregates per-tenant training completion % (from KnowBe4 / Hoxhunt) and BGV
completion % (from AuthBridge / OnGrid) into compact widget data the
compliance dashboard can render without touching the connectors directly.

Design notes
------------
- Pure-data service. Does NOT call connector classes — instead it accepts
  raw stat dicts so the caller (the connector scheduler, an admin endpoint,
  or a test) controls where the data comes from.
- Returns plain dicts so JSON serialisation is trivial and the same shape
  works in the admin dashboard widget AND the auditor portal evidence view.
- Compliance citations live in `framework_evidence` so the auditor portal
  knows which framework controls these stats evidence.

This is the only NEW service touching the existing compliance module — it
does NOT modify any existing service, per task constraint.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# Compliance-control mapping for the auditor portal.
TRAINING_FRAMEWORK_EVIDENCE = [
    {
        "framework_short_code": "ISO27001",
        "control_code": "A.6.3",
        "control_title": "Information security awareness, education and training",
    },
    {
        "framework_short_code": "SOC2",
        "control_code": "CC1.4",
        "control_title": "Demonstrate commitment to attract, develop and retain competent personnel",
    },
]

BGV_FRAMEWORK_EVIDENCE = [
    {
        "framework_short_code": "HIPAA",
        "control_code": "164.308(a)(3)",
        "control_title": "Workforce security — authorisation and supervision",
    },
    {
        "framework_short_code": "HIPAA",
        "control_code": "164.308(a)(1)(ii)(B)",
        "control_title": "Risk management",
    },
    {
        "framework_short_code": "ISO27001",
        "control_code": "A.6.1",
        "control_title": "Screening",
    },
]


@dataclass
class CompletionStats:
    """Tenant-scoped roll-up for one source (LMS or BGV)."""

    total: int
    completed: int
    incomplete: int

    @property
    def completion_pct(self) -> float:
        if self.total <= 0:
            return 0.0
        return round((self.completed / self.total) * 100.0, 1)


def compute_training_rollup(
    knowbe4_stats: Optional[Dict[str, int]] = None,
    hoxhunt_stats: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """
    Combine KnowBe4 + Hoxhunt user training stats into a single roll-up.

    Each stats dict has shape: {"total": int, "completed": int}.
    Either may be None (connector not configured) — we sum across whatever is
    present so a tenant with only one LMS still gets a number.
    """
    total = 0
    completed = 0
    sources: List[str] = []
    if knowbe4_stats is not None:
        total += int(knowbe4_stats.get("total", 0))
        completed += int(knowbe4_stats.get("completed", 0))
        sources.append("knowbe4")
    if hoxhunt_stats is not None:
        total += int(hoxhunt_stats.get("total", 0))
        completed += int(hoxhunt_stats.get("completed", 0))
        sources.append("hoxhunt")

    incomplete = max(0, total - completed)
    stats = CompletionStats(total=total, completed=completed, incomplete=incomplete)

    return {
        "label": "Training Completion %",
        "completion_pct": stats.completion_pct,
        "total_users": stats.total,
        "completed_users": stats.completed,
        "incomplete_users": stats.incomplete,
        "sources": sources,
        "framework_evidence": list(TRAINING_FRAMEWORK_EVIDENCE),
    }


def compute_bgv_rollup(
    authbridge_stats: Optional[Dict[str, int]] = None,
    ongrid_stats: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """Combine AuthBridge + OnGrid BGV stats into a single roll-up."""
    total = 0
    completed = 0
    sources: List[str] = []
    if authbridge_stats is not None:
        total += int(authbridge_stats.get("total", 0))
        completed += int(authbridge_stats.get("completed", 0))
        sources.append("authbridge")
    if ongrid_stats is not None:
        total += int(ongrid_stats.get("total", 0))
        completed += int(ongrid_stats.get("completed", 0))
        sources.append("ongrid")

    incomplete = max(0, total - completed)
    stats = CompletionStats(total=total, completed=completed, incomplete=incomplete)

    return {
        "label": "BGV Completion %",
        "completion_pct": stats.completion_pct,
        "total_employees": stats.total,
        "completed_employees": stats.completed,
        "incomplete_employees": stats.incomplete,
        "sources": sources,
        "framework_evidence": list(BGV_FRAMEWORK_EVIDENCE),
    }


def compute_dashboard_widgets(
    knowbe4_stats: Optional[Dict[str, int]] = None,
    hoxhunt_stats: Optional[Dict[str, int]] = None,
    authbridge_stats: Optional[Dict[str, int]] = None,
    ongrid_stats: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """Top-level helper for the dashboard endpoint."""
    return {
        "training": compute_training_rollup(knowbe4_stats, hoxhunt_stats),
        "bgv": compute_bgv_rollup(authbridge_stats, ongrid_stats),
    }

"""
Compliance Scoring Engine — P2B.11.

Computes per-framework compliance scores from the most recent ControlCheckRun
of each control within (or before) a given as-of date.

Score formula (decided & documented):
  score = (pass_count / applicable_count) * 100
  where applicable_count = pass_count + fail_count (inconclusive EXCLUDED).

Rationale for excluding inconclusive:
  An inconclusive run signals "we don't yet know" — counting it as a failure
  would mark a healthy environment as failing simply because the check couldn't
  reach a verdict (e.g. transient API error). Counting as success would hide
  real risk. Excluding from the denominator gives a fair "score on what we
  actually know" — a separate `inconclusive_count` is surfaced for visibility.

Edge cases:
  - Zero applicable controls   → score = 0.0   (no signal yet)
  - All inconclusive           → score = 0.0   (no signal yet)
  - Control with no run        → counted as inconclusive (not yet evaluated)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.models.control_run import ControlCheckRun
from compliance_backend.models.score_snapshot import ComplianceScoreSnapshot

logger = logging.getLogger(__name__)

# Threshold used for the "score dropped" warning emitted by calculate_framework_score.
# This is data-layer logging only — actual alert publication on the event bus is
# explicitly out of scope for P2B.11.
SCORE_DROP_WARN_THRESHOLD = 10.0  # percentage points


@dataclass
class FrameworkScore:
    """Result of calculate_framework_score."""
    framework_id: str
    framework_short_code: Optional[str]
    score: float                  # 0.0 – 100.0
    pass_count: int
    fail_count: int
    inconclusive_count: int
    total_controls: int           # all controls in current version
    total_applicable: int         # pass + fail (denominator)
    as_of: datetime
    failing_control_ids: List[str]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["as_of"] = self.as_of.isoformat()
        return d


@dataclass
class CategoryBreakdown:
    category: str
    pass_count: int
    fail_count: int
    inconclusive_count: int
    score: float


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ScoringEngine:
    """Stateless service — pass DB session in via constructor."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    #  Per-framework score
    # ------------------------------------------------------------------ #

    async def calculate_framework_score(
        self,
        tenant_id: str,
        framework_id: str,
        as_of_date: Optional[datetime] = None,
    ) -> FrameworkScore:
        """Compute current score for one framework."""
        as_of = as_of_date or datetime.utcnow()

        # Resolve current framework version + controls
        framework = (await self.db.execute(
            select(Framework).where(Framework.id == framework_id)
        )).scalar_one_or_none()
        framework_short = framework.short_code if framework else None

        controls = await self._current_controls(framework_id)
        total_controls = len(controls)

        pass_count = 0
        fail_count = 0
        inconclusive_count = 0
        failing_ids: List[str] = []

        for ctrl in controls:
            status = await self._latest_status(ctrl.id, tenant_id, as_of)
            if status == "pass":
                pass_count += 1
            elif status == "fail":
                fail_count += 1
                failing_ids.append(ctrl.id)
            else:
                inconclusive_count += 1  # includes "not yet evaluated"

        total_applicable = pass_count + fail_count
        score = (pass_count / total_applicable * 100.0) if total_applicable > 0 else 0.0

        result = FrameworkScore(
            framework_id=framework_id,
            framework_short_code=framework_short,
            score=round(score, 2),
            pass_count=pass_count,
            fail_count=fail_count,
            inconclusive_count=inconclusive_count,
            total_controls=total_controls,
            total_applicable=total_applicable,
            as_of=as_of,
            failing_control_ids=failing_ids,
        )

        # Score-drop warning (data-layer only — no event bus emission here)
        await self._maybe_warn_on_drop(tenant_id, framework_id, result)
        return result

    # ------------------------------------------------------------------ #
    #  All frameworks
    # ------------------------------------------------------------------ #

    async def calculate_all_frameworks(
        self,
        tenant_id: str,
        as_of_date: Optional[datetime] = None,
    ) -> Dict[str, FrameworkScore]:
        """Compute scores for every framework in the registry, keyed by short_code."""
        frameworks = (await self.db.execute(
            select(Framework).order_by(Framework.short_code)
        )).scalars().all()

        out: Dict[str, FrameworkScore] = {}
        for fw in frameworks:
            score = await self.calculate_framework_score(
                tenant_id=tenant_id,
                framework_id=fw.id,
                as_of_date=as_of_date,
            )
            out[fw.short_code] = score
        return out

    # ------------------------------------------------------------------ #
    #  Category breakdown (for drill-down)
    # ------------------------------------------------------------------ #

    async def category_breakdown(
        self,
        tenant_id: str,
        framework_id: str,
        as_of_date: Optional[datetime] = None,
    ) -> List[CategoryBreakdown]:
        as_of = as_of_date or datetime.utcnow()
        controls = await self._current_controls(framework_id)

        # Group by category
        buckets: Dict[str, Dict[str, int]] = {}
        for ctrl in controls:
            cat = ctrl.category or "uncategorized"
            bucket = buckets.setdefault(
                cat, {"pass": 0, "fail": 0, "inconclusive": 0}
            )
            status = await self._latest_status(ctrl.id, tenant_id, as_of)
            if status in bucket:
                bucket[status] += 1
            else:
                bucket["inconclusive"] += 1

        out: List[CategoryBreakdown] = []
        for cat, b in sorted(buckets.items()):
            denom = b["pass"] + b["fail"]
            score = (b["pass"] / denom * 100.0) if denom > 0 else 0.0
            out.append(CategoryBreakdown(
                category=cat,
                pass_count=b["pass"],
                fail_count=b["fail"],
                inconclusive_count=b["inconclusive"],
                score=round(score, 2),
            ))
        return out

    # ------------------------------------------------------------------ #
    #  Trend (historical snapshots)
    # ------------------------------------------------------------------ #

    async def compliance_trend(
        self,
        tenant_id: str,
        framework_id: str,
        days_back: int = 30,
    ) -> List[Tuple[str, float]]:
        """Return (date_iso, score) pairs from snapshots, oldest first."""
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        rows = (await self.db.execute(
            select(ComplianceScoreSnapshot).where(
                and_(
                    ComplianceScoreSnapshot.tenant_id == tenant_id,
                    ComplianceScoreSnapshot.framework_id == framework_id,
                    ComplianceScoreSnapshot.snapshot_date >= cutoff,
                )
            ).order_by(ComplianceScoreSnapshot.snapshot_date.asc())
        )).scalars().all()
        return [(r.snapshot_date.isoformat(), r.score) for r in rows]

    # ------------------------------------------------------------------ #
    #  Snapshot writer
    # ------------------------------------------------------------------ #

    async def write_daily_snapshot(
        self,
        tenant_id: str,
        framework_id: str,
        as_of_date: Optional[datetime] = None,
    ) -> ComplianceScoreSnapshot:
        """Compute current score and persist a snapshot. Caller commits."""
        score = await self.calculate_framework_score(
            tenant_id=tenant_id,
            framework_id=framework_id,
            as_of_date=as_of_date,
        )
        snap = ComplianceScoreSnapshot(
            tenant_id=tenant_id,
            framework_id=framework_id,
            snapshot_date=score.as_of,
            score=score.score,
            pass_count=score.pass_count,
            fail_count=score.fail_count,
            inconclusive_count=score.inconclusive_count,
            total_applicable=score.total_applicable,
        )
        self.db.add(snap)
        await self.db.flush()
        return snap

    async def write_snapshots_for_all_frameworks(
        self,
        tenant_id: str,
        as_of_date: Optional[datetime] = None,
    ) -> List[ComplianceScoreSnapshot]:
        """Snapshot every framework — used by the nightly job."""
        frameworks = (await self.db.execute(
            select(Framework)
        )).scalars().all()
        snaps = []
        for fw in frameworks:
            snap = await self.write_daily_snapshot(
                tenant_id=tenant_id,
                framework_id=fw.id,
                as_of_date=as_of_date,
            )
            snaps.append(snap)
        return snaps

    # ------------------------------------------------------------------ #
    #  Internals
    # ------------------------------------------------------------------ #

    async def _current_controls(self, framework_id: str) -> List[Control]:
        versions = (await self.db.execute(
            select(FrameworkVersion).where(FrameworkVersion.framework_id == framework_id)
        )).scalars().all()
        if not versions:
            return []
        current = next((v for v in versions if v.is_current), versions[0])
        rows = (await self.db.execute(
            select(Control).where(Control.framework_version_id == current.id)
        )).scalars().all()
        return list(rows)

    async def _latest_status(
        self, control_id: str, tenant_id: str, as_of: datetime
    ) -> str:
        """Return 'pass' / 'fail' / 'inconclusive' / 'inconclusive' (default)."""
        row = (await self.db.execute(
            select(ControlCheckRun).where(
                and_(
                    ControlCheckRun.control_id == control_id,
                    ControlCheckRun.tenant_id == tenant_id,
                    ControlCheckRun.run_at <= as_of,
                )
            ).order_by(ControlCheckRun.run_at.desc()).limit(1)
        )).scalar_one_or_none()
        if row is None:
            return "inconclusive"  # never evaluated == not yet known
        return row.status

    async def _maybe_warn_on_drop(
        self,
        tenant_id: str,
        framework_id: str,
        current: FrameworkScore,
    ) -> None:
        """Log a warning when score has dropped > SCORE_DROP_WARN_THRESHOLD vs last snapshot."""
        last = (await self.db.execute(
            select(ComplianceScoreSnapshot)
            .where(
                and_(
                    ComplianceScoreSnapshot.tenant_id == tenant_id,
                    ComplianceScoreSnapshot.framework_id == framework_id,
                )
            )
            .order_by(ComplianceScoreSnapshot.snapshot_date.desc())
            .limit(1)
        )).scalar_one_or_none()
        if last is None:
            return
        delta = last.score - current.score
        if delta > SCORE_DROP_WARN_THRESHOLD:
            logger.warning(
                "Compliance score dropped: tenant=%s framework=%s prev=%.2f now=%.2f delta=%.2f",
                tenant_id, framework_id, last.score, current.score, delta,
            )

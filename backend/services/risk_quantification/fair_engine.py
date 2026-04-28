"""
FAIR Risk Quantification engine — Project_33a §13 LIVE
(MVP scaffold, 16th license module).

Reference: Open FAIR (https://www.opengroup.org/forum/security-forum-0/openfair).

Computation
-----------
    Loss Magnitude (LM) =
          (records_at_risk * data_record_value_usd)        # primary direct loss
        + breach_response_cost_usd                          # primary response loss
        + regulatory_fine_probability * regulatory_fine_amount_usd   # secondary
        + brand_damage_estimate_usd                          # secondary

    Annual Loss Exposure (ALE) = LEF * LM

The MVP version does NOT do Monte Carlo over LEF/LM distributions.  We
take point estimates the analyst supplies and compute deterministic ALE.
Probabilistic modelling is roadmap.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.risk_quantification import FAIRAssumptions, FAIRRiskAssessment

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FAIRDefaults:
    data_record_value_usd: float = 150.0
    breach_response_cost_usd: float = 500_000.0
    regulatory_fine_probability: float = 0.30
    regulatory_fine_amount_usd: float = 2_000_000.0
    brand_damage_estimate_usd: float = 1_000_000.0


DEFAULT_ASSUMPTIONS = FAIRDefaults()


# --------------------------------------------------------------------------- #
def compute_loss_magnitude(
    *,
    records_at_risk: int,
    assumptions: FAIRAssumptions | FAIRDefaults,
) -> tuple[float, dict[str, float]]:
    """
    Returns (LM, components_breakdown).

    Components breakdown is the per-component contribution so the dashboard
    can show 'data records X% / response Y% / regulatory Z% / brand W%'.
    """
    if records_at_risk < 0:
        raise ValueError("records_at_risk must be >= 0")

    direct_loss = records_at_risk * float(assumptions.data_record_value_usd)
    response_cost = float(assumptions.breach_response_cost_usd)
    regulatory_expected = (
        float(assumptions.regulatory_fine_probability)
        * float(assumptions.regulatory_fine_amount_usd)
    )
    brand_damage = float(assumptions.brand_damage_estimate_usd)
    total = direct_loss + response_cost + regulatory_expected + brand_damage

    components = {
        "direct_loss_records_usd": round(direct_loss, 2),
        "response_cost_usd": round(response_cost, 2),
        "regulatory_expected_usd": round(regulatory_expected, 2),
        "brand_damage_usd": round(brand_damage, 2),
    }
    return round(total, 2), components


def compute_ale(*, loss_event_frequency: float, loss_magnitude_usd: float) -> float:
    if loss_event_frequency < 0:
        raise ValueError("loss_event_frequency must be >= 0")
    if loss_magnitude_usd < 0:
        raise ValueError("loss_magnitude_usd must be >= 0")
    return round(loss_event_frequency * loss_magnitude_usd, 2)


# --------------------------------------------------------------------------- #
async def upsert_assumptions(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    data_record_value_usd: Optional[float] = None,
    breach_response_cost_usd: Optional[float] = None,
    regulatory_fine_probability: Optional[float] = None,
    regulatory_fine_amount_usd: Optional[float] = None,
    brand_damage_estimate_usd: Optional[float] = None,
    notes: Optional[str] = None,
) -> FAIRAssumptions:
    """Always inserts a new row (history preserved)."""
    if regulatory_fine_probability is not None and not (0.0 <= regulatory_fine_probability <= 1.0):
        raise ValueError("regulatory_fine_probability must be in [0,1]")
    for k, v in (
        ("data_record_value_usd", data_record_value_usd),
        ("breach_response_cost_usd", breach_response_cost_usd),
        ("regulatory_fine_amount_usd", regulatory_fine_amount_usd),
        ("brand_damage_estimate_usd", brand_damage_estimate_usd),
    ):
        if v is not None and v < 0:
            raise ValueError(f"{k} must be >= 0")

    a = FAIRAssumptions(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        data_record_value_usd=(
            data_record_value_usd if data_record_value_usd is not None
            else DEFAULT_ASSUMPTIONS.data_record_value_usd
        ),
        breach_response_cost_usd=(
            breach_response_cost_usd if breach_response_cost_usd is not None
            else DEFAULT_ASSUMPTIONS.breach_response_cost_usd
        ),
        regulatory_fine_probability=(
            regulatory_fine_probability if regulatory_fine_probability is not None
            else DEFAULT_ASSUMPTIONS.regulatory_fine_probability
        ),
        regulatory_fine_amount_usd=(
            regulatory_fine_amount_usd if regulatory_fine_amount_usd is not None
            else DEFAULT_ASSUMPTIONS.regulatory_fine_amount_usd
        ),
        brand_damage_estimate_usd=(
            brand_damage_estimate_usd if brand_damage_estimate_usd is not None
            else DEFAULT_ASSUMPTIONS.brand_damage_estimate_usd
        ),
        notes=notes,
    )
    db.add(a)
    await db.flush()
    return a


async def get_assumptions(
    db: AsyncSession, tenant_id: uuid.UUID
) -> FAIRAssumptions | FAIRDefaults:
    """Returns latest assumptions row OR DEFAULT_ASSUMPTIONS if none set."""
    row = (
        await db.execute(
            select(FAIRAssumptions)
            .where(FAIRAssumptions.tenant_id == tenant_id)
            .order_by(desc(FAIRAssumptions.created_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    return row if row is not None else DEFAULT_ASSUMPTIONS


# --------------------------------------------------------------------------- #
async def record_assessment(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    risk_id: str,
    risk_label: str,
    loss_event_frequency: float,
    records_at_risk: int = 0,
    extra_loss_usd: float = 0.0,
    assumptions: FAIRAssumptions | FAIRDefaults | None = None,
) -> FAIRRiskAssessment:
    """
    Compute LM + ALE for a risk and persist.

    `extra_loss_usd` lets the analyst layer in additional one-off costs
    (e.g. ransom payment).
    """
    if not risk_id or not risk_id.strip():
        raise ValueError("risk_id required")
    if not risk_label or not risk_label.strip():
        raise ValueError("risk_label required")

    assum = assumptions if assumptions is not None else await get_assumptions(db, tenant_id)
    lm, components = compute_loss_magnitude(
        records_at_risk=records_at_risk, assumptions=assum
    )
    if extra_loss_usd:
        if extra_loss_usd < 0:
            raise ValueError("extra_loss_usd must be >= 0")
        lm += extra_loss_usd
        components["extra_loss_usd"] = round(extra_loss_usd, 2)

    ale = compute_ale(loss_event_frequency=loss_event_frequency, loss_magnitude_usd=lm)

    row = FAIRRiskAssessment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        risk_id=risk_id.strip(),
        risk_label=risk_label.strip(),
        loss_event_frequency=loss_event_frequency,
        loss_magnitude_usd=lm,
        annual_loss_exposure_usd=ale,
        components=components,
    )
    db.add(row)
    await db.flush()
    return row


async def list_assessments(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    limit: int = 100,
    offset: int = 0,
) -> list[FAIRRiskAssessment]:
    stmt = (
        select(FAIRRiskAssessment)
        .where(FAIRRiskAssessment.tenant_id == tenant_id)
        .order_by(FAIRRiskAssessment.annual_loss_exposure_usd.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_assessment_by_risk_id(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    risk_id: str,
) -> Optional[FAIRRiskAssessment]:
    """Latest assessment for the given risk_id."""
    stmt = (
        select(FAIRRiskAssessment)
        .where(
            FAIRRiskAssessment.tenant_id == tenant_id,
            FAIRRiskAssessment.risk_id == risk_id,
        )
        .order_by(desc(FAIRRiskAssessment.computed_at))
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def aggregate(db: AsyncSession, tenant_id: uuid.UUID, *, top_n: int = 10) -> dict[str, Any]:
    """Return total ALE + top-N risks (each with its latest ALE)."""
    # Latest assessment per risk_id
    subq = (
        select(
            FAIRRiskAssessment.risk_id,
            func.max(FAIRRiskAssessment.computed_at).label("max_at"),
        )
        .where(FAIRRiskAssessment.tenant_id == tenant_id)
        .group_by(FAIRRiskAssessment.risk_id)
        .subquery()
    )
    latest_stmt = (
        select(FAIRRiskAssessment)
        .join(
            subq,
            (FAIRRiskAssessment.risk_id == subq.c.risk_id)
            & (FAIRRiskAssessment.computed_at == subq.c.max_at),
        )
        .where(FAIRRiskAssessment.tenant_id == tenant_id)
    )
    latest_rows = list((await db.execute(latest_stmt)).scalars().all())
    latest_rows.sort(key=lambda r: float(r.annual_loss_exposure_usd), reverse=True)

    total_ale = sum(float(r.annual_loss_exposure_usd) for r in latest_rows)
    top_risks = latest_rows[:top_n]
    return {
        "total_ale_usd": round(total_ale, 2),
        "risk_count": len(latest_rows),
        "top_risks": [
            {
                "risk_id": r.risk_id,
                "risk_label": r.risk_label,
                "annual_loss_exposure_usd": float(r.annual_loss_exposure_usd),
                "loss_event_frequency": r.loss_event_frequency,
                "loss_magnitude_usd": float(r.loss_magnitude_usd),
                "components": r.components,
                "computed_at": r.computed_at,
            }
            for r in top_risks
        ],
    }

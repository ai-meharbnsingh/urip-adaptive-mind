"""
ai_security_service — Project_33a §13 LIVE (MVP scaffold, 13th license module).

Honest depth note: this is the inventory + governance ledger.  The runtime
prompt-injection sidecar and model-file scanner are roadmap.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.ai_security import (
    GOVERNANCE_FRAMEWORKS,
    PROVIDER_VALUES,
    AIModel,
    GovernanceAssessment,
    PromptInjectionEvent,
)

logger = logging.getLogger(__name__)


_VALID_SEVERITY = {"critical", "high", "medium", "low"}
_VALID_DETECTION_SOURCE = {"manual_upload", "webhook", "sidecar"}
_VALID_RISK_LEVEL = {"critical", "high", "medium", "low"}


# --------------------------------------------------------------------------- #
def _validate_provider(p: str) -> None:
    if p not in PROVIDER_VALUES:
        raise ValueError(f"Invalid provider {p!r}; allowed: {sorted(PROVIDER_VALUES)}")


def _validate_framework(f: str) -> None:
    if f not in GOVERNANCE_FRAMEWORKS:
        raise ValueError(f"Invalid framework {f!r}; allowed: {sorted(GOVERNANCE_FRAMEWORKS)}")


# --------------------------------------------------------------------------- #
async def create_ai_model(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    name: str,
    provider: str,
    purpose: Optional[str] = None,
    training_data_summary: Optional[str] = None,
    deployment_endpoints: Optional[list[str]] = None,
    risk_level: str = "medium",
    last_audited_at: Optional[datetime] = None,
) -> AIModel:
    if not name or not name.strip():
        raise ValueError("name is required")
    _validate_provider(provider)
    if risk_level not in _VALID_RISK_LEVEL:
        raise ValueError(f"Invalid risk_level {risk_level!r}")

    model = AIModel(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=name.strip(),
        provider=provider,
        purpose=purpose,
        training_data_summary=training_data_summary,
        deployment_endpoints=deployment_endpoints,
        risk_level=risk_level,
        last_audited_at=last_audited_at,
    )
    db.add(model)
    await db.flush()
    return model


async def list_ai_models(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    provider: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AIModel]:
    stmt = select(AIModel).where(AIModel.tenant_id == tenant_id)
    if provider:
        _validate_provider(provider)
        stmt = stmt.where(AIModel.provider == provider)
    stmt = stmt.order_by(AIModel.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# --------------------------------------------------------------------------- #
async def record_prompt_injection(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    prompt_excerpt: str,
    ai_model_id: Optional[uuid.UUID] = None,
    detection_source: str = "manual_upload",
    severity: str = "medium",
    blocked: bool = False,
    metadata: Optional[dict[str, Any]] = None,
) -> PromptInjectionEvent:
    if not prompt_excerpt or not prompt_excerpt.strip():
        raise ValueError("prompt_excerpt is required")
    if detection_source not in _VALID_DETECTION_SOURCE:
        raise ValueError(f"Invalid detection_source {detection_source!r}")
    if severity not in _VALID_SEVERITY:
        raise ValueError(f"Invalid severity {severity!r}")

    event = PromptInjectionEvent(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        ai_model_id=ai_model_id,
        prompt_excerpt=prompt_excerpt.strip()[:4000],  # protect storage
        detection_source=detection_source,
        severity=severity,
        blocked=blocked,
        metadata_json=metadata,
    )
    db.add(event)
    await db.flush()
    return event


async def list_prompt_injections(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    ai_model_id: Optional[uuid.UUID] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[PromptInjectionEvent]:
    stmt = select(PromptInjectionEvent).where(PromptInjectionEvent.tenant_id == tenant_id)
    if ai_model_id:
        stmt = stmt.where(PromptInjectionEvent.ai_model_id == ai_model_id)
    if severity:
        stmt = stmt.where(PromptInjectionEvent.severity == severity)
    stmt = stmt.order_by(PromptInjectionEvent.detected_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# --------------------------------------------------------------------------- #
async def record_governance_assessment(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    ai_model_id: uuid.UUID,
    framework: str,
    score: int,
    findings: Optional[list[dict[str, Any]]] = None,
) -> GovernanceAssessment:
    _validate_framework(framework)
    if not isinstance(score, int) or score < 0 or score > 100:
        raise ValueError("score must be int in [0,100]")

    g = GovernanceAssessment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        ai_model_id=ai_model_id,
        framework=framework,
        score=score,
        findings=findings,
    )
    db.add(g)
    await db.flush()
    return g


async def list_governance_assessments(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    ai_model_id: Optional[uuid.UUID] = None,
) -> list[GovernanceAssessment]:
    stmt = select(GovernanceAssessment).where(GovernanceAssessment.tenant_id == tenant_id)
    if ai_model_id:
        stmt = stmt.where(GovernanceAssessment.ai_model_id == ai_model_id)
    stmt = stmt.order_by(GovernanceAssessment.assessed_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def aggregate_governance_status(
    db: AsyncSession, tenant_id: uuid.UUID
) -> dict[str, Any]:
    """Latest governance score per (model, framework) pair + per-framework averages."""
    # Pull all rows (small N — MVP scaffold)
    stmt = select(GovernanceAssessment, AIModel).join(
        AIModel, GovernanceAssessment.ai_model_id == AIModel.id
    ).where(GovernanceAssessment.tenant_id == tenant_id)
    rows = (await db.execute(stmt)).all()

    latest_by_pair: dict[tuple[uuid.UUID, str], GovernanceAssessment] = {}
    model_names: dict[uuid.UUID, str] = {}
    for g, m in rows:
        model_names[m.id] = m.name
        key = (m.id, g.framework)
        prior = latest_by_pair.get(key)
        if prior is None or g.assessed_at > prior.assessed_at:
            latest_by_pair[key] = g

    by_framework: dict[str, list[int]] = {fw: [] for fw in GOVERNANCE_FRAMEWORKS}
    per_model: list[dict[str, Any]] = []
    for (model_id, framework), g in latest_by_pair.items():
        by_framework[framework].append(g.score)
        per_model.append({
            "model_id": str(model_id),
            "model_name": model_names.get(model_id),
            "framework": framework,
            "score": g.score,
            "assessed_at": g.assessed_at,
        })

    averages = {
        fw: (round(sum(scores) / len(scores), 2) if scores else None)
        for fw, scores in by_framework.items()
    }

    # Total models in inventory
    total_models = (await db.execute(
        select(func.count(AIModel.id)).where(AIModel.tenant_id == tenant_id)
    )).scalar_one()

    return {
        "total_models": total_models,
        "framework_averages": averages,
        "per_model_assessments": per_model,
    }

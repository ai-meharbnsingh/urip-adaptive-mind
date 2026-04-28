"""
Auditor read-only API — P2B.10

All endpoints below require an auditor JWT (kind="auditor"). They are
filtered automatically by the auditor's bound (tenant_id, framework_id,
audit_period_start, audit_period_end). Every action is logged to
auditor_activity_log.

Endpoints:
  GET  /auditor/controls                  — controls in framework with current status
  GET  /auditor/controls/{id}             — control detail + evidence list
  GET  /auditor/evidence                  — list evidence in audit period
  GET  /auditor/evidence/{id}/download    — download a single evidence file
  GET  /auditor/policies                  — list policies + acknowledgment status
  GET  /auditor/policies/{id}             — policy detail + version history
  POST /auditor/evidence-requests         — request additional evidence
"""
from __future__ import annotations

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.database import get_async_session
from compliance_backend.middleware.auditor_auth import (
    require_auditor,
    AuditorContext,
    log_auditor_action,
)
from compliance_backend.models.framework import (
    Framework,
    FrameworkVersion,
    Control,
)
from compliance_backend.models.control_run import ControlCheckRun
from compliance_backend.models.evidence import Evidence
from compliance_backend.models.auditor import EvidenceRequest
from compliance_backend.services.evidence_service import EvidenceService

router = APIRouter(prefix="/auditor", tags=["auditor"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AuditorControlOut(BaseModel):
    id: str
    control_code: str
    category: str
    title: Optional[str]
    description: str
    # Latest status within audit period: pass | fail | inconclusive | not_evaluated
    current_status: str
    last_run_at: Optional[str]


class AuditorEvidenceOut(BaseModel):
    id: str
    control_id: str
    type: str
    audit_period: str
    captured_at: str
    captured_by: str


class AuditorControlDetail(BaseModel):
    control: AuditorControlOut
    evidence: List[AuditorEvidenceOut]


class AuditorPolicyOut(BaseModel):
    id: str
    name: str
    current_version: Optional[str]
    acknowledged_count: int
    pending_count: int


class AuditorPolicyDetail(BaseModel):
    id: str
    name: str
    description: Optional[str]
    versions: List[dict]


class EvidenceRequestCreate(BaseModel):
    control_id: Optional[str] = None
    description: str = Field(..., min_length=1, max_length=4000)


class EvidenceRequestOut(BaseModel):
    id: str
    control_id: Optional[str]
    description: str
    requested_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _list_framework_controls(
    session: AsyncSession, framework_id: str
) -> List[Control]:
    """Return controls of the framework's current version."""
    versions = (await session.execute(
        select(FrameworkVersion)
        .where(FrameworkVersion.framework_id == framework_id)
        .order_by(FrameworkVersion.is_current.desc())
    )).scalars().all()
    if not versions:
        return []
    current = next((v for v in versions if v.is_current), versions[0])
    rows = (await session.execute(
        select(Control)
        .where(Control.framework_version_id == current.id)
        .order_by(Control.control_code)
    )).scalars().all()
    return list(rows)


async def _latest_run_status(
    session: AsyncSession,
    control_id: str,
    tenant_id: str,
    period_end,
) -> tuple[str, Optional[str]]:
    """Return (status, last_run_at_iso) for a control within audit period."""
    row = (await session.execute(
        select(ControlCheckRun)
        .where(
            and_(
                ControlCheckRun.control_id == control_id,
                ControlCheckRun.tenant_id == tenant_id,
                ControlCheckRun.run_at <= period_end,
            )
        )
        .order_by(ControlCheckRun.run_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if row is None:
        return "not_evaluated", None
    return row.status, row.run_at.isoformat()


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------

@router.get("/controls", response_model=List[AuditorControlOut])
async def list_controls(
    request: Request,
    auditor: AuditorContext = Depends(require_auditor),
    session: AsyncSession = Depends(get_async_session),
) -> List[AuditorControlOut]:
    controls = await _list_framework_controls(session, auditor.framework_id)
    out: List[AuditorControlOut] = []
    for c in controls:
        status_str, last_run = await _latest_run_status(
            session, c.id, auditor.tenant_id, auditor.period_end,
        )
        out.append(AuditorControlOut(
            id=c.id,
            control_code=c.control_code,
            category=c.category,
            title=c.title,
            description=c.description,
            current_status=status_str,
            last_run_at=last_run,
        ))
    await log_auditor_action(
        session, auditor, action="list_controls",
        target_type="control", target_id=None, request=request,
    )
    await session.commit()
    return out


@router.get("/controls/{control_id}", response_model=AuditorControlDetail)
async def get_control(
    control_id: str,
    request: Request,
    auditor: AuditorContext = Depends(require_auditor),
    session: AsyncSession = Depends(get_async_session),
) -> AuditorControlDetail:
    # Verify control belongs to auditor's framework.
    #
    # M8 / Kimi MED-008 — Use the SAME generic 404 message for every
    # non-visible case (control does not exist OR control belongs to a
    # different framework).  Differentiating the two messages lets an
    # auditor enumerate control IDs across frameworks they should not see.
    GENERIC_NOT_FOUND = "Control not found."
    control = (await session.execute(
        select(Control).where(Control.id == control_id)
    )).scalar_one_or_none()
    if control is None:
        raise HTTPException(status_code=404, detail=GENERIC_NOT_FOUND)
    fv = (await session.execute(
        select(FrameworkVersion).where(FrameworkVersion.id == control.framework_version_id)
    )).scalar_one_or_none()
    if fv is None or fv.framework_id != auditor.framework_id:
        raise HTTPException(status_code=404, detail=GENERIC_NOT_FOUND)

    status_str, last_run = await _latest_run_status(
        session, control.id, auditor.tenant_id, auditor.period_end,
    )

    evidence_rows = (await session.execute(
        select(Evidence).where(
            and_(
                Evidence.control_id == control_id,
                Evidence.tenant_id == auditor.tenant_id,
                Evidence.captured_at >= auditor.period_start,
                Evidence.captured_at <= auditor.period_end,
            )
        ).order_by(Evidence.captured_at.desc())
    )).scalars().all()

    detail = AuditorControlDetail(
        control=AuditorControlOut(
            id=control.id,
            control_code=control.control_code,
            category=control.category,
            title=control.title,
            description=control.description,
            current_status=status_str,
            last_run_at=last_run,
        ),
        evidence=[
            AuditorEvidenceOut(
                id=e.id, control_id=e.control_id, type=e.type,
                audit_period=e.audit_period,
                captured_at=e.captured_at.isoformat(),
                captured_by=e.captured_by,
            )
            for e in evidence_rows
        ],
    )

    await log_auditor_action(
        session, auditor, action="view_control",
        target_type="control", target_id=control.id, request=request,
    )
    await session.commit()
    return detail


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

@router.get("/evidence", response_model=List[AuditorEvidenceOut])
async def list_evidence(
    request: Request,
    control_id: Optional[str] = Query(None),
    auditor: AuditorContext = Depends(require_auditor),
    session: AsyncSession = Depends(get_async_session),
) -> List[AuditorEvidenceOut]:
    filters = [
        Evidence.tenant_id == auditor.tenant_id,
        Evidence.captured_at >= auditor.period_start,
        Evidence.captured_at <= auditor.period_end,
    ]
    if control_id:
        filters.append(Evidence.control_id == control_id)
    # Restrict to evidence whose framework matches the auditor's framework.
    # Some evidence rows have framework_id NULL (auto-collected before framework
    # was wired). We additionally accept those if their control belongs to the
    # framework — but for safety on the auditor side, we require an explicit match.
    filters.append(Evidence.framework_id == auditor.framework_id)

    rows = (await session.execute(
        select(Evidence).where(and_(*filters)).order_by(Evidence.captured_at.desc())
    )).scalars().all()

    out = [
        AuditorEvidenceOut(
            id=e.id, control_id=e.control_id, type=e.type,
            audit_period=e.audit_period,
            captured_at=e.captured_at.isoformat(),
            captured_by=e.captured_by,
        )
        for e in rows
    ]
    await log_auditor_action(
        session, auditor, action="list_evidence",
        target_type="evidence", target_id=None, request=request,
    )
    await session.commit()
    return out


@router.get("/evidence/{evidence_id}/download")
async def download_evidence(
    evidence_id: str,
    request: Request,
    auditor: AuditorContext = Depends(require_auditor),
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    svc = EvidenceService(db=session)
    record = await svc.get_evidence(evidence_id, auditor.tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Evidence not found.")
    # Framework + period scoping
    if record.framework_id != auditor.framework_id:
        raise HTTPException(status_code=404, detail="Evidence not in audited framework.")
    if not (auditor.period_start <= record.captured_at <= auditor.period_end):
        raise HTTPException(status_code=404, detail="Evidence outside audit period.")

    try:
        content = await svc.get_evidence_content(evidence_id, auditor.tenant_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Evidence artifact missing.")
    except Exception as exc:
        # CRIT-009 — surface tamper events to the auditor as 409, not 500.
        # Importing inside the handler avoids a top-level cycle.
        from compliance_backend.services.evidence_service import EvidenceTamperError

        if isinstance(exc, EvidenceTamperError):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Evidence integrity check failed — on-disk artifact does "
                    "not match the recorded hash. Notify the tenant admin."
                ),
            )
        raise

    await log_auditor_action(
        session, auditor, action="download_evidence",
        target_type="evidence", target_id=evidence_id, request=request,
    )
    await session.commit()

    content_type_map = {
        "screenshot": "image/png",
        "config": "application/json",
        "log": "text/plain",
        "ticket": "application/json",
        "document": "application/octet-stream",
    }
    media_type = content_type_map.get(record.type, "application/octet-stream")
    # CRIT-009 — include the integrity hash so the external auditor can
    # independently verify the file matches what compliance recorded.
    response_headers = {
        "Content-Disposition": f'attachment; filename="evidence_{evidence_id}.bin"',
    }
    if record.content_sha256:
        response_headers["X-Evidence-Hash"] = record.content_sha256
    return Response(
        content=content,
        media_type=media_type,
        headers=response_headers,
    )


# ---------------------------------------------------------------------------
# Policies — defensive imports because policy module is owned by Kimi
# ---------------------------------------------------------------------------

@router.get("/policies", response_model=List[AuditorPolicyOut])
async def list_policies(
    request: Request,
    auditor: AuditorContext = Depends(require_auditor),
    session: AsyncSession = Depends(get_async_session),
) -> List[AuditorPolicyOut]:
    """List policies + acknowledgment counts.

    Defensive: this scope cannot touch policy* services owned by Kimi.
    We read directly from the policy/policy_version/policy_acknowledgment models
    using SQL only (no business logic).
    """
    out: List[AuditorPolicyOut] = []
    try:
        from compliance_backend.models.policy import (
            Policy,
            PolicyVersion,
            PolicyAcknowledgment,
        )
    except ImportError:
        # Policy models not present in this build — return empty list rather than 500.
        await log_auditor_action(
            session, auditor, action="list_policies",
            target_type="policy", target_id=None, request=request,
        )
        await session.commit()
        return out

    policies = (await session.execute(
        select(Policy).where(Policy.tenant_id == auditor.tenant_id)
    )).scalars().all()

    for p in policies:
        # Current version
        latest_v = (await session.execute(
            select(PolicyVersion)
            .where(PolicyVersion.policy_id == p.id)
            .order_by(PolicyVersion.created_at.desc())
            .limit(1)
        )).scalar_one_or_none()
        # Ack counts within audit period
        acks = (await session.execute(
            select(PolicyAcknowledgment).where(
                and_(
                    PolicyAcknowledgment.policy_id == p.id,
                    PolicyAcknowledgment.acknowledged_at >= auditor.period_start,
                    PolicyAcknowledgment.acknowledged_at <= auditor.period_end,
                )
            )
        )).scalars().all()
        ack_count = len(acks)
        out.append(AuditorPolicyOut(
            id=p.id,
            name=getattr(p, "name", getattr(p, "title", "(unnamed)")),
            current_version=getattr(latest_v, "version_number", None) if latest_v else None,
            acknowledged_count=ack_count,
            pending_count=0,  # Pending count requires user-roster knowledge — out of scope.
        ))

    await log_auditor_action(
        session, auditor, action="list_policies",
        target_type="policy", target_id=None, request=request,
    )
    await session.commit()
    return out


@router.get("/policies/{policy_id}", response_model=AuditorPolicyDetail)
async def get_policy(
    policy_id: str,
    request: Request,
    auditor: AuditorContext = Depends(require_auditor),
    session: AsyncSession = Depends(get_async_session),
) -> AuditorPolicyDetail:
    try:
        from compliance_backend.models.policy import Policy, PolicyVersion
    except ImportError:
        raise HTTPException(status_code=404, detail="Policy not found.")

    policy = (await session.execute(
        select(Policy).where(
            and_(Policy.id == policy_id, Policy.tenant_id == auditor.tenant_id)
        )
    )).scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found.")

    versions = (await session.execute(
        select(PolicyVersion).where(PolicyVersion.policy_id == policy.id)
        .order_by(PolicyVersion.created_at.desc())
    )).scalars().all()

    detail = AuditorPolicyDetail(
        id=policy.id,
        name=getattr(policy, "name", getattr(policy, "title", "(unnamed)")),
        description=getattr(policy, "description", None),
        versions=[
            {
                "id": v.id,
                "version_number": getattr(v, "version_number", None),
                "created_at": v.created_at.isoformat() if getattr(v, "created_at", None) else None,
            }
            for v in versions
        ],
    )

    await log_auditor_action(
        session, auditor, action="view_policy",
        target_type="policy", target_id=policy.id, request=request,
    )
    await session.commit()
    return detail


# ---------------------------------------------------------------------------
# Evidence requests
# ---------------------------------------------------------------------------

@router.post(
    "/evidence-requests",
    response_model=EvidenceRequestOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_evidence_request(
    body: EvidenceRequestCreate,
    request: Request,
    auditor: AuditorContext = Depends(require_auditor),
    session: AsyncSession = Depends(get_async_session),
) -> EvidenceRequestOut:
    req = EvidenceRequest(
        auditor_access_id=auditor.access_id,
        control_id=body.control_id,
        description=body.description,
    )
    session.add(req)
    await session.flush()

    await log_auditor_action(
        session, auditor, action="request_evidence",
        target_type="evidence_request", target_id=req.id, request=request,
    )
    await session.commit()

    return EvidenceRequestOut(
        id=req.id,
        control_id=req.control_id,
        description=req.description,
        requested_at=req.requested_at.isoformat(),
    )

"""
Training + BGV roll-up dashboard endpoint.

Endpoints:
  GET /admin/training-bgv-rollup
        Returns the dashboard widget payload for the caller's tenant:
            {
              "training": {label, completion_pct, total_users, …, framework_evidence},
              "bgv":      {label, completion_pct, total_employees, …, framework_evidence}
            }

  POST /admin/training-bgv-rollup
        Same shape as GET but lets the caller supply per-source stats inline
        (used by the connector scheduler when it has just polled the LMS/BGV
        connectors).

Auth: require_compliance_admin — only compliance admins can view the
dashboard widgets.

This is the wiring for PART 4(R/S):
  - Compliance dashboard: "Training Completion %" + "BGV Completion %"
  - Auditor portal: framework_evidence shows which controls these stats evidence
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from compliance_backend.middleware.auth import is_compliance_admin, require_auth
from compliance_backend.services.training_bgv_rollup import (
    compute_dashboard_widgets,
)

router = APIRouter(prefix="/admin/training-bgv-rollup", tags=["dashboard"])


class SourceStats(BaseModel):
    total: int = Field(default=0, ge=0)
    completed: int = Field(default=0, ge=0)


class RollupRequest(BaseModel):
    knowbe4: Optional[SourceStats] = None
    hoxhunt: Optional[SourceStats] = None
    authbridge: Optional[SourceStats] = None
    ongrid: Optional[SourceStats] = None


def _require_admin(claims: dict) -> None:
    if not is_compliance_admin(claims):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required.",
        )


@router.get("")
async def get_rollup(claims: dict = Depends(require_auth)) -> Dict[str, Any]:
    """
    Return the latest training + BGV roll-up for the caller's tenant.

    For now (no connector scheduler wired in yet), this returns zeroed
    widgets so the dashboard renders the layout immediately. The POST
    variant lets the scheduler push real numbers in.
    """
    _require_admin(claims)
    return compute_dashboard_widgets()


@router.post("")
async def post_rollup(
    body: RollupRequest,
    claims: dict = Depends(require_auth),
) -> Dict[str, Any]:
    """Compute roll-up from supplied per-source stats."""
    _require_admin(claims)

    def _to_dict(s: Optional[SourceStats]) -> Optional[Dict[str, int]]:
        return None if s is None else {"total": s.total, "completed": s.completed}

    return compute_dashboard_widgets(
        knowbe4_stats=_to_dict(body.knowbe4),
        hoxhunt_stats=_to_dict(body.hoxhunt),
        authbridge_stats=_to_dict(body.authbridge),
        ongrid_stats=_to_dict(body.ongrid),
    )

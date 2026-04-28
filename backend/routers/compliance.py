"""Thin URIP-side compliance router.

The full compliance product is a separate service running on its own port
(see compliance/ directory). The URIP frontend's domain-compliance-summary
page just needs a posture aggregate per framework — nothing tenant-mutating
happens here. This router returns an empty list when no compliance data is
available locally so the frontend renders "--" instead of throwing a 404.

When the standalone compliance service is wired in via service-to-service
HTTP, replace the body of frameworks_summary with a fetch + cache.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.middleware.auth import get_current_user
from backend.models.user import User

router = APIRouter()


@router.get("/frameworks/summary")
async def frameworks_summary(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Aggregate compliance posture per framework.

    Returns an empty list today — the standalone compliance service holds
    the framework data. The frontend's domain-compliance-summary.html
    renders "--" for unknown scores, so an empty response is a graceful
    no-op (vs. a 404 that lit up the browser console).
    """
    return {"frameworks": []}

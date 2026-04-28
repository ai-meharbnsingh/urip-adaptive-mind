"""
backend/routers/notifications.py — Compliance notifications endpoint.

Exposes the in-process notification store maintained by
backend/services/event_subscribers.py so the frontend can render unread
counts and a notification feed.

Closes the Gemini round-B "zombie data sink" finding: notifications were
ingested via event_subscribers but no GET endpoint surfaced them.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from backend.middleware.auth import get_current_user
from backend.services.event_subscribers import (
    get_compliance_notifications,
    clear_compliance_notifications,
)

router = APIRouter()


@router.get("", summary="List compliance notifications for the current tenant")
async def list_notifications(current_user: Any = Depends(get_current_user)):
    tenant_id = str(getattr(current_user, "tenant_id", "")) or "unknown"
    items = get_compliance_notifications(tenant_id)
    return {"items": items, "total": len(items), "tenant_id": tenant_id}


@router.delete("", summary="Clear all notifications for the current tenant")
async def clear_notifications(current_user: Any = Depends(get_current_user)):
    tenant_id = str(getattr(current_user, "tenant_id", "")) or "unknown"
    clear_compliance_notifications(tenant_id)
    return {"cleared": True, "tenant_id": tenant_id}

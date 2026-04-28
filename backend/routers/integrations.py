"""
backend/routers/integrations.py — Lightweight integration health endpoint.

Provides a fast, unauthenticated-friendly status check for each registered
connector so the frontend "Not configured" detection works without requiring
full authentication.

Endpoints
---------
GET /api/integrations/{tool_name}/health
    Check whether a connector is configured and reachable for the current tenant.

    Response shape:
        {"status": "Connected",      "connector": "jira", "last_check": "2026-04-28T…"}
        {"status": "Not configured", "connector": "jira"}
        {"status": "Error",          "connector": "jira", "detail": "…message…"}

    HTTP status code is ALWAYS 200 — the frontend distinguishes state via
    the ``status`` field, not the HTTP code.

Design notes
------------
- The endpoint first checks whether credentials exist for the tenant.  If none
  are stored, it returns ``{"status": "Not configured"}`` immediately — no
  network call.
- If credentials exist, it instantiates the connector, calls authenticate()
  then health_check(), and returns the result.
- Falls back gracefully when the credential vault or DB is not configured:
  returns ``{"status": "Not configured"}`` rather than a 5xx.
- Uses ``_global_registry`` from connectors.base.registry to check connector
  existence without instantiation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.tenant import TenantContext
from connectors.base.registry import _global_registry

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{tool_name}/health", response_model=None)
async def integration_health(
    tool_name: str,
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Return the health status of a connector for the current tenant.

    Steps
    -----
    1. Check whether ``tool_name`` is a registered connector.
       → Unknown connector → {"status": "Not configured"}
    2. Look up stored credentials in the TenantConnectorCredential table.
       → No credentials → {"status": "Not configured"}
    3. Instantiate the connector, call authenticate(), then health_check().
       → Connected → {"status": "Connected", "last_check": "<iso>"}
       → Auth / health failure → {"status": "Error", "detail": "…"}

    Always returns HTTP 200 — status is communicated via the ``status`` field.
    """
    # ── Step 1: is this a known connector? ──────────────────────────────────
    if tool_name not in _global_registry:
        return {"status": "Not configured", "connector": tool_name}

    # ── Step 2: look up tenant credentials ──────────────────────────────────
    tenant_id: str = getattr(current_user, "tenant_id", None) or "unknown"
    credentials: dict[str, Any] | None = None

    try:
        from sqlalchemy import select

        from backend.models.tenant_connector_credential import TenantConnectorCredential
        from backend.services.crypto_service import decrypt_credentials

        result = await db.execute(
            select(TenantConnectorCredential).where(
                TenantConnectorCredential.tenant_id == tenant_id,
                TenantConnectorCredential.connector_name == tool_name,
            )
        )
        row = result.scalar_one_or_none()

        if row is None:
            return {"status": "Not configured", "connector": tool_name}

        credentials = decrypt_credentials(row.encrypted_credentials)

    except Exception as exc:
        # Vault / DB not yet wired in this environment — degrade gracefully.
        logger.warning(
            "integrations_health: credential lookup failed for %s/%s: %s",
            tenant_id, tool_name, exc,
        )
        return {"status": "Not configured", "connector": tool_name}

    if not credentials:
        return {"status": "Not configured", "connector": tool_name}

    # ── Step 3: instantiate and probe ────────────────────────────────────────
    try:
        factory = _global_registry.get(tool_name)
        connector = factory()

        # authenticate() verifies the stored credentials against the live API.
        credentials["tenant_id"] = tenant_id
        connector.authenticate(credentials)

        # health_check() returns a ConnectorHealth dataclass.
        health = connector.health_check()

        last_check = datetime.now(timezone.utc).isoformat()

        if health.status == "ok":
            return {
                "status": "Connected",
                "connector": tool_name,
                "last_check": last_check,
                "health_status": health.status,
            }
        else:
            return {
                "status": "Error",
                "connector": tool_name,
                "last_check": last_check,
                "health_status": health.status,
                "detail": health.last_error or "Connector health degraded.",
            }

    except Exception as exc:
        logger.warning(
            "integrations_health: probe failed for %s/%s: %s",
            tenant_id, tool_name, exc,
        )
        return {
            "status": "Error",
            "connector": tool_name,
            "detail": str(exc),
        }

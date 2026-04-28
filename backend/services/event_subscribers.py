"""
backend.services.event_subscribers — URIP-side handlers for cross-service events.

Subscribes to:
    compliance.control.failed   → store unified-panel notification + (if tenant
                                  has `compliance_link_auto_create_risk: true`)
                                  insert a Risk row whose `asset` encodes the
                                  failing control_id (the linkage anchor).
    compliance.policy.expiring  → store unified-panel notification.

Publishes:
    urip.risk.created   — fired by `publish_risk_created`
    urip.risk.resolved  — fired by `publish_risk_resolved`

IN-MEMORY NOTIFICATION STORE — DESIGN NOTE
-------------------------------------------
``_NOTIFICATIONS`` is an in-process dict keyed by tenant_id.  This is the
correct design for single-instance deployments and local development.

Gemini CRITICAL finding (AUDIT_GEMINI_TRI_A.md:44):
    In a multi-instance (HA / Kubernetes) deployment this store has two problems:
    1. Each pod maintains its own copy — a request hitting pod B won't see
       notifications written by pod A.
    2. A pod restart wipes all unseen notifications.

Migration path (deferred to separate sprint — see docs/SCALING.md):
    Replace ``_NOTIFICATIONS`` with Redis-backed storage:
        LPUSH urip:notif:{tenant_id} <json_payload>
        LRANGE urip:notif:{tenant_id} 0 -1  (read all)
        DEL    urip:notif:{tenant_id}        (clear)
    Use ``redis.asyncio`` (already in requirements.txt via celery[redis]).
    Set a TTL (e.g. 7 days) to prevent unbounded growth.
    Alternatively land notifications in the Postgres `audit_log` table so they
    survive Redis restarts and are queryable.

A startup warning is emitted when ``URIP_ENV=production`` to make this gap
explicitly visible in logs.

Idempotency
-----------
`register_urip_subscribers` is safe to call multiple times — duplicate
registrations are short-circuited via a sentinel attribute on the bus.
"""
from __future__ import annotations

import logging
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from backend.database import async_session as default_async_session
from backend.models.risk import Risk
from backend.models.tenant import Tenant
from shared.events import (
    TOPIC_CONTROL_FAILED,
    TOPIC_POLICY_EXPIRING,
    TOPIC_RISK_CREATED,
    TOPIC_RISK_RESOLVED,
    InProcessEventBus,
    get_event_bus,
)
from shared.events.topics import (
    ControlFailedPayload,
    PolicyExpiringPayload,
    RiskCreatedPayload,
    RiskResolvedPayload,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory notification store — single-instance only (see module docstring)
# ---------------------------------------------------------------------------

# Gemini CRITICAL finding (AUDIT_GEMINI_TRI_A.md:44): this store is in-process.
# Emit a structured warning at import time in production environments so the gap
# is visible in logs and monitoring.  Full Redis migration is tracked as a
# separate sprint (see docs/SCALING.md).
_URIP_ENV = os.environ.get("URIP_ENV", "").lower()
if _URIP_ENV in ("production", "prod", "staging"):
    logger.warning(
        "event_subscribers: _NOTIFICATIONS is an in-memory store — "
        "notifications will be lost on pod restart and are NOT shared across "
        "multiple instances (URIP_ENV=%s). "
        "Migrate to Redis pub/sub before scaling horizontally. "
        "See docs/SCALING.md for the migration path.",
        _URIP_ENV,
    )

# Tenant_id → list of {topic, payload, recv_at}.
_NOTIFICATIONS: dict[str, list[dict[str, Any]]] = defaultdict(list)
# Bound at import time to a sentinel so we can no-op double-register.
_REGISTERED_SENTINEL = "_urip_subscribers_registered"


# ---------------------------------------------------------------------------
# Notification store helpers
# ---------------------------------------------------------------------------
def _record_notification(tenant_id: str, topic: str, payload: dict) -> None:
    _NOTIFICATIONS[tenant_id].append(
        {
            "topic": topic,
            "payload": payload,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def get_compliance_notifications(tenant_id: str) -> list[dict[str, Any]]:
    """Caller — usually a unified-dashboard endpoint — reads what compliance has
    pushed for this tenant since process start."""
    return list(_NOTIFICATIONS.get(tenant_id, ()))


def clear_compliance_notifications(tenant_id: str | None = None) -> None:
    """Test helper."""
    if tenant_id is None:
        _NOTIFICATIONS.clear()
    else:
        _NOTIFICATIONS.pop(tenant_id, None)


# ---------------------------------------------------------------------------
# Subscriber callbacks
# ---------------------------------------------------------------------------
async def _on_control_failed(payload: dict[str, Any]) -> None:
    try:
        parsed = ControlFailedPayload(**payload)
    except Exception as exc:
        logger.warning("control_failed: invalid payload: %s", exc)
        return
    _record_notification(parsed.tenant_id, TOPIC_CONTROL_FAILED, payload)

    # If the tenant opted into auto-link, insert a Risk row.
    try:
        tenant_uuid = uuid.UUID(parsed.tenant_id)
    except ValueError:
        # tenant_id may be a non-UUID string in cross-service tests; skip.
        logger.debug("control_failed: tenant_id %r is not a UUID — auto-create skipped",
                     parsed.tenant_id)
        return

    # Always re-resolve through the module attribute so test fixtures that
    # rebind backend.database.async_session take effect.
    import backend.database as _db_mod
    sm = getattr(_db_mod, "async_session", default_async_session)
    async with sm() as session:
        tenant_q = await session.execute(select(Tenant).where(Tenant.id == tenant_uuid))
        tenant = tenant_q.scalar_one_or_none()
        if tenant is None:
            logger.info("control_failed: tenant %s unknown — skipping risk insert", tenant_uuid)
            return
        if not (tenant.settings or {}).get("compliance_link_auto_create_risk"):
            return
        suffix = uuid.uuid4().hex[:4].upper()
        from backend.services.sla_service import compute_sla_deadline
        risk = Risk(
            risk_id=f"RISK-CTRL-{suffix}",
            finding=f"Control failure: {parsed.control_name}",
            description=(
                f"Auto-linked from compliance control {parsed.control_id} "
                f"({parsed.framework}): {parsed.details or ''}"
            ).strip(),
            source="threat_intel",  # neutral source bucket for derived risks
            domain="compliance",
            cvss_score=7.5,
            severity="high",
            asset=f"control:{parsed.control_id}",
            owner_team="Compliance",
            status="open",
            sla_deadline=compute_sla_deadline("high"),
            tenant_id=tenant_uuid,
            composite_score=7.5,
            in_kev_catalog=False,
            exploit_status="none",
            epss_score=0.10,
        )
        session.add(risk)
        try:
            await session.commit()
        except Exception as exc:
            logger.exception("control_failed: failed to insert linked risk: %s", exc)


async def _on_policy_expiring(payload: dict[str, Any]) -> None:
    try:
        parsed = PolicyExpiringPayload(**payload)
    except Exception as exc:
        logger.warning("policy_expiring: invalid payload: %s", exc)
        return
    _record_notification(parsed.tenant_id, TOPIC_POLICY_EXPIRING, payload)


# ---------------------------------------------------------------------------
# Registration entry point
# ---------------------------------------------------------------------------
def register_urip_subscribers(bus: InProcessEventBus | None = None) -> InProcessEventBus:
    """Wire URIP-side handlers to the bus.  Idempotent."""
    bus = bus or get_event_bus()
    if getattr(bus, _REGISTERED_SENTINEL, False):
        return bus
    bus.subscribe(TOPIC_CONTROL_FAILED, _on_control_failed)
    bus.subscribe(TOPIC_POLICY_EXPIRING, _on_policy_expiring)
    setattr(bus, _REGISTERED_SENTINEL, True)
    return bus


# ---------------------------------------------------------------------------
# Publishers — used by URIP routers
# ---------------------------------------------------------------------------
async def publish_risk_created(risk: Risk) -> None:
    bus = get_event_bus()
    payload = RiskCreatedPayload(
        risk_id=risk.risk_id,
        tenant_id=str(risk.tenant_id) if risk.tenant_id else "",
        severity=str(risk.severity or "medium"),
        source=str(risk.source or "unknown"),
        finding=str(risk.finding or ""),
        cvss_score=float(risk.cvss_score or 0.0),
        created_at=(getattr(risk, "created_at", None) or datetime.now(timezone.utc)).isoformat(),
    ).model_dump()
    try:
        await bus.publish(TOPIC_RISK_CREATED, payload)
    except Exception as exc:  # pragma: no cover
        logger.warning("publish_risk_created failed: %s", exc)


async def publish_risk_resolved(
    risk: Risk, *, resolved_by: str = "system", resolution: str = "resolved"
) -> None:
    bus = get_event_bus()
    payload = RiskResolvedPayload(
        risk_id=risk.risk_id,
        tenant_id=str(risk.tenant_id) if risk.tenant_id else "",
        resolved_by=resolved_by,
        resolved_at=datetime.now(timezone.utc).isoformat(),
        resolution=resolution,
    ).model_dump()
    try:
        await bus.publish(TOPIC_RISK_RESOLVED, payload)
    except Exception as exc:  # pragma: no cover
        logger.warning("publish_risk_resolved failed: %s", exc)

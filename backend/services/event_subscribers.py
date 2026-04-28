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

NOTIFICATION BACKEND SELECTION
-------------------------------
At import time the module selects one of two notification backends:

  ``_InProcessNotificationStore``  — in-memory defaultdict, single-instance only.
    Default for dev/test when neither URIP_NOTIFICATION_BACKEND=redis nor
    URIP_ENV in {production, staging} with REDIS_URL set.

  ``_RedisNotificationStore``       — Redis-backed, horizontally scalable.
    Selected when EITHER:
      • URIP_NOTIFICATION_BACKEND=redis  (explicit opt-in, any env)
      • URIP_ENV in {production, prod, staging} AND REDIS_URL is set

    Key scheme: ``urip:notif:{tenant_id}``  (LPUSH / LRANGE / DEL)
    TTL: 7 days (NOTIF_TTL_SECONDS).

    If Redis is unreachable at push/get time, operations log a warning and
    fall back gracefully rather than crashing the app.

Idempotency
-----------
`register_urip_subscribers` is safe to call multiple times — duplicate
registrations are short-circuited via a sentinel attribute on the bus.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

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
# Constants
# ---------------------------------------------------------------------------
NOTIF_TTL_SECONDS = 7 * 24 * 3600  # 7 days
_REGISTERED_SENTINEL = "_urip_subscribers_registered"


# ---------------------------------------------------------------------------
# Backend protocol
# ---------------------------------------------------------------------------
@runtime_checkable
class NotificationBackend(Protocol):
    """Interface that both store implementations satisfy."""

    async def push(self, tenant_id: str, payload: dict[str, Any]) -> None: ...
    async def get(self, tenant_id: str) -> list[dict[str, Any]]: ...
    async def clear(self, tenant_id: str | None = None) -> None: ...


# ---------------------------------------------------------------------------
# Implementation 1: In-process (dev / test default)
# ---------------------------------------------------------------------------
class _InProcessNotificationStore:
    """Thread-safe enough for asyncio; not safe across processes."""

    def __init__(self) -> None:
        self._store: dict[str, list[dict[str, Any]]] = defaultdict(list)

    async def push(self, tenant_id: str, payload: dict[str, Any]) -> None:
        self._store[tenant_id].append(payload)

    async def get(self, tenant_id: str) -> list[dict[str, Any]]:
        return list(self._store.get(tenant_id, ()))

    async def clear(self, tenant_id: str | None = None) -> None:
        if tenant_id is None:
            self._store.clear()
        else:
            self._store.pop(tenant_id, None)


# ---------------------------------------------------------------------------
# Implementation 2: Redis-backed
# ---------------------------------------------------------------------------
class _RedisNotificationStore:
    """
    Redis-backed notification store.

    LPUSH urip:notif:{tenant_id}  → newest entry at index 0
    LRANGE … 0 -1                → all entries
    DEL …                        → clear

    Falls back gracefully (warning, no crash) when Redis is unreachable.
    """

    def __init__(self, redis_url: str) -> None:
        try:
            import redis.asyncio as aioredis  # type: ignore
            self._client = aioredis.from_url(redis_url, decode_responses=True)
        except Exception as exc:  # pragma: no cover
            logger.warning("_RedisNotificationStore: could not create client: %s", exc)
            self._client = None

    def _key(self, tenant_id: str) -> str:
        return f"urip:notif:{tenant_id}"

    async def push(self, tenant_id: str, payload: dict[str, Any]) -> None:
        if self._client is None:  # pragma: no cover
            return
        try:
            key = self._key(tenant_id)
            await self._client.lpush(key, json.dumps(payload))
            await self._client.expire(key, NOTIF_TTL_SECONDS)
        except Exception as exc:
            logger.warning(
                "RedisNotificationStore.push failed for tenant %s: %s — notification dropped",
                tenant_id, exc,
            )

    async def get(self, tenant_id: str) -> list[dict[str, Any]]:
        if self._client is None:  # pragma: no cover
            return []
        try:
            raw = await self._client.lrange(self._key(tenant_id), 0, -1)
            return [json.loads(x) for x in raw]
        except Exception as exc:
            logger.warning(
                "RedisNotificationStore.get failed for tenant %s: %s — returning []",
                tenant_id, exc,
            )
            return []

    async def clear(self, tenant_id: str | None = None) -> None:
        if self._client is None:  # pragma: no cover
            return
        try:
            if tenant_id is None:
                keys = await self._client.keys("urip:notif:*")
                if keys:
                    await self._client.delete(*keys)
            else:
                await self._client.delete(self._key(tenant_id))
        except Exception as exc:
            logger.warning(
                "RedisNotificationStore.clear failed (tenant=%s): %s", tenant_id, exc
            )


# ---------------------------------------------------------------------------
# Backend selection (chosen once at import time)
# ---------------------------------------------------------------------------
# Gemini round-D MED finding: prior code read URIP_ENV / REDIS_URL /
# URIP_NOTIFICATION_BACKEND directly from os.environ, bypassing settings
# (and ignoring .env values when shell environment differs). Source via
# settings so .env-loaded values + env vars stay in sync.
from backend.config import settings as _settings

_URIP_ENV = (getattr(_settings, "URIP_ENV", None) or os.environ.get("URIP_ENV", "")).lower()
_REDIS_URL = getattr(_settings, "REDIS_URL", None) or os.environ.get("REDIS_URL", "")
_NOTIFICATION_BACKEND_ENV = (
    getattr(_settings, "URIP_NOTIFICATION_BACKEND", None)
    or os.environ.get("URIP_NOTIFICATION_BACKEND", "")
).lower()

_use_redis = (
    _NOTIFICATION_BACKEND_ENV == "redis"
    or (_URIP_ENV in ("production", "prod", "staging") and bool(_REDIS_URL))
)

if _use_redis:
    _NOTIFICATION_BACKEND: NotificationBackend = _RedisNotificationStore(
        _REDIS_URL or "redis://redis:6379/0"
    )
    logger.info(
        "event_subscribers: using Redis notification backend (URIP_ENV=%s, REDIS_URL=%s)",
        _URIP_ENV or "n/a",
        _REDIS_URL,
    )
else:
    _NOTIFICATION_BACKEND = _InProcessNotificationStore()
    # Emit production warning ONLY when in-process store is selected in prod/staging.
    if _URIP_ENV in ("production", "prod", "staging"):
        logger.warning(
            "event_subscribers: _NOTIFICATIONS is an in-memory store — "
            "notifications will be lost on pod restart and are NOT shared across "
            "multiple instances (URIP_ENV=%s). "
            "Set REDIS_URL to enable the Redis backend, or set "
            "URIP_NOTIFICATION_BACKEND=redis explicitly. "
            "See docs/SCALING.md for the migration path.",
            _URIP_ENV,
        )


# ---------------------------------------------------------------------------
# Public store helpers (async — wraps the selected backend)
# ---------------------------------------------------------------------------
async def _record_notification(tenant_id: str, topic: str, payload: dict) -> None:
    """Push a structured notification entry into the selected backend."""
    entry = {
        "topic": topic,
        "payload": payload,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    await _NOTIFICATION_BACKEND.push(tenant_id, entry)


async def notify_compliance_event(tenant_id: str, payload: dict[str, Any]) -> None:
    """Push a raw payload dict directly into the backend (used by tests + future callers)."""
    await _NOTIFICATION_BACKEND.push(tenant_id, payload)


async def get_compliance_notifications(tenant_id: str) -> list[dict[str, Any]]:
    """Caller — usually a unified-dashboard endpoint — reads what compliance has
    pushed for this tenant."""
    return await _NOTIFICATION_BACKEND.get(tenant_id)


async def clear_compliance_notifications(tenant_id: str | None = None) -> None:
    """Clear notifications for a tenant (or all tenants if None)."""
    await _NOTIFICATION_BACKEND.clear(tenant_id)


# ---------------------------------------------------------------------------
# Subscriber callbacks
# ---------------------------------------------------------------------------
async def _on_control_failed(payload: dict[str, Any]) -> None:
    try:
        parsed = ControlFailedPayload(**payload)
    except Exception as exc:
        logger.warning("control_failed: invalid payload: %s", exc)
        return
    await _record_notification(parsed.tenant_id, TOPIC_CONTROL_FAILED, payload)

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
    await _record_notification(parsed.tenant_id, TOPIC_POLICY_EXPIRING, payload)


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

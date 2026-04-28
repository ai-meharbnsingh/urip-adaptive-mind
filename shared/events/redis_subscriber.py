"""
shared.events.redis_subscriber — Subscribe side of the distributed event bus.

When multiple URIP pods are running they each hold an in-process
InProcessEventBus singleton.  ``publish()`` already *mirrors* events to Redis
via ``InProcessEventBus.attach_redis``.  This module closes the other half:
each pod subscribes to the Redis channel pattern and fans inbound messages out
to its *local* bus subscribers WITHOUT re-publishing to Redis (which would
create an infinite loop).

Usage (called from backend/main.py startup hook when
URIP_DISTRIBUTED_EVENTS=1/true/yes):

    from shared.events.bus import _global_bus  # (or get_event_bus())
    from shared.events.redis_subscriber import start_redis_event_subscriber
    await start_redis_event_subscriber(bus, settings.REDIS_URL)

Loop-prevention
---------------
``_fanout_local(topic, payload)`` calls subscribers directly on the bus
*without* going through ``bus.publish()``.  ``bus.publish()`` is what
forwards to Redis, so skipping it breaks the loop:

    Redis message → _fanout_local → local subscribers only  ✓
    bus.publish   → local subscribers + Redis mirror        (publish path, not used here)

Idempotency
-----------
A module-level ``_SUBSCRIBER_TASK`` sentinel ensures that
``start_redis_event_subscriber`` is a no-op when called more than once in the
same process.

Graceful degradation
--------------------
If the redis package is missing or the connection fails, a warning is logged
and the function returns without raising — the app continues to run with
in-process-only event delivery.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shared.events.bus import InProcessEventBus

logger = logging.getLogger(__name__)

# Sentinel — set to the running asyncio.Task once started.
_SUBSCRIBER_TASK: asyncio.Task | None = None


async def start_redis_event_subscriber(
    bus: "InProcessEventBus",
    redis_url: str,
    channel_pattern: str = "urip:events:*",
) -> None:
    """
    Start (once) an asyncio background task that PSUBSCRIBEs to
    ``channel_pattern`` on Redis and dispatches every inbound message to
    local bus subscribers via ``_fanout_local`` (no Redis re-publish).

    Subsequent calls while the task is alive are no-ops.

    Args:
        bus: The process-local InProcessEventBus singleton.
        redis_url: Redis connection URL (e.g. "redis://redis:6379/0").
        channel_pattern: PSUBSCRIBE glob pattern (default "urip:events:*").
    """
    global _SUBSCRIBER_TASK

    # Idempotency guard — if already running, do nothing.
    if _SUBSCRIBER_TASK is not None and not _SUBSCRIBER_TASK.done():
        logger.debug("start_redis_event_subscriber: already running — no-op")
        return

    try:
        import redis.asyncio as aioredis  # type: ignore
    except ImportError:  # pragma: no cover
        logger.warning(
            "start_redis_event_subscriber: redis package not installed — "
            "distributed events disabled"
        )
        return

    _SUBSCRIBER_TASK = asyncio.create_task(
        _subscriber_loop(bus, redis_url, channel_pattern),
        name="urip-redis-event-subscriber",
    )
    logger.info(
        "start_redis_event_subscriber: started (pattern=%s, redis=%s)",
        channel_pattern,
        redis_url,
    )


async def _subscriber_loop(
    bus: "InProcessEventBus",
    redis_url: str,
    channel_pattern: str,
) -> None:
    """Background task: PSUBSCRIBE and dispatch inbound messages locally.

    Gemini round-D LOW finding: prior version exited on Redis disconnect with
    no retry. The loop now reconnects with exponential backoff (1s → 30s cap)
    so distributed events resume automatically after a Redis restart instead
    of stalling until the next pod restart.
    """
    import redis.asyncio as aioredis  # type: ignore

    backoff = 1.0
    backoff_max = 30.0
    while True:
        try:
            client = aioredis.from_url(redis_url, decode_responses=True)
            pubsub = client.pubsub()
            await pubsub.psubscribe(channel_pattern)
            logger.info("redis_subscriber: PSUBSCRIBE %s — listening", channel_pattern)
            backoff = 1.0  # reset on successful connect

            async for message in pubsub.listen():
                if message is None:
                    continue
                if message.get("type") not in ("pmessage", "message"):
                    continue
                channel: str = message.get("channel") or message.get("pattern") or ""
                raw = message.get("data")
                if not isinstance(raw, str):
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError as exc:
                    logger.warning("redis_subscriber: bad JSON on %s: %s", channel, exc)
                    continue

                if ":" in channel:
                    topic = channel.rsplit(":", 1)[-1]
                else:
                    topic = channel

                _fanout_local(bus, topic, payload)

        except asyncio.CancelledError:
            logger.info("redis_subscriber: task cancelled — shutting down")
            raise
        except Exception as exc:
            logger.warning(
                "redis_subscriber: connection error (%s) — reconnecting in %.1fs: %s",
                redis_url, backoff, exc,
            )
            try:
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                raise
            backoff = min(backoff * 2, backoff_max)


def _log_task_result(task: asyncio.Task) -> None:
    """Done-callback that surfaces silent task failures.

    Gemini round-D MED finding: the prior code launched async handlers with
    asyncio.create_task() and never awaited them, so handler crashes were
    swallowed. This callback logs every non-Cancelled exception with full
    traceback so operators see real bugs in their notifications/logs.
    """
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            "redis_subscriber: background handler task %r raised — %s",
            task.get_name() or "<unnamed>", exc, exc_info=exc,
        )


def _fanout_local(bus: "InProcessEventBus", topic: str, payload: dict) -> None:
    """
    Deliver ``payload`` to local bus subscribers for ``topic``.

    Deliberately bypasses ``bus.publish()`` to avoid re-mirroring to Redis
    and creating an infinite message loop.
    """
    callbacks = list(bus._subscribers.get(topic, ()))
    # Also record in history for test introspection.
    bus._history[topic].append(payload)
    for cb in callbacks:
        try:
            result = cb(payload)
            if asyncio.iscoroutine(result):
                bg = asyncio.create_task(result, name=f"redis_subscriber:{topic}")
                bg.add_done_callback(_log_task_result)
        except Exception as exc:
            logger.exception("redis_subscriber: local handler for %s raised: %s", topic, exc)

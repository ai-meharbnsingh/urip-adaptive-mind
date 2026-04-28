"""
shared.events.bus — In-process event bus with optional Redis backing.

The factory ships a single shared bus singleton.  In production, services use
the same Redis instance and `publish` round-trips through Redis pub/sub.  In
tests and local dev, the bus runs purely in-process — subscribers are added
via `subscribe(topic, callback)` and `publish` invokes them synchronously.

This module gives the codebase a single integration point so the full URIP↔
Compliance event flow can be wired without forcing every test to spin up Redis.

Wiring guarantee
----------------
`get_event_bus()` returns the same singleton across the process.  Any module
that wants to publish or subscribe imports it once.  Tests that need a clean
state call `reset_event_bus()` between cases.
"""
from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


def _log_task_result(task: asyncio.Task) -> None:
    """Done-callback surfacing silent task failures (Gemini round-D MED)."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            "event_bus: background subscriber task %r raised — %s",
            task.get_name() or "<unnamed>", exc, exc_info=exc,
        )


# A subscriber may be sync or async.  We coerce both to a coroutine for unified
# scheduling.
SubscriberCallback = Callable[[dict[str, Any]], Any | Awaitable[Any]]


class InProcessEventBus:
    """
    Lightweight asyncio-friendly pub/sub for cross-service notifications.

    - publish(topic, payload) → fires every registered subscriber.  Async
      subscribers run as background tasks; sync subscribers run inline.
    - subscribe(topic, cb)    → register cb; returns an unsubscribe handle.
    - history(topic) lets tests assert "an event was published" without
      racing the subscriber tasks.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[SubscriberCallback]] = defaultdict(list)
        self._history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        # When a Redis URL is set we mirror publishes to Redis so cross-process
        # subscribers (e.g. compliance worker) see them too.
        self._redis_client = None
        self._redis_url: str | None = None

    # ---------------- subscribe / publish ---------------- #
    def subscribe(self, topic: str, cb: SubscriberCallback) -> Callable[[], None]:
        self._subscribers[topic].append(cb)

        def unsubscribe() -> None:
            try:
                self._subscribers[topic].remove(cb)
            except ValueError:
                pass

        return unsubscribe

    async def publish(self, topic: str, payload: dict[str, Any]) -> int:
        """Returns the number of in-process subscribers fired (matches Redis API)."""
        # 1. Persist for tests.
        self._history[topic].append(payload)

        # 2. Mirror to Redis if configured.
        if self._redis_client is not None:
            try:
                await self._redis_client.publish(topic, payload)
            except Exception as exc:  # pragma: no cover — best-effort
                logger.warning("Redis mirror publish failed for %s: %s", topic, exc)

        # 3. Fan-out to in-process subscribers.
        # Gemini round-D MED: async callbacks were create_task'd and orphaned,
        # so handler crashes were silently swallowed. Add a done-callback that
        # surfaces exceptions to logs.
        callbacks = list(self._subscribers.get(topic, ()))
        fired = 0
        for cb in callbacks:
            try:
                result = cb(payload)
                if asyncio.iscoroutine(result):
                    bg = asyncio.create_task(result, name=f"event_bus:{topic}")
                    bg.add_done_callback(_log_task_result)
                fired += 1
            except Exception as exc:
                logger.exception("Subscriber for %s raised: %s", topic, exc)
        return fired

    # ---------------- history / introspection ---------------- #
    def history(self, topic: str) -> list[dict[str, Any]]:
        return list(self._history.get(topic, ()))

    def published_to(self, topic: str) -> list[dict[str, Any]]:
        """Alias used by e2e fixtures."""
        return self.history(topic)

    def reset(self) -> None:
        self._subscribers.clear()
        self._history.clear()

    # ---------------- optional Redis mirror ---------------- #
    def attach_redis(self, redis_client) -> None:
        """Attach a `RedisEventClient` (or compatible) so publishes also hit Redis."""
        self._redis_client = redis_client

    def detach_redis(self) -> None:
        self._redis_client = None


# ----------------- module-level singleton ----------------- #
_BUS: InProcessEventBus | None = None


def get_event_bus() -> InProcessEventBus:
    global _BUS
    if _BUS is None:
        _BUS = InProcessEventBus()
        # If a Redis URL is set in env, attach a real RedisEventClient.  We do
        # this lazily so tests without Redis still work.
        url = os.environ.get("URIP_REDIS_URL")
        if url:
            try:
                from shared.events.redis_client import RedisEventClient
                _BUS.attach_redis(RedisEventClient(url=url))
            except Exception as exc:  # pragma: no cover
                logger.warning("Could not attach Redis (%s): %s", url, exc)
    return _BUS


def reset_event_bus() -> None:
    """Test helper — wipes subscribers + history.  NEVER call from prod code."""
    global _BUS
    if _BUS is not None:
        _BUS.reset()
        _BUS.detach_redis()
    _BUS = None

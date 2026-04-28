"""
tests/test_shared/test_distributed_events.py

Unit tests for shared.events.redis_subscriber — distributed event bus
subscribe side.

Uses fakeredis and direct internal-state inspection rather than a real
Redis server.
"""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.events.bus import InProcessEventBus
from shared.events.redis_subscriber import (
    _fanout_local,
    start_redis_event_subscriber,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bus() -> InProcessEventBus:
    """Return a fresh InProcessEventBus (not the global singleton)."""
    return InProcessEventBus()


# ---------------------------------------------------------------------------
# _fanout_local
# ---------------------------------------------------------------------------

class TestFanoutLocal:
    @pytest.mark.asyncio
    async def test_dispatches_to_local_sync_handler(self):
        bus = _make_bus()
        received: list[dict] = []

        def handler(payload: dict) -> None:
            received.append(payload)

        bus.subscribe("urip.risk.created", handler)
        _fanout_local(bus, "urip.risk.created", {"risk_id": "R-001"})

        assert len(received) == 1
        assert received[0]["risk_id"] == "R-001"

    @pytest.mark.asyncio
    async def test_dispatches_to_local_async_handler(self):
        bus = _make_bus()
        received: list[dict] = []

        async def handler(payload: dict) -> None:
            received.append(payload)

        bus.subscribe("urip.risk.created", handler)
        _fanout_local(bus, "urip.risk.created", {"risk_id": "R-002"})

        # Let any created tasks run
        await asyncio.sleep(0)
        assert len(received) == 1

    def test_records_in_history(self):
        bus = _make_bus()
        _fanout_local(bus, "test.topic", {"n": 42})
        assert bus.history("test.topic") == [{"n": 42}]

    def test_no_subscribers_does_not_raise(self):
        bus = _make_bus()
        # Should not raise even with no subscribers
        _fanout_local(bus, "unknown.topic", {"x": 1})

    @pytest.mark.asyncio
    async def test_does_not_call_bus_publish(self):
        """_fanout_local must NOT call bus.publish() — that would re-mirror to Redis."""
        bus = _make_bus()
        bus.publish = AsyncMock()  # type: ignore[assignment]
        _fanout_local(bus, "some.topic", {"y": 2})
        bus.publish.assert_not_called()


# ---------------------------------------------------------------------------
# start_redis_event_subscriber idempotency
# ---------------------------------------------------------------------------

class TestSubscriberIdempotent:
    @pytest.mark.asyncio
    async def test_idempotent_start(self):
        """Calling start_redis_event_subscriber twice should be a no-op
        after the first call (same task, not a second one)."""
        import shared.events.redis_subscriber as sub_mod

        bus = _make_bus()

        # Build a mock that immediately cancels so the task exits cleanly
        async def _noop_loop(*args, **kwargs):
            await asyncio.sleep(0)

        with patch.object(sub_mod, "_subscriber_loop", side_effect=_noop_loop) as mock_loop:
            # Reset sentinel before test
            sub_mod._SUBSCRIBER_TASK = None
            await start_redis_event_subscriber(bus, "redis://localhost:6379/0")
            task1 = sub_mod._SUBSCRIBER_TASK

            # Second call — task1 might be done already (noop), so let's also
            # confirm with a live task
            sub_mod._SUBSCRIBER_TASK = None
            await start_redis_event_subscriber(bus, "redis://localhost:6379/0")
            task2 = sub_mod._SUBSCRIBER_TASK

            # Both calls used _subscriber_loop (once each) — what we care about
            # is that calling again while the task is alive is a no-op.
            # Patch a long-running loop to test that:
            async def _long_loop(*args, **kwargs):
                await asyncio.sleep(100)

            sub_mod._SUBSCRIBER_TASK = None
            with patch.object(sub_mod, "_subscriber_loop", side_effect=_long_loop):
                await start_redis_event_subscriber(bus, "redis://localhost:6379/0")
                live_task = sub_mod._SUBSCRIBER_TASK
                assert live_task is not None and not live_task.done()

                # Second call while running → no-op
                call_count_before = mock_loop.call_count
                await start_redis_event_subscriber(bus, "redis://localhost:6379/0")
                # _subscriber_loop should NOT have been called again
                # (mock_loop is the outer mock — inner patch took over, so
                # live task is still the same object)
                assert sub_mod._SUBSCRIBER_TASK is live_task

                live_task.cancel()
                try:
                    await live_task
                except (asyncio.CancelledError, Exception):
                    pass

    @pytest.mark.asyncio
    async def test_subscriber_does_not_loop_back_to_redis(self):
        """_fanout_local bypasses bus.publish so messages are NOT re-published to Redis."""
        bus = _make_bus()
        # Attach a mock redis client to detect re-publish attempts
        redis_mock = AsyncMock()
        bus.attach_redis(redis_mock)

        _fanout_local(bus, "urip.risk.created", {"risk_id": "R-NO-LOOP"})

        # redis_mock.publish should NEVER have been called via _fanout_local
        redis_mock.publish.assert_not_called()


# ---------------------------------------------------------------------------
# _subscriber_loop — message delivery (mocked pubsub)
# ---------------------------------------------------------------------------

class TestSubscriberLoop:
    """Test the _subscriber_loop logic using a mock pubsub."""

    @pytest.mark.asyncio
    async def test_subscriber_dispatches_to_local_handlers(self):
        """A pmessage received from Redis must be dispatched to local bus handlers."""
        bus = _make_bus()
        received: list[dict] = []

        bus.subscribe("urip.risk.created", lambda p: received.append(p))

        # Simulate a Redis pmessage
        test_payload = {"risk_id": "R-123", "severity": "critical"}
        message = {
            "type": "pmessage",
            "channel": "urip:events:urip.risk.created",
            "pattern": "urip:events:*",
            "data": json.dumps(test_payload),
        }

        # Build a mock pubsub that yields one message then an asyncio.CancelledError
        async def fake_listen():
            yield message
            raise asyncio.CancelledError()

        mock_pubsub = AsyncMock()
        mock_pubsub.listen = fake_listen
        mock_pubsub.psubscribe = AsyncMock()

        mock_client = AsyncMock()
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)

        import shared.events.redis_subscriber as sub_mod
        with patch("redis.asyncio.from_url", return_value=mock_client):
            try:
                await sub_mod._subscriber_loop(bus, "redis://localhost:6379", "urip:events:*")
            except asyncio.CancelledError:
                pass

        assert len(received) == 1
        assert received[0]["risk_id"] == "R-123"

    @pytest.mark.asyncio
    async def test_subscriber_skips_non_message_types(self):
        """Subscribe/psubscribe confirmation messages (type != pmessage) must be ignored."""
        bus = _make_bus()
        received: list[dict] = []
        bus.subscribe("urip.risk.created", lambda p: received.append(p))

        subscribe_ack = {"type": "psubscribe", "channel": None, "data": 1}

        async def fake_listen():
            yield subscribe_ack
            raise asyncio.CancelledError()

        mock_pubsub = AsyncMock()
        mock_pubsub.listen = fake_listen
        mock_pubsub.psubscribe = AsyncMock()

        mock_client = AsyncMock()
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)

        import shared.events.redis_subscriber as sub_mod
        with patch("redis.asyncio.from_url", return_value=mock_client):
            try:
                await sub_mod._subscriber_loop(bus, "redis://localhost:6379", "urip:events:*")
            except asyncio.CancelledError:
                pass

        assert received == [], "Ack messages should not be dispatched"

    @pytest.mark.asyncio
    async def test_bad_json_does_not_crash_loop(self):
        """Malformed JSON in a message should log a warning, not crash the loop."""
        bus = _make_bus()

        bad_message = {
            "type": "pmessage",
            "channel": "urip:events:urip.risk.created",
            "pattern": "urip:events:*",
            "data": "NOT JSON {{{",
        }
        good_message = {
            "type": "pmessage",
            "channel": "urip:events:urip.risk.created",
            "pattern": "urip:events:*",
            "data": json.dumps({"risk_id": "R-OK"}),
        }

        received: list = []
        bus.subscribe("urip.risk.created", lambda p: received.append(p))

        async def fake_listen():
            yield bad_message
            yield good_message
            raise asyncio.CancelledError()

        mock_pubsub = AsyncMock()
        mock_pubsub.listen = fake_listen
        mock_pubsub.psubscribe = AsyncMock()
        mock_client = AsyncMock()
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)

        import shared.events.redis_subscriber as sub_mod
        with patch("redis.asyncio.from_url", return_value=mock_client):
            try:
                await sub_mod._subscriber_loop(bus, "redis://localhost:6379", "urip:events:*")
            except asyncio.CancelledError:
                pass

        # Only the good message should arrive
        assert len(received) == 1
        assert received[0]["risk_id"] == "R-OK"

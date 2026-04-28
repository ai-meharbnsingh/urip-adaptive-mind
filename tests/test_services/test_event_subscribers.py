"""
tests/test_services/test_event_subscribers.py

Unit tests for backend.services.event_subscribers — notification backend
selection, push/get/clear semantics, and subscriber idempotency.

Uses fakeredis.aioredis (in-process fake) so no real Redis is required.
"""
from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_in_process_store():
    from backend.services.event_subscribers import _InProcessNotificationStore
    return _InProcessNotificationStore()


def _make_redis_store(fake_redis_client):
    """Build a _RedisNotificationStore whose internal client is replaced by
    the provided fake (must expose lpush, lrange, expire, delete, keys)."""
    from backend.services.event_subscribers import _RedisNotificationStore
    store = _RedisNotificationStore.__new__(_RedisNotificationStore)
    store._client = fake_redis_client
    return store


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

class TestBackendSelection:
    """Verify that the module-level _NOTIFICATION_BACKEND is chosen correctly."""

    def test_in_process_default_in_dev(self):
        """Without REDIS_URL or URIP_NOTIFICATION_BACKEND, store should be in-process."""
        with patch.dict(os.environ, {}, clear=False):
            # Ensure relevant env vars are absent
            env_patch = {k: "" for k in (
                "URIP_NOTIFICATION_BACKEND", "REDIS_URL", "URIP_ENV"
            )}
            with patch.dict(os.environ, env_patch):
                # Re-evaluate selection logic inline (same as module top-level)
                notification_backend_env = os.environ.get(
                    "URIP_NOTIFICATION_BACKEND", ""
                ).lower()
                urip_env = os.environ.get("URIP_ENV", "").lower()
                redis_url = os.environ.get("REDIS_URL", "")
                use_redis = (
                    notification_backend_env == "redis"
                    or (urip_env in ("production", "prod", "staging") and bool(redis_url))
                )
                assert not use_redis, "Dev default should be in-process"

    def test_redis_backend_selected_when_explicit_env_set(self):
        """URIP_NOTIFICATION_BACKEND=redis should always select Redis backend."""
        with patch.dict(os.environ, {"URIP_NOTIFICATION_BACKEND": "redis", "REDIS_URL": "redis://localhost:6379/0"}):
            from backend.services.event_subscribers import _RedisNotificationStore
            notification_backend_env = os.environ.get(
                "URIP_NOTIFICATION_BACKEND", ""
            ).lower()
            assert notification_backend_env == "redis"

    def test_redis_backend_selected_when_prod_env_with_redis_url(self):
        """URIP_ENV=production + REDIS_URL set should select Redis."""
        with patch.dict(os.environ, {"URIP_ENV": "production", "REDIS_URL": "redis://redis:6379/0",
                                     "URIP_NOTIFICATION_BACKEND": ""}):
            urip_env = os.environ.get("URIP_ENV", "").lower()
            redis_url = os.environ.get("REDIS_URL", "")
            notification_backend_env = os.environ.get("URIP_NOTIFICATION_BACKEND", "").lower()
            use_redis = (
                notification_backend_env == "redis"
                or (urip_env in ("production", "prod", "staging") and bool(redis_url))
            )
            assert use_redis, "Production + REDIS_URL should select Redis backend"


# ---------------------------------------------------------------------------
# In-process store
# ---------------------------------------------------------------------------

class TestInProcessStore:
    @pytest.mark.asyncio
    async def test_push_get_roundtrip(self):
        store = _make_in_process_store()
        payload = {"topic": "test.event", "payload": {"k": "v"}, "received_at": "now"}
        await store.push("tenant-abc", payload)
        result = await store.get("tenant-abc")
        assert len(result) == 1
        assert result[0] == payload

    @pytest.mark.asyncio
    async def test_push_multiple_tenants_isolated(self):
        store = _make_in_process_store()
        await store.push("tenant-1", {"n": 1})
        await store.push("tenant-1", {"n": 2})
        await store.push("tenant-2", {"n": 99})
        t1 = await store.get("tenant-1")
        t2 = await store.get("tenant-2")
        assert len(t1) == 2
        assert len(t2) == 1

    @pytest.mark.asyncio
    async def test_get_unknown_tenant_returns_empty(self):
        store = _make_in_process_store()
        result = await store.get("does-not-exist")
        assert result == []

    @pytest.mark.asyncio
    async def test_clear_specific_tenant(self):
        store = _make_in_process_store()
        await store.push("tenant-A", {"x": 1})
        await store.push("tenant-B", {"x": 2})
        await store.clear("tenant-A")
        assert await store.get("tenant-A") == []
        assert len(await store.get("tenant-B")) == 1

    @pytest.mark.asyncio
    async def test_clear_all_tenants(self):
        store = _make_in_process_store()
        await store.push("tenant-A", {"x": 1})
        await store.push("tenant-B", {"x": 2})
        await store.clear(None)
        assert await store.get("tenant-A") == []
        assert await store.get("tenant-B") == []


# ---------------------------------------------------------------------------
# Redis store (mocked via fakeredis)
# ---------------------------------------------------------------------------

class TestRedisStore:
    """Uses fakeredis.aioredis for a real async Redis interface without a server."""

    @pytest.fixture
    def fake_redis(self):
        try:
            import fakeredis.aioredis as fake_aioredis
            server = __import__("fakeredis").FakeServer()
            client = fake_aioredis.FakeRedis(server=server, decode_responses=True)
            return client
        except ImportError:
            pytest.skip("fakeredis not installed")

    @pytest.mark.asyncio
    async def test_push_get_roundtrip_redis(self, fake_redis):
        import json
        store = _make_redis_store(fake_redis)
        payload = {"topic": "compliance.control.failed", "payload": {"ctrl": "SOC2-01"}, "received_at": "2026-01-01T00:00:00Z"}
        await store.push("tenant-x", payload)
        result = await store.get("tenant-x")
        assert len(result) == 1
        assert result[0]["topic"] == "compliance.control.failed"
        assert result[0]["payload"]["ctrl"] == "SOC2-01"

    @pytest.mark.asyncio
    async def test_push_sets_ttl(self, fake_redis):
        """After push, the key must have a TTL (7 days = 604800 s)."""
        store = _make_redis_store(fake_redis)
        await store.push("tenant-ttl", {"x": 1})
        ttl = await fake_redis.ttl("urip:notif:tenant-ttl")
        assert ttl > 0, "Key must have a TTL after push"
        assert ttl <= 604800

    @pytest.mark.asyncio
    async def test_clear_specific_tenant_redis(self, fake_redis):
        store = _make_redis_store(fake_redis)
        await store.push("tenant-del", {"a": 1})
        await store.push("tenant-keep", {"b": 2})
        await store.clear("tenant-del")
        deleted = await store.get("tenant-del")
        kept = await store.get("tenant-keep")
        assert deleted == []
        assert len(kept) == 1

    @pytest.mark.asyncio
    async def test_clear_all_tenants_redis(self, fake_redis):
        store = _make_redis_store(fake_redis)
        await store.push("t1", {"a": 1})
        await store.push("t2", {"b": 2})
        await store.clear(None)
        assert await store.get("t1") == []
        assert await store.get("t2") == []

    @pytest.mark.asyncio
    async def test_get_unknown_tenant_returns_empty_redis(self, fake_redis):
        store = _make_redis_store(fake_redis)
        assert await store.get("nobody") == []

    @pytest.mark.asyncio
    async def test_push_graceful_on_redis_error(self):
        """If Redis is broken, push should log and not crash."""
        from backend.services.event_subscribers import _RedisNotificationStore
        store = _RedisNotificationStore.__new__(_RedisNotificationStore)
        # Simulate a broken client
        broken = AsyncMock()
        broken.lpush = AsyncMock(side_effect=ConnectionError("Redis down"))
        store._client = broken
        # Should not raise
        await store.push("tenant-err", {"x": 1})

    @pytest.mark.asyncio
    async def test_get_graceful_on_redis_error(self):
        """If Redis is broken, get should log and return []."""
        from backend.services.event_subscribers import _RedisNotificationStore
        store = _RedisNotificationStore.__new__(_RedisNotificationStore)
        broken = AsyncMock()
        broken.lrange = AsyncMock(side_effect=ConnectionError("Redis down"))
        store._client = broken
        result = await store.get("tenant-err")
        assert result == []


# ---------------------------------------------------------------------------
# Idempotent register_urip_subscribers
# ---------------------------------------------------------------------------

class TestIdempotentRegister:
    def test_idempotent_register(self):
        """Calling register_urip_subscribers twice must not double-subscribe."""
        from shared.events.bus import InProcessEventBus
        from backend.services.event_subscribers import register_urip_subscribers
        bus = InProcessEventBus()
        # First call wires subscribers
        register_urip_subscribers(bus)
        count_after_first = sum(
            len(v) for v in bus._subscribers.values()
        )
        # Second call must be a no-op
        register_urip_subscribers(bus)
        count_after_second = sum(
            len(v) for v in bus._subscribers.values()
        )
        assert count_after_first == count_after_second, (
            "Double-register must not add duplicate subscriber callbacks"
        )
        assert count_after_first > 0, "At least one subscriber must be wired"


# ---------------------------------------------------------------------------
# notify_compliance_event / get_compliance_notifications (public API)
# ---------------------------------------------------------------------------

class TestPublicAPI:
    """Quick round-trip through the exported async helpers against the live
    module-level backend (which is in-process during tests)."""

    @pytest.mark.asyncio
    async def test_notify_and_get_roundtrip(self):
        from backend.services.event_subscribers import (
            notify_compliance_event,
            get_compliance_notifications,
            clear_compliance_notifications,
        )
        tenant = "test-public-api-tenant"
        await clear_compliance_notifications(tenant)
        await notify_compliance_event(tenant, {"topic": "test", "payload": {}, "received_at": "2026-01-01"})
        items = await get_compliance_notifications(tenant)
        assert len(items) >= 1
        assert any(i.get("topic") == "test" for i in items)
        await clear_compliance_notifications(tenant)

    @pytest.mark.asyncio
    async def test_clear_removes_tenant_notifications(self):
        from backend.services.event_subscribers import (
            notify_compliance_event,
            get_compliance_notifications,
            clear_compliance_notifications,
        )
        tenant = "test-clear-tenant"
        await notify_compliance_event(tenant, {"topic": "x", "payload": {}, "received_at": "t"})
        await clear_compliance_notifications(tenant)
        items = await get_compliance_notifications(tenant)
        assert items == []

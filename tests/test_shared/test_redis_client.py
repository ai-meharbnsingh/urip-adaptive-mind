"""
TDD: shared.events.redis_client — async publish + subscribe

Tests:
  - publish_and_consume: publish a message, subscribe, receive it back
  - publish_returns_receivers: publish returns int (number of receivers)
  - subscribe_yields_message: subscribe generator yields the published payload

Marked @pytest.mark.integration — skipped when Redis is unavailable.
"""

import asyncio
import json
import uuid

import pytest

# RED until shared/events/redis_client.py exists
from shared.events.redis_client import RedisEventClient


def _redis_url() -> str:
    """Return the Redis URL to use for integration tests."""
    import os
    return os.environ.get("REDIS_URL", "redis://localhost:6379/15")


async def _redis_available(url: str) -> bool:
    """Return True if Redis is reachable."""
    try:
        import redis.asyncio as aioredis  # type: ignore
        client = aioredis.from_url(url)
        await client.ping()
        await client.aclose()
        return True
    except Exception:
        return False


@pytest.fixture
async def redis_client():
    """Provide a RedisEventClient connected to the test Redis DB (db 15)."""
    url = _redis_url()
    if not await _redis_available(url):
        pytest.skip("Redis not available — integration test skipped")
    client = RedisEventClient(url=url)
    yield client
    await client.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publish_returns_integer(redis_client: RedisEventClient):
    """publish() must return an int (receiver count — 0 when no subscribers)."""
    channel = f"test.channel.{uuid.uuid4()}"
    payload = {"hello": "world", "value": 42}
    result = await redis_client.publish(channel, payload)
    assert isinstance(result, int)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publish_and_consume_round_trip(redis_client: RedisEventClient):
    """
    Subscribe to a channel, publish a payload, and verify the subscriber
    receives exactly that payload within 2 seconds.
    """
    channel = f"test.roundtrip.{uuid.uuid4()}"
    sent_payload = {"risk_id": str(uuid.uuid4()), "severity": "critical", "value": 99}

    received: list[dict] = []

    async def _subscriber():
        async for msg in redis_client.subscribe(channel):
            received.append(msg)
            break  # Stop after first message

    # Start subscriber as background task
    sub_task = asyncio.create_task(_subscriber())

    # Give the subscriber a moment to register
    await asyncio.sleep(0.1)

    # Publish
    await redis_client.publish(channel, sent_payload)

    # Wait for subscriber with timeout
    try:
        await asyncio.wait_for(sub_task, timeout=2.0)
    except asyncio.TimeoutError:
        sub_task.cancel()
        pytest.fail("Subscriber did not receive message within 2 seconds")

    assert len(received) == 1
    assert received[0] == sent_payload


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publish_serializes_non_string_values(redis_client: RedisEventClient):
    """
    publish() must handle nested dicts and lists — JSON-serializable payloads.
    subscribe() must deserialize back to the original structure.
    """
    channel = f"test.serial.{uuid.uuid4()}"
    payload = {
        "items": [1, 2, 3],
        "nested": {"key": "value"},
        "flag": True,
    }

    received: list[dict] = []

    async def _subscriber():
        async for msg in redis_client.subscribe(channel):
            received.append(msg)
            break

    sub_task = asyncio.create_task(_subscriber())
    await asyncio.sleep(0.1)
    await redis_client.publish(channel, payload)
    try:
        await asyncio.wait_for(sub_task, timeout=2.0)
    except asyncio.TimeoutError:
        sub_task.cancel()
        pytest.fail("Subscriber did not receive serialized message")

    assert received[0]["items"] == [1, 2, 3]
    assert received[0]["nested"]["key"] == "value"
    assert received[0]["flag"] is True

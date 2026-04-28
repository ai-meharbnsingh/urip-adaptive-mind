"""
shared.events.redis_client — Async Redis pub/sub helper

Wraps redis.asyncio pub/sub into a clean publish/subscribe API.
JSON-serializes payloads on publish, deserializes on receive.

Requires: redis>=4.0.0 (redis[asyncio]) — install separately:
    pip install redis

Usage:
    from shared.events.redis_client import RedisEventClient

    client = RedisEventClient(url="redis://localhost:6379")

    # Publish
    receivers = await client.publish("urip.risk.created", {"risk_id": "...", ...})

    # Subscribe (async generator)
    async for payload in client.subscribe("urip.risk.created"):
        process(payload)
        break  # or run indefinitely

    await client.close()
"""

import json
from typing import AsyncIterator

try:
    import redis.asyncio as aioredis  # type: ignore
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False


class RedisUnavailableError(RuntimeError):
    """Raised when redis package is not installed."""


class RedisEventClient:
    """
    Async Redis publish/subscribe client.

    Args:
        url: Redis connection URL (e.g. redis://localhost:6379/0)
    """

    def __init__(self, url: str = "redis://localhost:6379") -> None:
        if not _REDIS_AVAILABLE:
            raise RedisUnavailableError(
                "redis package is not installed. "
                "Install with: pip install redis"
            )
        self._url = url
        self._client: "aioredis.Redis" = aioredis.from_url(url, decode_responses=True)

    async def publish(self, channel: str, payload: dict) -> int:
        """
        Publish a JSON-serialized payload to a Redis channel.

        Args:
            channel: The Redis pub/sub channel name.
            payload: A JSON-serializable dict.

        Returns:
            Number of clients that received the message.
        """
        message = json.dumps(payload)
        result = await self._client.publish(channel, message)
        return result

    async def subscribe(self, channel: str) -> AsyncIterator[dict]:
        """
        Subscribe to a Redis channel and yield deserialized payloads.

        This is an async generator — it runs until the caller breaks or
        the connection is closed.

        Args:
            channel: The Redis pub/sub channel name.

        Yields:
            Deserialized dict payload for each message received.
        """
        pubsub = self._client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    yield json.loads(data)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    async def close(self) -> None:
        """Close the underlying Redis connection."""
        await self._client.aclose()

# URIP Horizontal Scaling Guide

## In-Memory Notification Store Migration

**Module**: `backend/services/event_subscribers.py`
**Gap**: `_NOTIFICATIONS` is a process-local dict — won't survive pod restarts and won't scale across multiple instances.

### Migration to Redis Pub/Sub

Replace the three helper functions with Redis-backed equivalents:

```python
import redis.asyncio as aioredis
import json, os

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
NOTIF_TTL_SECONDS = 7 * 24 * 3600  # 7 days

async def _record_notification(tenant_id: str, topic: str, payload: dict) -> None:
    r = aioredis.from_url(REDIS_URL)
    key = f"urip:notif:{tenant_id}"
    entry = json.dumps({"topic": topic, "payload": payload,
                         "received_at": datetime.now(timezone.utc).isoformat()})
    await r.lpush(key, entry)
    await r.expire(key, NOTIF_TTL_SECONDS)

async def get_compliance_notifications(tenant_id: str) -> list[dict]:
    r = aioredis.from_url(REDIS_URL)
    key = f"urip:notif:{tenant_id}"
    raw = await r.lrange(key, 0, -1)
    return [json.loads(x) for x in raw]

async def clear_compliance_notifications(tenant_id: str | None = None) -> None:
    r = aioredis.from_url(REDIS_URL)
    if tenant_id is None:
        # Pattern-delete — use with caution on large datasets
        keys = await r.keys("urip:notif:*")
        if keys:
            await r.delete(*keys)
    else:
        await r.delete(f"urip:notif:{tenant_id}")
```

Note: `redis.asyncio` is already available via `celery[redis]` in `requirements.txt`.

## RBAC scope hardening (partial — Gemini round-B+C)

Top-5 admin endpoints now enforce per-resource scopes via
`backend/middleware/scopes.py`. Full RBAC overhaul (granular permission
model + admin UI for scope assignment + tenant-level role customisation)
remains a separate sprint; this layer is an additive upgrade, not a
replacement of `role_required`.

## InProcessEventBus distributed pub/sub (Gemini round-D)

`shared/events/bus.py` mirrors outbound `publish()` to Redis when
`attach_redis()` is called, and the round-D `redis_subscriber.py` adds the
inbound side via `PSUBSCRIBE`. With `URIP_DISTRIBUTED_EVENTS=1` set, every pod
both publishes to and subscribes from Redis — multi-instance deployments now
get cross-pod event delivery without each handler explicitly using the Redis
client.

Remaining technical debt:

- The redis subscriber starts at FastAPI startup. Background workers (Celery)
  do not auto-start it; they would need an explicit hook in
  `backend/services/celery_app.py` to participate.
- `bus._subscribers` is process-local. A fully distributed event log (events
  durable across the entire fleet, replayable) would require Redis Streams or
  Kafka, not pub/sub. Not in scope for this sprint.

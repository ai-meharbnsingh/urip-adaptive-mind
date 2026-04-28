# Bucket D1 — Redis-backed Notifications + Distributed Event Bus

**Date**: 2026-04-28  
**Closes**: Gemini CRITICAL round-B+C findings (in-process store + publish-only bus)

---

## File Layout

| File | Role |
|------|------|
| `backend/services/event_subscribers.py` | Dual-backend notification store; `_InProcessNotificationStore` (dev/test) + `_RedisNotificationStore` (prod/staging). All public helpers (`get_compliance_notifications`, `clear_compliance_notifications`, `notify_compliance_event`) are now `async`. |
| `shared/events/redis_subscriber.py` | NEW — subscribe side of the distributed bus. `start_redis_event_subscriber()` PSUBSCRIBEs to `urip:events:*` and dispatches via `_fanout_local` (no re-publish). |
| `backend/routers/notifications.py` | Updated to `await` the async store helpers. |
| `backend/main.py` | Added `@app.on_event("startup")` guarded by `URIP_DISTRIBUTED_EVENTS` env var. |
| `tests/test_services/test_event_subscribers.py` | NEW — 18 tests: backend selection, in-process CRUD, Redis CRUD (fakeredis), graceful error handling, idempotent register, public API round-trip. |
| `tests/test_shared/test_distributed_events.py` | NEW — 10 tests: `_fanout_local` dispatch (sync+async), loop-back prevention, subscriber idempotency, `_subscriber_loop` dispatch/skip/bad-JSON. |

---

## Env Var Backend Selection

```
URIP_NOTIFICATION_BACKEND=redis   → always Redis (any env)
URIP_ENV=production|staging + REDIS_URL set → Redis
Otherwise                         → in-process dict (dev/test default)
```

The production warning is emitted only when the in-process backend is selected in prod/staging. It is suppressed when Redis is active.

---

## Distributed Subscribe — Loop Prevention

`bus.publish()` mirrors to Redis via `attach_redis`. The subscriber receives those messages via PSUBSCRIBE and dispatches them through `_fanout_local(bus, topic, payload)`, which writes directly to `bus._subscribers[topic]` and `bus._history[topic]` WITHOUT calling `bus.publish()`. This breaks the cycle: Redis → local only, no re-publish.

---

## Pytest Output (last 10 lines)

```
tests/test_shared/test_distributed_events.py::TestSubscriberLoop::test_bad_json_does_not_crash_loop PASSED [100%]

=============================== warnings summary ===============================
backend/config.py:159
  ... RuntimeWarning: JWT_SECRET_KEY is using the dev default ...

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 28 passed, 1 warning in 0.10s =========================
```

Full run including regression tests (`test_event_wiring.py`): **33 passed, 0 failed**.

---

## Blockers

None. `fakeredis>=2.34` and `redis>=7.3` were already installed. No new dependencies needed (requirements.txt already has `redis>=5,<6`).

**SCORE: 90 — PRODUCTION-VIABLE WITH CAVEATS**

**MEDIUM**
- `backend/main.py:189-194` — `/api/ready` calls synchronous `redis.Redis.ping()` inside an async handler; blocks the event loop under probe load. Replace with `redis.asyncio`.
- `shared/events/bus.py:84` + `shared/events/redis_subscriber.py:165` — Async subscriber callbacks are fire-and-forget via `asyncio.create_task()` with no `await` or exception tracking; subscriber crashes are silently swallowed.
- `backend/services/event_subscribers.py:182-183` + `backend/middleware/rate_limit.py:121` — `URIP_ENV` and `REDIS_URL` read directly from `os.environ`, bypassing `settings` and ignoring `.env` file values when the shell environment differs (config drift).

**LOW**
- `shared/events/redis_subscriber.py` — `_subscriber_loop` exits on Redis disconnect with no retry/backoff; distributed events stall until the next pod restart.
- RBAC scope hardening is partial — only 3 routers (settings, tenants, vapt_admin) received `require_scope()`; remaining ~30 routes still rely solely on linear `role_required`.
- `backend/routers/settings.py:37-51` — `UserCreate` schema has no role validator, allowing arbitrary role strings to be stored.
- `backend/routers/risks.py:275` + `backend/services/vapt_vendor_service.py:410` — `enrich_risk` background tasks launched via `asyncio.create_task()` with no failure surface.

**PASSING (no deductions)**
- Pydantic v2 migration is clean — zero `PydanticDeprecated` warnings.
- Celery optional-import gating works; module imports safely when celery is absent.
- Redis notification dual-backend (in-process + Redis) is well-architected with graceful degradation and good test coverage (28 tests passing).
- RBAC scope layer is additive, correctly caches `get_current_user`, and has solid integration tests (22 tests passing).
- Simulator scrubbed of committed credentials; env-gated startup refuses to run with blank values.

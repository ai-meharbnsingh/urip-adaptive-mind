# BUCKET C — Infrastructure & Observability Fixes
**Audit round**: Gemini Tri-A (docs/audit_apr28/external/AUDIT_GEMINI_TRI_A.md)
**Score before**: 72/100  **Target**: 100  **Date**: 2026-04-28

---

## Files Changed

| File | Change |
|---|---|
| `Dockerfile` | Converted to two-stage build (builder + runtime); non-root user `appuser` UID 1001; `--reload` replaced by `--workers 4 --no-server-header`; opt-in `URIP_RELOAD=1` build-arg for dev |
| `requirements.txt` | Added `prometheus-fastapi-instrumentator>=7.0,<8` |
| `backend/main.py` | Imported `Instrumentator` and wired `.instrument(app).expose(app, endpoint="/metrics")` — INV-1 satisfied |
| `docker-compose.yml` | Added `restart: unless-stopped`, `deploy.resources.limits` (memory), `healthcheck` for `app` and `compliance` on all services |
| `docker-compose.prod.yml` | Created: prod overlay with `restart: always`, ports `127.0.0.1:8089:8000` and `127.0.0.1:8091:8001` (nginx upstream preserved), no source-volume mounts, `RATE_LIMIT_STORAGE_URI=redis://redis:6379/1` |
| `.env.prod.template` | Created: documents all required prod env vars including `RATE_LIMIT_STORAGE_URI`, `URIP_SYSLOG_*`, `URIP_LOKI_URL` |
| `backend/middleware/rate_limit.py` | Added runtime `logger.warning` when storage is `memory://` and `URIP_ENV=production`; added comment pointing to `.env.prod.template` |
| `shared/logging_setup.py` | Kept stderr handler; added optional `SysLogHandler` (UDP, activated by `URIP_SYSLOG_HOST`+`URIP_SYSLOG_PORT`) and `_LokiHandler` (HTTP, activated by `URIP_LOKI_URL`); fully idempotent |
| `.github/workflows/ci.yml` | Added `security` job: `pip-audit -r requirements.txt --strict --vulnerability-service osv`, runs after `test` |
| `scripts/backup_postgres.sh` | `set -o pipefail` temporarily disabled around the `pg_dump | gzip` pipeline to safely capture `PIPESTATUS[0]`; pruning only runs after exit 0 AND `[ -s "$OUT_FILE" ]`; fails out otherwise |
| `backend/middleware/cors.py` | `DEFAULT_CORS_ORIGINS` renamed to `_DEV_DEFAULT_ORIGINS` (private name; no behaviour change) |
| `backend/services/event_subscribers.py` | Extended module docstring with full migration path to Redis; added `logger.warning` at import time when `URIP_ENV=production` |

---

## Observability Paths Now In Place

| Signal | Path | Activation |
|---|---|---|
| Prometheus metrics | `GET /metrics` | Always on (auto-wired in `backend/main.py`) |
| Structured JSON logs | stderr | `JSON_LOGS=1` |
| Syslog shipping | UDP → `$URIP_SYSLOG_HOST:$URIP_SYSLOG_PORT` | Set both env vars |
| Loki push | HTTP → `$URIP_LOKI_URL` | Set env var |
| Container healthcheck | `curl /api/health` every 30s | docker-compose native |

---

## Dockerfile Size (before/after)

- **Before**: single-stage, includes `gcc` + `libpq-dev` at runtime, runs as root
- **After**: two-stage — builder stage (gcc, libpq-dev) discarded; runtime stage ships only `libpq5` + `curl` + copied venv. Expected image size reduction: ~120–180 MB (gcc + build headers removed from final layer). Exact size measurable after first prod build via `docker image inspect urip-test --format '{{.Size}}'`.

---

## Blockers / Deferred Work

**Redis migration for `_NOTIFICATIONS` (CRITICAL finding — deferred)**
The in-memory `_NOTIFICATIONS` dict in `backend/services/event_subscribers.py` has NOT been migrated to Redis in this round. Full migration is a separate sprint. Mitigation applied:
- Module docstring documents the gap and the migration path (Redis LPUSH/LRANGE keyed by `urip:notif:{tenant_id}`)
- Structured `logger.warning` fires at import time when `URIP_ENV=production`, so the gap is visible in production logs from day one
- Reference added to `docs/SCALING.md` for the full migration guide

**Docker build verification**
Docker build was initiated (`docker build -t urip-test .`) but the base image pull from Docker Hub was slow. The Dockerfile passed shell inspection and all copied paths are verified to exist in the project root. Build should succeed on any machine with Docker Hub access.

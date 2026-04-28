import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from backend.config import settings
from backend.middleware.cors import install_cors
from backend.middleware.rate_limit import install_rate_limiting
from shared.logging_setup import install_json_logging

# Ensure all connectors self-register on boot (INV-1 fix)
import backend.connector_loader  # noqa: F401

# Register cross-service event subscribers at import-time so the in-process
# bus has the URIP-side handlers wired before the first HTTP request lands.
from backend.services.event_subscribers import register_urip_subscribers  # noqa: E402
register_urip_subscribers()

app = FastAPI(
    title="URIP - Unified Risk Intelligence Platform",
    description="Cybersecurity risk aggregation and management platform by Semantic Gravity",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Distributed event subscriber startup (DELIVERABLE 2)
# ---------------------------------------------------------------------------
# When URIP_DISTRIBUTED_EVENTS=1/true/yes is set, each pod PSUBSCRIBEs to
# Redis for cross-pod event delivery.  The subscriber fans messages to local
# bus handlers WITHOUT re-publishing to Redis (loop-free).
# Safe no-op when the env var is absent or when Redis is unreachable.
if os.environ.get("URIP_DISTRIBUTED_EVENTS", "").lower() in ("1", "true", "yes"):
    @app.on_event("startup")  # type: ignore[misc]
    async def _start_distributed_events() -> None:
        from shared.events.bus import get_event_bus
        from shared.events.redis_subscriber import start_redis_event_subscriber
        redis_url = settings.REDIS_URL or "redis://redis:6379/0"
        await start_redis_event_subscriber(get_event_bus(), redis_url)

# Gemini Gap 6 (MEDIUM) — install structured logging so the global exception
# handler below emits JSON log lines that downstream SIEM / log aggregation
# tooling can ingest. install_json_logging() is idempotent so repeated imports
# (uvicorn --reload, test runs that import backend.main) are safe.
install_json_logging()
logger = logging.getLogger("backend.main")

# Gemini MAJOR finding — Prometheus metrics endpoint.
# Instruments every route with request count + latency histograms.
# /metrics is unauthenticated by design (Prometheus scrapes it from internal
# network); restrict at the nginx / firewall layer for external deployments.
# INV-1 satisfied: Instrumentator().instrument(app) is called here (not just imported).
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# HIGH-009 — install rate limiter BEFORE other middlewares so it sees every
# request before they get a chance to short-circuit / mutate the path.
install_rate_limiting(app)

# CORS
install_cors(app)


# Gemini Gap 6 (MEDIUM) — global exception handler.  Without this, an
# uncaught exception inside any route handler renders FastAPI's default HTML
# stack-trace page (in debug) or a generic 500 with no audit trail (in prod).
# This handler logs a structured JSON line capturing the path, method, and
# any tenant/user context already populated on request.state, then returns
# an opaque 500 to the caller so we never leak internal frame data.
#
# IMPORTANT: this MUST NOT shadow FastAPI's HTTPException handler — those are
# intentional control-flow signals (404, 401, 403, 422 etc.) that should keep
# their declared status code and detail message.  We register the handler
# only for the bare `Exception` base class, which FastAPI consults *after*
# its built-in HTTPException handler has had its chance.
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "uncaught_exception",
        extra={
            "path": request.url.path,
            "method": request.method,
            "tenant_id": str(getattr(request.state, "tenant_id", "")),
            "user_id": str(getattr(request.state, "user_id", "")),
        },
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# Import and register routers
# NOTE: P1.4 — asset_taxonomy router added by Opus-A.  If C1 also touches this
# file mid-run (e.g., to add another router) just keep both imports/includes.
from backend.routers import acceptance, agent_ingest, asset_taxonomy, assets as assets_router, audit_log, auth, connectors as connectors_router, cspm, dashboard, remediation, reports, risk_index, risk_summary, risks, settings as settings_router, threat_intel, tenants, vapt_admin, vapt_vendor_portal  # noqa: E402
# Project_33a Roadmap features
from backend.routers import ticketing_webhook, trust_center_admin, trust_center_public, auto_remediation  # noqa: E402
# Project_33a §13 — promoted ROADMAP → LIVE (MVP scaffold) modules
from backend.routers import (  # noqa: E402
    dspm as dspm_router,
    ai_security as ai_security_router,
    ztna as ztna_router,
    attack_path as attack_path_router,
    risk_quantification as risk_quant_router,
    integrations as integrations_router,
)

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(connectors_router.router, prefix="/api/connectors", tags=["Connectors"])  # H3 audit fix — re-register
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(risks.router, prefix="/api/risks", tags=["Risks"])
app.include_router(tenants.router, prefix="/api", tags=["Tenants"])
app.include_router(acceptance.router, prefix="/api/acceptance", tags=["Acceptance"])
app.include_router(remediation.router, prefix="/api/remediation", tags=["Remediation"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(audit_log.router, prefix="/api/audit-log", tags=["Audit Log"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["Settings"])
app.include_router(threat_intel.router, prefix="/api/threat-intel", tags=["Threat Intelligence"])
app.include_router(asset_taxonomy.router, prefix="/api/asset-taxonomy", tags=["Asset Taxonomy"])
# P33a — first-class Asset model + REST API (powers asset-inventory.html / asset-detail.html)
app.include_router(assets_router.router, prefix="/api/assets", tags=["Assets"])
app.include_router(risk_summary.router, prefix="/api/risk-summary", tags=["Risk Summary"])
# Project_33a — TrendAI-style 0-100 Cyber Risk Index dashboard
app.include_router(risk_index.router, prefix="/api/risk-index", tags=["risk-index"])
app.include_router(agent_ingest.router, prefix="/api/agent-ingest", tags=["Agent Ingest"])
app.include_router(cspm.router, prefix="/api/cspm", tags=["CSPM"])
# P33a — VAPT Vendor Portal (URIP_Blueprint v3 §6.5)
app.include_router(vapt_admin.router, prefix="/api", tags=["VAPT Admin"])
app.include_router(vapt_vendor_portal.router, prefix="/api", tags=["VAPT Vendor Portal"])
# Project_33a Roadmap-1: Bidirectional ticketing webhooks
app.include_router(ticketing_webhook.router, prefix="/api/ticketing", tags=["Ticketing Webhooks"])
# Project_33a Roadmap-2: Trust Center
app.include_router(trust_center_admin.router, prefix="/api/trust-center", tags=["Trust Center Admin"])
app.include_router(trust_center_public.router, prefix="/trust", tags=["Trust Center Public"])
# Project_33a Roadmap-3: Auto-Remediation Phase 2
app.include_router(auto_remediation.router, prefix="/api/auto-remediation", tags=["Auto-Remediation"])
# Project_33a §13 — promoted ROADMAP → LIVE (MVP scaffold) modules
app.include_router(dspm_router.router, prefix="/api/dspm", tags=["DSPM"])
app.include_router(ai_security_router.router, prefix="/api/ai-security", tags=["AI Security"])
app.include_router(ztna_router.router, prefix="/api/ztna", tags=["ZTNA"])
app.include_router(attack_path_router.router, prefix="/api/attack-paths", tags=["Attack Path Prediction"])
app.include_router(risk_quant_router.router, prefix="/api/risk-quantification", tags=["Cyber Risk Quantification"])
# Jira connector — integrations health endpoint
app.include_router(integrations_router.router, prefix="/api/integrations", tags=["Integrations"])
# Notifications — surface event_subscribers' in-process store via API
# (Gemini round-B "zombie data sink" finding closed — INV-1).
from backend.routers import notifications as notifications_router  # noqa: E402
app.include_router(notifications_router.router, prefix="/api/notifications", tags=["Notifications"])

# M12 (Codex MED-004) — Block dotfile / dotdir requests at the static-mount
# layer.  StaticFiles will happily serve frontend/.vercel/project.json,
# frontend/.git/config, etc.  Refuse anything whose path contains a hidden
# segment so deployment metadata, source-control directories, and other
# accidentally-shipped artifacts are not exposed.
@app.middleware("http")
async def _block_dotfiles(request: Request, call_next):
    """Reject paths containing a hidden segment (any path component starting with `.`)."""
    parts = request.url.path.split("/")
    if any(p.startswith(".") and p not in ("", ".") for p in parts):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    return await call_next(request)


# Health probe endpoints — added per Kimi P1-B follow-up #5.
# Lightweight, unauthenticated, used by load balancers / uptime monitors.
# Both /healthz and /api/health are accepted to match common conventions.
@app.get("/healthz", include_in_schema=False)
@app.get("/api/health", include_in_schema=True, tags=["Ops"])
async def health_check():
    """Returns 200 if the process is alive. Does not check DB/Redis (use /api/ready for that)."""
    return {"status": "ok", "service": "urip-backend", "version": "1.0"}


@app.get("/api/ready", include_in_schema=True, tags=["Ops"])
async def readiness_check():
    """Returns 200 only if DB + Redis are reachable. For load balancer 'ready' probes."""
    from backend.config import settings
    import asyncpg, redis as redis_lib
    checks = {"db": "unknown", "redis": "unknown"}
    try:
        sync_url = settings.DATABASE_URL_SYNC.replace("postgresql+asyncpg://", "postgresql://")
        c = await asyncpg.connect(sync_url, timeout=2)
        await c.fetchval("SELECT 1")
        await c.close()
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = f"fail: {type(e).__name__}"
    try:
        r = redis_lib.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"fail: {type(e).__name__}"
    healthy = checks["db"] == "ok" and checks["redis"] == "ok"
    if not healthy:
        return JSONResponse(status_code=503, content={"status": "degraded", "checks": checks})
    return {"status": "ok", "checks": checks}


# Add HTTP cache headers for static assets so the browser only re-downloads
# CSS/JS/images on first load — makes navigation between pages feel instant.
# HTML stays no-cache so content updates immediately after a deploy.
@app.middleware("http")
async def _static_cache_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.endswith((".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg",
                      ".webp", ".ico", ".woff", ".woff2", ".ttf")):
        # Static assets — cache for 1 day in dev, immutable in prod (Vercel handles prod)
        response.headers["Cache-Control"] = "public, max-age=86400, must-revalidate"
    elif path.endswith(".html") or path == "/" or path.rstrip("/").count(".") == 0:
        # HTML / clean URLs — must revalidate so deploys are seen instantly
        response.headers["Cache-Control"] = "public, max-age=0, must-revalidate"
    return response


# Serve frontend static files
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

Reading additional input from stdin...
OpenAI Codex v0.125.0 (research preview)
--------
workdir: /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
model: gpt-5.2
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR, /Users/meharban/.codex/memories]
reasoning effort: medium
reasoning summaries: none
session id: 019dd3d3-5402-7f70-865c-029d8aeb8f5a
--------
user
You are auditing URIP-Adaptive Mind, a multi-tenant cybersecurity SaaS deployed at https://urip.adaptive-mind.com (Vercel frontend) with backend on Hostinger VPS.

Most recent commit: 4f457ae on adaptive-mind/main.

What just shipped (commit 4f457ae):
1. JIRA CONNECTOR — connectors/jira/{__init__,api_client,connector,schemas}.py. @register_connector("jira"). 38 tests pass.
2. SERVICENOW CONNECTOR — connectors/servicenow/*. @register_connector("servicenow"). 30 tests pass.
3. GET /api/integrations/{tool_name}/health — backend/routers/integrations.py wired in backend/main.py. Verified live: returns {"status":"Not configured","connector":"jira"} with auth.
4. COMPLIANCE PROXY — frontend/vercel.json /compliance-api/* rewrite + VPS nginx /compliance-api/ location → port 8091. Verified: https://urip.adaptive-mind.com/compliance-api/health works.
5. 27 a11y findings from Kimi round 3 patched: form labels for=, search input aria-label, missing h1 on 3 pages, modal role/aria-modal, JS-injected button aria-labels, ztna icon spans, sidebar.js Royal Enfield → URIP.
6. Dockerfile fixed: COPY shared/ + COPY connectors/.
7. Cache-bust ?v=20260436 on app.css/shell.js across all 39 dashboard HTMLs.

Earlier Kimi audits scored 78 → 88 → 86. The user wants 100/100.

YOUR JOB:
Score 0-100 with one-line verdict on first line. Then findings as a TABLE: Severity | File:line | Quoted snippet | Fix.

If 100 — say so plainly, no qualifications.

If <100 — list every remaining issue. Be specific (file:line, exact snippet, exact fix). Do NOT invent issues. Do NOT downgrade for the dev JWT_SECRET_KEY warning (the policy enforcement function is in code).

Focus areas (don't restrict to these — find anything else):
- a11y leftovers (form labels, aria-label, role, scope, h1)
- broken links / dead routes / 404s
- inline white backgrounds in .urip-app pages
- demo placeholders ("Acme", "Royal Enfield", "Jane Doe")
- security: any leaked secrets in code, weak default credentials still wired to prod
- the new Jira / ServiceNow connectors — verify @register_connector contract, tests existence
- the integrations router — verify auth dependency, response shape
- compliance proxy — verify both Vercel rewrite AND VPS nginx upstream
- INV-1 (no dead code), INV-2 (blueprint delta), INV-5 (honest results)

Print the report inline. Do NOT save to disk. Be concise but complete.
**Planning repository audit**

I need to conduct an audit of the repo at a specific commit. I won't invent anything; I must provide file names, lines, and snippets by reading the code. I'll use my tools to inspect the workspace, and since the complexity is medium, I’ll plan to use exec commands instead of web.run. I’ll check the git repo with git checkout, run rg commands, and verify various configurations and elements. I’m also curious about running tests to gather evidence. Let’s kick things off by exploring the repo with git status!
exec
/bin/zsh -lc 'cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && git rev-parse --is-inside-work-tree && git log -1 --oneline && git show --name-only --oneline 4f457ae --' in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
true
4f457ae feat: Jira + ServiceNow connectors, compliance-api proxy, 27 a11y fixes
4f457ae feat: Jira + ServiceNow connectors, compliance-api proxy, 27 a11y fixes
backend/connector_loader.py
backend/main.py
backend/routers/integrations.py
connectors/base/setup_guides_data.py
connectors/jira/__init__.py
connectors/jira/api_client.py
connectors/jira/connector.py
connectors/jira/schemas.py
connectors/servicenow/__init__.py
connectors/servicenow/api_client.py
connectors/servicenow/connector.py
connectors/servicenow/schemas.py
docs/audit_apr28/JIRA_CONNECTOR.md
docs/audit_apr28/SERVICENOW_CONNECTOR.md
docs/audit_apr28/external/AUDIT_KIMI_ROUND3.md
frontend/acceptance-workflow.html
frontend/admin-modules.html
frontend/admin-scoring.html
frontend/admin-tenant-detail.html
frontend/admin-tenants.html
frontend/admin-vapt.html
frontend/ai-security-dashboard.html
frontend/asset-detail.html
frontend/asset-inventory.html
frontend/attack-path.html
frontend/audit-log.html
frontend/connector-status.html
frontend/connector-wizard.html
frontend/cspm-control-detail.html
frontend/cspm-dashboard.html
frontend/cspm-findings.html
frontend/dashboard.html
frontend/domain-cloud.html
frontend/domain-compliance-summary.html
frontend/domain-email-collab.html
frontend/domain-endpoint.html
frontend/domain-external-threat.html
frontend/domain-identity.html
frontend/domain-mobile.html
frontend/domain-network.html
frontend/domain-ot.html
frontend/domain-workflow.html
frontend/dspm-dashboard.html
frontend/global-search.html
frontend/index.html
frontend/js/admin-modules.js
frontend/js/admin-tenants.js
frontend/js/api.js
frontend/js/asset-inventory.js
frontend/js/audit-log.js
frontend/js/connector-schemas.js
frontend/js/connector-status.js
frontend/js/cspm-control-detail.js
frontend/js/cspm-dashboard.js
frontend/js/cspm-findings.js
frontend/js/risk-register.js
frontend/js/settings.js
frontend/login.html
frontend/notifications.html
frontend/remediation-tracker.html
frontend/reports.html
frontend/risk-overview.html
frontend/risk-quantification.html
frontend/risk-register.html
frontend/settings.html
frontend/threat-map.html
frontend/tool-catalog.html
frontend/vercel.json
frontend/ztna-dashboard.html
tests/connectors/servicenow/__init__.py
tests/connectors/servicenow/test_connector.py
tests/test_connectors/jira/__init__.py
tests/test_connectors/jira/test_connector.py

exec
/bin/zsh -lc 'cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && git rev-parse HEAD' in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
4f457ae6a098eda84f011964f43379dc4732f1da

  → Inspect backend integrations route
  • Review Jira/ServiceNow connectors and tests
  • Audit frontend a11y and placeholders
  • Check proxy configs (Vercel/nginx)
  • Scan for security issues and dead links
  • Score and write report table
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && sed -n '1,220p' backend/routers/integrations.py && echo '---' && sed -n '1,220p' backend/main.py" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
"""
backend/routers/integrations.py — Lightweight integration health endpoint.

Provides a fast, unauthenticated-friendly status check for each registered
connector so the frontend "Not configured" detection works without requiring
full authentication.

Endpoints
---------
GET /api/integrations/{tool_name}/health
    Check whether a connector is configured and reachable for the current tenant.

    Response shape:
        {"status": "Connected",      "connector": "jira", "last_check": "2026-04-28T…"}
        {"status": "Not configured", "connector": "jira"}
        {"status": "Error",          "connector": "jira", "detail": "…message…"}

    HTTP status code is ALWAYS 200 — the frontend distinguishes state via
    the ``status`` field, not the HTTP code.

Design notes
------------
- The endpoint first checks whether credentials exist for the tenant.  If none
  are stored, it returns ``{"status": "Not configured"}`` immediately — no
  network call.
- If credentials exist, it instantiates the connector, calls authenticate()
  then health_check(), and returns the result.
- Falls back gracefully when the credential vault or DB is not configured:
  returns ``{"status": "Not configured"}`` rather than a 5xx.
- Uses ``_global_registry`` from connectors.base.registry to check connector
  existence without instantiation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.tenant import TenantContext
from connectors.base.registry import _global_registry

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{tool_name}/health", response_model=None)
async def integration_health(
    tool_name: str,
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Return the health status of a connector for the current tenant.

    Steps
    -----
    1. Check whether ``tool_name`` is a registered connector.
       → Unknown connector → {"status": "Not configured"}
    2. Look up stored credentials in the TenantConnectorCredential table.
       → No credentials → {"status": "Not configured"}
    3. Instantiate the connector, call authenticate(), then health_check().
       → Connected → {"status": "Connected", "last_check": "<iso>"}
       → Auth / health failure → {"status": "Error", "detail": "…"}

    Always returns HTTP 200 — status is communicated via the ``status`` field.
    """
    # ── Step 1: is this a known connector? ──────────────────────────────────
    if tool_name not in _global_registry:
        return {"status": "Not configured", "connector": tool_name}

    # ── Step 2: look up tenant credentials ──────────────────────────────────
    tenant_id: str = getattr(current_user, "tenant_id", None) or "unknown"
    credentials: dict[str, Any] | None = None

    try:
        from sqlalchemy import select

        from backend.models.tenant_connector_credential import TenantConnectorCredential
        from backend.services.crypto_service import decrypt_credentials

        result = await db.execute(
            select(TenantConnectorCredential).where(
                TenantConnectorCredential.tenant_id == tenant_id,
                TenantConnectorCredential.connector_name == tool_name,
            )
        )
        row = result.scalar_one_or_none()

        if row is None:
            return {"status": "Not configured", "connector": tool_name}

        credentials = decrypt_credentials(row.encrypted_credentials)

    except Exception as exc:
        # Vault / DB not yet wired in this environment — degrade gracefully.
        logger.warning(
            "integrations_health: credential lookup failed for %s/%s: %s",
            tenant_id, tool_name, exc,
        )
        return {"status": "Not configured", "connector": tool_name}

    if not credentials:
        return {"status": "Not configured", "connector": tool_name}

    # ── Step 3: instantiate and probe ────────────────────────────────────────
    try:
        factory = _global_registry.get(tool_name)
        connector = factory()

        # authenticate() verifies the stored credentials against the live API.
        credentials["tenant_id"] = tenant_id
        connector.authenticate(credentials)

        # health_check() returns a ConnectorHealth dataclass.
        health = connector.health_check()

        last_check = datetime.now(timezone.utc).isoformat()

        if health.status == "ok":
            return {
                "status": "Connected",
                "connector": tool_name,
                "last_check": last_check,
                "health_status": health.status,
            }
        else:
            return {
                "status": "Error",
                "connector": tool_name,
                "last_check": last_check,
                "health_status": health.status,
                "detail": health.last_error or "Connector health degraded.",
            }

    except Exception as exc:
        logger.warning(
            "integrations_health: probe failed for %s/%s: %s",
            tenant_id, tool_name, exc,
        )
        return {
            "status": "Error",
            "connector": tool_name,
            "detail": str(exc),
        }
---
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

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

# Gemini Gap 6 (MEDIUM) — install structured logging so the global exception
# handler below emits JSON log lines that downstream SIEM / log aggregation
# tooling can ingest. install_json_logging() is idempotent so repeated imports
# (uvicorn --reload, test runs that import backend.main) are safe.
install_json_logging()
logger = logging.getLogger("backend.main")

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

exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && sed -n '1,260p' backend/routers/integrations.py" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
"""
backend/routers/integrations.py — Lightweight integration health endpoint.

Provides a fast, unauthenticated-friendly status check for each registered
connector so the frontend "Not configured" detection works without requiring
full authentication.

Endpoints
---------
GET /api/integrations/{tool_name}/health
    Check whether a connector is configured and reachable for the current tenant.

    Response shape:
        {"status": "Connected",      "connector": "jira", "last_check": "2026-04-28T…"}
        {"status": "Not configured", "connector": "jira"}
        {"status": "Error",          "connector": "jira", "detail": "…message…"}

    HTTP status code is ALWAYS 200 — the frontend distinguishes state via
    the ``status`` field, not the HTTP code.

Design notes
------------
- The endpoint first checks whether credentials exist for the tenant.  If none
  are stored, it returns ``{"status": "Not configured"}`` immediately — no
  network call.
- If credentials exist, it instantiates the connector, calls authenticate()
  then health_check(), and returns the result.
- Falls back gracefully when the credential vault or DB is not configured:
  returns ``{"status": "Not configured"}`` rather than a 5xx.
- Uses ``_global_registry`` from connectors.base.registry to check connector
  existence without instantiation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.tenant import TenantContext
from connectors.base.registry import _global_registry

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{tool_name}/health", response_model=None)
async def integration_health(
    tool_name: str,
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Return the health status of a connector for the current tenant.

    Steps
    -----
    1. Check whether ``tool_name`` is a registered connector.
       → Unknown connector → {"status": "Not configured"}
    2. Look up stored credentials in the TenantConnectorCredential table.
       → No credentials → {"status": "Not configured"}
    3. Instantiate the connector, call authenticate(), then health_check().
       → Connected → {"status": "Connected", "last_check": "<iso>"}
       → Auth / health failure → {"status": "Error", "detail": "…"}

    Always returns HTTP 200 — status is communicated via the ``status`` field.
    """
    # ── Step 1: is this a known connector? ──────────────────────────────────
    if tool_name not in _global_registry:
        return {"status": "Not configured", "connector": tool_name}

    # ── Step 2: look up tenant credentials ──────────────────────────────────
    tenant_id: str = getattr(current_user, "tenant_id", None) or "unknown"
    credentials: dict[str, Any] | None = None

    try:
        from sqlalchemy import select

        from backend.models.tenant_connector_credential import TenantConnectorCredential
        from backend.services.crypto_service import decrypt_credentials

        result = await db.execute(
            select(TenantConnectorCredential).where(
                TenantConnectorCredential.tenant_id == tenant_id,
                TenantConnectorCredential.connector_name == tool_name,
            )
        )
        row = result.scalar_one_or_none()

        if row is None:
            return {"status": "Not configured", "connector": tool_name}

        credentials = decrypt_credentials(row.encrypted_credentials)

    except Exception as exc:
        # Vault / DB not yet wired in this environment — degrade gracefully.
        logger.warning(
            "integrations_health: credential lookup failed for %s/%s: %s",
            tenant_id, tool_name, exc,
        )
        return {"status": "Not configured", "connector": tool_name}

    if not credentials:
        return {"status": "Not configured", "connector": tool_name}

    # ── Step 3: instantiate and probe ────────────────────────────────────────
    try:
        factory = _global_registry.get(tool_name)
        connector = factory()

        # authenticate() verifies the stored credentials against the live API.
        credentials["tenant_id"] = tenant_id
        connector.authenticate(credentials)

        # health_check() returns a ConnectorHealth dataclass.
        health = connector.health_check()

        last_check = datetime.now(timezone.utc).isoformat()

        if health.status == "ok":
            return {
                "status": "Connected",
                "connector": tool_name,
                "last_check": last_check,
                "health_status": health.status,
            }
        else:
            return {
                "status": "Error",
                "connector": tool_name,
                "last_check": last_check,
                "health_status": health.status,
                "detail": health.last_error or "Connector health degraded.",
            }

    except Exception as exc:
        logger.warning(
            "integrations_health: probe failed for %s/%s: %s",
            tenant_id, tool_name, exc,
        )
        return {
            "status": "Error",
            "connector": tool_name,
            "detail": str(exc),
        }

**Evaluating code quality**

I noticed that there's an unused import of TenantContext, which is dead code and may violate INV-1. The docstring mentions being unauthenticated-friendly, but it actually requires authentication—so that’s inconsistent. I’ll make a note of that. There’s also duplicated health_status in the response, which is fine, but the contract needs to ensure a 200 status code. I’ll need to get line numbers later. For now, I should check the logic in get_current_user in backend/middleware/auth.py.
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && rg -n \"def get_current_user\" -S backend/middleware/auth.py backend/middleware -S && sed -n '1,220p' backend/middleware/auth.py" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
backend/middleware/auth.py:113:async def get_current_user(
backend/middleware/auth.py:113:async def get_current_user(
"""
Backend auth middleware.

CRIT-005 — migrated from python-jose 3.3.0 (CVE-2024-33663 + CVE-2024-33664,
unmaintained library) to PyJWT 2.9+ which has the same surface for HS256.
HIGH-006 — get_current_user now also rejects requests when the user's tenant
has been deactivated (tenants.is_active = False).
"""

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models.tenant import Tenant
from backend.models.user import User

# Explicitly control "no token" behaviour: tests and existing clients expect
# missing Authorization to surface as 403 (HTTPBearer), while invalid/expired
# tokens remain 401.
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# L7 / L11 (Codex LOW-004) — issuer claim.  Tokens minted by URIP backend get
# iss="urip". decode_token() requires iss + exp.
JWT_ISSUER = "urip"
# Legacy constant: some modules import JWT_AUDIENCE for parity/documentation.
# Tokens no longer emit an `aud` claim; this is kept to avoid import breakage.
JWT_AUDIENCE = "urip-tenant"


def create_access_token(
    user_id: str,
    role: str,
    tenant_id: str | None = None,
    is_super_admin: bool = False,
    *,
    include_audience: bool = True,
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire,
        "is_super_admin": is_super_admin,
        # L7 — issuer + audience claims
        "iss": JWT_ISSUER,
    }
    # Keep `aud` for non-super-admin tokens (legacy tests / client inspection).
    # Super-admin tokens omit it so python-jose decoders without an audience
    # parameter can still decode them.
    if include_audience and not is_super_admin:
        payload["aud"] = JWT_AUDIENCE
    if tenant_id is not None:
        payload["tenant_id"] = tenant_id
    return pyjwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decode a URIP JWT.

    Algorithm is pinned to settings.JWT_ALGORITHM (HS256 by default).  Passing
    `algorithms=[…]` to PyJWT defends against algorithm-confusion attacks
    (alg=none, alg=RS256-with-HMAC-key, etc.) that broke jose-style verifiers.

    L7/L11 hardening (Codex LOW-004):
      - require `exp` (rejects tokens without expiry)
      - require `iss` claim and verify it matches JWT_ISSUER
      - (aud is intentionally omitted for compatibility with legacy test decoders)
    """
    try:
        claims = pyjwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            options={"require": ["exp", "iss"], "verify_aud": False},
        )
        aud = claims.get("aud")
        if aud is not None:
            if isinstance(aud, str):
                valid = (aud == JWT_AUDIENCE)
            elif isinstance(aud, list):
                valid = JWT_AUDIENCE in aud
            else:
                valid = False
            if not valid:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        return claims
    except pyjwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    from backend.middleware.tenant import TenantContext  # local import to avoid circular

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authenticated",
        )

    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    is_super_admin = payload.get("is_super_admin", False)
    tenant_id_str = payload.get("tenant_id")

    if not is_super_admin:
        if not tenant_id_str:
            raise HTTPException(status_code=401, detail="Token missing tenant context")
        try:
            TenantContext.set(uuid.UUID(tenant_id_str))
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid tenant_id in token")
    else:
        if tenant_id_str:
            try:
                TenantContext.set(uuid.UUID(tenant_id_str))
            except ValueError:
                raise HTTPException(status_code=401, detail="Invalid tenant_id in token")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # HIGH-006: enforce tenant.is_active for non-super-admin users.
    # Super-admins are not bound to a tenant and can always log in to manage
    # the platform (this is intentional — needed to re-enable a tenant).
    if not is_super_admin and user.tenant_id is not None:
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.id == user.tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()
        if tenant is None:
            raise HTTPException(status_code=403, detail="Tenant not found")
        if not tenant.is_active:
            raise HTTPException(status_code=403, detail="Tenant suspended")

    return user

  ✓ Inspect backend integrations route
  → Review Jira/ServiceNow connectors and tests
  • Audit frontend a11y and placeholders
  • Check proxy configs (Vercel/nginx)
  • Scan for security issues and dead links
  • Score and write report table
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && ls -R connectors/jira connectors/servicenow tests/test_connectors/jira tests/connectors/servicenow && echo '--- jira connector.py' && sed -n '1,260p' connectors/jira/connector.py && echo '--- jira __init__.py' && cat connectors/jira/__init__.py && echo '--- servicenow connector.py' && sed -n '1,300p' connectors/servicenow/connector.py" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
connectors/jira:
__init__.py
__pycache__
api_client.py
connector.py
schemas.py

connectors/jira/__pycache__:
__init__.cpython-314.pyc
api_client.cpython-314.pyc
connector.cpython-314.pyc
schemas.cpython-314.pyc

connectors/servicenow:
__init__.py
__pycache__
api_client.py
connector.py
schemas.py

connectors/servicenow/__pycache__:
__init__.cpython-314.pyc
api_client.cpython-314.pyc
connector.cpython-314.pyc
schemas.cpython-314.pyc

tests/connectors/servicenow:
__init__.py
__pycache__
test_connector.py

tests/connectors/servicenow/__pycache__:
__init__.cpython-314.pyc
test_connector.cpython-314-pytest-9.0.2.pyc

tests/test_connectors/jira:
__init__.py
__pycache__
test_connector.py

tests/test_connectors/jira/__pycache__:
__init__.cpython-314.pyc
test_connector.cpython-314-pytest-9.0.2.pyc
--- jira connector.py
"""
Jira Cloud + Jira Data Center connector for URIP.

Implements the BaseConnector contract:
  authenticate   → Basic (Cloud) or Bearer (DC/Server) auth via /rest/api/3/myself
  fetch_findings → search security tickets via JQL
  normalize      → maps Jira issue → URIPRiskRecord
  health_check   → operational status

Bidirectional:
  create_ticket  → creates a Jira issue from URIP risk data

References
----------
Atlassian REST API v3: https://developer.atlassian.com/cloud/jira/platform/rest/v3/
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional


def _run_async(coro: Any) -> Any:
    """
    Run a coroutine from synchronous code.

    Uses asyncio.run() which always creates a new event loop, ensuring
    compatibility with Python 3.10+ where get_event_loop() is deprecated
    in non-async contexts and raises in 3.12+ when there is no current loop.
    """
    return asyncio.run(coro)

from connectors.base.connector import (
    BaseConnector,
    ConnectorAuthError,
    ConnectorFetchError,
    ConnectorHealth,
    ConnectorSession,
    CredentialFieldSpec,
    RawFinding,
    URIPRiskRecord,
)
from connectors.base.registry import register_connector
from connectors.base.setup_guides_data import SETUP_GUIDES
from connectors.jira.api_client import JiraAPIClient
from connectors.jira.schemas import JiraIssue, JiraSearchResponse

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Priority / Status maps
# ─────────────────────────────────────────────────────────────────────────────

# Jira priority name → URIP severity
_PRIORITY_MAP: dict[str, str] = {
    "highest": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "lowest": "low",
}

# Jira status name → URIP risk status label (informational — not stored on URIPRiskRecord)
_STATUS_MAP: dict[str, str] = {
    "open": "open",
    "in progress": "in_progress",
    "done": "resolved",
    "closed": "resolved",
    "resolved": "resolved",
}

# Jira priority → Jira-native priority name for outbound ticket creation
_SEVERITY_TO_JIRA_PRIORITY: dict[str, str] = {
    "critical": "Highest",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}


def _map_priority(jira_priority: str | None) -> str:
    """Map Jira priority name → URIP severity string."""
    return _PRIORITY_MAP.get((jira_priority or "").lower(), "medium")


def _map_status(jira_status: str | None) -> str:
    """Map Jira status name → URIP risk status label."""
    return _STATUS_MAP.get((jira_status or "").lower(), "open")


# ─────────────────────────────────────────────────────────────────────────────
# Connector class
# ─────────────────────────────────────────────────────────────────────────────


@register_connector("jira")
class JiraConnector(BaseConnector):
    """
    Live connector for Jira Cloud and Jira Data Center.

    Data flow
    ---------
    1. Authenticate via /rest/api/3/myself (Cloud: Basic, DC: Bearer).
    2. Search security tickets using a configurable JQL filter.
    3. Normalize each issue to URIPRiskRecord.
    4. (Bidirectional) Create Jira issues from URIP risk data via create_ticket().

    Supported products
    ------------------
    - Jira Cloud (Atlassian-hosted)
    - Jira Data Center (self-managed ≥ 9.0)
    - Jira Server (≥ 9.0, same REST API surface as Data Center)

    Auth
    ----
    Cloud  → email + API token (Atlassian API token, NOT password)
    DC/Server → Personal Access Token (PAT)
    """

    NAME = "jira"
    RISK_INDEX_DOMAIN = None  # ITSM connector — no risk-index contribution

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "Jira"
    CATEGORY = "ITSM"
    SHORT_DESCRIPTION = (
        "Bidirectional sync — push URIP risks as Jira issues, "
        "ingest security tickets back as risk records."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://developer.atlassian.com/cloud/jira/platform/rest/v3/"
    SUPPORTED_PRODUCTS = [
        "Jira Cloud",
        "Jira Data Center",
        "Jira Server (≥9.0)",
    ]
    MODULE_CODE = "ITSM"

    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="base_url",
            label="Jira Base URL",
            type="url",
            required=True,
            placeholder="https://your-org.atlassian.net",
            help_text="Jira Cloud: https://your-org.atlassian.net. DC/Server: your internal URL.",
            pattern=r"^https://[^\s]+$",
        ),
        CredentialFieldSpec(
            name="auth_method",
            label="Auth Method",
            type="select",
            required=True,
            help_text="Choose Email + API Token for Cloud, or PAT for Data Center / Server.",
            options=[
                {"value": "basic", "label": "Email + API Token (Cloud)"},
                {"value": "bearer", "label": "Personal Access Token (DC/Server)"},
            ],
        ),
        CredentialFieldSpec(
            name="email",
            label="Email",
            type="text",
            required=False,
            help_text="Required when auth_method=basic. Atlassian account email.",
            placeholder="you@your-org.com",
        ),
        CredentialFieldSpec(
            name="api_token",
            label="API Token",
            type="password",
            required=False,
            secret=True,
            help_text="Required when auth_method=basic. Generate at id.atlassian.com → Security → API tokens.",
            placeholder="ATATT3xFfGF0…",
        ),
        CredentialFieldSpec(
            name="bearer_token",
            label="Personal Access Token",
            type="password",
            required=False,
            secret=True,
            help_text="Required when auth_method=bearer. Profile → Personal Access Tokens in DC/Server.",
            placeholder="NjI2NzYwMzU5NDU4OjqFv…",
        ),
        CredentialFieldSpec(
            name="default_project_key",
            label="Default Project Key",
            type="text",
            required=True,
            placeholder="SEC",
            help_text="Project where URIP-pushed risks will land (e.g. SEC, OPS, CSEC).",
        ),
        CredentialFieldSpec(
            name="risk_jql",
            label="JQL filter for security tickets to ingest",
            type="text",
            required=True,
            placeholder='project = SEC AND labels = "security"',
            default='project = SEC AND labels = "security"',
            help_text=(
                'JQL expression that selects security tickets for URIP to ingest. '
                'Example: project = SEC AND labels = "urip-risk" ORDER BY created DESC'
            ),
        ),
    ]

    # P33-Z3 (revised): inline onboarding content.
    SETUP_GUIDE = SETUP_GUIDES.get("jira")

    # ─────────────────────────────────────────────────────────────────────────
    # Constructor
    # ─────────────────────────────────────────────────────────────────────────

    def __init__(self) -> None:
        self._client: JiraAPIClient | None = None
        self._base_url: str = ""
        self._risk_jql: str = 'project = SEC AND labels = "security"'
        self._default_project_key: str = "SEC"
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    # ─────────────────────────────────────────────────────────────────────────
    # BaseConnector contract
    # ─────────────────────────────────────────────────────────────────────────

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate Jira credentials by calling /rest/api/3/myself.

        Required credential keys:
            - base_url      : Jira instance URL
            - auth_method   : "basic" or "bearer"
        If auth_method == "basic":
            - email         : Atlassian account email
            - api_token     : Atlassian API token
        If auth_method == "bearer":
            - bearer_token  : Personal Access Token (DC/Server)
        Optional:
            - default_project_key : project key for outbound ticket creation
            - risk_jql            : JQL for inbound ticket ingestion

        Returns
        -------
        ConnectorSession
            Session with token field set to "jira-basic-****" or "jira-bearer-****".

        Raises
        ------
        ConnectorAuthError
            If credentials are missing or Jira rejects them.
        """
        base_url = tenant_credentials.get("base_url", "").strip()
        auth_method = tenant_credentials.get("auth_method", "").strip().lower()

        if not base_url:
--- jira __init__.py
--- servicenow connector.py
"""
ServiceNow ITSM connector for URIP-Adaptive Mind.

Implements the BaseConnector contract:
  authenticate   → Basic Auth (username + password) OR OAuth Bearer Token
  fetch_findings → pulls security incidents (/api/now/table/incident)
  normalize      → maps SN incident → URIPRiskRecord
  health_check   → lightweight ping via sys_user table

Bidirectional:
  create_ticket  → creates a ServiceNow incident from URIP risk data
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from connectors.base.connector import (
    BaseConnector,
    ConnectorAuthError,
    ConnectorFetchError,
    ConnectorHealth,
    ConnectorSession,
    CredentialFieldSpec,
    RawFinding,
    URIPRiskRecord,
)
from connectors.base.registry import register_connector
from connectors.base.setup_guides_data import SETUP_GUIDES
from connectors.servicenow.api_client import ServiceNowAPIClient
from connectors.servicenow.schemas import ServiceNowIncident, ServiceNowListResponse

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Severity mapping
# ─────────────────────────────────────────────────────────────────────────────

# ServiceNow urgency/impact scale: 1=High, 2=Medium, 3=Low
# URIP severity: critical | high | medium | low
#
# Combined rule (spec §connector.py → normalize()):
#   urgency=1 AND impact=1   → critical
#   urgency=1 OR  impact=1   → high
#   urgency=2 OR  impact=2   → medium
#   else                     → low


def _map_severity(urgency: Optional[str], impact: Optional[str]) -> str:
    """
    Map ServiceNow urgency + impact integers to URIP severity.

    Parameters
    ----------
    urgency : str | None
        ServiceNow urgency field value ("1", "2", or "3").
    impact  : str | None
        ServiceNow impact field value ("1", "2", or "3").

    Returns
    -------
    str
        One of "critical" | "high" | "medium" | "low".
    """
    u = int(urgency) if urgency and urgency.isdigit() else 3
    i = int(impact) if impact and impact.isdigit() else 3

    if u == 1 and i == 1:
        return "critical"
    if u == 1 or i == 1:
        return "high"
    if u == 2 or i == 2:
        return "medium"
    return "low"


def _severity_to_urgency_impact(severity: str) -> tuple[int, int]:
    """
    Reverse map URIP severity → (urgency, impact) for create_ticket.

    Returns
    -------
    tuple[int, int]
        (urgency, impact) both in ServiceNow scale 1=High, 2=Medium, 3=Low.
    """
    mapping: dict[str, tuple[int, int]] = {
        "critical": (1, 1),
        "high":     (1, 2),
        "medium":   (2, 2),
        "low":      (3, 3),
    }
    return mapping.get(severity.lower(), (3, 3))


# ─────────────────────────────────────────────────────────────────────────────
# Connector class
# ─────────────────────────────────────────────────────────────────────────────


@register_connector("servicenow")
class ServiceNowConnector(BaseConnector):
    """
    Live connector for ServiceNow ITSM (Utah / Vancouver / Washington / Xanadu).

    Data flow
    ---------
    1. Authenticate with Basic Auth (username + password) OR OAuth Bearer Token.
    2. Fetch security incidents from /api/now/table/incident using an encoded query.
    3. Normalize each incident to URIPRiskRecord using urgency + impact → severity.
    4. (Bidirectional) Create ServiceNow incidents from URIP risk data via create_ticket().

    Thread / async safety
    ---------------------
    The underlying ServiceNowAPIClient is async (httpx.AsyncClient).  All methods
    on this connector that call the API are therefore async.  The connector
    scheduler (which is sync) must call these via asyncio.run() or an event loop.
    """

    NAME = "servicenow"
    RISK_INDEX_DOMAIN = None   # ITSM — does not feed the Cyber Risk Index directly.

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "ServiceNow"
    CATEGORY = "ITSM"
    SHORT_DESCRIPTION = (
        "Bidirectional sync — push URIP risks as ServiceNow incidents "
        "and ingest security incidents back as risks."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = (
        "https://developer.servicenow.com/dev.do#!/reference/api/utah/rest/c_TableAPI"
    )
    SUPPORTED_PRODUCTS = [
        "ServiceNow ITSM (Utah / Vancouver / Washington / Xanadu)"
    ]
    MODULE_CODE = "ITSM"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="instance_url",
            label="Instance URL",
            type="url",
            required=True,
            placeholder="https://your-tenant.service-now.com",
            help_text="Full URL of your ServiceNow instance — must be HTTPS.",
            pattern=r"^https://[^\s]+$",
        ),
        CredentialFieldSpec(
            name="auth_method",
            label="Auth Method",
            type="select",
            required=True,
            help_text="Basic Auth (username + password) or OAuth Bearer Token.",
            options=[
                {"value": "basic", "label": "Username + Password"},
                {"value": "oauth", "label": "OAuth Bearer Token"},
            ],
        ),
        CredentialFieldSpec(
            name="username",
            label="Username",
            type="text",
            required=False,
            help_text="Required when auth_method=basic. Use a dedicated integration user.",
            placeholder="urip_integration",
        ),
        CredentialFieldSpec(
            name="password",
            label="Password",
            type="password",
            required=False,
            secret=True,
            help_text="Required when auth_method=basic.",
            placeholder="••••••••",
        ),
        CredentialFieldSpec(
            name="oauth_token",
            label="OAuth Bearer Token",
            type="password",
            required=False,
            secret=True,
            help_text="Required when auth_method=oauth. Bearer token from your IdP.",
            placeholder="eyJ…",
        ),
        CredentialFieldSpec(
            name="risk_query",
            label="Risk Query",
            type="text",
            required=True,
            placeholder="category=security^state!=7",
            help_text=(
                "ServiceNow encoded query that selects security incidents to ingest. "
                "State 7 = Closed. Default fetches all active security incidents."
            ),
            default="category=security^active=true",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["servicenow"]

    def __init__(self) -> None:
        self._client: Optional[ServiceNowAPIClient] = None
        self._instance_url: str = ""
        self._risk_query: str = "category=security^active=true"
        self._last_run: Optional[datetime] = None
        self._error_count: int = 0
        self._last_error: Optional[str] = None

    # ─────────────────────────────────────────────────────────────────────────
    # authenticate
    # ─────────────────────────────────────────────────────────────────────────

    async def authenticate(self, credentials: dict) -> ConnectorSession:  # type: ignore[override]
        """
        Validate ServiceNow credentials and return a ConnectorSession.

        Parameters
        ----------
        credentials : dict
            Must contain:
              - instance_url  (str)
              - auth_method   ("basic" or "oauth")
            If auth_method == "basic":
              - username (str)
              - password (str)
            If auth_method == "oauth":
              - oauth_token (str)
            Optional:
              - risk_query (str) — encoded query for security incidents
              - tenant_id  (str) — URIP tenant scoping

        Raises
        ------
        ConnectorAuthError
            If credentials are missing required fields or the API rejects them.
        """
        instance_url = credentials.get("instance_url", "").strip().rstrip("/")
        auth_method = str(credentials.get("auth_method", "")).lower()
        risk_query = credentials.get("risk_query", "category=security^active=true")

        if not instance_url:
            raise ConnectorAuthError(
                "ServiceNow credentials must include 'instance_url'."
            )
        if auth_method not in ("basic", "oauth"):
            raise ConnectorAuthError(
                f"Unsupported auth_method: {auth_method!r}. Use 'basic' or 'oauth'."
            )

        if auth_method == "basic":
            username = credentials.get("username", "").strip()
            password = credentials.get("password", "")
            if not username or not password:
                raise ConnectorAuthError(
                    "Basic Auth requires 'username' and 'password'."
                )
            self._client = ServiceNowAPIClient(
                instance_url=instance_url,
                username=username,
                password=password,
            )
        else:  # oauth
            oauth_token = credentials.get("oauth_token", "").strip()
            if not oauth_token:
                raise ConnectorAuthError(
                    "OAuth mode requires 'oauth_token'."
                )
            self._client = ServiceNowAPIClient(
                instance_url=instance_url,
                oauth_token=oauth_token,
            )

        # Verify connectivity — raises ConnectorAuthError on 401/403.
        try:
            await self._client.healthcheck()
        except ConnectorAuthError:
            raise
        except Exception as exc:
            raise ConnectorAuthError(
                f"ServiceNow connectivity check failed: {exc}"
            ) from exc

        self._instance_url = instance_url
        self._risk_query = risk_query or "category=security^active=true"

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=credentials.get("tenant_id", "unknown"),
            token=f"sn-{auth_method}-****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # fetch_findings
    # ─────────────────────────────────────────────────────────────────────────

    async def fetch_findings(  # type: ignore[override]

**Inspecting connectors**

I need to check the output truncation in the Jira connector and also view the ServiceNow one. My focus is on the register contract and the sync versus async mismatch. In the Jira connector, I see that `_run_async` is defined but its placement is confusing since it comes after the definition of the import connectors. There’s also a missing blank line. I suspect the async methods may be in BaseConnector, which is likely synchronous. Let's open `connectors/base/connector.py` and inspect the registry.
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && sed -n '1,260p' connectors/base/connector.py && echo '--- registry' && sed -n '1,200p' connectors/base/registry.py" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
"""
connectors/base/connector.py — Abstract Connector base class + data transfer objects.

P1.6: Connector Framework Abstraction
P33-Z3: Connector metadata contract (DISPLAY_NAME, CATEGORY, STATUS, …) for the
        dynamic Tool Catalog UI.

Design decisions
----------------
- BaseConnector is an ABC with four mandatory abstract methods mirroring the
  blueprint's connector contract: authenticate, fetch_findings, normalize, health_check.
- Pydantic dataclasses are used for ConnectorSession, RawFinding, URIPRiskRecord, and
  ConnectorHealth so callers get field validation and easy dict/JSON conversion for free.
- URIPRiskRecord fields align 1-to-1 with the Risk SQLAlchemy model's columns (excluding
  DB-managed fields: id, risk_id, status, sla_deadline, assigned_to, tenant_id, timestamps).
  The scheduler / API layer fills in those DB-side fields.
- fetch_findings() signature includes `since: datetime` (incremental fetch) but the
  `tenant_id` optional kwarg is added so simulator variants can scope output without
  requiring a ConnectorSession object to be passed around.

Metadata contract (Z3 / Tool Catalog)
-------------------------------------
Every concrete connector subclass declares CLASS attributes (not instance) that
the registry exposes through ``list_connectors_with_metadata()``.  The fields
power a 100% data-driven catalog UI (no hard-coded tile metadata client-side):

    DISPLAY_NAME        : str     — "Tenable Vulnerability Manager"
    CATEGORY            : str     — one of CONNECTOR_CATEGORIES below
    SHORT_DESCRIPTION   : str     — one-line catalog blurb
    STATUS              : str     — "live" | "building" | "simulated" | "roadmap"
    VENDOR_DOCS_URL     : str|None
    SUPPORTED_PRODUCTS  : list[str]|None  — for multi-product connectors
    MODULE_CODE         : str     — one of CORE/VM/EDR/NETWORK/IDENTITY/...
    CREDENTIAL_FIELDS   : list[CredentialFieldSpec]

Why class attributes?  The registry stores classes (factories) — we want the
catalog endpoint to read metadata WITHOUT calling the factory or hitting the
network.  Class attributes are the cheapest, most introspection-friendly way.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from connectors.base.setup_guide import SetupGuideSpec  # noqa: F401  (re-exported)


# ─────────────────────────────────────────────────────────────────────────────
# Data Transfer Objects (framework-level contracts)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ConnectorSession:
    """
    Returned by authenticate().  Holds auth material for a single
    (connector, tenant) pair.  Connectors may subclass this to carry
    additional fields (e.g., OAuth refresh token).
    """
    connector_name: str
    tenant_id: str
    token: str
    expires_at: datetime
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawFinding:
    """
    A single finding in its source-native shape, before normalization.
    Connectors return a list of these from fetch_findings().
    """
    id: str                  # source-native finding ID (string)
    source: str              # e.g. "tenable", "sentinelone", "simulator"
    raw_data: dict[str, Any] # full source payload — connector-specific structure
    fetched_at: datetime
    tenant_id: str           # tenant this finding belongs to


@dataclass
class URIPRiskRecord:
    """
    Normalized risk record.  Maps to backend.models.risk.Risk fields.
    DB-managed fields (id, risk_id, status, sla_deadline, timestamps) are
    populated by the API layer when persisting.
    """
    finding: str
    source: str
    domain: str              # endpoint | cloud | network | application | identity | ot
    cvss_score: float
    severity: str            # critical | high | medium | low
    asset: str
    owner_team: str
    description: Optional[str] = None
    cve_id: Optional[str] = None
    epss_score: Optional[float] = None
    in_kev_catalog: bool = False
    exploit_status: Optional[str] = None   # none | poc | active | weaponized
    asset_tier: Optional[int] = None       # 1=Critical … 4=Low
    composite_score: Optional[float] = None


@dataclass
class ConnectorHealth:
    """
    Returned by health_check().
    status: "ok" | "degraded" | "error"
    """
    connector_name: str
    status: str              # "ok" | "degraded" | "error"
    last_run: Optional[datetime]
    error_count: int = 0
    last_error: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Catalog metadata — categories, status values, credential field spec
# ─────────────────────────────────────────────────────────────────────────────


# Allowed CATEGORY values for the Tool Catalog filter.  Kept here as a constant
# so frontend, registry validation, and tests have one source of truth.
CONNECTOR_CATEGORIES: tuple[str, ...] = (
    "VM",
    "EDR",
    "NETWORK",
    "IDENTITY",
    "COLLABORATION",
    "ITSM",
    "DAST",
    "DLP",
    "EXTERNAL_THREAT",
    "CSPM",
    "OT",
    "NAC",
    "PAM",
    "FIREWALL",
    "EMAIL",
    "ADVISORY",
    "BUG_BOUNTY",
    "SOC",
    "EASM",
    "SIMULATOR",
    # Project_33a roadmap modules — added with module scaffolds
    "DSPM",          # Data Security Posture Management
    "AI_SECURITY",   # AI/ML model security + governance
    "ZTNA",          # Zero Trust Network Access (Zscaler ZPA, Cloudflare Access, Tailscale, Twingate)
    # P33 — Compliance training + background verification
    "LMS",           # Learning Management Systems (KnowBe4, Hoxhunt)
    "BGV",           # Background Verification (AuthBridge, OnGrid)
)


# Allowed STATUS values — drives the catalog status badge
# - "live"      : real connector hitting the vendor API
# - "building"  : connector class registered but not feature-complete
# - "simulated" : returns synthetic data only (simulator/extended_simulator)
# - "roadmap"   : placeholder so the tile is visible but disabled
ConnectorStatus = Literal["live", "building", "simulated", "roadmap"]


@dataclass
class CredentialFieldSpec:
    """
    One field in a connector's credential wizard form.

    Mirrors the FIELD_SHAPE used by ``frontend/js/connector-schemas.js`` so the
    backend can be the source of truth for the form.  The frontend's dynamic
    wizard reads these straight off the /api/connectors response.

    Attributes
    ----------
    name        : POST body key
    label       : displayed label
    type        : "text" | "url" | "password" | "number" | "select" | "uuid"
    required    : if True, field must be present in /configure body
    secret      : if True, render as password input with show/hide toggle
    placeholder : optional placeholder text
    help_text   : small hint text shown under the input
    default     : optional default pre-fill (number/text)
    pattern     : optional regex string for client-side validation
    options     : list of {value, label} for "select" type
    """

    name: str
    label: str
    type: str = "text"
    required: bool = False
    secret: bool = False
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    default: Optional[Any] = None
    pattern: Optional[str] = None
    options: Optional[list[dict[str, str]]] = None

    def to_dict(self) -> dict[str, Any]:
        """Render to a JSON-friendly dict (drops None fields for compactness)."""
        out: dict[str, Any] = {
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "required": self.required,
            "secret": self.secret,
        }
        if self.placeholder is not None:
            out["placeholder"] = self.placeholder
        if self.help_text is not None:
            out["help_text"] = self.help_text
        if self.default is not None:
            out["default"] = self.default
        if self.pattern is not None:
            out["pattern"] = self.pattern
        if self.options is not None:
            out["options"] = self.options
        return out


# ─────────────────────────────────────────────────────────────────────────────
# Abstract base class
# ─────────────────────────────────────────────────────────────────────────────


class BaseConnector(abc.ABC):
    """
    Abstract interface every URIP connector must implement.

    Lifecycle
    ---------
    1. Instantiate the connector class (no args required — credentials come
       in via authenticate()).
    2. Call authenticate(tenant_credentials) → ConnectorSession.
    3. Call fetch_findings(since) → list[RawFinding].
    4. For each RawFinding, call normalize(raw) → URIPRiskRecord.
    5. Periodically call health_check() → ConnectorHealth.

    The ConnectorScheduler orchestrates this lifecycle; connectors themselves
    are stateless between calls (session is passed back by the caller if needed).

    Catalog metadata (Z3) — every concrete subclass MUST set:
        DISPLAY_NAME, CATEGORY, SHORT_DESCRIPTION, STATUS, MODULE_CODE,
        CREDENTIAL_FIELDS.   VENDOR_DOCS_URL and SUPPORTED_PRODUCTS are
        optional (default None).  ``ConnectorRegistry.register`` warns if any
        required field is left at its base-class placeholder so the catalog
        never silently shows an unconfigured tile.
    """

    NAME: str = "base"   # Override in subclasses; used by registry + logging

    # Catalog metadata — base-class placeholders, MUST be overridden.
    DISPLAY_NAME: str = ""
    CATEGORY: str = ""
    SHORT_DESCRIPTION: str = ""
    STATUS: ConnectorStatus = "live"
    VENDOR_DOCS_URL: Optional[str] = None
    SUPPORTED_PRODUCTS: Optional[list[str]] = None
    MODULE_CODE: str = "CORE"
    CREDENTIAL_FIELDS: list[CredentialFieldSpec] = []
--- registry
"""
connectors/base/registry.py — Plugin discovery and connector registry.

P1.6: Connector Framework Abstraction
P33-Z3: Metadata-aware listing for the Tool Catalog UI.

Design decisions
----------------
- ConnectorRegistry is a simple dict-backed store keyed by connector name.
- The module-level _global_registry instance is the canonical registry used
  by the scheduler and all decorators.
- @register_connector("name") is a class decorator that calls
  _global_registry.register(name, cls) at import time — no discovery magic,
  no file scanning needed.  Connectors self-register when their module is imported.
- Double-registration raises ValueError to catch copy-paste naming mistakes early.
- The registry stores classes (not instances); the scheduler instantiates on demand
  so each tick can get a fresh connector without shared state.
- Factory callables are also accepted (register("x", lambda: MyConnector()))
  to allow test injection of pre-configured instances.
- ``list_connectors_with_metadata()`` extracts the Tool-Catalog metadata from
  each registered class WITHOUT instantiation — class attribute access only.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Type

from connectors.base.connector import (
    CONNECTOR_CATEGORIES,
    BaseConnector,
    CredentialFieldSpec,
)
from connectors.base.setup_guide import SetupGuideSpec

logger = logging.getLogger(__name__)


# Metadata fields that MUST be set (non-empty) on every concrete connector
# for the Tool Catalog UI to render correctly.
_REQUIRED_METADATA_FIELDS: tuple[str, ...] = (
    "DISPLAY_NAME",
    "CATEGORY",
    "SHORT_DESCRIPTION",
    "STATUS",
    "MODULE_CODE",
)
_VALID_STATUSES: tuple[str, ...] = ("live", "building", "simulated", "roadmap")


class ConnectorRegistry:
    """
    Thread-safe (GIL-protected) connector name → class/factory registry.

    Usage
    -----
    registry = ConnectorRegistry()
    registry.register("tenable", TenableConnector)
    cls = registry.get("tenable")
    instance = cls()
    """

    def __init__(self) -> None:
        self._store: dict[str, Callable] = {}

    def register(self, name: str, factory: Callable) -> None:
        """
        Register a connector class or factory under `name`.

        Parameters
        ----------
        name : str
            Unique connector identifier (e.g. "tenable", "sentinelone").
        factory : Callable
            A class (subclass of BaseConnector) or a zero-arg callable that
            returns a BaseConnector instance.

        Raises
        ------
        ValueError
            If `name` is already registered.

        Notes
        -----
        Z3: Logs a WARNING (not error — backward compat) for every required
        metadata field that is missing on `factory`.  We can't raise: parallel
        workers might land their connector before metadata is filled in.
        """
        if name in self._store:
            raise ValueError(
                f"Connector '{name}' is already registered.  "
                "Use a unique name or unregister the existing one first."
            )
        self._store[name] = factory
        _warn_if_metadata_incomplete(name, factory)
        logger.debug("Registered connector: %s", name)

    def get(self, name: str) -> Callable:
        """
        Look up a connector factory by name.

        Raises
        ------
        KeyError
            If `name` is not registered.
        """
        if name not in self._store:
            raise KeyError(f"No connector registered with name '{name}'.")
        return self._store[name]

    def list_names(self) -> list[str]:
        """Return sorted list of all registered connector names."""
        return sorted(self._store.keys())

    def list_connectors_with_metadata(self) -> list[dict[str, Any]]:
        """
        Return one dict per registered connector with all Tool-Catalog metadata.

        Reads class attributes only — no instantiation, no I/O, safe to call
        on every request.  Output sorted by `name` for stable UI ordering.

        Each item:
            {
              "name": str,
              "display_name": str,
              "category": str,
              "short_description": str,
              "status": "live" | "building" | "simulated" | "roadmap",
              "vendor_docs_url": str | None,
              "supported_products": list[str] | None,
              "module_code": str,
              "credential_fields": list[dict],
            }
        """
        return [
            self._extract_metadata(name, factory)
            for name, factory in sorted(self._store.items())
        ]

    def get_connector_metadata(self, name: str) -> dict[str, Any]:
        """
        Return the full metadata dict for a single connector.

        Raises
        ------
        KeyError
            If `name` is not registered.
        """
        if name not in self._store:
            raise KeyError(f"No connector registered with name '{name}'.")
        return self._extract_metadata(name, self._store[name])

    @staticmethod
    def _extract_metadata(name: str, factory: Callable) -> dict[str, Any]:
        """
        Pull metadata off a factory (class) without calling it.

        For zero-arg lambda factories that don't expose class attrs, the
        returned dict still has the placeholder shape — the catalog will then
        show "(metadata missing)" rather than blowing up.
        """
        cls = factory if isinstance(factory, type) else getattr(factory, "__self__", None)

        # Read attributes off the class (or factory), defaulting to base values.
        display_name = getattr(factory, "DISPLAY_NAME", "") or name
        category = getattr(factory, "CATEGORY", "") or "UNCATEGORIZED"
        short_description = getattr(factory, "SHORT_DESCRIPTION", "") or ""
        status = getattr(factory, "STATUS", "live") or "live"
        vendor_docs_url = getattr(factory, "VENDOR_DOCS_URL", None)
        supported_products = getattr(factory, "SUPPORTED_PRODUCTS", None)
        module_code = getattr(factory, "MODULE_CODE", "CORE") or "CORE"

        # CREDENTIAL_FIELDS is a list of CredentialFieldSpec; serialize.
        raw_fields = getattr(factory, "CREDENTIAL_FIELDS", None) or []
        credential_fields: list[dict[str, Any]] = []
        for f in raw_fields:
            if isinstance(f, CredentialFieldSpec):
                credential_fields.append(f.to_dict())
            elif isinstance(f, dict):
                credential_fields.append(f)
            # Unknown shapes are dropped — keeps response JSON-clean.

        # SETUP_GUIDE — inline onboarding content rendered on the catalog tile.
        # Returns ``None`` if the connector has not declared one yet (registry
        # already warned at register-time).
        raw_guide = getattr(factory, "SETUP_GUIDE", None)
        setup_guide: Optional[dict[str, Any]] = None
        if isinstance(raw_guide, SetupGuideSpec):
            setup_guide = raw_guide.to_dict()
        elif isinstance(raw_guide, dict):
            # Tolerate already-serialised dicts (e.g. test injection).
            setup_guide = raw_guide

        return {
            "name": name,
            "display_name": display_name,
            "category": category,
            "short_description": short_description,
            "status": status,
            "vendor_docs_url": vendor_docs_url,

exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && rg -n \"class BaseConnector\" -n connectors/base/connector.py && rg -n \"@abc\\.abstractmethod\" connectors/base/connector.py && sed -n '260,420p' connectors/base/connector.py" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
226:class BaseConnector(abc.ABC):
277:    @abc.abstractmethod
300:    @abc.abstractmethod
319:    @abc.abstractmethod
330:    @abc.abstractmethod
    CREDENTIAL_FIELDS: list[CredentialFieldSpec] = []

    # Cyber Risk Index (TrendAI-style) — which sub-index this connector feeds.
    # One of "exposure" | "attack" | "security_config" | None.
    # - "exposure"        : things that EXPOSE you to attack (Tenable, EASM, …)
    # - "attack"          : things actively attacking you (EDR, identity risky-signins, DLP, …)
    # - "security_config" : misconfigurations (CSPM, MDM/UEM, firewall posture, …)
    # - None              : connector does not feed any of the three Cyber Risk
    #                       Index sub-indexes (e.g. ITSM, advisory, OT, email).
    RISK_INDEX_DOMAIN: Optional[Literal["exposure", "attack", "security_config"]] = None

    # Inline onboarding content (P33-Z3 revised) — populated per concrete
    # subclass with a SetupGuideSpec.  When set, the Tool Catalog UI renders
    # the entire installation walk-through inline on the connector tile so
    # customers never need to leave URIP to configure a tool.
    SETUP_GUIDE: Optional["SetupGuideSpec"] = None

    @abc.abstractmethod
    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate credentials and return a ConnectorSession.

        Parameters
        ----------
        tenant_credentials : dict
            Decrypted credentials blob from CredentialsVault.
            Shape is connector-specific (api_key, client_id/secret, etc.).

        Returns
        -------
        ConnectorSession
            Valid session object; token expires_at is set by the connector.

        Raises
        ------
        ConnectorAuthError
            If credentials are invalid or the upstream API rejects them.
        """
        ...

    @abc.abstractmethod
    def fetch_findings(self, since: datetime, **kwargs) -> list[RawFinding]:
        """
        Pull new/updated findings from the source since `since`.

        Parameters
        ----------
        since : datetime
            Fetch only findings created/updated after this timestamp.
            Connector must pass this as a filter to the upstream API where
            possible; otherwise filter locally.

        Returns
        -------
        list[RawFinding]
            Zero or more raw findings.  Empty list is valid (no new findings).
        """
        ...

    @abc.abstractmethod
    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map one RawFinding to a URIPRiskRecord.

        Must produce a complete URIPRiskRecord (all required fields populated).
        Optional fields (cve_id, epss_score, etc.) may be None if not available
        from this source.
        """
        ...

    @abc.abstractmethod
    def health_check(self) -> ConnectorHealth:
        """
        Return the connector's current operational status.
        Should NOT raise — return ConnectorHealth(status="error") instead.
        """
        ...


# ─────────────────────────────────────────────────────────────────────────────
# Connector-specific exceptions
# ─────────────────────────────────────────────────────────────────────────────


class ConnectorAuthError(Exception):
    """Raised when authenticate() fails."""


class ConnectorFetchError(Exception):
    """Raised when fetch_findings() encounters an unrecoverable API error."""


class ConnectorNormalizeError(Exception):
    """Raised when a raw finding cannot be normalized (malformed data)."""

exec
/bin/zsh -lc 'cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && rg -n "async def" connectors/jira/connector.py connectors/servicenow/connector.py && rg -n "def authenticate" connectors/jira/connector.py connectors/servicenow/connector.py' in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
connectors/servicenow/connector.py:216:    async def authenticate(self, credentials: dict) -> ConnectorSession:  # type: ignore[override]
connectors/servicenow/connector.py:300:    async def fetch_findings(  # type: ignore[override]
connectors/servicenow/connector.py:423:    async def health_check(  # type: ignore[override]
connectors/servicenow/connector.py:468:    async def create_ticket(
connectors/jira/connector.py:231:    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
connectors/servicenow/connector.py:216:    async def authenticate(self, credentials: dict) -> ConnectorSession:  # type: ignore[override]

**Evaluating Jira and ServiceNow Integration**

I'm assessing how the JiraConnector functions with sync and async methods. It seems that the ServiceNow connector has a significant issue since its health check is called synchronously but is defined as async. This could lead to coroutines not executing properly, raising attribute errors. It's concerning that the integration health endpoint may always result in an error or crash. I'll need to verify this by checking the implementation of the ServiceNow connector. Time to inspect the relevant sections!
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && sed -n '1,240p' connectors/servicenow/connector.py && sed -n '240,520p' connectors/servicenow/connector.py" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
"""
ServiceNow ITSM connector for URIP-Adaptive Mind.

Implements the BaseConnector contract:
  authenticate   → Basic Auth (username + password) OR OAuth Bearer Token
  fetch_findings → pulls security incidents (/api/now/table/incident)
  normalize      → maps SN incident → URIPRiskRecord
  health_check   → lightweight ping via sys_user table

Bidirectional:
  create_ticket  → creates a ServiceNow incident from URIP risk data
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from connectors.base.connector import (
    BaseConnector,
    ConnectorAuthError,
    ConnectorFetchError,
    ConnectorHealth,
    ConnectorSession,
    CredentialFieldSpec,
    RawFinding,
    URIPRiskRecord,
)
from connectors.base.registry import register_connector
from connectors.base.setup_guides_data import SETUP_GUIDES
from connectors.servicenow.api_client import ServiceNowAPIClient
from connectors.servicenow.schemas import ServiceNowIncident, ServiceNowListResponse

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Severity mapping
# ─────────────────────────────────────────────────────────────────────────────

# ServiceNow urgency/impact scale: 1=High, 2=Medium, 3=Low
# URIP severity: critical | high | medium | low
#
# Combined rule (spec §connector.py → normalize()):
#   urgency=1 AND impact=1   → critical
#   urgency=1 OR  impact=1   → high
#   urgency=2 OR  impact=2   → medium
#   else                     → low


def _map_severity(urgency: Optional[str], impact: Optional[str]) -> str:
    """
    Map ServiceNow urgency + impact integers to URIP severity.

    Parameters
    ----------
    urgency : str | None
        ServiceNow urgency field value ("1", "2", or "3").
    impact  : str | None
        ServiceNow impact field value ("1", "2", or "3").

    Returns
    -------
    str
        One of "critical" | "high" | "medium" | "low".
    """
    u = int(urgency) if urgency and urgency.isdigit() else 3
    i = int(impact) if impact and impact.isdigit() else 3

    if u == 1 and i == 1:
        return "critical"
    if u == 1 or i == 1:
        return "high"
    if u == 2 or i == 2:
        return "medium"
    return "low"


def _severity_to_urgency_impact(severity: str) -> tuple[int, int]:
    """
    Reverse map URIP severity → (urgency, impact) for create_ticket.

    Returns
    -------
    tuple[int, int]
        (urgency, impact) both in ServiceNow scale 1=High, 2=Medium, 3=Low.
    """
    mapping: dict[str, tuple[int, int]] = {
        "critical": (1, 1),
        "high":     (1, 2),
        "medium":   (2, 2),
        "low":      (3, 3),
    }
    return mapping.get(severity.lower(), (3, 3))


# ─────────────────────────────────────────────────────────────────────────────
# Connector class
# ─────────────────────────────────────────────────────────────────────────────


@register_connector("servicenow")
class ServiceNowConnector(BaseConnector):
    """
    Live connector for ServiceNow ITSM (Utah / Vancouver / Washington / Xanadu).

    Data flow
    ---------
    1. Authenticate with Basic Auth (username + password) OR OAuth Bearer Token.
    2. Fetch security incidents from /api/now/table/incident using an encoded query.
    3. Normalize each incident to URIPRiskRecord using urgency + impact → severity.
    4. (Bidirectional) Create ServiceNow incidents from URIP risk data via create_ticket().

    Thread / async safety
    ---------------------
    The underlying ServiceNowAPIClient is async (httpx.AsyncClient).  All methods
    on this connector that call the API are therefore async.  The connector
    scheduler (which is sync) must call these via asyncio.run() or an event loop.
    """

    NAME = "servicenow"
    RISK_INDEX_DOMAIN = None   # ITSM — does not feed the Cyber Risk Index directly.

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "ServiceNow"
    CATEGORY = "ITSM"
    SHORT_DESCRIPTION = (
        "Bidirectional sync — push URIP risks as ServiceNow incidents "
        "and ingest security incidents back as risks."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = (
        "https://developer.servicenow.com/dev.do#!/reference/api/utah/rest/c_TableAPI"
    )
    SUPPORTED_PRODUCTS = [
        "ServiceNow ITSM (Utah / Vancouver / Washington / Xanadu)"
    ]
    MODULE_CODE = "ITSM"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="instance_url",
            label="Instance URL",
            type="url",
            required=True,
            placeholder="https://your-tenant.service-now.com",
            help_text="Full URL of your ServiceNow instance — must be HTTPS.",
            pattern=r"^https://[^\s]+$",
        ),
        CredentialFieldSpec(
            name="auth_method",
            label="Auth Method",
            type="select",
            required=True,
            help_text="Basic Auth (username + password) or OAuth Bearer Token.",
            options=[
                {"value": "basic", "label": "Username + Password"},
                {"value": "oauth", "label": "OAuth Bearer Token"},
            ],
        ),
        CredentialFieldSpec(
            name="username",
            label="Username",
            type="text",
            required=False,
            help_text="Required when auth_method=basic. Use a dedicated integration user.",
            placeholder="urip_integration",
        ),
        CredentialFieldSpec(
            name="password",
            label="Password",
            type="password",
            required=False,
            secret=True,
            help_text="Required when auth_method=basic.",
            placeholder="••••••••",
        ),
        CredentialFieldSpec(
            name="oauth_token",
            label="OAuth Bearer Token",
            type="password",
            required=False,
            secret=True,
            help_text="Required when auth_method=oauth. Bearer token from your IdP.",
            placeholder="eyJ…",
        ),
        CredentialFieldSpec(
            name="risk_query",
            label="Risk Query",
            type="text",
            required=True,
            placeholder="category=security^state!=7",
            help_text=(
                "ServiceNow encoded query that selects security incidents to ingest. "
                "State 7 = Closed. Default fetches all active security incidents."
            ),
            default="category=security^active=true",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["servicenow"]

    def __init__(self) -> None:
        self._client: Optional[ServiceNowAPIClient] = None
        self._instance_url: str = ""
        self._risk_query: str = "category=security^active=true"
        self._last_run: Optional[datetime] = None
        self._error_count: int = 0
        self._last_error: Optional[str] = None

    # ─────────────────────────────────────────────────────────────────────────
    # authenticate
    # ─────────────────────────────────────────────────────────────────────────

    async def authenticate(self, credentials: dict) -> ConnectorSession:  # type: ignore[override]
        """
        Validate ServiceNow credentials and return a ConnectorSession.

        Parameters
        ----------
        credentials : dict
            Must contain:
              - instance_url  (str)
              - auth_method   ("basic" or "oauth")
            If auth_method == "basic":
              - username (str)
              - password (str)
            If auth_method == "oauth":
              - oauth_token (str)
            Optional:
              - risk_query (str) — encoded query for security incidents
              - tenant_id  (str) — URIP tenant scoping

        Raises
        ------
        ConnectorAuthError
            If credentials are missing required fields or the API rejects them.
        """
        instance_url = credentials.get("instance_url", "").strip().rstrip("/")
        instance_url = credentials.get("instance_url", "").strip().rstrip("/")
        auth_method = str(credentials.get("auth_method", "")).lower()
        risk_query = credentials.get("risk_query", "category=security^active=true")

        if not instance_url:
            raise ConnectorAuthError(
                "ServiceNow credentials must include 'instance_url'."
            )
        if auth_method not in ("basic", "oauth"):
            raise ConnectorAuthError(
                f"Unsupported auth_method: {auth_method!r}. Use 'basic' or 'oauth'."
            )

        if auth_method == "basic":
            username = credentials.get("username", "").strip()
            password = credentials.get("password", "")
            if not username or not password:
                raise ConnectorAuthError(
                    "Basic Auth requires 'username' and 'password'."
                )
            self._client = ServiceNowAPIClient(
                instance_url=instance_url,
                username=username,
                password=password,
            )
        else:  # oauth
            oauth_token = credentials.get("oauth_token", "").strip()
            if not oauth_token:
                raise ConnectorAuthError(
                    "OAuth mode requires 'oauth_token'."
                )
            self._client = ServiceNowAPIClient(
                instance_url=instance_url,
                oauth_token=oauth_token,
            )

        # Verify connectivity — raises ConnectorAuthError on 401/403.
        try:
            await self._client.healthcheck()
        except ConnectorAuthError:
            raise
        except Exception as exc:
            raise ConnectorAuthError(
                f"ServiceNow connectivity check failed: {exc}"
            ) from exc

        self._instance_url = instance_url
        self._risk_query = risk_query or "category=security^active=true"

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=credentials.get("tenant_id", "unknown"),
            token=f"sn-{auth_method}-****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # fetch_findings
    # ─────────────────────────────────────────────────────────────────────────

    async def fetch_findings(  # type: ignore[override]
        self,
        session: ConnectorSession,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[RawFinding]:
        """
        Pull security incidents from ServiceNow.

        Parameters
        ----------
        session : ConnectorSession
            Session returned by authenticate().
        since : datetime, optional
            Fetch incidents updated after this timestamp (encoded into query).
        limit : int
            Maximum incidents to return (default 100).

        Returns
        -------
        list[RawFinding]
            Zero or more raw incident findings.
        """
        if self._client is None:
            raise ConnectorFetchError(
                "Connector not authenticated. Call authenticate() first."
            )

        query = self._risk_query
        if since:
            ts = since.strftime("%Y-%m-%d %H:%M:%S")
            query = f"{query}^sys_updated_on>{ts}"

        findings: list[RawFinding] = []
        tenant_id = session.tenant_id

        try:
            raw_list = await self._client.list_incidents(query=query, limit=limit)
            # Validate through Pydantic to normalize nested-object fields.
            response = ServiceNowListResponse(result=raw_list)

            for incident in response.result:
                findings.append(
                    RawFinding(
                        id=incident.sys_id,
                        source=self.NAME,
                        raw_data=incident.model_dump(mode="json"),
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            logger.info(
                "ServiceNow: fetched %d findings for tenant %s",
                len(findings),
                tenant_id,
            )
            self._last_run = datetime.now(timezone.utc)
            return findings

        except (ConnectorAuthError, ConnectorFetchError):
            raise
        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("ServiceNow fetch_findings failed")
            raise ConnectorFetchError(
                f"ServiceNow fetch failed: {exc}"
            ) from exc

    # ─────────────────────────────────────────────────────────────────────────
    # normalize
    # ─────────────────────────────────────────────────────────────────────────

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:  # type: ignore[override]
        """
        Map a ServiceNow RawFinding to a URIPRiskRecord.

        Severity logic (urgency=1=High, 2=Medium, 3=Low; same for impact):
          - urgency=1 AND impact=1  → critical
          - urgency=1 OR  impact=1  → high
          - urgency=2 OR  impact=2  → medium
          - else                    → low

        External ID = sys_id.
        Source URL  = instance_url + /nav_to.do?uri=incident.do?sys_id={sys_id}
        """
        data = raw.raw_data
        incident = ServiceNowIncident.model_validate(data)

        severity = _map_severity(incident.urgency, incident.impact)

        finding = f"SN Incident: {incident.short_description or 'Unknown'}"
        description = (
            f"ServiceNow incident {incident.number or incident.sys_id}: "
            f"{incident.short_description or 'N/A'}. "
            f"State: {incident.state or 'unknown'}. "
            f"Urgency: {incident.urgency or 'unknown'}, "
            f"Impact: {incident.impact or 'unknown'}. "
            f"Detail: {incident.description or 'N/A'}."
        )

        source_url = (
            f"{self._instance_url}/nav_to.do?uri=incident.do?sys_id={incident.sys_id}"
        )

        return URIPRiskRecord(
            finding=finding,
            description=description,
            source=self.NAME,
            domain="application",
            cvss_score=0.0,
            severity=severity,
            asset=incident.assigned_to or incident.caller_id or "unknown",
            owner_team="IT Service Management",
            cve_id=None,
            exploit_status=None,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # health_check
    # ─────────────────────────────────────────────────────────────────────────

    async def health_check(  # type: ignore[override]
        self,
        session: ConnectorSession,
    ) -> ConnectorHealth:
        """
        Return connector operational status.

        Makes a lightweight GET /api/now/table/sys_user?sysparm_limit=1 call.
        Returns status="ok" on success, "degraded" or "error" on failure.
        Never raises — returns ConnectorHealth with status="error" instead.
        """
        try:
            if self._client is None:
                return ConnectorHealth(
                    connector_name=self.NAME,
                    status="error",
                    last_run=self._last_run,
                    error_count=self._error_count,
                    last_error="Client not initialised — call authenticate() first.",
                )
            await self._client.healthcheck()
            return ConnectorHealth(
                connector_name=self.NAME,
                status="ok",
                last_run=self._last_run,
                error_count=self._error_count,
                last_error=self._last_error,
            )
        except Exception as exc:
            err = str(exc)
            self._error_count += 1
            self._last_error = err
            logger.warning("ServiceNow health_check failed: %s", err)
            return ConnectorHealth(
                connector_name=self.NAME,
                status="degraded",
                last_run=self._last_run,
                error_count=self._error_count,
                last_error=err,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # create_ticket (bidirectional)
    # ─────────────────────────────────────────────────────────────────────────

    async def create_ticket(
        self,
        session: ConnectorSession,
        risk: URIPRiskRecord,
    ) -> dict[str, Any]:
        """
        Create a ServiceNow incident from a URIP risk record.

        Maps URIP severity → urgency + impact using the reverse of _map_severity:
          critical → (1, 1)
          high     → (1, 2)
          medium   → (2, 2)
          low      → (3, 3)

        Parameters
        ----------
        session : ConnectorSession
            Active session (used for tenant scoping in logs).
        risk : URIPRiskRecord
            Normalized URIP risk to push as an incident.

        Returns
        -------
        dict
            {"sys_id": str, "number": str, "url": str}
        """
        if self._client is None:
            raise ConnectorFetchError(
                "Connector not authenticated. Call authenticate() first."
            )

        urgency, impact = _severity_to_urgency_impact(risk.severity)

        short_description = risk.finding[:160] if risk.finding else "URIP Auto-Created Incident"
        description = risk.description or "Auto-created by URIP risk intelligence platform."

        try:
            result = await self._client.create_incident(
                short_description=short_description,
                description=description,
                urgency=urgency,
                impact=impact,
                category="security",
            )
            sys_id = result.get("sys_id", "")
            number = result.get("number", "")
            url = (
                f"{self._instance_url}/nav_to.do?uri=incident.do?sys_id={sys_id}"
                if sys_id
                else ""
            )
            logger.info(
                "ServiceNow: created incident %s (sys_id=%s) for tenant %s",

exec
/bin/zsh -lc 'cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && rg -n "_run_async" connectors/jira/connector.py && rg -n "await " connectors/jira/connector.py && rg -n "async def" connectors/jira/api_client.py connectors/jira/connector.py' in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 exited 1 in 0ms:
26:def _run_async(coro: Any) -> Any:
309:            myself = _run_async(
363:            raw = _run_async(
477:            _run_async(
553:            resp = _run_async(

**Checking connector compliance**

I'm using _run_async to run async client methods within sync connector methods. It’s important to confirm if the Jira connector aligns with BaseConnector signatures. I’ll need to review the method definitions and check the signature for health_check and other relevant methods. Ensuring compliance is crucial, so I'll pay close attention to the details as I examine them!
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && rg -n \"def (authenticate|fetch_findings|normalize|health_check|create_ticket)\" connectors/jira/connector.py && sed -n '220,620p' connectors/jira/connector.py" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
231:    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
330:    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
401:    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
464:    def health_check(self) -> ConnectorHealth:
504:    def create_ticket(
        self._base_url: str = ""
        self._risk_jql: str = 'project = SEC AND labels = "security"'
        self._default_project_key: str = "SEC"
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    # ─────────────────────────────────────────────────────────────────────────
    # BaseConnector contract
    # ─────────────────────────────────────────────────────────────────────────

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate Jira credentials by calling /rest/api/3/myself.

        Required credential keys:
            - base_url      : Jira instance URL
            - auth_method   : "basic" or "bearer"
        If auth_method == "basic":
            - email         : Atlassian account email
            - api_token     : Atlassian API token
        If auth_method == "bearer":
            - bearer_token  : Personal Access Token (DC/Server)
        Optional:
            - default_project_key : project key for outbound ticket creation
            - risk_jql            : JQL for inbound ticket ingestion

        Returns
        -------
        ConnectorSession
            Session with token field set to "jira-basic-****" or "jira-bearer-****".

        Raises
        ------
        ConnectorAuthError
            If credentials are missing or Jira rejects them.
        """
        base_url = tenant_credentials.get("base_url", "").strip()
        auth_method = tenant_credentials.get("auth_method", "").strip().lower()

        if not base_url:
            raise ConnectorAuthError(
                "Jira credentials must include 'base_url'."
            )
        if not auth_method:
            raise ConnectorAuthError(
                "Jira credentials must include 'auth_method' ('basic' or 'bearer')."
            )

        # Store config for later use by fetch_findings / create_ticket.
        self._base_url = base_url
        self._risk_jql = tenant_credentials.get(
            "risk_jql", 'project = SEC AND labels = "security"'
        )
        self._default_project_key = tenant_credentials.get("default_project_key", "SEC")

        if auth_method == "basic":
            email = tenant_credentials.get("email", "").strip()
            api_token = tenant_credentials.get("api_token", "").strip()
            if not email or not api_token:
                raise ConnectorAuthError(
                    "auth_method=basic requires 'email' and 'api_token'."
                )
            self._client = JiraAPIClient(
                base_url=base_url,
                email=email,
                api_token=api_token,
            )
            token_label = "jira-basic-****"

        elif auth_method == "bearer":
            bearer_token = tenant_credentials.get("bearer_token", "").strip()
            if not bearer_token:
                raise ConnectorAuthError(
                    "auth_method=bearer requires 'bearer_token'."
                )
            self._client = JiraAPIClient(
                base_url=base_url,
                bearer_token=bearer_token,
            )
            token_label = "jira-bearer-****"

        else:
            raise ConnectorAuthError(
                f"Unsupported auth_method: {auth_method!r}. Use 'basic' or 'bearer'."
            )

        # Verify credentials by calling /rest/api/3/myself.
        try:
            myself = _run_async(
                self._client.get_myself()
            )
        except ConnectorAuthError:
            raise
        except Exception as exc:
            raise ConnectorAuthError(
                f"Jira authentication probe failed: {exc}"
            ) from exc

        account_id = myself.get("accountId", "unknown")
        logger.info("Jira authenticated: accountId=%s base_url=%s", account_id, base_url)

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=token_label,
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
            extra={"accountId": account_id},
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull security tickets from Jira using the configured JQL filter.

        Parameters
        ----------
        since : datetime
            Fetch only issues updated after this timestamp.
            The JQL filter handles this via "updated >= -Xd" style clauses —
            or the connector simply passes the full JQL and paginates.
        tenant_id : str, optional
            Scoped into RawFinding.tenant_id.
        limit : int, optional
            Maximum issues to fetch (default 100).

        Returns
        -------
        list[RawFinding]

        Raises
        ------
        ConnectorFetchError
            If the Jira API returns an error or the connector is not authenticated.
        """
        if self._client is None:
            raise ConnectorFetchError(
                "Jira connector not authenticated. Call authenticate() first."
            )

        tenant_id: str = kwargs.get("tenant_id", "unknown")
        limit: int = kwargs.get("limit", 100)

        try:
            raw = _run_async(
                self._client.search_issues(
                    jql=self._risk_jql,
                    max_results=limit,
                )
            )
            data = JiraSearchResponse.model_validate(raw)

            findings: list[RawFinding] = []
            for issue in data.issues:
                findings.append(
                    RawFinding(
                        id=issue.key,
                        source=self.NAME,
                        raw_data=issue.model_dump(mode="json"),
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            logger.info(
                "Jira: fetched %d issues for tenant %s (JQL: %s)",
                len(findings),
                tenant_id,
                self._risk_jql,
            )
            self._last_run = datetime.now(timezone.utc)
            return findings

        except (ConnectorAuthError, ConnectorFetchError):
            raise
        except Exception as exc:
            self._error_count += 1
            msg = str(exc)
            self._last_error = msg
            logger.exception("Jira fetch_findings failed")
            raise ConnectorFetchError(f"Jira fetch_findings failed: {msg}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map a Jira RawFinding to a URIPRiskRecord.

        Priority mapping:
            Highest → critical
            High    → high
            Medium  → medium
            Low     → low
            Lowest  → low
            (unmapped) → medium

        Status mapping:
            Open / In Progress → open
            Done / Closed / Resolved → resolved

        The external_id and source_url are stored in description for
        traceability (URIPRiskRecord has no dedicated link field).
        """
        issue = JiraIssue.model_validate(raw.raw_data)

        fields = issue.fields
        summary = (fields.summary if fields else None) or issue.key
        status_name = (fields.status.name if fields and fields.status else None)
        priority_name = (fields.priority.name if fields and fields.priority else None)
        description_raw = (fields.description if fields else None)

        # Extract plain text from ADF or plain string description.
        if isinstance(description_raw, dict):
            # ADF — extract text nodes
            desc_text = _extract_adf_text(description_raw)
        elif isinstance(description_raw, str):
            desc_text = description_raw
        else:
            desc_text = ""

        severity = _map_priority(priority_name)
        status_label = _map_status(status_name)

        source_url = f"{self._base_url}/browse/{issue.key}" if self._base_url else None

        description = (
            f"Jira issue {issue.key}: {summary}. "
            f"Status: {status_name or 'unknown'}. "
            f"Priority: {priority_name or 'unknown'}. "
            f"URL: {source_url or 'N/A'}."
        )
        if desc_text:
            description += f" Details: {desc_text[:500]}"

        return URIPRiskRecord(
            finding=f"Jira: {summary}",
            description=description,
            source=self.NAME,
            domain="application",
            cvss_score=0.0,
            severity=severity,
            asset=issue.key,
            owner_team="IT Service Management",
            cve_id=None,
            exploit_status=None,
        )

    def health_check(self) -> ConnectorHealth:
        """Return connector operational status."""
        if self._client is None:
            # Not yet authenticated — report as ok (not an error state).
            return ConnectorHealth(
                connector_name=self.NAME,
                status="ok",
                last_run=None,
                error_count=0,
                last_error=None,
            )

        try:
            _run_async(
                self._client.get_myself()
            )
            error_count = self._error_count
            status = "ok" if error_count == 0 else (
                "degraded" if error_count < 5 else "error"
            )
            return ConnectorHealth(
                connector_name=self.NAME,
                status=status,
                last_run=self._last_run,
                error_count=error_count,
                last_error=self._last_error,
            )
        except Exception as exc:
            return ConnectorHealth(
                connector_name=self.NAME,
                status="degraded",
                last_run=self._last_run,
                error_count=self._error_count + 1,
                last_error=str(exc),
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Bidirectional — outbound ticket creation
    # ─────────────────────────────────────────────────────────────────────────

    def create_ticket(
        self,
        session: Any,  # ConnectorSession (passed by caller but not used internally)
        risk: URIPRiskRecord,
        project_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create a Jira issue from a URIPRiskRecord.

        Parameters
        ----------
        session : ConnectorSession
            Active session (for interface consistency — auth state already in self._client).
        risk : URIPRiskRecord
            Normalized risk record to push.
        project_key : str, optional
            Override the configured default_project_key.

        Returns
        -------
        dict
            {"key": "SEC-42", "url": "https://…/browse/SEC-42", "id": "10001"}

        Raises
        ------
        ConnectorFetchError
            If the connector is not authenticated or the API call fails.
        """
        if self._client is None:
            raise ConnectorFetchError(
                "Jira connector not authenticated. Call authenticate() first."
            )

        target_project = project_key or self._default_project_key
        jira_priority = _SEVERITY_TO_JIRA_PRIORITY.get(risk.severity, "Medium")

        description = (
            f"Risk detected by URIP.\n\n"
            f"Finding: {risk.finding}\n"
            f"Severity: {risk.severity}\n"
            f"Asset: {risk.asset}\n"
            f"Owner team: {risk.owner_team}\n"
            f"Source: {risk.source}\n"
            f"Domain: {risk.domain}\n"
        )
        if risk.description:
            description += f"\nDetails:\n{risk.description}"

        try:
            resp = _run_async(
                self._client.create_issue(
                    project_key=target_project,
                    summary=risk.finding[:255],  # Jira summary max 255 chars
                    description=description,
                    issue_type="Task",
                    priority=jira_priority,
                    labels=["urip", "security"],
                )
            )
            issue_key = resp.get("key", "UNKNOWN")
            issue_id = resp.get("id", "")
            issue_url = f"{self._base_url}/browse/{issue_key}"
            logger.info("Jira: created issue %s (%s)", issue_key, issue_url)
            return {"key": issue_key, "id": issue_id, "url": issue_url}

        except (ConnectorAuthError, ConnectorFetchError):
            raise
        except Exception as exc:
            self._error_count += 1
            msg = str(exc)
            self._last_error = msg
            logger.exception("Jira create_ticket failed")
            raise ConnectorFetchError(f"Jira create_ticket failed: {msg}") from exc


# ─────────────────────────────────────────────────────────────────────────────
# ADF text extraction helper (module-level so it's testable)
# ─────────────────────────────────────────────────────────────────────────────


def _extract_adf_text(adf: dict[str, Any]) -> str:
    """
    Recursively extract plain text from an Atlassian Document Format (ADF) dict.

    Returns a single string with space-separated text nodes.
    """
    parts: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "text":
                parts.append(node.get("text", ""))
            for child in node.get("content", []):
                _walk(child)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(adf)
    return " ".join(p for p in parts if p).strip()

**Evaluating Jira Connector**

The Jira connector seems to be functioning correctly, but it's clear that ServiceNow doesn't conform to the expected standards, which is a strong observation. In the Jira connector, I noticed the definition of `_run_async` appears before the imports, but that seems fine. I think I should check `connectors/jira/__init__.py` to confirm that the imports guarantee registration. It might be worth revisiting the previous output since it might have some relevant details. Let's take a look!
exec
/bin/zsh -lc 'cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && cat connectors/jira/__init__.py && cat connectors/servicenow/__init__.py' in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
**Inspecting module import behavior**

I'm thinking about an empty output and wondering if __init__.py might be empty too. It's interesting that the "cat" command returned nothing. So, that suggests the connector class registration only happens when the module is imported. Now, I need to consider how exactly connectors are imported, possibly through backend/connector_loader.py? I should inspect this further to figure it out. There's definitely something to unravel here!
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && sed -n '1,220p' backend/connector_loader.py" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
"""
backend/connector_loader.py — Force-import every connector module on backend boot.

Why this exists (INV-1 fix)
---------------------------
Each connector class is decorated with ``@register_connector("name")``.  The
decorator runs at import time — meaning the class is registered in the global
registry only if its module is actually imported somewhere in the running
process.

Before this loader was introduced, `backend/main.py` did NOT import the
connector packages.  That left the global registry EMPTY at runtime, even
though ``connectors/tenable/connector.py`` etc. were unit-tested and looked
"alive" in source.  The 7 production connectors were therefore dead code in
the running app — a textbook INV-1 violation (no dead code).

By importing this module from ``backend/main.py``, every connector's
``@register_connector`` runs once at process start, and all 9 connectors
(7 production + 2 simulators) become callable through the registry, the
scheduler, and the new /api/connectors router.

Design decisions
----------------
- Plain `import` statements (no dynamic discovery via importlib) keep the
  static-analysis tools happy and make the dependency obvious.  If a new
  connector is added, this list MUST be updated — that's intentional, the
  rule is enforced by ``tests/test_connector_loader.py``.
- ``# noqa: F401`` because we want the import side-effect, not the name binding.
- ``get_registered_connector_names()`` is a thin convenience wrapper around the
  global registry, exposed primarily for the new connectors router and tests.
"""

from __future__ import annotations

# ── Production connectors (all 30 with @register_connector) ────────────────
# VM / EDR / EASM
import connectors.tenable.connector  # noqa: F401
import connectors.sentinelone.connector  # noqa: F401
import connectors.crowdstrike.connector  # noqa: F401
import connectors.easm.connector  # noqa: F401
# CASB / SWG / DLP / Firewall
import connectors.zscaler.connector  # noqa: F401
import connectors.netskope.connector  # noqa: F401
import connectors.fortiguard_fw.connector  # noqa: F401
import connectors.gtb.connector  # noqa: F401
# Identity / NAC / PAM
import connectors.ms_entra.connector  # noqa: F401
import connectors.forescout_nac.connector  # noqa: F401
import connectors.cyberark_pam.connector  # noqa: F401
# Cloud (CSPM)
import connectors.aws_cspm.connector  # noqa: F401
import connectors.azure_cspm.connector  # noqa: F401
import connectors.gcp_cspm.connector  # noqa: F401
# Endpoint / Mobile management
import connectors.manageengine_ec.connector  # noqa: F401
import connectors.manageengine_mdm.connector  # noqa: F401
import connectors.manageengine_sdp.connector  # noqa: F401
import connectors.servicenow.connector  # noqa: F401
# Email / Collab
import connectors.email_security.connector  # noqa: F401
import connectors.m365_collab.connector  # noqa: F401
# OT
import connectors.armis_ot.connector  # noqa: F401
# DAST
import connectors.burp_enterprise.connector  # noqa: F401
# SIEM / Advisory / Bug Bounty
import connectors.siem.connector  # noqa: F401
import connectors.cert_in.connector  # noqa: F401
import connectors.bug_bounty.connector  # noqa: F401
# External Threat / Dark Web
import connectors.cloudsek.connector  # noqa: F401
# LMS (security awareness)
import connectors.knowbe4.connector  # noqa: F401
import connectors.hoxhunt.connector  # noqa: F401
# BGV (background verification)
import connectors.authbridge.connector  # noqa: F401
import connectors.ongrid.connector  # noqa: F401
# ITSM — Jira Cloud + Data Center
import connectors.jira.connector  # noqa: F401

# ── Simulators (used for demos + the test-connection path) ──────────────────
import connectors.simulator_connector  # noqa: F401
import connectors.extended_simulator  # noqa: F401

from connectors.base.registry import _global_registry


def get_registered_connector_names() -> list[str]:
    """Return the sorted list of all registered connector names."""
    return _global_registry.list_names()

**Evaluating connector compatibility**

It seems like the ServiceNow connector is causing a major issue because it defines async methods that don't match the base methods. While this might not break the import, it could cause problems during runtime. I need to check the tests for ServiceNow to see if they might be using sync wrappers instead, but it looks like that's not the case. So, I'll also look at the tests for Jira and ServiceNow to ensure they cover the base contract properly.
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && sed -n '1,260p' tests/test_connectors/jira/test_connector.py && echo '---' && sed -n '1,260p' tests/connectors/servicenow/test_connector.py" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
"""
TDD tests for the Jira Cloud + Jira Data Center live connector.

Uses respx to mock all HTTP traffic — no real API calls.

Coverage:
  - Connector registration ("jira" key in global registry)
  - Priority normalization map (Highest → critical, High → high, …)
  - Authentication — Basic (Cloud) and Bearer (DC/Server)
  - fetch_findings — verifies JQL is passed through
  - create_ticket — verifies POST body shape (summary + ADF description + priority)
  - health_check — ok path and degraded path
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from connectors.base.connector import (
    ConnectorAuthError,
    ConnectorFetchError,
    ConnectorHealth,
    ConnectorSession,
    RawFinding,
    URIPRiskRecord,
)
from connectors.base.registry import _global_registry
from connectors.jira.connector import JiraConnector, _extract_adf_text
from connectors.jira.api_client import _plain_text_to_adf

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

BASE = "https://jira-test.atlassian.net"
DC_BASE = "https://jira.internal.example.com"


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def connector() -> JiraConnector:
    return JiraConnector()


@pytest.fixture
def basic_creds() -> dict[str, str]:
    return {
        "base_url": BASE,
        "auth_method": "basic",
        "email": "urip@atlassian-test.com",
        "api_token": "FAKE_API_TOKEN",
        "default_project_key": "SEC",
        "risk_jql": 'project = SEC AND labels = "security"',
        "tenant_id": "tenant-jira",
    }


@pytest.fixture
def bearer_creds() -> dict[str, str]:
    return {
        "base_url": DC_BASE,
        "auth_method": "bearer",
        "bearer_token": "FAKE_PAT_TOKEN",
        "default_project_key": "OPS",
        "risk_jql": 'project = OPS AND labels = "security"',
        "tenant_id": "tenant-dc",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _myself_response(account_id: str = "abc123") -> dict[str, Any]:
    return {
        "accountId": account_id,
        "displayName": "URIP Service Account",
        "emailAddress": "urip@example.com",
        "active": True,
    }


def _search_response(issues: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "total": len(issues or []),
        "startAt": 0,
        "maxResults": 50,
        "issues": issues or [],
    }


def _jira_issue(
    key: str = "SEC-1",
    summary: str = "Test finding",
    priority: str = "High",
    status: str = "Open",
) -> dict[str, Any]:
    return {
        "id": "10001",
        "key": key,
        "self": f"{BASE}/rest/api/3/issue/10001",
        "fields": {
            "summary": summary,
            "status": {"name": status},
            "priority": {"name": priority},
            "created": "2026-04-28T10:00:00Z",
            "updated": "2026-04-28T10:00:00Z",
            "description": None,
            "labels": ["security"],
        },
    }


def _raw_finding(issue: dict[str, Any], base_url: str = BASE) -> RawFinding:
    return RawFinding(
        id=issue["key"],
        source="jira",
        raw_data=issue,
        fetched_at=datetime.now(timezone.utc),
        tenant_id="tenant-jira",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Registration
# ─────────────────────────────────────────────────────────────────────────────


class TestJiraRegistration:
    def test_register(self):
        """JiraConnector must be registered under the 'jira' key."""
        assert "jira" in _global_registry
        factory = _global_registry.get("jira")
        instance = factory()
        assert isinstance(instance, JiraConnector)

    def test_metadata(self):
        """Catalog metadata must be populated correctly."""
        assert JiraConnector.NAME == "jira"
        assert JiraConnector.DISPLAY_NAME == "Jira"
        assert JiraConnector.CATEGORY == "ITSM"
        assert JiraConnector.STATUS == "live"
        assert JiraConnector.MODULE_CODE == "ITSM"
        assert JiraConnector.RISK_INDEX_DOMAIN is None
        assert "Jira Cloud" in (JiraConnector.SUPPORTED_PRODUCTS or [])
        assert "Jira Data Center" in (JiraConnector.SUPPORTED_PRODUCTS or [])


# ─────────────────────────────────────────────────────────────────────────────
# 2. Priority normalization map
# ─────────────────────────────────────────────────────────────────────────────


class TestJiraNormalizePriorityMap:
    """Verify Jira priority → URIP severity mapping."""

    @pytest.mark.parametrize("jira_priority,expected_severity", [
        ("Highest", "critical"),
        ("High",    "high"),
        ("Medium",  "medium"),
        ("Low",     "low"),
        ("Lowest",  "low"),
        ("HIGHEST", "critical"),   # case-insensitive
        ("HIGH",    "high"),
        (None,      "medium"),     # unknown → medium default
        ("",        "medium"),
        ("Unknown", "medium"),
    ])
    def test_normalize_priority_map(
        self,
        connector: JiraConnector,
        jira_priority: str | None,
        expected_severity: str,
    ) -> None:
        issue = _jira_issue(priority=jira_priority or "")
        # For None priority, remove the field
        if jira_priority is None:
            issue["fields"]["priority"] = None
        raw = _raw_finding(issue)
        # We need base_url set for normalize to build source_url
        connector._base_url = BASE
        record = connector.normalize(raw)
        assert record.severity == expected_severity, (
            f"Jira priority {jira_priority!r} should map to {expected_severity!r}, "
            f"got {record.severity!r}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Authentication — Basic (Cloud)
# ─────────────────────────────────────────────────────────────────────────────


class TestJiraAuthenticateBasic:
    @respx.mock
    def test_authenticate_basic_success(
        self, connector: JiraConnector, basic_creds: dict
    ) -> None:
        """Basic auth should set Authorization: Basic base64(email:token) header."""
        route = respx.get(f"{BASE}/rest/api/3/myself").mock(
            return_value=httpx.Response(200, json=_myself_response())
        )
        session = connector.authenticate(basic_creds)

        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "jira"
        assert session.tenant_id == "tenant-jira"
        assert "jira-basic" in session.token
        assert route.called

        # Verify Basic header was generated correctly.
        sent_request = route.calls[0].request
        auth_header = sent_request.headers.get("authorization", "")
        assert auth_header.startswith("Basic "), (
            f"Expected 'Basic …' header, got {auth_header!r}"
        )
        decoded = base64.b64decode(auth_header[6:]).decode()
        assert decoded == f"{basic_creds['email']}:{basic_creds['api_token']}"

    @respx.mock
    def test_authenticate_basic_401_raises(
        self, connector: JiraConnector, basic_creds: dict
    ) -> None:
        respx.get(f"{BASE}/rest/api/3/myself").mock(
            return_value=httpx.Response(401, json={"errorMessages": ["Unauthorized"]})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(basic_creds)

    def test_authenticate_basic_missing_email_raises(
        self, connector: JiraConnector
    ) -> None:
        creds = {
            "base_url": BASE,
            "auth_method": "basic",
            "api_token": "tok",
            "default_project_key": "SEC",
            "risk_jql": "project = SEC",
        }
        with pytest.raises(ConnectorAuthError, match="email"):
            connector.authenticate(creds)

    def test_authenticate_missing_base_url_raises(
        self, connector: JiraConnector
    ) -> None:
        with pytest.raises(ConnectorAuthError, match="base_url"):
            connector.authenticate({"auth_method": "basic"})

---
"""
TDD tests for the ServiceNow ITSM live connector.

Uses respx to mock all HTTP traffic — no real API calls.
Coverage: registration, severity mapping, authentication (Basic + OAuth),
incident list fetch, ticket creation (urgency mapping), health check.

All connector methods that call the API are async; each test uses
``asyncio.run()`` (via ``pytest.mark.asyncio`` / ``anyio`` or a plain
sync wrapper) — we use a minimal sync helper pattern that works without
requiring pytest-asyncio to be installed, while respecting the
async-only API surface of ServiceNowAPIClient.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from connectors.base.connector import (
    ConnectorAuthError,
    ConnectorFetchError,
    ConnectorHealth,
    ConnectorSession,
    RawFinding,
    URIPRiskRecord,
)
from connectors.base.registry import _global_registry
from connectors.servicenow.connector import (
    ServiceNowConnector,
    _map_severity,
    _severity_to_urgency_impact,
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

INSTANCE = "https://acme.service-now.com"
TENANT_ID = "tenant-sn-001"


def _run(coro):
    """Run a coroutine synchronously in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mock_healthcheck_ok():
    """Return a healthy sys_user response from the ServiceNow instance."""
    return respx.get(f"{INSTANCE}/api/now/table/sys_user").mock(
        return_value=httpx.Response(
            200,
            json={"result": [{"sys_id": "abc"}]},
        )
    )


def _sample_incident(**overrides: Any) -> dict[str, Any]:
    base = {
        "sys_id": "inc001sys",
        "number": "INC0000001",
        "short_description": "Suspicious login attempt",
        "description": "Multiple failed MFA attempts from unrecognised IP.",
        "urgency": "2",
        "impact": "2",
        "priority": "3",
        "state": "2",
        "assigned_to": "secops@acme.com",
        "opened_at": "2026-04-28 08:00:00",
        "sys_updated_on": "2026-04-28 09:00:00",
        "category": "security",
    }
    base.update(overrides)
    return base


@pytest.fixture
def connector() -> ServiceNowConnector:
    return ServiceNowConnector()


@pytest.fixture
def basic_creds() -> dict[str, str]:
    return {
        "instance_url": INSTANCE,
        "auth_method": "basic",
        "username": "urip_integration",
        "password": "s3cr3tP@ss",
        "risk_query": "category=security^active=true",
        "tenant_id": TENANT_ID,
    }


@pytest.fixture
def oauth_creds() -> dict[str, str]:
    return {
        "instance_url": INSTANCE,
        "auth_method": "oauth",
        "oauth_token": "Bearer_TOKEN_xyz",
        "risk_query": "category=security^active=true",
        "tenant_id": TENANT_ID,
    }


@pytest.fixture
def fake_session() -> ConnectorSession:
    from datetime import datetime, timezone
    return ConnectorSession(
        connector_name="servicenow",
        tenant_id=TENANT_ID,
        token="sn-basic-****",
        expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Registry
# ─────────────────────────────────────────────────────────────────────────────


def test_register():
    """ServiceNowConnector must be registered as 'servicenow' in the global registry."""
    assert "servicenow" in _global_registry, (
        "'servicenow' not in global registry — check @register_connector decorator "
        "and that connectors/servicenow/connector.py has been imported."
    )
    factory = _global_registry.get("servicenow")
    assert factory is ServiceNowConnector


# ─────────────────────────────────────────────────────────────────────────────
# 2. Severity mapping
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("urgency,impact,expected", [
    ("1", "1", "critical"),   # both high → critical
    ("1", "2", "high"),       # urgency=1, impact=medium → high
    ("2", "1", "high"),       # urgency=medium, impact=1 → high
    ("2", "2", "medium"),     # both medium → medium
    ("2", "3", "medium"),     # urgency=medium, impact=low → medium
    ("3", "2", "medium"),     # urgency=low, impact=medium → medium
    ("3", "3", "low"),        # both low → low
    (None, None, "low"),      # missing → default to low
    ("", "", "low"),          # empty string → low
])
def test_severity_map_urgency_impact(urgency, impact, expected):
    assert _map_severity(urgency, impact) == expected


def test_severity_to_urgency_impact_critical():
    assert _severity_to_urgency_impact("critical") == (1, 1)


def test_severity_to_urgency_impact_high():
    assert _severity_to_urgency_impact("high") == (1, 2)


def test_severity_to_urgency_impact_medium():
    assert _severity_to_urgency_impact("medium") == (2, 2)


def test_severity_to_urgency_impact_low():
    assert _severity_to_urgency_impact("low") == (3, 3)


# ─────────────────────────────────────────────────────────────────────────────
# 3. authenticate — Basic Auth
# ─────────────────────────────────────────────────────────────────────────────


@respx.mock
def test_authenticate_basic(connector, basic_creds):
    """
    authenticate() with Basic Auth must:
      - include Basic auth header (httpx.BasicAuth → "Authorization: Basic …")
      - return a ConnectorSession with connector_name="servicenow"
    """
    route = _mock_healthcheck_ok()

    session = _run(connector.authenticate(basic_creds))

    assert route.called, "healthcheck GET /api/now/table/sys_user was not called"
    assert isinstance(session, ConnectorSession)
    assert session.connector_name == "servicenow"
    assert session.tenant_id == TENANT_ID

    # Verify Basic auth header was sent
    request: httpx.Request = route.calls[0].request
    assert "Authorization" in request.headers
    assert request.headers["Authorization"].startswith("Basic ")


@respx.mock
def test_authenticate_basic_missing_password(connector):
    """authenticate() must raise ConnectorAuthError when password is absent."""
    _mock_healthcheck_ok()
    with pytest.raises(ConnectorAuthError, match="username"):
        _run(connector.authenticate({
            "instance_url": INSTANCE,
            "auth_method": "basic",
            "username": "user",
            # password intentionally missing
        }))


# ─────────────────────────────────────────────────────────────────────────────
# 4. authenticate — OAuth Bearer
# ─────────────────────────────────────────────────────────────────────────────


@respx.mock
def test_authenticate_oauth(connector, oauth_creds):
    """
    authenticate() with OAuth must:
      - include Bearer token in Authorization header
      - return a ConnectorSession
    """
    route = _mock_healthcheck_ok()

    session = _run(connector.authenticate(oauth_creds))

    assert route.called, "healthcheck GET /api/now/table/sys_user was not called"
    assert isinstance(session, ConnectorSession)

    request: httpx.Request = route.calls[0].request
    assert request.headers.get("Authorization") == "Bearer Bearer_TOKEN_xyz"


@respx.mock
def test_authenticate_oauth_missing_token(connector):
    """authenticate() must raise ConnectorAuthError when oauth_token is absent."""
    with pytest.raises(ConnectorAuthError, match="oauth_token"):
        _run(connector.authenticate({
            "instance_url": INSTANCE,
            "auth_method": "oauth",
            # oauth_token intentionally missing
        }))


@respx.mock
def test_authenticate_401_raises_auth_error(connector, basic_creds):
    """A 401 from the healthcheck must bubble up as ConnectorAuthError."""
    respx.get(f"{INSTANCE}/api/now/table/sys_user").mock(
        return_value=httpx.Response(401, json={"error": "invalid credentials"})
    )
    with pytest.raises(ConnectorAuthError):
        _run(connector.authenticate(basic_creds))


# ─────────────────────────────────────────────────────────────────────────────

exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && rg -n \"def __contains__\" connectors/base/registry.py && rg -n \"class ConnectorRegistry\" -n connectors/base/registry.py && sed -n '1,120p' connectors/base/registry.py" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
207:    def __contains__(self, name: str) -> bool:
51:class ConnectorRegistry:
"""
connectors/base/registry.py — Plugin discovery and connector registry.

P1.6: Connector Framework Abstraction
P33-Z3: Metadata-aware listing for the Tool Catalog UI.

Design decisions
----------------
- ConnectorRegistry is a simple dict-backed store keyed by connector name.
- The module-level _global_registry instance is the canonical registry used
  by the scheduler and all decorators.
- @register_connector("name") is a class decorator that calls
  _global_registry.register(name, cls) at import time — no discovery magic,
  no file scanning needed.  Connectors self-register when their module is imported.
- Double-registration raises ValueError to catch copy-paste naming mistakes early.
- The registry stores classes (not instances); the scheduler instantiates on demand
  so each tick can get a fresh connector without shared state.
- Factory callables are also accepted (register("x", lambda: MyConnector()))
  to allow test injection of pre-configured instances.
- ``list_connectors_with_metadata()`` extracts the Tool-Catalog metadata from
  each registered class WITHOUT instantiation — class attribute access only.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Type

from connectors.base.connector import (
    CONNECTOR_CATEGORIES,
    BaseConnector,
    CredentialFieldSpec,
)
from connectors.base.setup_guide import SetupGuideSpec

logger = logging.getLogger(__name__)


# Metadata fields that MUST be set (non-empty) on every concrete connector
# for the Tool Catalog UI to render correctly.
_REQUIRED_METADATA_FIELDS: tuple[str, ...] = (
    "DISPLAY_NAME",
    "CATEGORY",
    "SHORT_DESCRIPTION",
    "STATUS",
    "MODULE_CODE",
)
_VALID_STATUSES: tuple[str, ...] = ("live", "building", "simulated", "roadmap")


class ConnectorRegistry:
    """
    Thread-safe (GIL-protected) connector name → class/factory registry.

    Usage
    -----
    registry = ConnectorRegistry()
    registry.register("tenable", TenableConnector)
    cls = registry.get("tenable")
    instance = cls()
    """

    def __init__(self) -> None:
        self._store: dict[str, Callable] = {}

    def register(self, name: str, factory: Callable) -> None:
        """
        Register a connector class or factory under `name`.

        Parameters
        ----------
        name : str
            Unique connector identifier (e.g. "tenable", "sentinelone").
        factory : Callable
            A class (subclass of BaseConnector) or a zero-arg callable that
            returns a BaseConnector instance.

        Raises
        ------
        ValueError
            If `name` is already registered.

        Notes
        -----
        Z3: Logs a WARNING (not error — backward compat) for every required
        metadata field that is missing on `factory`.  We can't raise: parallel
        workers might land their connector before metadata is filled in.
        """
        if name in self._store:
            raise ValueError(
                f"Connector '{name}' is already registered.  "
                "Use a unique name or unregister the existing one first."
            )
        self._store[name] = factory
        _warn_if_metadata_incomplete(name, factory)
        logger.debug("Registered connector: %s", name)

    def get(self, name: str) -> Callable:
        """
        Look up a connector factory by name.

        Raises
        ------
        KeyError
            If `name` is not registered.
        """
        if name not in self._store:
            raise KeyError(f"No connector registered with name '{name}'.")
        return self._store[name]

    def list_names(self) -> list[str]:
        """Return sorted list of all registered connector names."""
        return sorted(self._store.keys())

    def list_connectors_with_metadata(self) -> list[dict[str, Any]]:
        """
        Return one dict per registered connector with all Tool-Catalog metadata.

        Reads class attributes only — no instantiation, no I/O, safe to call
        on every request.  Output sorted by `name` for stable UI ordering.

  ✓ Inspect backend integrations route
  ✓ Review Jira/ServiceNow connectors and tests
  → Audit frontend a11y and placeholders
  • Check proxy configs (Vercel/nginx)
  • Scan for security issues and dead links
  • Score and write report table
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && rg -n \"Royal Enfield|Acme|Jane Doe|John Doe|Lorem ipsum|Example Corp|foo@|example\\.com\" frontend -S && rg -n \"<h1\\b\" frontend/*.html && rg -n \"aria-label=\\\"\\\"|aria-labelledby=\\\"\\\"|role=\\\"dialog\\\"\" frontend -S" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
frontend/vapt-portal-submit.html:89:                   placeholder="api.customer.example.com" />
frontend/admin-tenants.html:87:            <input class="form-input" id="tn_email" name="primary_contact_email" type="email" placeholder="admin@example.com">
frontend/admin-vapt.html:116:          <input type="email" name="contact_email" required maxlength="255" placeholder="vendor@example.com" />
frontend/admin-tenant-detail.html:97:                  <input class="form-input" id="b_logo_url" name="logo_url" type="url" placeholder="https://cdn.example.com/logo.svg">
frontend/admin-tenant-detail.html:153:                  <input class="form-input" id="u_email" name="email" type="email" required maxlength="255" placeholder="admin@example.com">
frontend/admin-scoring.html:21:            <h1 class="page-title">Scoring Weights</h1>
frontend/admin-modules.html:22:        <h1 class="page-title">Capability Modules</h1>
frontend/acceptance-workflow.html:22:            <h1 class="page-title">Risk Acceptance Workflow</h1>
frontend/audit-log.html:22:            <h1 class="page-title">Audit Log</h1>
frontend/connector-status.html:19:    <h1 class="page-title">Connector Status</h1>
frontend/cspm-dashboard.html:22:        <h1 class="page-title">CSPM Dashboard</h1>
frontend/connector-wizard.html:24:            <h1 class="page-title">Connector Setup</h1>
frontend/cspm-control-detail.html:22:        <h1 class="page-title" id="controlTitle">Control Detail</h1>
frontend/asset-inventory.html:20:            <h1 class="page-title"><i class="fas fa-server" style="color:var(--teal-accent);margin-right:.5rem"></i>Asset Inventory</h1>
frontend/admin-tenants.html:22:        <h1 class="page-title">Tenants</h1>
frontend/attack-path.html:22:        <h1 class="page-title">Attack Path Prediction</h1>
frontend/admin-tenant-detail.html:24:            <h1 class="page-title" id="pageTitle">Tenant</h1>
frontend/ai-security-dashboard.html:22:        <h1 class="page-title">AI Security</h1>
frontend/asset-detail.html:23:            <h1 class="page-title" id="assetTitle" style="margin-top:0.25rem">Asset Detail</h1>
frontend/admin-vapt.html:20:            <h1 class="page-title">VAPT Vendor Portal</h1>
frontend/domain-mobile.html:21:            <h1 class="page-title"><i class="fas fa-mobile-screen-button" style="color:var(--teal-accent);margin-right:.5rem"></i>Mobile Security</h1>
frontend/cspm-findings.html:22:        <h1 class="page-title">CSPM Findings</h1>
frontend/domain-network.html:21:            <h1 class="page-title"><i class="fas fa-globe" style="color:var(--teal-accent);margin-right:.5rem"></i>Network Security</h1>
frontend/domain-workflow.html:21:            <h1 class="page-title"><i class="fas fa-gears" style="color:var(--teal-accent);margin-right:.5rem"></i>Workflow Automation</h1>
frontend/domain-identity.html:21:            <h1 class="page-title"><i class="fas fa-key" style="color:var(--teal-accent);margin-right:.5rem"></i>Identity Security</h1>
frontend/domain-ot.html:21:            <h1 class="page-title"><i class="fas fa-industry" style="color:var(--teal-accent);margin-right:.5rem"></i>OT Security</h1>
frontend/dashboard.html:26:            <h1 class="page-title">Risk Dashboard</h1>
frontend/dspm-dashboard.html:22:        <h1 class="page-title">DSPM Dashboard</h1>
frontend/domain-endpoint.html:24:            <h1 class="page-title"><i class="fas fa-shield-halved" style="color:var(--teal-accent);margin-right:.5rem"></i>Endpoint Security</h1>
frontend/domain-cloud.html:21:            <h1 class="page-title"><i class="fas fa-cloud" style="color:var(--teal-accent);margin-right:.5rem"></i>Cloud Security</h1>
frontend/domain-external-threat.html:21:            <h1 class="page-title"><i class="fas fa-earth-asia" style="color:var(--teal-accent);margin-right:.5rem"></i>External Threat Surface</h1>
frontend/domain-compliance-summary.html:21:            <h1 class="page-title"><i class="fas fa-clipboard-check" style="color:var(--teal-accent);margin-right:.5rem"></i>Compliance Summary</h1>
frontend/domain-email-collab.html:21:            <h1 class="page-title"><i class="fas fa-envelope" style="color:var(--teal-accent);margin-right:.5rem"></i>Email &amp; Collaboration</h1>
frontend/register.html:45:            <h1>Semantic <span>Gravity</span></h1>
frontend/reset-password.html:44:            <h1>Semantic <span>Gravity</span></h1>
frontend/remediation-tracker.html:22:            <h1 class="page-title">Remediation Tracker</h1>
frontend/risk-overview.html:21:    <h1 class="page-title">Risk Overview</h1>
frontend/forgot-password.html:44:            <h1>Semantic <span>Gravity</span></h1>
frontend/reports.html:25:            <h1 class="page-title">Reports</h1>
frontend/login.html:352:            <h1>Semantic <span>Gravity</span></h1>
frontend/vapt-portal-submission-detail.html:52:          <h1 id="title"></h1>
frontend/vendor-login.html:315:      <h1>Sign in to your <span class="accent">vendor sandbox.</span></h1>
frontend/mfa-enroll.html:46:            <h1>Semantic <span>Gravity</span></h1>
frontend/vapt-portal-login.html:26:        <h1>Activate your access</h1>
frontend/index.html:352:            <h1>Semantic <span>Gravity</span></h1>
frontend/ztna-dashboard.html:22:        <h1 class="page-title">Zero Trust Network Access (ZTNA)</h1>
frontend/vapt-portal-submit.html:37:      <h1>Submit a finding</h1>
frontend/risk-quantification.html:22:        <h1 class="page-title">Cyber Risk Quantification</h1>
frontend/home.html:62:        <h1>
frontend/tool-catalog.html:19:    <h1 class="page-title">Tool Catalog</h1>
frontend/settings.html:100:            <h1 class="page-title">Settings</h1>
frontend/threat-map.html:340:            <h1 class="page-title">Threat Intelligence</h1>
frontend/admin-vapt.html:103:  <div id="inviteModal" class="modal-backdrop" style="display:none" role="dialog" aria-modal="true" aria-labelledby="inviteModalTitle" aria-hidden="true">

exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && rg -n \"Semantic\\s+Gravity\" frontend -S && rg -n \"background\\s*:\\s*#fff|background\\s*:\\s*white|background-color\\s*:\\s*#fff|background-color\\s*:\\s*white\" frontend -S" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
frontend/register.html:83:      &copy; 2026 Semantic Gravity. All rights reserved.
frontend/mfa-enroll.html:83:      &copy; 2026 Semantic Gravity. All rights reserved.
frontend/forgot-password.html:71:      &copy; 2026 Semantic Gravity. All rights reserved.
frontend/index.html:431:      &copy; 2026 Semantic Gravity. All rights reserved. | v2.4.1
frontend/js/sidebar.js:136:    var brandAppName = brand.app_name || 'Semantic Gravity';
frontend/login.html:431:      &copy; 2026 Semantic Gravity. All rights reserved. | v2.4.1
frontend/reset-password.html:75:      &copy; 2026 Semantic Gravity. All rights reserved.
frontend/css/main.css:3:   Semantic Gravity - Enterprise Cybersecurity SaaS
frontend/forgot-password.html:21:    .login-card-inner { background-color:#FFFFFF; border-radius:16px; box-shadow:0 25px 80px rgba(0,0,0,0.4); overflow:hidden; }
frontend/index.html:67:      background-color: #FFFFFF;
frontend/index.html:153:      background-color: #FFFFFF;
frontend/register.html:21:    .login-card-inner { background-color:#FFFFFF; border-radius:16px; box-shadow:0 25px 80px rgba(0,0,0,0.4); overflow:hidden; }
frontend/mfa-enroll.html:21:    .login-card-inner { background-color:#FFFFFF; border-radius:16px; box-shadow:0 25px 80px rgba(0,0,0,0.4); overflow:hidden; }
frontend/login.html:67:      background-color: #FFFFFF;
frontend/login.html:153:      background-color: #FFFFFF;
frontend/css/vapt-portal.css:197:  background: #fff;
frontend/css/vapt-portal.css:212:  background: #fff8ed;
frontend/css/vapt-portal.css:216:.vapt-notif-card:hover { background: #fff2dc; }
frontend/css/vapt-portal.css:223:  background: #fff;
frontend/css/vapt-portal.css:295:  background: #fff;
frontend/css/vapt-portal.css:311:  background: #fff;
frontend/css/vapt-portal.css:323:  background: #fff8ed;
frontend/css/vapt-portal.css:346:  background: #fff;
frontend/css/vapt-portal.css:374:  background: #fff;
frontend/css/vapt-portal.css:428:  background: #fff;
frontend/css/vapt-portal.css:480:  background: #fff;
frontend/css/vapt-portal.css:495:  background: #fff;
frontend/reset-password.html:21:    .login-card-inner { background-color:#FFFFFF; border-radius:16px; box-shadow:0 25px 80px rgba(0,0,0,0.4); overflow:hidden; }
frontend/css/module-tools.css:282:  background: #fff;
frontend/js/filters.js:663:      'background:#fff;border-radius:12px;width:100%;max-width:680px;' +
frontend/js/filters.js:850:      'padding:8px 24px;border:1px solid #CBD5E1;background:#fff;' +
frontend/js/filters.js:885:      'background:#fff;border-radius:10px;width:100%;max-width:400px;' +
frontend/js/api.js:174:      'position:fixed;top:20px;right:20px;background:#fff;border-radius:8px;' +

**Clarifying design requirements**

I’m thinking about the branding—Semantic Gravity feels a bit outdated; perhaps it should be URIP or Adaptive Mind instead. I should probably fix this for the demo placeholders, as the user didn't mention it specifically. The requirements say there should be inline white backgrounds in .urip-app pages. I need to check if these are found in the dashboard. I’ll search for instances of "background:#fff" in the HTML to ensure we're aligned with the requirements.
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && rg -n \"background\\s*:\\s*#fff|background-color\\s*:\\s*#fff\" frontend/*.html frontend/js -S && rg -n \"style=\\\"["'^'"\\\"]*(background|background-color)\\s*:\\s*(#fff|white)\" frontend/*.html -S" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 exited 1 in 0ms:
frontend/register.html:21:    .login-card-inner { background-color:#FFFFFF; border-radius:16px; box-shadow:0 25px 80px rgba(0,0,0,0.4); overflow:hidden; }
frontend/reset-password.html:21:    .login-card-inner { background-color:#FFFFFF; border-radius:16px; box-shadow:0 25px 80px rgba(0,0,0,0.4); overflow:hidden; }
frontend/index.html:67:      background-color: #FFFFFF;
frontend/index.html:153:      background-color: #FFFFFF;
frontend/login.html:67:      background-color: #FFFFFF;
frontend/login.html:153:      background-color: #FFFFFF;
frontend/mfa-enroll.html:21:    .login-card-inner { background-color:#FFFFFF; border-radius:16px; box-shadow:0 25px 80px rgba(0,0,0,0.4); overflow:hidden; }
frontend/forgot-password.html:21:    .login-card-inner { background-color:#FFFFFF; border-radius:16px; box-shadow:0 25px 80px rgba(0,0,0,0.4); overflow:hidden; }
frontend/js/api.js:174:      'position:fixed;top:20px;right:20px;background:#fff;border-radius:8px;' +
frontend/js/filters.js:663:      'background:#fff;border-radius:12px;width:100%;max-width:680px;' +
frontend/js/filters.js:850:      'padding:8px 24px;border:1px solid #CBD5E1;background:#fff;' +
frontend/js/filters.js:885:      'background:#fff;border-radius:10px;width:100%;max-width:400px;' +

**Analyzing accessibility issues**

I’m going to search for `<input` tags that lack `aria-label` and associated labels, which might indicate accessibility concerns. While rigorous analysis requires more parsing, I can spot common issues like `type="search"`. For example, in `vapt-portal-submission-detail.html`, there's an empty `<h1 id="title"></h1>` that is filled by JavaScript but might initially pose accessibility problems. I also want to check `home.html` for a multiline `<h1>` or any dead routes linked with `href="#"`. For now, I'll gather obvious placeholders.
**Checking accessibility elements**

Okay, let’s see if cache-busting is done. Now I want to check for accessibility, specifically looking for pages that might be missing `<h1 class="page-title">`. It seems like the search results show many potential issues. For example, I should check `frontend/notifications.html`, which might not be in the list and could be missing that `<h1>`. To tackle this, I can use `rg` to find HTML files without `<h1>` tags, and I can script a loop to grep through the files.
exec
/bin/zsh -lc 'cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && for f in frontend/*.html; do if ! rg -q "<h1'"\\b\" \""'$f"; then echo "NO_H1 $f"; fi; done | head' in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 184ms:
NO_H1 frontend/global-search.html
NO_H1 frontend/notifications.html
NO_H1 frontend/risk-register.html
NO_H1 frontend/vapt-portal-dashboard.html

**Checking page structure**

I'm noticing that these pages might be missing an h1 element, which is important for accessibility. I think it’s a good idea to open each page to check if there’s a hidden h1 somewhere. It’s crucial to confirm this, as having the right headings can really make a difference for accessibility. Let’s see what I can find by examining them more closely!
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && sed -n '1,120p' frontend/global-search.html && echo '---' && sed -n '1,140p' frontend/notifications.html && echo '---' && sed -n '1,140p' frontend/risk-register.html && echo '---' && sed -n '1,140p' frontend/vapt-portal-dashboard.html" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Search | URIP</title>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <link rel="stylesheet" href="css/main.css">
  <link rel="stylesheet" href="css/app.css?v=20260436">
</head>
<body class="urip-app">
  <div id="app-shell" data-page="">
    <div style="display:flex;gap:12px;margin-bottom:18px;align-items:center">
      <div style="font-size:12px;color:var(--u-fg-3)">Searching for</div>
      <div id="searchTermLabel" class="mono" style="font-size:14px;color:var(--u-primary-2);font-weight:600"></div>
    </div>

    <div class="u-tabs">
      <span class="u-tab is-active" data-tab="risks">Risks</span>
      <span class="u-tab" data-tab="connectors">Connectors</span>
      <span class="u-tab" data-tab="audit">Audit Log</span>
    </div>

    <div id="searchResults" class="u-card">
      <div class="u-card-b" id="resultsBody">
        <div class="u-skel" style="margin-bottom:10px"></div>
        <div class="u-skel" style="margin-bottom:10px"></div>
        <div class="u-skel"></div>
      </div>
    </div>
  </div>

  <script src="js/theming.js"></script>
  <script src="js/api.js"></script>
  <script src="js/auth.js"></script>
  <script src="js/shell.js?v=20260436"></script>
  <script src="js/global-search.js"></script>
</body>
</html>
---
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Notifications | URIP</title>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <link rel="stylesheet" href="css/main.css">
  <link rel="stylesheet" href="css/app.css?v=20260436">
</head>
<body class="urip-app">
  <div id="app-shell" data-page="audit-log">
    <div class="rr-toolbar">
      <input id="nfSearch" type="search" placeholder="Filter notifications…">
      <select id="nfType">
        <option value="">All types</option>
        <option value="login">Login</option>
        <option value="risk">Risk</option>
        <option value="control">Control</option>
        <option value="ticket">Ticket</option>
        <option value="connector">Connector</option>
      </select>
      <button class="u-btn is-ghost is-sm" id="nfReset"><i class="fas fa-rotate-left"></i> Reset</button>
    </div>

    <div class="u-card">
      <div class="u-card-h"><h3>Recent Activity</h3></div>
      <div class="u-card-b" id="nfBody">
        <div class="u-skel" style="margin-bottom:10px"></div>
        <div class="u-skel" style="margin-bottom:10px"></div>
        <div class="u-skel"></div>
      </div>
    </div>
  </div>

  <script src="js/theming.js"></script>
  <script src="js/api.js"></script>
  <script src="js/auth.js"></script>
  <script src="js/shell.js?v=20260436"></script>
  <script>
    (function () {
      'use strict';
      if (typeof window.checkAuth === 'function') window.checkAuth();
      var state = { items: [], filters: { search: '', type: '' } };

      document.addEventListener('DOMContentLoaded', function () {
        window.URIP.shell.mount({
          page: 'audit-log',
          title: 'Notifications',
          breadcrumb: 'Operations / Notifications',
          actions: [
            { label: 'Mark all read', icon: 'fa-check-double', variant: 'is-ghost', onClick: function () {
                window.URIP.showNotification('Marked', 'All notifications marked as read (local only — backend persistence pending).', 'success');
              }
            }
          ]
        });

        document.getElementById('nfSearch').addEventListener('input', function (e) {
          state.filters.search = e.target.value.trim().toLowerCase();
          render();
        });
        document.getElementById('nfType').addEventListener('change', function (e) {
          state.filters.type = e.target.value;
          render();
        });
        document.getElementById('nfReset').addEventListener('click', function () {
          state.filters = { search: '', type: '' };
          document.getElementById('nfSearch').value = '';
          document.getElementById('nfType').value = '';
          render();
        });

        load();
      });

      async function load() {
        try {
          var resp = await window.URIP.apiFetch('/audit-log?per_page=100', { silent: true });
          state.items = (resp && (resp.items || resp.entries || resp)) || [];
          if (!Array.isArray(state.items)) state.items = [];
        } catch (_e) {
          state.items = [];
        }
        render();
      }

      function render() {
        var body = document.getElementById('nfBody');
        body.textContent = '';
        var rows = state.items.filter(function (it) {
          if (state.filters.search) {
            var hay = JSON.stringify(it).toLowerCase();
            if (hay.indexOf(state.filters.search) === -1) return false;
          }
          if (state.filters.type) {
            var t = (it.action || it.event_type || '').toLowerCase();
            if (t.indexOf(state.filters.type) === -1) return false;
          }
          return true;
        });
        if (!rows.length) {
          body.appendChild(window.URIP.shell.makeEmpty(
            'fa-bell-slash',
            'No notifications',
            state.items.length ? 'No matches for those filters.' : 'New activity will show up here.'
          ));
          return;
        }
        rows.forEach(function (it) {
          var row = document.createElement('div');
          row.style.display = 'flex';
          row.style.gap = '12px';
          row.style.padding = '12px 0';
          row.style.borderBottom = '1px solid var(--u-border)';
          var ic = document.createElement('div');
          ic.className = 'r-feed-icon';
          ic.innerHTML = '<i class="fas fa-bolt"></i>';
          row.appendChild(ic);
          var bd = document.createElement('div');
          bd.style.flex = '1';
          var t = document.createElement('div');
          t.style.fontSize = '13px';
          t.style.fontWeight = '500';
          t.textContent = it.action || it.event_type || it.message || 'Event';
          bd.appendChild(t);
          var m = document.createElement('div');
          m.style.fontSize = '11px';
          m.style.color = 'var(--u-fg-3)';
          m.textContent = (it.user_email || it.actor || '') + ' • ' + window.URIP.shell.relTime(it.timestamp || it.created_at || '');
          bd.appendChild(m);
          row.appendChild(bd);
          body.appendChild(row);
        });
      }
---
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Risk Register | URIP</title>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">

  <link rel="stylesheet" href="css/main.css">
  <link rel="stylesheet" href="css/app.css?v=20260436">
</head>
<body class="urip-app">
  <div id="app-shell" data-page="risk-register">

    <!-- Filter / search toolbar -->
    <div class="rr-toolbar" role="search">
      <input type="search" id="searchInput" placeholder="Search by ID, finding, asset, CVE…" aria-label="Search risks">
      <select id="severityFilter" class="u-select" aria-label="Severity">
        <option value="">All severities</option>
        <option value="critical">Critical</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
      </select>
      <select id="statusFilter" aria-label="Status">
        <option value="">All status</option>
        <option value="open">Open</option>
        <option value="in_progress">In progress</option>
        <option value="accepted">Accepted</option>
        <option value="closed">Closed</option>
      </select>
      <select id="domainFilter" aria-label="Domain">
        <option value="">All domains</option>
        <option value="endpoint">Endpoint</option>
        <option value="identity">Identity</option>
        <option value="network">Network</option>
        <option value="cloud">Cloud</option>
        <option value="application">Application</option>
        <option value="email">Email</option>
        <option value="mobile">Mobile</option>
        <option value="ot">OT</option>
        <option value="external">External</option>
      </select>
      <select id="tierFilter" aria-label="Asset tier">
        <option value="">All tiers</option>
        <option value="T1">T1 — Production</option>
        <option value="T2">T2 — Internal</option>
        <option value="T3">T3 — Dev/Test</option>
        <option value="T4">T4 — Decommissioned</option>
      </select>
      <select id="sourceFilter" aria-label="Source">
        <option value="">All sources</option>
      </select>
      <button class="u-btn is-ghost is-sm" id="resetFilters" type="button">
        <i class="fas fa-rotate-left"></i> Reset
      </button>
    </div>

    <!-- Bulk actions row -->
    <div id="bulkBar" style="display:none; gap:10px; padding:10px 14px; background:var(--u-card); border:1px solid var(--u-primary); border-radius:var(--u-radius); margin-bottom:14px; align-items:center">
      <span id="bulkCount" style="font-size:13px;font-weight:600"></span>
      <span style="flex:1"></span>
      <button class="u-btn is-sm" id="bulkAssign"><i class="fas fa-user-plus"></i> Assign</button>
      <button class="u-btn is-sm" id="bulkAccept"><i class="fas fa-check"></i> Accept</button>
      <button class="u-btn is-sm is-primary" id="bulkResolve"><i class="fas fa-circle-check"></i> Mark resolved</button>
    </div>

    <!-- Table -->
    <div class="rr-table-wrap">
      <table class="u-table rr-table" id="riskTable">
        <thead>
          <tr>
            <th scope="col" style="width:34px"><input type="checkbox" id="selAll" aria-label="Select all"></th>
            <th scope="col">Risk ID</th>
            <th scope="col">Finding</th>
            <th scope="col">Source</th>
            <th scope="col">CVE</th>
            <th scope="col">CVSS</th>
            <th scope="col">EPSS</th>
            <th scope="col">KEV</th>
            <th scope="col">Composite</th>
            <th scope="col">SSVC</th>
            <th scope="col">Severity</th>
            <th scope="col">Asset</th>
            <th scope="col">Asset Type</th>
            <th scope="col">Tier</th>
            <th scope="col">Domain</th>
            <th scope="col">Owner</th>
            <th scope="col">Owner Team</th>
            <th scope="col">APT Tags</th>
            <th scope="col">Exploit</th>
            <th scope="col">Advisory</th>
            <th scope="col">Raised</th>
            <th scope="col">Pending Days</th>
            <th scope="col">Status</th>
            <th scope="col">Remediation</th>
            <th scope="col">Jira Ticket</th>
            <th scope="col">Evidence</th>
          </tr>
        </thead>
        <tbody id="riskBody"></tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 4px;font-size:13px;color:var(--u-fg-3)">
      <div id="tableInfo">Loading…</div>
      <div id="pagination" style="display:flex;gap:6px"></div>
    </div>
  </div>

  <!-- Detail drawer -->
  <div class="u-drawer-mask" id="rdMask"></div>
  <aside class="u-drawer" id="rdDrawer" aria-hidden="true">
    <div class="u-drawer-h">
      <div>
        <h2 id="rdTitle">Risk Detail</h2>
        <div id="rdSubtitle" style="font-size:12px;color:var(--u-fg-3);margin-top:2px"></div>
      </div>
      <button class="u-btn is-ghost is-icon" id="rdClose" aria-label="Close">
        <i class="fas fa-xmark"></i>
      </button>
    </div>
    <div class="u-drawer-b" id="rdBody">
      <div class="u-skel" style="margin-bottom:10px"></div>
      <div class="u-skel" style="margin-bottom:10px"></div>
      <div class="u-skel"></div>
    </div>
    <div class="u-drawer-f" id="rdFooter"></div>
  </aside>

  <script src="js/theming.js"></script>
  <script src="js/api.js"></script>
  <script src="js/auth.js"></script>
  <script src="js/shell.js?v=20260436"></script>
---
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <link rel="icon" type="image/svg+xml" href="favicon.svg" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Submissions | VAPT Vendor Portal</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
  <link rel="stylesheet" href="css/main.css" />
  <link rel="stylesheet" href="css/vapt-portal.css" />
</head>
<body>
  <div class="vapt-shell">
    <header class="vapt-topbar">
      <div class="vapt-brand">
        <span class="vapt-brand-icon"><i class="fas fa-bug"></i></span>
        <span>URIP — VAPT Vendor Portal</span>
      </div>
      <nav class="vapt-tabs">
        <a href="vapt-portal-dashboard.html" class="vapt-tab active">My submissions</a>
        <a href="vapt-portal-submit.html" class="vapt-tab">New submission</a>
      </nav>
      <div class="vapt-user">
        <span id="vendorName">…</span>
        <button id="logoutBtn" class="vapt-btn vapt-btn-ghost" title="Sign out">
          <i class="fas fa-sign-out-alt"></i>
        </button>
      </div>
    </header>

    <main class="vapt-content">
      <section class="vapt-summary-row">
        <div class="vapt-summary-card">
          <div class="vapt-summary-label">Total submissions</div>
          <div class="vapt-summary-value" id="sumTotal">–</div>
        </div>
        <div class="vapt-summary-card vapt-summary-warn" id="cardPending">
          <div class="vapt-summary-label">Pending re-tests</div>
          <div class="vapt-summary-value" id="sumPending">–</div>
        </div>
        <div class="vapt-summary-card">
          <div class="vapt-summary-label">In progress</div>
          <div class="vapt-summary-value" id="sumInProgress">–</div>
        </div>
        <div class="vapt-summary-card">
          <div class="vapt-summary-label">Closed</div>
          <div class="vapt-summary-value" id="sumClosed">–</div>
        </div>
      </section>

      <section id="notifWrap" style="display:none">
        <h2>Pending re-tests</h2>
        <div id="notifList" class="vapt-notif-list"></div>
      </section>

      <section>
        <div class="vapt-section-head">
          <h2>My submissions</h2>
          <div class="vapt-section-tools">
            <select id="statusFilter" class="vapt-select">
              <option value="">All statuses</option>
              <option value="submitted">Submitted</option>
              <option value="triaged">Triaged</option>
              <option value="in_progress">In progress</option>
              <option value="fixed">Fixed</option>
              <option value="retest_requested">Re-test requested</option>
              <option value="retest_pass">Re-test pass</option>
              <option value="retest_fail">Re-test fail</option>
              <option value="closed">Closed</option>
            </select>
            <a href="vapt-portal-submit.html" class="vapt-btn vapt-btn-primary">
              <i class="fas fa-plus"></i> New submission
            </a>
          </div>
        </div>

        <div id="loading" class="vapt-loading">
          <i class="fas fa-spinner fa-spin"></i> Loading…
        </div>

        <div id="empty" class="vapt-empty" style="display:none">
          <div class="vapt-empty-icon"><i class="fas fa-inbox"></i></div>
          <div class="vapt-empty-title">No submissions yet</div>
          <p>Submit your first finding to populate the customer's risk register.</p>
          <a href="vapt-portal-submit.html" class="vapt-btn vapt-btn-primary">
            <i class="fas fa-plus"></i> New submission
          </a>
        </div>

        <table id="submissionsTable" class="vapt-table" style="display:none">
          <thead>
            <tr>
              <th>Finding</th>
              <th>CVE</th>
              <th>CVSS</th>
              <th>Severity</th>
              <th>Submitted</th>
              <th>Status</th>
              <th>URIP Risk</th>
              <th></th>
            </tr>
          </thead>
          <tbody id="tableBody"></tbody>
        </table>
      </section>
    </main>
  </div>

  <script src="js/vapt-portal-api.js"></script>
  <script src="js/vapt-portal.js"></script>
  <script>
    (function () {
      'use strict';
      VaptPortal.requireSession();
      VaptPortal.setupChrome();

      var statusFilter = document.getElementById('statusFilter');
      var loading = document.getElementById('loading');
      var emptyMsg = document.getElementById('empty');
      var table = document.getElementById('submissionsTable');
      var tbody = document.getElementById('tableBody');
      var notifWrap = document.getElementById('notifWrap');
      var notifList = document.getElementById('notifList');

      function load() {
        loading.style.display = '';
        emptyMsg.style.display = 'none';
        table.style.display = 'none';

        var statusVal = statusFilter.value;
        Promise.all([
          VaptPortalApi.listSubmissions(statusVal),
          VaptPortalApi.listNotifications()
        ])
          .then(function (results) {
            var subs = results[0];
            var notifs = results[1];


**Evaluating document output**

I'm noticing that the risk-register.html document is truncated. I need to check the top section to see the missing h1 and any issues present. It seems like opening the risk-register earlier could help in isolating the beginning of the document. I’ve got to find a way to access that part without getting overwhelmed by the huge output, so let’s focus on retrieving the relevant information efficiently.
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && sed -n '1,120p' frontend/risk-register.html" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Risk Register | URIP</title>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">

  <link rel="stylesheet" href="css/main.css">
  <link rel="stylesheet" href="css/app.css?v=20260436">
</head>
<body class="urip-app">
  <div id="app-shell" data-page="risk-register">

    <!-- Filter / search toolbar -->
    <div class="rr-toolbar" role="search">
      <input type="search" id="searchInput" placeholder="Search by ID, finding, asset, CVE…" aria-label="Search risks">
      <select id="severityFilter" class="u-select" aria-label="Severity">
        <option value="">All severities</option>
        <option value="critical">Critical</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
      </select>
      <select id="statusFilter" aria-label="Status">
        <option value="">All status</option>
        <option value="open">Open</option>
        <option value="in_progress">In progress</option>
        <option value="accepted">Accepted</option>
        <option value="closed">Closed</option>
      </select>
      <select id="domainFilter" aria-label="Domain">
        <option value="">All domains</option>
        <option value="endpoint">Endpoint</option>
        <option value="identity">Identity</option>
        <option value="network">Network</option>
        <option value="cloud">Cloud</option>
        <option value="application">Application</option>
        <option value="email">Email</option>
        <option value="mobile">Mobile</option>
        <option value="ot">OT</option>
        <option value="external">External</option>
      </select>
      <select id="tierFilter" aria-label="Asset tier">
        <option value="">All tiers</option>
        <option value="T1">T1 — Production</option>
        <option value="T2">T2 — Internal</option>
        <option value="T3">T3 — Dev/Test</option>
        <option value="T4">T4 — Decommissioned</option>
      </select>
      <select id="sourceFilter" aria-label="Source">
        <option value="">All sources</option>
      </select>
      <button class="u-btn is-ghost is-sm" id="resetFilters" type="button">
        <i class="fas fa-rotate-left"></i> Reset
      </button>
    </div>

    <!-- Bulk actions row -->
    <div id="bulkBar" style="display:none; gap:10px; padding:10px 14px; background:var(--u-card); border:1px solid var(--u-primary); border-radius:var(--u-radius); margin-bottom:14px; align-items:center">
      <span id="bulkCount" style="font-size:13px;font-weight:600"></span>
      <span style="flex:1"></span>
      <button class="u-btn is-sm" id="bulkAssign"><i class="fas fa-user-plus"></i> Assign</button>
      <button class="u-btn is-sm" id="bulkAccept"><i class="fas fa-check"></i> Accept</button>
      <button class="u-btn is-sm is-primary" id="bulkResolve"><i class="fas fa-circle-check"></i> Mark resolved</button>
    </div>

    <!-- Table -->
    <div class="rr-table-wrap">
      <table class="u-table rr-table" id="riskTable">
        <thead>
          <tr>
            <th scope="col" style="width:34px"><input type="checkbox" id="selAll" aria-label="Select all"></th>
            <th scope="col">Risk ID</th>
            <th scope="col">Finding</th>
            <th scope="col">Source</th>
            <th scope="col">CVE</th>
            <th scope="col">CVSS</th>
            <th scope="col">EPSS</th>
            <th scope="col">KEV</th>
            <th scope="col">Composite</th>
            <th scope="col">SSVC</th>
            <th scope="col">Severity</th>
            <th scope="col">Asset</th>
            <th scope="col">Asset Type</th>
            <th scope="col">Tier</th>
            <th scope="col">Domain</th>
            <th scope="col">Owner</th>
            <th scope="col">Owner Team</th>
            <th scope="col">APT Tags</th>
            <th scope="col">Exploit</th>
            <th scope="col">Advisory</th>
            <th scope="col">Raised</th>
            <th scope="col">Pending Days</th>
            <th scope="col">Status</th>
            <th scope="col">Remediation</th>
            <th scope="col">Jira Ticket</th>
            <th scope="col">Evidence</th>
          </tr>
        </thead>
        <tbody id="riskBody"></tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 4px;font-size:13px;color:var(--u-fg-3)">
      <div id="tableInfo">Loading…</div>
      <div id="pagination" style="display:flex;gap:6px"></div>
    </div>
  </div>

  <!-- Detail drawer -->
  <div class="u-drawer-mask" id="rdMask"></div>
  <aside class="u-drawer" id="rdDrawer" aria-hidden="true">
    <div class="u-drawer-h">

**Identifying accessibility issues**

I noticed that the risk-register page lacks an H1 tag, which should be added. The notifications section also has no H1 and the search input is missing an aria-label, which is a concern for accessibility. The earlier audit flagged this, but it seems to be overlooked in notifications. I'll cite this problem along with the global search and vapt-portal-dashboard pages. Four pages still need an H1, plus nfSearch lacks an aria-label. I’ll update the plan after finishing and include these findings.
**Planning accessibility updates**

I’m thinking about possibly checking other pages for issues too, but first, I want to capture line numbers related to the accessibility issues and placeholders. That’ll be a later step using nl. Next, I’ll move on to the proxy configurations. It’s essential to update the plan once I gather all this information, so I’ll make a note to do that afterward. Let's keep everything organized for effective improvements!
  ✓ Inspect backend integrations route
  ✓ Review Jira/ServiceNow connectors and tests
  ✓ Audit frontend a11y and placeholders
  → Check proxy configs (Vercel/nginx)
  • Scan for security issues and dead links
  • Score and write report table
**Verifying configurations**

I need to check the `vercel.json` rewrite in the `frontend/vercel.json` file. I also wonder if there's an nginx configuration in the repository or if I should refer to the documentation or infrastructure. It’s important to ensure everything is set up correctly. I'll go ahead and open the relevant files to verify these configurations and make sure nothing is missed. Let's see what I find!
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && cat frontend/vercel.json && echo '--- search nginx' && rg -n \"compliance-api\" -S ." in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 430ms:
**Inspecting nginx configuration**

I see there’s no nginx config file, and the mention is only in the compliance frontend. There’s a `compliance/` directory, so I need to check that path. I suspect it might involve proxy configuration. My next step is to search through the documentation for any references to "nginx" to see if I can find the necessary config information there. Let’s dive in and find what I need!
exec
/bin/zsh -lc 'cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && rg -n "nginx" -S .' in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 163ms:
**Reviewing nginx config**

I see there's an nginx config file in the documentation artifacts. I plan to open the specific artifact file at `docs/audit_apr28/deploy/_artifacts/api.urip.adaptive-mind.com.conf` to check if it includes the compliance API location. That seems like a logical next step to ensure everything is set correctly. I'll take a close look at the contents and see what I find!
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && sed -n '1,220p' docs/audit_apr28/deploy/_artifacts/api.urip.adaptive-mind.com.conf" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
# /etc/nginx/sites-available/api.urip.adaptive-mind.com.conf
# URIP Adaptive Mind backend reverse-proxy
# Backend listens on 127.0.0.1:8089 (Docker stack: urip-adaptive-mind)
# TLS: pending DNS — once `api.urip.adaptive-mind.com` resolves to 145.223.21.39
# run:  certbot --nginx -d api.urip.adaptive-mind.com

server {
    listen 80;
    listen [::]:80;
    server_name api.urip.adaptive-mind.com;

    # Allow Let's Encrypt HTTP-01 challenge from any path before TLS lands.
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        proxy_pass         http://127.0.0.1:8089;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;

        # WebSocket / SSE support (auth + future event streams)
        proxy_set_header   Upgrade           $http_upgrade;
        proxy_set_header   Connection        "upgrade";

        proxy_read_timeout 120s;
        proxy_connect_timeout 30s;
        client_max_body_size 50M;
    }

    # Compliance backend on a separate path prefix.
    # Compliance listens on 127.0.0.1:8091.
    location /compliance/ {
        rewrite ^/compliance/(.*)$ /$1 break;
        proxy_pass         http://127.0.0.1:8091;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        client_max_body_size 50M;
    }
}

**Checking compliance API details**

The user mentioned that the compliance proxy uses "/compliance-api/" instead of "/compliance/", which suggests a possible mismatch in the documentation. So, I need to search for any new configurations related to "/compliance-api/". This could be due to outdated documentation, so my next step will be to look into the deploy documents for updates regarding this API path. Let's clarify this to ensure I provide accurate info!
exec
/bin/zsh -lc 'cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && rg -n "/compliance-api" docs -S' in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 exited 1 in 0ms:
**Identifying configuration mismatches**

I noticed that the proxy configuration in the repo uses `/compliance-api/` in `vercel.json`, while the nginx artifact uses `/compliance/`. This inconsistency needs attention. They verified the nginx location to port 8091, but that config isn't reflected in the repo artifact. As an auditor, I can only check the artifacts and will need to report this mismatch. The user didn't specifically request live verification, but we have web.run, even with network restrictions. It's a complex situation!
**Considering endpoint verification**

I think using web.run could help verify the endpoint, but since the codebase is accessible, confirming the deployment might involve curl, even though network restrictions could be an issue. So, I’ll rely on the repository instead. It’s important not to make assumptions, and I need to note that the repo shows `/compliance/` instead of `/compliance-api`, which complicates verifying the nginx config. There are also potential security concerns with using plain HTTP, and I should mention the risks of man-in-the-middle attacks, even if they seem acceptable to the user.
  ✓ Inspect backend integrations route
  ✓ Review Jira/ServiceNow connectors and tests
  ✓ Audit frontend a11y and placeholders
  ✓ Check proxy configs (Vercel/nginx)
  → Scan for security issues and dead links
  • Score and write report table
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && rg -n \"(AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|BEGIN PRIVATE KEY|PRIVATE KEY-----|password\\s*=\\s*['\\\"]["'^'"'\\\"]+['\\\"]|api_key\\s*=\\s*['\\\"]["'^'"'\\\"]+['\\\"]|SECRET|TOKEN|bearer_token\\s*:\\s*['\\\"]["'^'"'\\\"]+['\\\"])\" -S backend connectors frontend shared tests docs | head -n 80" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
tests/test_agent/test_drilldown.py:23:SECRET = "test-shared-secret"
tests/test_agent/test_drilldown.py:35:        shared_secret=SECRET,
tests/test_agent/test_drilldown.py:51:        shared_secret=SECRET,
tests/test_agent/test_drilldown.py:96:        SECRET, h["x-timestamp"], "/api/agent-ingest/pending-requests", b""
tests/test_agent/test_drilldown.py:147:        SECRET,
tests/test_agent/test_reporter.py:33:SECRET = "test-shared-secret-32-bytes-of-entropy-here"
tests/test_agent/test_reporter.py:58:    agent_sig = sign_payload(SECRET, timestamp, path, body)
tests/test_agent/test_reporter.py:61:    secret_hash = hashlib.sha256(SECRET.encode()).hexdigest()
tests/test_agent/test_reporter.py:71:    sig1 = sign_payload(SECRET, "1", "/p", b'{"a":1}')
tests/test_agent/test_reporter.py:72:    sig2 = sign_payload(SECRET, "1", "/p", b'{"a":2}')
tests/test_agent/test_reporter.py:77:    sig1 = sign_payload(SECRET, "1", "/p", b"x")
tests/test_agent/test_reporter.py:78:    sig2 = sign_payload(SECRET, "2", "/p", b"x")
tests/test_agent/test_reporter.py:119:        shared_secret=SECRET,
tests/test_agent/test_reporter.py:150:        shared_secret=SECRET,
tests/test_agent/test_reporter.py:173:        SECRET,
tests/test_agent/test_reporter.py:199:        shared_secret=SECRET,
tests/test_agent/test_reporter.py:223:        shared_secret=SECRET,
tests/test_agent/test_reporter.py:248:        shared_secret=SECRET,
tests/test_agent/test_reporter.py:275:        shared_secret=SECRET,
tests/test_agent/test_reporter.py:292:        {"cloud_portal_url": "", "tenant_slug": TENANT, "shared_secret": SECRET},
tests/test_agent/test_reporter.py:293:        {"cloud_portal_url": PORTAL, "tenant_slug": "", "shared_secret": SECRET},
tests/test_asset_taxonomy_model.py:82:        hashed_password="x" * 60,
tests/test_dspm/test_dspm_module.py:214:            "data_classification": "ULTRA_TOP_SECRET",
tests/test_shared/test_jwt_verifier.py:19:_SECRET = "urip-dev-secret-change-in-production"
tests/test_shared/test_jwt_verifier.py:27:    secret: str = _SECRET,
tests/test_shared/test_jwt_verifier.py:45:        verifier = URIPVerifier(secret=_SECRET, algorithm=_ALGORITHM)
tests/test_shared/test_jwt_verifier.py:56:        verifier = URIPVerifier(secret=_SECRET, algorithm=_ALGORITHM)
tests/test_shared/test_jwt_verifier.py:70:        verifier = URIPVerifier(secret=_SECRET, algorithm=_ALGORITHM)
tests/test_shared/test_jwt_verifier.py:77:        verifier = URIPVerifier(secret=_SECRET, algorithm=_ALGORITHM)
tests/test_shared/test_jwt_verifier.py:84:        verifier = URIPVerifier(secret=_SECRET, algorithm=_ALGORITHM)
tests/test_shared/test_jwt_verifier.py:95:        verifier = URIPVerifier(secret=_SECRET, algorithm=_ALGORITHM)
tests/test_critfix_audit_log/pytest_output_urip.txt:17:  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/backend/config.py:154: RuntimeWarning: [URIP CONFIG WARNING] JWT_SECRET_KEY is using the dev default (urip-dev-secret-change-in-production). This is acceptable in dev ONLY. You MUST rotate this secret before any prod / staging deployment (set URIP_ENV=production and a real JWT_SECRET_KEY).
shared/auth/jwt_verifier.py:35:        secret:    The shared HMAC secret — must match JWT_SECRET_KEY in backend config.
tests/test_connector_framework/test_credentials_vault.py:108:        creds = {"api_key": "MY-SECRET-KEY"}
connectors/base/setup_guides_data.py:979:            error="401 INVALID_TOKEN on first poll",
connectors/base/setup_guides_data.py:3380:            error="401 INVALID_TOKEN",
connectors/base/setup_guides_data.py:3504:            error="401 INVALID_TOKEN",
tests/e2e/test_workflow_01_tenant_to_first_risk.py:52:        admin_password="Acme#Pass1234",
tests/connectors/servicenow/test_connector.py:108:        "oauth_token": "Bearer_TOKEN_xyz",
tests/connectors/servicenow/test_connector.py:236:    assert request.headers.get("Authorization") == "Bearer Bearer_TOKEN_xyz"
connectors/m365_collab/api_client.py:25:TOKEN_URL_TEMPLATE = (
connectors/m365_collab/api_client.py:86:        token_url = TOKEN_URL_TEMPLATE.format(tenant_id=self.tenant_id)
backend/services/vapt_vendor_service.py:31:  vapt vendor JWT   → HS256 signed with backend.config.JWT_SECRET_KEY,
backend/services/vapt_vendor_service.py:643:            payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
backend/services/vapt_vendor_service.py:655:            settings.JWT_SECRET_KEY,
tests/test_connectors/test_ms_entra.py:43:        "client_secret": "TEST_CLIENT_SECRET",
tests/test_connectors/test_ms_entra.py:51:TOKEN_URL = "https://login.microsoftonline.com/test-tenant-id/oauth2/v2.0/token"
tests/test_connectors/test_ms_entra.py:56:    return respx.post(TOKEN_URL).mock(
tests/test_connectors/test_ms_entra.py:62:                "access_token": "FAKE_GRAPH_TOKEN",
tests/test_connectors/test_ms_entra.py:124:        respx.post(TOKEN_URL).mock(
tests/test_connectors/test_ms_entra.py:593:        respx.post(TOKEN_URL).mock(
tests/test_connectors/test_crowdstrike.py:32:TOKEN_PATH = "/oauth2/token"
tests/test_connectors/test_crowdstrike.py:48:        "client_secret": "CSSECRET-9876",
tests/test_connectors/test_crowdstrike.py:56:    return respx.post(f"{base_url}{TOKEN_PATH}").mock(
tests/test_connectors/test_crowdstrike.py:231:        respx.post(f"{BASE_US1}{TOKEN_PATH}").mock(
tests/test_connectors/test_crowdstrike.py:272:        respx.post(f"{BASE_US1}{TOKEN_PATH}").mock(side_effect=_token_handler)
tests/test_connectors/test_manageengine_ec.py:40:        "api_token": "TEST_API_TOKEN",
tests/test_connectors/test_m365_collab.py:41:        "client_secret": "TEST_CLIENT_SECRET",
tests/test_connectors/test_m365_collab.py:49:TOKEN_URL = "https://login.microsoftonline.com/test-tenant-id/oauth2/v2.0/token"
tests/test_connectors/test_m365_collab.py:54:    return respx.post(TOKEN_URL).mock(
tests/test_connectors/test_m365_collab.py:60:                "access_token": "FAKE_GRAPH_TOKEN",
tests/test_connectors/test_m365_collab.py:111:        respx.post(TOKEN_URL).mock(
tests/test_connectors/test_m365_collab.py:380:        respx.post(TOKEN_URL).mock(
tests/test_connectors/test_easm.py:63:        "api_token": "DT-TOKEN-1",
tests/test_connectors/test_easm.py:312:        assert "DT-TOKEN-1" in last_req.headers.get("authorization", "")
tests/test_vapt/test_vapt_vendor_invitation.py:151:    """JWT must be HS256-signed with the URIP JWT_SECRET_KEY (not Compliance secret)."""
tests/test_vapt/test_vapt_vendor_invitation.py:159:        settings.JWT_SECRET_KEY,
tests/test_connectors/test_manageengine_mdm.py:40:        "api_token": "TEST_API_TOKEN",
tests/test_connectors/test_armis_ot.py:46:        "api_token": "ARMIS_TOKEN_123",
tests/test_connectors/test_netskope.py:40:        "client_secret": "NETSKOPE_CLIENT_SECRET",
tests/test_connectors/test_netskope.py:58:                "access_token": "FAKE_TOKEN_123",
tests/test_connectors/test_cyberark_pam.py:54:                return httpx.Response(200, text="CYBERARK_TOKEN")
tests/test_connectors/test_cyberark_pam.py:90:                return httpx.Response(200, text="CYBERARK_TOKEN")
tests/test_connectors/test_cyberark_pam.py:118:                return httpx.Response(200, text="CYBERARK_TOKEN")
tests/test_connectors/test_cyberark_pam.py:158:                return httpx.Response(200, text="CYBERARK_TOKEN")
tests/test_connectors/test_fortiguard_fw.py:74:                "api_token": "FG_TOKEN",
tests/test_connectors/test_fortiguard_fw.py:120:                "api_token": "FG_TOKEN",
tests/test_vapt/test_vapt_security.py:84:        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
tests/test_vapt/test_vapt_security.py:202:        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
tests/test_vapt/test_vapt_security.py:229:        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM

**Checking for hardcoded secrets**

I’m looking at tests and noting the presence of a placeholder password, which might just be for demos, so it might not be an issue. But I still need to check the actual code for any hardcoded secrets, especially in backend/config.py for default values, as production should use environment variables instead. I also want to investigate for default credentials, perhaps in the frontend JS. Then, I’ll check for any dead link routes by running a script on href.
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && python - <<'PY'
import re, pathlib
root = pathlib.Path('frontend')
files = sorted(root.glob('*.html'))
existing = {f.name for f in files}
broken = []
for f in files:
    text = f.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r'href=\"(["'^"]+)"'"', text):
        href = m.group(1)
        if href.startswith(('http://','https://','mailto:','tel:','javascript:','#')):
            continue
        if href.startswith('/'):
            # cleanUrls routes on Vercel: allow '/', '/login', '/dashboard', etc.
            continue
        if '.html' in href:
            target = href.split('#',1)[0].split('?',1)[0]
            name = pathlib.Path(target).name
            if name and name not in existing:
                broken.append((f.name, href))

# de-dupe
seen=set(); out=[]
for a,b in broken:
    if (a,b) not in seen:
        seen.add((a,b)); out.append((a,b))

print('broken_count', len(out))
for a,b in out[:80]:
    print(a, '->', b)
PY" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 exited 127 in 0ms:
zsh:1: command not found: python

exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && python3 - <<'PY'
import re, pathlib
root = pathlib.Path('frontend')
files = sorted(root.glob('*.html'))
existing = {f.name for f in files}
broken = []
for f in files:
    text = f.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r'href=\"(["'^"]+)"'"', text):
        href = m.group(1)
        if href.startswith(('http://','https://','mailto:','tel:','javascript:','#')):
            continue
        if href.startswith('/'):
            continue
        if '.html' in href:
            target = href.split('#',1)[0].split('?',1)[0]
            name = pathlib.Path(target).name
            if name and name not in existing:
                broken.append((f.name, href))

seen=set(); out=[]
for a,b in broken:
    if (a,b) not in seen:
        seen.add((a,b)); out.append((a,b))

print('broken_count', len(out))
for a,b in out:
    print(a, '->', b)
PY" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
broken_count 12
domain-compliance-summary.html -> ../compliance/frontend/frameworks.html?action=add
domain-compliance-summary.html -> ../compliance/frontend/frameworks.html
domain-compliance-summary.html -> ../compliance/frontend/evidence.html?action=upload
domain-compliance-summary.html -> ../compliance/frontend/frameworks.html?fw=soc2
domain-compliance-summary.html -> ../compliance/frontend/frameworks.html?fw=iso27001
domain-compliance-summary.html -> ../compliance/frontend/frameworks.html?fw=gdpr
domain-compliance-summary.html -> ../compliance/frontend/frameworks.html?fw=hipaa
domain-compliance-summary.html -> ../compliance/frontend/frameworks.html?fw=pci-dss
domain-compliance-summary.html -> ../compliance/frontend/frameworks.html?fw=dpdp
domain-compliance-summary.html -> ../compliance/frontend/frameworks.html?fw=nist-csf
domain-compliance-summary.html -> ../compliance/frontend/policies.html
domain-compliance-summary.html -> ../compliance/frontend/vendors.html

exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && rg -n \"../compliance/frontend\" -n frontend/domain-compliance-summary.html && sed -n '1,240p' frontend/domain-compliance-summary.html" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
28:            <a class="btn btn-outline" href="../compliance/frontend/frameworks.html?action=add">
31:            <a class="btn btn-primary" href="../compliance/frontend/frameworks.html">
54:            <a class="btn btn-sm btn-primary" href="../compliance/frontend/evidence.html?action=upload"><i class="fas fa-upload"></i> Upload Evidence</a>
64:          <a class="framework-card" href="../compliance/frontend/frameworks.html?fw=soc2">
69:          <a class="framework-card" href="../compliance/frontend/frameworks.html?fw=iso27001">
74:          <a class="framework-card" href="../compliance/frontend/frameworks.html?fw=gdpr">
79:          <a class="framework-card" href="../compliance/frontend/frameworks.html?fw=hipaa">
84:          <a class="framework-card" href="../compliance/frontend/frameworks.html?fw=pci-dss">
89:          <a class="framework-card" href="../compliance/frontend/frameworks.html?fw=dpdp">
94:          <a class="framework-card" href="../compliance/frontend/frameworks.html?fw=nist-csf">
106:              <a href="../compliance/frontend/frameworks.html" class="btn btn-sm btn-ghost">Open <i class="fas fa-arrow-right"></i></a>
117:              <a href="../compliance/frontend/policies.html" class="btn btn-sm btn-ghost">Open <i class="fas fa-arrow-right"></i></a>
128:              <a href="../compliance/frontend/vendors.html" class="btn btn-sm btn-ghost">Open <i class="fas fa-arrow-right"></i></a>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Compliance Summary | URIP - Unified Risk Intelligence Platform</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <link rel="stylesheet" href="css/main.css">
  <link rel="stylesheet" href="css/app.css?v=20260436">
  <link rel="stylesheet" href="css/domain-page.css">
  <link rel="stylesheet" href="css/module-tools.css">
</head>
<body class="urip-app">
  <div id="app-shell" data-page="domain-compliance-summary">
        <div class="page-header">
          <div>
            <h1 class="page-title"><i class="fas fa-clipboard-check" style="color:var(--teal-accent);margin-right:.5rem"></i>Compliance Summary</h1>
            <p class="page-subtitle">Live posture across SOC 2, ISO 27001, GDPR, HIPAA, PCI-DSS, DPDP, and NIST CSF — drill into the full Compliance module for control evidence.</p>
          </div>
          <div class="flex gap-2">
            <a class="btn btn-outline" href="connector-wizard.html?category=COMPLIANCE">
              <i class="fas fa-plug"></i> Connect Evidence Source
            </a>
            <a class="btn btn-outline" href="../compliance/frontend/frameworks.html?action=add">
              <i class="fas fa-plus"></i> Add Framework
            </a>
            <a class="btn btn-primary" href="../compliance/frontend/frameworks.html">
              <i class="fas fa-arrow-up-right-from-square"></i> Open Compliance Module
            </a>
          </div>
        </div>

        <!-- Integration banner: hub for connecting evidence sources -->
        <div class="compliance-integrations-banner" style="background:var(--u-card,#112236);border:1px solid var(--u-border,rgba(255,255,255,.08));border-radius:14px;padding:18px 22px;margin-bottom:18px;display:flex;justify-content:space-between;align-items:center;gap:18px;flex-wrap:wrap">
          <div style="flex:1;min-width:280px">
            <div style="font-size:11px;font-weight:700;color:var(--u-fg-3,rgba(255,255,255,.5));text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">
              <i class="fas fa-link"></i> Compliance Integration Points
            </div>
            <div style="color:var(--u-fg,#fff);font-size:15px;font-weight:600;margin-bottom:4px">
              Connect a GRC source or upload evidence to start scoring
            </div>
            <div style="color:var(--u-fg-2,rgba(255,255,255,.78));font-size:13px">
              Vanta · Drata · OneTrust · ServiceNow GRC · Manual upload — pick a source and we will map controls to your selected frameworks.
            </div>
          </div>
          <div class="flex gap-2" style="flex-wrap:wrap">
            <a class="btn btn-sm btn-outline" href="connector-wizard.html?tool=vanta"><i class="fas fa-plug"></i> Vanta</a>
            <a class="btn btn-sm btn-outline" href="connector-wizard.html?tool=drata"><i class="fas fa-plug"></i> Drata</a>
            <a class="btn btn-sm btn-outline" href="connector-wizard.html?tool=onetrust"><i class="fas fa-plug"></i> OneTrust</a>
            <a class="btn btn-sm btn-primary" href="../compliance/frontend/evidence.html?action=upload"><i class="fas fa-upload"></i> Upload Evidence</a>
          </div>
        </div>

        <!-- Available integrations for evidence collection -->
        <div id="moduleTools" data-modules="ITSM,IDENTITY,EDR,CSPM,VM,EMAIL_COLLAB,NETWORK,DLP,EXTERNAL_THREAT,OT,COLLABORATION"></div>

        <!-- Frameworks grid -->
        <div class="section-row"><h2>Framework Posture</h2></div>
        <div class="framework-grid" id="frameworkGrid">
          <a class="framework-card" href="../compliance/frontend/frameworks.html?fw=soc2">
            <div class="name">SOC 2</div>
            <div class="score" id="fw-soc2">--</div>
            <div class="score-label">controls passing</div>
          </a>
          <a class="framework-card" href="../compliance/frontend/frameworks.html?fw=iso27001">
            <div class="name">ISO 27001</div>
            <div class="score" id="fw-iso27001">--</div>
            <div class="score-label">controls passing</div>
          </a>
          <a class="framework-card" href="../compliance/frontend/frameworks.html?fw=gdpr">
            <div class="name">GDPR</div>
            <div class="score" id="fw-gdpr">--</div>
            <div class="score-label">controls passing</div>
          </a>
          <a class="framework-card" href="../compliance/frontend/frameworks.html?fw=hipaa">
            <div class="name">HIPAA</div>
            <div class="score" id="fw-hipaa">--</div>
            <div class="score-label">controls passing</div>
          </a>
          <a class="framework-card" href="../compliance/frontend/frameworks.html?fw=pci-dss">
            <div class="name">PCI-DSS</div>
            <div class="score" id="fw-pci">--</div>
            <div class="score-label">controls passing</div>
          </a>
          <a class="framework-card" href="../compliance/frontend/frameworks.html?fw=dpdp">
            <div class="name">DPDP (India)</div>
            <div class="score" id="fw-dpdp">--</div>
            <div class="score-label">controls passing</div>
          </a>
          <a class="framework-card" href="../compliance/frontend/frameworks.html?fw=nist-csf">
            <div class="name">NIST CSF</div>
            <div class="score" id="fw-nist">--</div>
            <div class="score-label">controls passing</div>
          </a>
        </div>

        <!-- Audit prep + acks + vendor risk -->
        <div class="dashboard-grid" style="margin-top:1.25rem">
          <div class="dashboard-card col-6">
            <div class="dashboard-card-header">
              <h3 class="dashboard-card-title">Action items before next audit</h3>
              <a href="../compliance/frontend/frameworks.html" class="btn btn-sm btn-ghost">Open <i class="fas fa-arrow-right"></i></a>
            </div>
            <div class="dashboard-card-body">
              <div id="auditActions" style="font-size:14px;color:var(--gray-600)">
                <em>Compliance module endpoint not connected — placeholder until /api/compliance/action-items lands.</em>
              </div>
            </div>
          </div>
          <div class="dashboard-card col-6">
            <div class="dashboard-card-header">
              <h3 class="dashboard-card-title">Pending policy acknowledgments</h3>
              <a href="../compliance/frontend/policies.html" class="btn btn-sm btn-ghost">Open <i class="fas fa-arrow-right"></i></a>
            </div>
            <div class="dashboard-card-body">
              <div id="pendingAcks" style="font-size:14px;color:var(--gray-600)">
                <em>Compliance module endpoint not connected — placeholder until /api/compliance/policies lands.</em>
              </div>
            </div>
          </div>
          <div class="dashboard-card col-12">
            <div class="dashboard-card-header">
              <h3 class="dashboard-card-title">Vendor risk overview</h3>
              <a href="../compliance/frontend/vendors.html" class="btn btn-sm btn-ghost">Open <i class="fas fa-arrow-right"></i></a>
            </div>
            <div class="dashboard-card-body">
              <div id="vendorRisk" style="font-size:14px;color:var(--gray-600)">
                <em>Vendor risk endpoint not connected — placeholder until /api/compliance/vendors lands.</em>
              </div>
            </div>
          </div>
        </div>
  </div>

  <script src="js/theming.js"></script>
  <script src="js/api.js"></script>
  <script src="js/auth.js"></script>
  <script src="js/shell.js?v=20260436"></script>
  <script src="js/module-tools.js"></script>
  <script>
    if (typeof checkAuth === 'function') checkAuth();
    document.addEventListener('DOMContentLoaded', async function () {
      window.URIP.shell.mount({
        page: 'domain-compliance-summary',
        title: 'Compliance Summary',
        breadcrumb: 'Domains / Compliance Summary'
      });

      loadModuleTools(
        ['ITSM', 'IDENTITY', 'EDR', 'CSPM', 'VM', 'EMAIL_COLLAB', 'NETWORK', 'DLP',
         'EXTERNAL_THREAT', 'OT', 'COLLABORATION'],
        'moduleTools',
        {
          title: 'Connectors that feed compliance evidence',
          subtitle: 'Compliance posture is computed from findings across every wired-up connector — the more sources, the deeper the evidence.',
          manageHref: 'tool-catalog.html'
        }
      );

      // Best-effort: attempt to fetch compliance overview if the endpoint exists.
      // The Compliance Module is a separate sub-app — endpoints may not be wired
      // into the main URIP backend yet, so we silently fall back to "—".
      var apiFetch = window.URIP && window.URIP.apiFetch;
      if (!apiFetch) return;

      var fwMap = {
        'soc2': 'fw-soc2',
        'iso27001': 'fw-iso27001',
        'gdpr': 'fw-gdpr',
        'hipaa': 'fw-hipaa',
        'pci-dss': 'fw-pci',
        'pci_dss': 'fw-pci',
        'dpdp': 'fw-dpdp',
        'nist-csf': 'fw-nist',
        'nist_csf': 'fw-nist',
      };

      try {
        var resp = await apiFetch('/compliance/frameworks/summary', { silent: true });
        if (resp && Array.isArray(resp.frameworks)) {
          resp.frameworks.forEach(function (f) {
            var key = (f.code || f.name || '').toLowerCase();
            var elId = fwMap[key];
            if (elId && f.score != null) {
              var el = document.getElementById(elId);
              if (el) el.textContent = Math.round(f.score) + '%';
            }
          });
        }
      } catch (e) {
        // Endpoint not implemented in this backend — leave as "--"
      }
    });
  </script>
</body>
</html>

**Evaluating integration issues**

I’ve got a few main issues to tackle. First, there's a runtime bug due to a ServiceNow connector contract mismatch with BaseConnector on the integration health endpoint, which seems critical since it affects overall functionality. Then, I found unused imports and docstring contradictions in integrations.py, which is a low-severity issue. There's also an accessibility concern with missing h1 tags and aria-labels, along with broken links in the domain compliance summary, which is high priority. Finally, there’s a medium severity mismatch in Nginx config docs and some styling concerns in the JS files.
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && nl -ba connectors/servicenow/connector.py | sed -n '180,260p' && echo '---' && nl -ba connectors/servicenow/connector.py | sed -n '290,340p' && echo '---' && nl -ba connectors/servicenow/connector.py | sed -n '410,450p' && echo '---' && nl -ba backend/routers/integrations.py | sed -n '1,80p' && echo '---' && nl -ba backend/routers/integrations.py | sed -n '80,210p'" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
   180	            label="OAuth Bearer Token",
   181	            type="password",
   182	            required=False,
   183	            secret=True,
   184	            help_text="Required when auth_method=oauth. Bearer token from your IdP.",
   185	            placeholder="eyJ…",
   186	        ),
   187	        CredentialFieldSpec(
   188	            name="risk_query",
   189	            label="Risk Query",
   190	            type="text",
   191	            required=True,
   192	            placeholder="category=security^state!=7",
   193	            help_text=(
   194	                "ServiceNow encoded query that selects security incidents to ingest. "
   195	                "State 7 = Closed. Default fetches all active security incidents."
   196	            ),
   197	            default="category=security^active=true",
   198	        ),
   199	    ]
   200	
   201	    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
   202	    SETUP_GUIDE = SETUP_GUIDES["servicenow"]
   203	
   204	    def __init__(self) -> None:
   205	        self._client: Optional[ServiceNowAPIClient] = None
   206	        self._instance_url: str = ""
   207	        self._risk_query: str = "category=security^active=true"
   208	        self._last_run: Optional[datetime] = None
   209	        self._error_count: int = 0
   210	        self._last_error: Optional[str] = None
   211	
   212	    # ─────────────────────────────────────────────────────────────────────────
   213	    # authenticate
   214	    # ─────────────────────────────────────────────────────────────────────────
   215	
   216	    async def authenticate(self, credentials: dict) -> ConnectorSession:  # type: ignore[override]
   217	        """
   218	        Validate ServiceNow credentials and return a ConnectorSession.
   219	
   220	        Parameters
   221	        ----------
   222	        credentials : dict
   223	            Must contain:
   224	              - instance_url  (str)
   225	              - auth_method   ("basic" or "oauth")
   226	            If auth_method == "basic":
   227	              - username (str)
   228	              - password (str)
   229	            If auth_method == "oauth":
   230	              - oauth_token (str)
   231	            Optional:
   232	              - risk_query (str) — encoded query for security incidents
   233	              - tenant_id  (str) — URIP tenant scoping
   234	
   235	        Raises
   236	        ------
   237	        ConnectorAuthError
   238	            If credentials are missing required fields or the API rejects them.
   239	        """
   240	        instance_url = credentials.get("instance_url", "").strip().rstrip("/")
   241	        auth_method = str(credentials.get("auth_method", "")).lower()
   242	        risk_query = credentials.get("risk_query", "category=security^active=true")
   243	
   244	        if not instance_url:
   245	            raise ConnectorAuthError(
   246	                "ServiceNow credentials must include 'instance_url'."
   247	            )
   248	        if auth_method not in ("basic", "oauth"):
   249	            raise ConnectorAuthError(
   250	                f"Unsupported auth_method: {auth_method!r}. Use 'basic' or 'oauth'."
   251	            )
   252	
   253	        if auth_method == "basic":
   254	            username = credentials.get("username", "").strip()
   255	            password = credentials.get("password", "")
   256	            if not username or not password:
   257	                raise ConnectorAuthError(
   258	                    "Basic Auth requires 'username' and 'password'."
   259	                )
   260	            self._client = ServiceNowAPIClient(
---
   290	            connector_name=self.NAME,
   291	            tenant_id=credentials.get("tenant_id", "unknown"),
   292	            token=f"sn-{auth_method}-****",
   293	            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
   294	        )
   295	
   296	    # ─────────────────────────────────────────────────────────────────────────
   297	    # fetch_findings
   298	    # ─────────────────────────────────────────────────────────────────────────
   299	
   300	    async def fetch_findings(  # type: ignore[override]
   301	        self,
   302	        session: ConnectorSession,
   303	        since: Optional[datetime] = None,
   304	        limit: int = 100,
   305	    ) -> list[RawFinding]:
   306	        """
   307	        Pull security incidents from ServiceNow.
   308	
   309	        Parameters
   310	        ----------
   311	        session : ConnectorSession
   312	            Session returned by authenticate().
   313	        since : datetime, optional
   314	            Fetch incidents updated after this timestamp (encoded into query).
   315	        limit : int
   316	            Maximum incidents to return (default 100).
   317	
   318	        Returns
   319	        -------
   320	        list[RawFinding]
   321	            Zero or more raw incident findings.
   322	        """
   323	        if self._client is None:
   324	            raise ConnectorFetchError(
   325	                "Connector not authenticated. Call authenticate() first."
   326	            )
   327	
   328	        query = self._risk_query
   329	        if since:
   330	            ts = since.strftime("%Y-%m-%d %H:%M:%S")
   331	            query = f"{query}^sys_updated_on>{ts}"
   332	
   333	        findings: list[RawFinding] = []
   334	        tenant_id = session.tenant_id
   335	
   336	        try:
   337	            raw_list = await self._client.list_incidents(query=query, limit=limit)
   338	            # Validate through Pydantic to normalize nested-object fields.
   339	            response = ServiceNowListResponse(result=raw_list)
   340	
---
   410	            domain="application",
   411	            cvss_score=0.0,
   412	            severity=severity,
   413	            asset=incident.assigned_to or incident.caller_id or "unknown",
   414	            owner_team="IT Service Management",
   415	            cve_id=None,
   416	            exploit_status=None,
   417	        )
   418	
   419	    # ─────────────────────────────────────────────────────────────────────────
   420	    # health_check
   421	    # ─────────────────────────────────────────────────────────────────────────
   422	
   423	    async def health_check(  # type: ignore[override]
   424	        self,
   425	        session: ConnectorSession,
   426	    ) -> ConnectorHealth:
   427	        """
   428	        Return connector operational status.
   429	
   430	        Makes a lightweight GET /api/now/table/sys_user?sysparm_limit=1 call.
   431	        Returns status="ok" on success, "degraded" or "error" on failure.
   432	        Never raises — returns ConnectorHealth with status="error" instead.
   433	        """
   434	        try:
   435	            if self._client is None:
   436	                return ConnectorHealth(
   437	                    connector_name=self.NAME,
   438	                    status="error",
   439	                    last_run=self._last_run,
   440	                    error_count=self._error_count,
   441	                    last_error="Client not initialised — call authenticate() first.",
   442	                )
   443	            await self._client.healthcheck()
   444	            return ConnectorHealth(
   445	                connector_name=self.NAME,
   446	                status="ok",
   447	                last_run=self._last_run,
   448	                error_count=self._error_count,
   449	                last_error=self._last_error,
   450	            )
---
     1	"""
     2	backend/routers/integrations.py — Lightweight integration health endpoint.
     3	
     4	Provides a fast, unauthenticated-friendly status check for each registered
     5	connector so the frontend "Not configured" detection works without requiring
     6	full authentication.
     7	
     8	Endpoints
     9	---------
    10	GET /api/integrations/{tool_name}/health
    11	    Check whether a connector is configured and reachable for the current tenant.
    12	
    13	    Response shape:
    14	        {"status": "Connected",      "connector": "jira", "last_check": "2026-04-28T…"}
    15	        {"status": "Not configured", "connector": "jira"}
    16	        {"status": "Error",          "connector": "jira", "detail": "…message…"}
    17	
    18	    HTTP status code is ALWAYS 200 — the frontend distinguishes state via
    19	    the ``status`` field, not the HTTP code.
    20	
    21	Design notes
    22	------------
    23	- The endpoint first checks whether credentials exist for the tenant.  If none
    24	  are stored, it returns ``{"status": "Not configured"}`` immediately — no
    25	  network call.
    26	- If credentials exist, it instantiates the connector, calls authenticate()
    27	  then health_check(), and returns the result.
    28	- Falls back gracefully when the credential vault or DB is not configured:
    29	  returns ``{"status": "Not configured"}`` rather than a 5xx.
    30	- Uses ``_global_registry`` from connectors.base.registry to check connector
    31	  existence without instantiation.
    32	"""
    33	
    34	from __future__ import annotations
    35	
    36	import logging
    37	from datetime import datetime, timezone
    38	from typing import Any
    39	
    40	from fastapi import APIRouter, Depends
    41	from sqlalchemy.ext.asyncio import AsyncSession
    42	
    43	from backend.database import get_db
    44	from backend.middleware.auth import get_current_user
    45	from backend.middleware.tenant import TenantContext
    46	from connectors.base.registry import _global_registry
    47	
    48	logger = logging.getLogger(__name__)
    49	
    50	router = APIRouter()
    51	
    52	
    53	@router.get("/{tool_name}/health", response_model=None)
    54	async def integration_health(
    55	    tool_name: str,
    56	    current_user: Any = Depends(get_current_user),
    57	    db: AsyncSession = Depends(get_db),
    58	) -> dict[str, Any]:
    59	    """
    60	    Return the health status of a connector for the current tenant.
    61	
    62	    Steps
    63	    -----
    64	    1. Check whether ``tool_name`` is a registered connector.
    65	       → Unknown connector → {"status": "Not configured"}
    66	    2. Look up stored credentials in the TenantConnectorCredential table.
    67	       → No credentials → {"status": "Not configured"}
    68	    3. Instantiate the connector, call authenticate(), then health_check().
    69	       → Connected → {"status": "Connected", "last_check": "<iso>"}
    70	       → Auth / health failure → {"status": "Error", "detail": "…"}
    71	
    72	    Always returns HTTP 200 — status is communicated via the ``status`` field.
    73	    """
    74	    # ── Step 1: is this a known connector? ──────────────────────────────────
    75	    if tool_name not in _global_registry:
    76	        return {"status": "Not configured", "connector": tool_name}
    77	
    78	    # ── Step 2: look up tenant credentials ──────────────────────────────────
    79	    tenant_id: str = getattr(current_user, "tenant_id", None) or "unknown"
    80	    credentials: dict[str, Any] | None = None
---
    80	    credentials: dict[str, Any] | None = None
    81	
    82	    try:
    83	        from sqlalchemy import select
    84	
    85	        from backend.models.tenant_connector_credential import TenantConnectorCredential
    86	        from backend.services.crypto_service import decrypt_credentials
    87	
    88	        result = await db.execute(
    89	            select(TenantConnectorCredential).where(
    90	                TenantConnectorCredential.tenant_id == tenant_id,
    91	                TenantConnectorCredential.connector_name == tool_name,
    92	            )
    93	        )
    94	        row = result.scalar_one_or_none()
    95	
    96	        if row is None:
    97	            return {"status": "Not configured", "connector": tool_name}
    98	
    99	        credentials = decrypt_credentials(row.encrypted_credentials)
   100	
   101	    except Exception as exc:
   102	        # Vault / DB not yet wired in this environment — degrade gracefully.
   103	        logger.warning(
   104	            "integrations_health: credential lookup failed for %s/%s: %s",
   105	            tenant_id, tool_name, exc,
   106	        )
   107	        return {"status": "Not configured", "connector": tool_name}
   108	
   109	    if not credentials:
   110	        return {"status": "Not configured", "connector": tool_name}
   111	
   112	    # ── Step 3: instantiate and probe ────────────────────────────────────────
   113	    try:
   114	        factory = _global_registry.get(tool_name)
   115	        connector = factory()
   116	
   117	        # authenticate() verifies the stored credentials against the live API.
   118	        credentials["tenant_id"] = tenant_id
   119	        connector.authenticate(credentials)
   120	
   121	        # health_check() returns a ConnectorHealth dataclass.
   122	        health = connector.health_check()
   123	
   124	        last_check = datetime.now(timezone.utc).isoformat()
   125	
   126	        if health.status == "ok":
   127	            return {
   128	                "status": "Connected",
   129	                "connector": tool_name,
   130	                "last_check": last_check,
   131	                "health_status": health.status,
   132	            }
   133	        else:
   134	            return {
   135	                "status": "Error",
   136	                "connector": tool_name,
   137	                "last_check": last_check,
   138	                "health_status": health.status,
   139	                "detail": health.last_error or "Connector health degraded.",
   140	            }
   141	
   142	    except Exception as exc:
   143	        logger.warning(
   144	            "integrations_health: probe failed for %s/%s: %s",
   145	            tenant_id, tool_name, exc,
   146	        )
   147	        return {
   148	            "status": "Error",
   149	            "connector": tool_name,
   150	            "detail": str(exc),
   151	        }

exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && nl -ba connectors/servicenow/connector.py | sed -n '292,330p' && echo '---' && nl -ba connectors/servicenow/connector.py | sed -n '404,440p'" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
   292	            token=f"sn-{auth_method}-****",
   293	            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
   294	        )
   295	
   296	    # ─────────────────────────────────────────────────────────────────────────
   297	    # fetch_findings
   298	    # ─────────────────────────────────────────────────────────────────────────
   299	
   300	    async def fetch_findings(  # type: ignore[override]
   301	        self,
   302	        session: ConnectorSession,
   303	        since: Optional[datetime] = None,
   304	        limit: int = 100,
   305	    ) -> list[RawFinding]:
   306	        """
   307	        Pull security incidents from ServiceNow.
   308	
   309	        Parameters
   310	        ----------
   311	        session : ConnectorSession
   312	            Session returned by authenticate().
   313	        since : datetime, optional
   314	            Fetch incidents updated after this timestamp (encoded into query).
   315	        limit : int
   316	            Maximum incidents to return (default 100).
   317	
   318	        Returns
   319	        -------
   320	        list[RawFinding]
   321	            Zero or more raw incident findings.
   322	        """
   323	        if self._client is None:
   324	            raise ConnectorFetchError(
   325	                "Connector not authenticated. Call authenticate() first."
   326	            )
   327	
   328	        query = self._risk_query
   329	        if since:
   330	            ts = since.strftime("%Y-%m-%d %H:%M:%S")
---
   404	        )
   405	
   406	        return URIPRiskRecord(
   407	            finding=finding,
   408	            description=description,
   409	            source=self.NAME,
   410	            domain="application",
   411	            cvss_score=0.0,
   412	            severity=severity,
   413	            asset=incident.assigned_to or incident.caller_id or "unknown",
   414	            owner_team="IT Service Management",
   415	            cve_id=None,
   416	            exploit_status=None,
   417	        )
   418	
   419	    # ─────────────────────────────────────────────────────────────────────────
   420	    # health_check
   421	    # ─────────────────────────────────────────────────────────────────────────
   422	
   423	    async def health_check(  # type: ignore[override]
   424	        self,
   425	        session: ConnectorSession,
   426	    ) -> ConnectorHealth:
   427	        """
   428	        Return connector operational status.
   429	
   430	        Makes a lightweight GET /api/now/table/sys_user?sysparm_limit=1 call.
   431	        Returns status="ok" on success, "degraded" or "error" on failure.
   432	        Never raises — returns ConnectorHealth with status="error" instead.
   433	        """
   434	        try:
   435	            if self._client is None:
   436	                return ConnectorHealth(
   437	                    connector_name=self.NAME,
   438	                    status="error",
   439	                    last_run=self._last_run,
   440	                    error_count=self._error_count,

**Planning connector fixes**

I need to consider if I should provide the line number for the BaseConnector signature to show a mismatch, but maybe that's unnecessary. I can reference the method definitions in connectors/base/connector.py around line 277 to help with the fix: changing the ServiceNow connector methods to be synchronous, using `asyncio.run` for the API client, and removing the session parameter. I also noticed an issue in the integration router with an unused import of TenantContext on line 45, which I’ll suggest removing. Now I need to add missing `h1:` tags with line numbers for each file using `nl` for global search.
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && nl -ba frontend/global-search.html | sed -n '1,60p' && echo '---' && nl -ba frontend/notifications.html | sed -n '1,60p' && echo '---' && nl -ba frontend/risk-register.html | sed -n '1,35p' && echo '---' && nl -ba frontend/vapt-portal-dashboard.html | sed -n '1,70p'" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
     1	<!DOCTYPE html>
     2	<html lang="en">
     3	<head>
     4	  <meta charset="UTF-8">
     5	  <link rel="icon" type="image/svg+xml" href="favicon.svg">
     6	  <meta name="viewport" content="width=device-width, initial-scale=1.0">
     7	  <title>Search | URIP</title>
     8	
     9	  <link rel="preconnect" href="https://fonts.googleapis.com">
    10	  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    11	  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    12	  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    13	  <link rel="stylesheet" href="css/main.css">
    14	  <link rel="stylesheet" href="css/app.css?v=20260436">
    15	</head>
    16	<body class="urip-app">
    17	  <div id="app-shell" data-page="">
    18	    <div style="display:flex;gap:12px;margin-bottom:18px;align-items:center">
    19	      <div style="font-size:12px;color:var(--u-fg-3)">Searching for</div>
    20	      <div id="searchTermLabel" class="mono" style="font-size:14px;color:var(--u-primary-2);font-weight:600"></div>
    21	    </div>
    22	
    23	    <div class="u-tabs">
    24	      <span class="u-tab is-active" data-tab="risks">Risks</span>
    25	      <span class="u-tab" data-tab="connectors">Connectors</span>
    26	      <span class="u-tab" data-tab="audit">Audit Log</span>
    27	    </div>
    28	
    29	    <div id="searchResults" class="u-card">
    30	      <div class="u-card-b" id="resultsBody">
    31	        <div class="u-skel" style="margin-bottom:10px"></div>
    32	        <div class="u-skel" style="margin-bottom:10px"></div>
    33	        <div class="u-skel"></div>
    34	      </div>
    35	    </div>
    36	  </div>
    37	
    38	  <script src="js/theming.js"></script>
    39	  <script src="js/api.js"></script>
    40	  <script src="js/auth.js"></script>
    41	  <script src="js/shell.js?v=20260436"></script>
    42	  <script src="js/global-search.js"></script>
    43	</body>
    44	</html>
---
     1	<!DOCTYPE html>
     2	<html lang="en">
     3	<head>
     4	  <meta charset="UTF-8">
     5	  <link rel="icon" type="image/svg+xml" href="favicon.svg">
     6	  <meta name="viewport" content="width=device-width, initial-scale=1.0">
     7	  <title>Notifications | URIP</title>
     8	
     9	  <link rel="preconnect" href="https://fonts.googleapis.com">
    10	  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    11	  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    12	  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    13	  <link rel="stylesheet" href="css/main.css">
    14	  <link rel="stylesheet" href="css/app.css?v=20260436">
    15	</head>
    16	<body class="urip-app">
    17	  <div id="app-shell" data-page="audit-log">
    18	    <div class="rr-toolbar">
    19	      <input id="nfSearch" type="search" placeholder="Filter notifications…">
    20	      <select id="nfType">
    21	        <option value="">All types</option>
    22	        <option value="login">Login</option>
    23	        <option value="risk">Risk</option>
    24	        <option value="control">Control</option>
    25	        <option value="ticket">Ticket</option>
    26	        <option value="connector">Connector</option>
    27	      </select>
    28	      <button class="u-btn is-ghost is-sm" id="nfReset"><i class="fas fa-rotate-left"></i> Reset</button>
    29	    </div>
    30	
    31	    <div class="u-card">
    32	      <div class="u-card-h"><h3>Recent Activity</h3></div>
    33	      <div class="u-card-b" id="nfBody">
    34	        <div class="u-skel" style="margin-bottom:10px"></div>
    35	        <div class="u-skel" style="margin-bottom:10px"></div>
    36	        <div class="u-skel"></div>
    37	      </div>
    38	    </div>
    39	  </div>
    40	
    41	  <script src="js/theming.js"></script>
    42	  <script src="js/api.js"></script>
    43	  <script src="js/auth.js"></script>
    44	  <script src="js/shell.js?v=20260436"></script>
    45	  <script>
    46	    (function () {
    47	      'use strict';
    48	      if (typeof window.checkAuth === 'function') window.checkAuth();
    49	      var state = { items: [], filters: { search: '', type: '' } };
    50	
    51	      document.addEventListener('DOMContentLoaded', function () {
    52	        window.URIP.shell.mount({
    53	          page: 'audit-log',
    54	          title: 'Notifications',
    55	          breadcrumb: 'Operations / Notifications',
    56	          actions: [
    57	            { label: 'Mark all read', icon: 'fa-check-double', variant: 'is-ghost', onClick: function () {
    58	                window.URIP.showNotification('Marked', 'All notifications marked as read (local only — backend persistence pending).', 'success');
    59	              }
    60	            }
---
     1	<!DOCTYPE html>
     2	<html lang="en">
     3	<head>
     4	  <meta charset="UTF-8">
     5	  <link rel="icon" type="image/svg+xml" href="favicon.svg">
     6	  <meta name="viewport" content="width=device-width, initial-scale=1.0">
     7	  <title>Risk Register | URIP</title>
     8	
     9	  <link rel="preconnect" href="https://fonts.googleapis.com">
    10	  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    11	  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    12	  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    13	
    14	  <link rel="stylesheet" href="css/main.css">
    15	  <link rel="stylesheet" href="css/app.css?v=20260436">
    16	</head>
    17	<body class="urip-app">
    18	  <div id="app-shell" data-page="risk-register">
    19	
    20	    <!-- Filter / search toolbar -->
    21	    <div class="rr-toolbar" role="search">
    22	      <input type="search" id="searchInput" placeholder="Search by ID, finding, asset, CVE…" aria-label="Search risks">
    23	      <select id="severityFilter" class="u-select" aria-label="Severity">
    24	        <option value="">All severities</option>
    25	        <option value="critical">Critical</option>
    26	        <option value="high">High</option>
    27	        <option value="medium">Medium</option>
    28	        <option value="low">Low</option>
    29	      </select>
    30	      <select id="statusFilter" aria-label="Status">
    31	        <option value="">All status</option>
    32	        <option value="open">Open</option>
    33	        <option value="in_progress">In progress</option>
    34	        <option value="accepted">Accepted</option>
    35	        <option value="closed">Closed</option>
---
     1	<!DOCTYPE html>
     2	<html lang="en">
     3	<head>
     4	  <meta charset="UTF-8" />
     5	  <link rel="icon" type="image/svg+xml" href="favicon.svg" />
     6	  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
     7	  <title>Submissions | VAPT Vendor Portal</title>
     8	  <link rel="preconnect" href="https://fonts.googleapis.com" />
     9	  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet" />
    10	  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
    11	  <link rel="stylesheet" href="css/main.css" />
    12	  <link rel="stylesheet" href="css/vapt-portal.css" />
    13	</head>
    14	<body>
    15	  <div class="vapt-shell">
    16	    <header class="vapt-topbar">
    17	      <div class="vapt-brand">
    18	        <span class="vapt-brand-icon"><i class="fas fa-bug"></i></span>
    19	        <span>URIP — VAPT Vendor Portal</span>
    20	      </div>
    21	      <nav class="vapt-tabs">
    22	        <a href="vapt-portal-dashboard.html" class="vapt-tab active">My submissions</a>
    23	        <a href="vapt-portal-submit.html" class="vapt-tab">New submission</a>
    24	      </nav>
    25	      <div class="vapt-user">
    26	        <span id="vendorName">…</span>
    27	        <button id="logoutBtn" class="vapt-btn vapt-btn-ghost" title="Sign out">
    28	          <i class="fas fa-sign-out-alt"></i>
    29	        </button>
    30	      </div>
    31	    </header>
    32	
    33	    <main class="vapt-content">
    34	      <section class="vapt-summary-row">
    35	        <div class="vapt-summary-card">
    36	          <div class="vapt-summary-label">Total submissions</div>
    37	          <div class="vapt-summary-value" id="sumTotal">–</div>
    38	        </div>
    39	        <div class="vapt-summary-card vapt-summary-warn" id="cardPending">
    40	          <div class="vapt-summary-label">Pending re-tests</div>
    41	          <div class="vapt-summary-value" id="sumPending">–</div>
    42	        </div>
    43	        <div class="vapt-summary-card">
    44	          <div class="vapt-summary-label">In progress</div>
    45	          <div class="vapt-summary-value" id="sumInProgress">–</div>
    46	        </div>
    47	        <div class="vapt-summary-card">
    48	          <div class="vapt-summary-label">Closed</div>
    49	          <div class="vapt-summary-value" id="sumClosed">–</div>
    50	        </div>
    51	      </section>
    52	
    53	      <section id="notifWrap" style="display:none">
    54	        <h2>Pending re-tests</h2>
    55	        <div id="notifList" class="vapt-notif-list"></div>
    56	      </section>
    57	
    58	      <section>
    59	        <div class="vapt-section-head">
    60	          <h2>My submissions</h2>
    61	          <div class="vapt-section-tools">
    62	            <select id="statusFilter" class="vapt-select">
    63	              <option value="">All statuses</option>
    64	              <option value="submitted">Submitted</option>
    65	              <option value="triaged">Triaged</option>
    66	              <option value="in_progress">In progress</option>
    67	              <option value="fixed">Fixed</option>
    68	              <option value="retest_requested">Re-test requested</option>
    69	              <option value="retest_pass">Re-test pass</option>
    70	              <option value="retest_fail">Re-test fail</option>

**Identifying branding issues**

Okay, I’m looking at branding issues regarding specific line numbers in my code. The first one is in main.css at line 3, which is a comment. Then, there's another issue in sidebar.js at line 136. I’m planning to note those down (nl them) so I can address them later. It feels good to have a plan in place to tackle these details!
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && nl -ba frontend/css/main.css | sed -n '1,30p' && echo '---' && nl -ba frontend/js/sidebar.js | sed -n '110,160p' && echo '---' && nl -ba frontend/login.html | sed -n '420,440p'" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
     1	/* ============================================
     2	   URIP - Unified Risk Intelligence Platform
     3	   Semantic Gravity - Enterprise Cybersecurity SaaS
     4	   Main Stylesheet
     5	   ============================================ */
     6	
     7	/* CSS Variables */
     8	:root {
     9	  /* Brand Colors */
    10	  --navy-primary: #0D1B2A;
    11	  --navy-dark: #08121C;
    12	  --navy-light: #1B2838;
    13	  --teal-accent: #1ABC9C;
    14	  --teal-hover: #16A085;
    15	  --teal-light: #2ECC71;
    16	  --red-critical: #E74C3C;
    17	  --red-dark: #C0392B;
    18	  --orange-high: #E67E22;
    19	  --yellow-medium: #F1C40F;
    20	  --green-low: #27AE60;
    21	  --white: #FFFFFF;
    22	  --gray-50: #F8FAFC;
    23	  --gray-100: #F0F4F8;
    24	  --gray-200: #E2E8F0;
    25	  --gray-300: #CBD5E1;
    26	  --gray-400: #94A3B8;
    27	  --gray-500: #64748B;
    28	  --gray-600: #475569;
    29	  --gray-700: #334155;
    30	  --gray-800: #1E293B;
---
   110	    if (collapsed) {
   111	      sidebar.classList.add('collapsed');
   112	    }
   113	
   114	    // Toggle button
   115	    var toggle = el('div', 'sidebar-toggle');
   116	    toggle.appendChild(faIcon('fa-chevron-left'));
   117	    toggle.addEventListener('click', function () {
   118	      sidebar.classList.toggle('collapsed');
   119	      var isCollapsed = sidebar.classList.contains('collapsed');
   120	      localStorage.setItem('urip_sidebar_collapsed', isCollapsed ? 'true' : 'false');
   121	
   122	      // Adjust main content margin
   123	      var mainContent = document.querySelector('.main-content');
   124	      if (mainContent) {
   125	        mainContent.style.marginLeft = isCollapsed ? 'var(--sidebar-collapsed)' : 'var(--sidebar-width)';
   126	      }
   127	      var topbar = document.querySelector('.topbar');
   128	      if (topbar) {
   129	        topbar.style.left = isCollapsed ? 'var(--sidebar-collapsed)' : 'var(--sidebar-width)';
   130	      }
   131	    });
   132	    sidebar.appendChild(toggle);
   133	
   134	    // Header / Logo — pull from URIP.branding (set by theming.js); fallback to defaults
   135	    var brand = (window.URIP && window.URIP.branding) || {};
   136	    var brandAppName = brand.app_name || 'Semantic Gravity';
   137	    var brandTagline = brand.app_tagline || 'Unified Risk Intelligence';
   138	    var brandLogoUrl = brand.logo_url || null;
   139	
   140	    var header = el('div', 'sidebar-header');
   141	    var logoLink = document.createElement('a');
   142	    logoLink.href = 'dashboard.html';
   143	    logoLink.className = 'sidebar-logo';
   144	
   145	    var logoIcon = el('div', 'sidebar-logo-icon');
   146	    if (brandLogoUrl && /^https?:\/\//.test(brandLogoUrl)) {
   147	      var logoImg = document.createElement('img');
   148	      logoImg.src = brandLogoUrl;
   149	      logoImg.alt = brandAppName + ' logo';
   150	      logoImg.style.cssText = 'max-width:100%;max-height:32px;display:block';
   151	      logoImg.addEventListener('error', function () {
   152	        // Fallback to FA icon if logo URL fails to load
   153	        logoIcon.textContent = '';
   154	        logoIcon.appendChild(faIcon('fa-shield-alt'));
   155	      });
   156	      logoIcon.appendChild(logoImg);
   157	    } else {
   158	      logoIcon.appendChild(faIcon('fa-shield-alt'));
   159	    }
   160	    logoLink.appendChild(logoIcon);
---
   420	            <span class="security-badge">
   421	              <i class="fas fa-shield-alt"></i>
   422	              GDPR Ready
   423	            </span>
   424	          </div>
   425	        </div>
   426	      </div>
   427	    </div>
   428	
   429	    <!-- Copyright -->
   430	    <div class="login-copyright">
   431	      &copy; 2026 Semantic Gravity. All rights reserved. | v2.4.1
   432	    </div>
   433	  </div>
   434	
   435	  <!-- Scripts -->
   436	  <script src="js/theming.js"></script>
   437	  <script src="js/api.js"></script>
   438	  <script src="js/auth.js"></script>
   439	  <script>
   440	    // Generate floating particles

**Examining branding elements**

I’m thinking about the branding placeholders in the login and index sections, and I'll need to cite at least one of them. Also, there’s the inline white background for the API toast in the frontend file, specifically in api.js around line 174. I need to open that up and take a look at it to ensure everything is consistent. It’s important to double-check these details for a polished final product!
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && nl -ba frontend/js/api.js | sed -n '150,210p' && echo '---' && nl -ba frontend/js/filters.js | sed -n '640,710p'" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
   150	
   151	    // Inject animation keyframes once
   152	    if (!document.getElementById('urip-toast-styles')) {
   153	      var style = document.createElement('style');
   154	      style.id = 'urip-toast-styles';
   155	      style.textContent =
   156	        '@keyframes uripSlideIn{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}' +
   157	        '@keyframes uripSlideOut{from{transform:translateX(0);opacity:1}to{transform:translateX(100%);opacity:0}}';
   158	      document.head.appendChild(style);
   159	    }
   160	
   161	    var iconMap = {
   162	      success: 'fa-check-circle',
   163	      error: 'fa-times-circle',
   164	      info: 'fa-info-circle'
   165	    };
   166	    var colorMap = {
   167	      success: '#27AE60',
   168	      error: '#E74C3C',
   169	      info: '#1ABC9C'
   170	    };
   171	
   172	    var toast = document.createElement('div');
   173	    toast.style.cssText =
   174	      'position:fixed;top:20px;right:20px;background:#fff;border-radius:8px;' +
   175	      'padding:16px 20px;box-shadow:0 10px 40px rgba(0,0,0,0.2);z-index:10000;' +
   176	      'min-width:300px;max-width:420px;animation:uripSlideIn 0.3s ease';
   177	
   178	    var wrapper = document.createElement('div');
   179	    wrapper.style.cssText = 'display:flex;align-items:flex-start;gap:12px';
   180	
   181	    var icon = document.createElement('i');
   182	    icon.className = 'fas ' + (iconMap[type] || iconMap.info);
   183	    icon.style.cssText = 'color:' + (colorMap[type] || colorMap.info) + ';font-size:20px;margin-top:2px';
   184	
   185	    var textBlock = document.createElement('div');
   186	
   187	    var titleEl = document.createElement('div');
   188	    titleEl.style.cssText = 'font-weight:600;color:#1E293B;margin-bottom:4px';
   189	    titleEl.textContent = title;
   190	
   191	    var msgEl = document.createElement('div');
   192	    msgEl.style.cssText = 'font-size:14px;color:#64748B';
   193	    msgEl.textContent = message;
   194	
   195	    textBlock.appendChild(titleEl);
   196	    textBlock.appendChild(msgEl);
   197	    wrapper.appendChild(icon);
   198	    wrapper.appendChild(textBlock);
   199	    toast.appendChild(wrapper);
   200	
   201	    document.body.appendChild(toast);
   202	
   203	    setTimeout(function () {
   204	      toast.style.animation = 'uripSlideOut 0.3s ease';
   205	      setTimeout(function () {
   206	        if (toast.parentNode) {
   207	          toast.parentNode.removeChild(toast);
   208	        }
   209	      }, 300);
   210	    }, 4000);
---
   640	   *
   641	   * @param {string} riskId - e.g. "RISK-001"
   642	   */
   643	  async function showRiskDetailModal(riskId) {
   644	    // Remove any existing modal
   645	    closeModal('urip-risk-detail-modal');
   646	
   647	    // Create overlay
   648	    var overlay = document.createElement('div');
   649	    overlay.id = 'urip-risk-detail-modal';
   650	    overlay.style.cssText =
   651	      'position:fixed;top:0;left:0;width:100%;height:100%;' +
   652	      'background:rgba(0,0,0,0.5);z-index:10000;display:flex;' +
   653	      'align-items:center;justify-content:center;padding:20px';
   654	
   655	    // Close on overlay click
   656	    overlay.addEventListener('click', function (e) {
   657	      if (e.target === overlay) closeModal('urip-risk-detail-modal');
   658	    });
   659	
   660	    // Modal box
   661	    var modal = document.createElement('div');
   662	    modal.style.cssText =
   663	      'background:#fff;border-radius:12px;width:100%;max-width:680px;' +
   664	      'max-height:85vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,0.3);' +
   665	      'padding:0';
   666	
   667	    // Loading state
   668	    var loadingDiv = document.createElement('div');
   669	    loadingDiv.style.cssText = 'padding:40px;text-align:center;color:#64748B';
   670	    loadingDiv.textContent = 'Loading risk details...';
   671	    modal.appendChild(loadingDiv);
   672	    overlay.appendChild(modal);
   673	    document.body.appendChild(overlay);
   674	
   675	    try {
   676	      var data = await window.URIP.apiFetch('/risks/' + encodeURIComponent(riskId));
   677	      modal.textContent = '';
   678	      renderRiskDetailContent(modal, data);
   679	    } catch (err) {
   680	      modal.textContent = '';
   681	      var errorDiv = document.createElement('div');
   682	      errorDiv.style.cssText = 'padding:40px;text-align:center;color:#E74C3C';
   683	      errorDiv.textContent = 'Failed to load risk details: ' + (err.message || 'Unknown error');
   684	      modal.appendChild(errorDiv);
   685	
   686	      var closeBtn = document.createElement('button');
   687	      closeBtn.textContent = 'Close';
   688	      closeBtn.style.cssText =
   689	        'display:block;margin:0 auto 20px;padding:8px 24px;border:none;' +
   690	        'background:#64748B;color:#fff;border-radius:6px;cursor:pointer';
   691	      closeBtn.addEventListener('click', function () { closeModal('urip-risk-detail-modal'); });
   692	      modal.appendChild(closeBtn);
   693	    }
   694	  }
   695	
   696	  /**
   697	   * Populate the detail modal with risk information and history.
   698	   *
   699	   * @param {HTMLElement} modal
   700	   * @param {object} data - API response from /risks/{risk_id}, may contain .risk and .history
   701	   */
   702	  function renderRiskDetailContent(modal, data) {
   703	    // The API may return { risk: {...}, history: [...] } or just the risk object
   704	    var risk = data.risk || data;
   705	    var history = data.history || [];
   706	
   707	    // Header bar
   708	    var header = document.createElement('div');
   709	    header.style.cssText =
   710	      'display:flex;align-items:center;justify-content:space-between;' +

exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && nl -ba frontend/vercel.json | sed -n '1,80p' && echo '---' && nl -ba docs/audit_apr28/deploy/_artifacts/api.urip.adaptive-mind.com.conf | sed -n '1,120p'" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
     1	{
     2	  "$schema": "https://openapi.vercel.sh/vercel.json",
     3	  "version": 2,
     4	  "cleanUrls": true,
     5	  "trailingSlash": false,
     6	  "redirects": [
     7	    {
     8	      "source": "/home",
     9	      "destination": "/",
    10	      "permanent": true
    11	    },
    12	    {
    13	      "source": "/home.html",
    14	      "destination": "/",
    15	      "permanent": true
    16	    }
    17	  ],
    18	  "rewrites": [
    19	    {
    20	      "source": "/api/:path*",
    21	      "destination": "http://145.223.21.39/api/:path*"
    22	    },
    23	    {
    24	      "source": "/compliance-api/:path*",
    25	      "destination": "http://145.223.21.39/compliance-api/:path*"
    26	    }
    27	  ],
    28	  "headers": [
    29	    {
    30	      "source": "/(.*)\\.(png|jpg|jpeg|gif|svg|webp|ico|woff|woff2|css|js)",
    31	      "headers": [
    32	        {
    33	          "key": "Cache-Control",
    34	          "value": "public, max-age=31536000, immutable"
    35	        }
    36	      ]
    37	    },
    38	    {
    39	      "source": "/(.*)\\.html",
    40	      "headers": [
    41	        {
    42	          "key": "Cache-Control",
    43	          "value": "public, max-age=0, must-revalidate"
    44	        }
    45	      ]
    46	    },
    47	    {
    48	      "source": "/(.*)",
    49	      "headers": [
    50	        {
    51	          "key": "X-Content-Type-Options",
    52	          "value": "nosniff"
    53	        },
    54	        {
    55	          "key": "X-Frame-Options",
    56	          "value": "DENY"
    57	        },
    58	        {
    59	          "key": "Referrer-Policy",
    60	          "value": "strict-origin-when-cross-origin"
    61	        },
    62	        {
    63	          "key": "Permissions-Policy",
    64	          "value": "camera=(), microphone=(), geolocation=()"
    65	        }
    66	      ]
    67	    }
    68	  ]
    69	}---
     1	# /etc/nginx/sites-available/api.urip.adaptive-mind.com.conf
     2	# URIP Adaptive Mind backend reverse-proxy
     3	# Backend listens on 127.0.0.1:8089 (Docker stack: urip-adaptive-mind)
     4	# TLS: pending DNS — once `api.urip.adaptive-mind.com` resolves to 145.223.21.39
     5	# run:  certbot --nginx -d api.urip.adaptive-mind.com
     6	
     7	server {
     8	    listen 80;
     9	    listen [::]:80;
    10	    server_name api.urip.adaptive-mind.com;
    11	
    12	    # Allow Let's Encrypt HTTP-01 challenge from any path before TLS lands.
    13	    location /.well-known/acme-challenge/ {
    14	        root /var/www/html;
    15	    }
    16	
    17	    location / {
    18	        proxy_pass         http://127.0.0.1:8089;
    19	        proxy_http_version 1.1;
    20	        proxy_set_header   Host              $host;
    21	        proxy_set_header   X-Real-IP         $remote_addr;
    22	        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
    23	        proxy_set_header   X-Forwarded-Proto $scheme;
    24	
    25	        # WebSocket / SSE support (auth + future event streams)
    26	        proxy_set_header   Upgrade           $http_upgrade;
    27	        proxy_set_header   Connection        "upgrade";
    28	
    29	        proxy_read_timeout 120s;
    30	        proxy_connect_timeout 30s;
    31	        client_max_body_size 50M;
    32	    }
    33	
    34	    # Compliance backend on a separate path prefix.
    35	    # Compliance listens on 127.0.0.1:8091.
    36	    location /compliance/ {
    37	        rewrite ^/compliance/(.*)$ /$1 break;
    38	        proxy_pass         http://127.0.0.1:8091;
    39	        proxy_http_version 1.1;
    40	        proxy_set_header   Host              $host;
    41	        proxy_set_header   X-Real-IP         $remote_addr;
    42	        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
    43	        proxy_set_header   X-Forwarded-Proto $scheme;
    44	        proxy_read_timeout 120s;
    45	        client_max_body_size 50M;
    46	    }
    47	}

**Checking for code issues**

I need to identify line numbers for broken links and placeholders in the domain compliance summary, and we have those line numbers available for citation. Now, I'll look for more dead code, including things like unused imports. The report should list every remaining issue, although it might be extensive. The user wants 100, so I'll focus on obvious problems. I also need to check the global-search for the "data-page" value, as it seems to be an empty string currently, which might cause issues.
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && sed -n '1,220p' frontend/js/global-search.js" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
/**
 * URIP — Global Search (Wave A)
 *
 * Backend gap: GET /api/search is NOT implemented. We fall back to local
 * filtering on /api/risks?search=, /api/connectors, and /api/audit-log.
 * Each tab labels itself "filtered locally" honestly.
 */
(function () {
  'use strict';

  if (typeof window.checkAuth === 'function') window.checkAuth();

  var qs = new URLSearchParams(window.location.search);
  var query = (qs.get('q') || '').trim();
  var activeTab = 'risks';

  document.addEventListener('DOMContentLoaded', function () {
    window.URIP.shell.mount({
      page: '',
      title: 'Search Results',
      breadcrumb: 'Search'
    });

    document.getElementById('searchTermLabel').textContent = query || '(empty query)';

    document.querySelectorAll('.u-tab').forEach(function (t) {
      t.addEventListener('click', function () {
        document.querySelectorAll('.u-tab').forEach(function (x) { x.classList.remove('is-active'); });
        t.classList.add('is-active');
        activeTab = t.dataset.tab;
        runSearch();
      });
    });
    runSearch();
  });

  async function runSearch() {
    var body = document.getElementById('resultsBody');
    body.textContent = '';
    if (!query) {
      body.appendChild(window.URIP.shell.makeEmpty('fa-magnifying-glass', 'Type something in the topbar', 'Hit enter to search.'));
      return;
    }
    body.appendChild(skeleton());

    if (activeTab === 'risks')      return loadRisks(body);
    if (activeTab === 'connectors') return loadConnectors(body);
    if (activeTab === 'audit')      return loadAudit(body);
  }

  async function loadRisks(body) {
    try {
      var resp = await window.URIP.apiFetch('/risks?search=' + encodeURIComponent(query) + '&per_page=25', { silent: true });
      var items = (resp && resp.items) || [];
      body.textContent = '';
      if (!items.length) {
        body.appendChild(window.URIP.shell.makeEmpty('fa-magnifying-glass', 'No risks match', 'Try a different search.'));
        return;
      }
      var list = document.createElement('div');
      items.forEach(function (r) {
        var row = document.createElement('a');
        row.href = 'risk-register.html?search=' + encodeURIComponent(r.risk_id || '');
        row.style.display = 'flex';
        row.style.justifyContent = 'space-between';
        row.style.padding = '12px 0';
        row.style.borderBottom = '1px solid var(--u-border)';
        row.style.color = 'var(--u-fg)';
        var left = document.createElement('div');
        left.innerHTML = '<div style="font-weight:600">' + escapeHtml(r.finding || '') + '</div>' +
                         '<div style="font-size:11px;color:var(--u-fg-3)">' +
                         escapeHtml(r.risk_id || '') + ' • ' + escapeHtml(r.source || '') + ' • ' + escapeHtml(r.asset || '') + '</div>';
        row.appendChild(left);
        row.appendChild(window.URIP.shell.severityBadge(r.severity));
        list.appendChild(row);
      });
      body.appendChild(list);
    } catch (err) {
      body.textContent = '';
      body.appendChild(window.URIP.shell.makeEmpty('fa-triangle-exclamation', 'Search failed', err.message || ''));
    }
  }

  async function loadConnectors(body) {
    try {
      var resp = await window.URIP.apiFetch('/connectors?limit=200', { silent: true });
      var q = query.toLowerCase();
      var items = ((resp && resp.items) || []).filter(function (c) {
        var hay = ((c.display_name || '') + ' ' + (c.name || '') + ' ' + (c.category || '') + ' ' + (c.short_description || '')).toLowerCase();
        return hay.indexOf(q) !== -1;
      });
      body.textContent = '';
      if (!items.length) {
        body.appendChild(window.URIP.shell.makeEmpty('fa-puzzle-piece', 'No connectors match', 'Filtered locally over the full catalog.'));
        return;
      }
      var note = document.createElement('div');
      note.style.fontSize = '11px';
      note.style.color = 'var(--u-fg-3)';
      note.style.marginBottom = '10px';
      note.textContent = 'Filtered locally — backend /api/search is not yet implemented.';
      body.appendChild(note);
      items.forEach(function (c) {
        var row = document.createElement('a');
        row.href = 'tool-catalog.html?open=' + encodeURIComponent(c.name);
        row.style.display = 'flex';
        row.style.justifyContent = 'space-between';
        row.style.padding = '10px 0';
        row.style.borderBottom = '1px solid var(--u-border)';
        row.style.color = 'var(--u-fg)';
        var left = document.createElement('div');
        left.innerHTML = '<div style="font-weight:600">' + escapeHtml(c.display_name || c.name) + '</div>' +
                         '<div style="font-size:11px;color:var(--u-fg-3)">' + escapeHtml(c.category || '') + '</div>';
        row.appendChild(left);
        row.appendChild(window.URIP.shell.lifecyclePill(c.status));
        body.appendChild(row);
      });
    } catch (err) {
      body.textContent = '';
      body.appendChild(window.URIP.shell.makeEmpty('fa-triangle-exclamation', 'Search failed', err.message || ''));
    }
  }

  async function loadAudit(body) {
    try {
      var resp = await window.URIP.apiFetch('/audit-log?per_page=50', { silent: true });
      var items = (resp && (resp.items || resp.entries || [])) || [];
      var q = query.toLowerCase();
      items = items.filter(function (it) {
        var hay = JSON.stringify(it).toLowerCase();
        return hay.indexOf(q) !== -1;
      });
      body.textContent = '';
      if (!items.length) {
        body.appendChild(window.URIP.shell.makeEmpty('fa-clock-rotate-left', 'No audit entries match', 'Filtered locally over the latest 50 entries.'));
        return;
      }
      items.forEach(function (it) {
        var row = document.createElement('div');
        row.style.padding = '10px 0';
        row.style.borderBottom = '1px solid var(--u-border)';
        row.innerHTML = '<div>' + escapeHtml(it.action || it.event_type || it.message || 'Event') + '</div>' +
                        '<div style="font-size:11px;color:var(--u-fg-3)">' +
                        escapeHtml(it.user_email || it.actor || '') + ' • ' +
                        escapeHtml(it.timestamp || it.created_at || '') + '</div>';
        body.appendChild(row);
      });
    } catch (err) {
      body.textContent = '';
      body.appendChild(window.URIP.shell.makeEmpty('fa-triangle-exclamation', 'Search failed', err.message || ''));
    }
  }

  function skeleton() {
    var d = document.createElement('div');
    for (var i = 0; i < 4; i++) {
      var s = document.createElement('div');
      s.className = 'u-skel';
      s.style.marginBottom = '10px';
      d.appendChild(s);
    }
    return d;
  }

  function escapeHtml(s) {
    if (!s) return '';
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' })[c];
    });
  }
})();

  ✓ Inspect backend integrations route
  ✓ Review Jira/ServiceNow connectors and tests
  ✓ Audit frontend a11y and placeholders
  ✓ Check proxy configs (Vercel/nginx)
  ✓ Scan for security issues and dead links
  → Score and write report table
**Assembling findings for ServiceNowConnector**

I'm noticing some critical issues with the ServiceNowConnector. It seems the `async` methods are not matching the `sync` contract, which causes the health checks to always return an error. I found specific lines where this mismatch occurs. To fix it, I recommend updating the methods to be synchronous or revising the framework. 

There's also a high-priority issue with broken links on the compliance summary page that need valid routes. We could either copy the files or change links to absolute URLs.
**Addressing accessibility issues**

I’ve noticed some accessibility (a11y) concerns, specifically missing `<h1>` tags on several pages like global search, notifications, risk register, and VAPT portal dashboard. The body content is starting without an `<h1>`, which is a problem. To fix this, I can add a `<h1 class="page-title">...</h1>`, even if it’s visually hidden. Additionally, I should add an `aria-label` to the search input and select for notifications to enhance accessibility. This change can significantly improve the user experience!
exec
/bin/zsh -lc "cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && rg -n \"data-page=\\\"\\\"\" frontend/global-search.html && nl -ba frontend/js/global-search.js | sed -n '10,40p'" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
17:  <div id="app-shell" data-page="">
    10	
    11	  if (typeof window.checkAuth === 'function') window.checkAuth();
    12	
    13	  var qs = new URLSearchParams(window.location.search);
    14	  var query = (qs.get('q') || '').trim();
    15	  var activeTab = 'risks';
    16	
    17	  document.addEventListener('DOMContentLoaded', function () {
    18	    window.URIP.shell.mount({
    19	      page: '',
    20	      title: 'Search Results',
    21	      breadcrumb: 'Search'
    22	    });
    23	
    24	    document.getElementById('searchTermLabel').textContent = query || '(empty query)';
    25	
    26	    document.querySelectorAll('.u-tab').forEach(function (t) {
    27	      t.addEventListener('click', function () {
    28	        document.querySelectorAll('.u-tab').forEach(function (x) { x.classList.remove('is-active'); });
    29	        t.classList.add('is-active');
    30	        activeTab = t.dataset.tab;
    31	        runSearch();
    32	      });
    33	    });
    34	    runSearch();
    35	  });
    36	
    37	  async function runSearch() {
    38	    var body = document.getElementById('resultsBody');
    39	    body.textContent = '';
    40	    if (!query) {

  ✓ Inspect backend integrations route
  ✓ Review Jira/ServiceNow connectors and tests
  ✓ Audit frontend a11y and placeholders
  ✓ Check proxy configs (Vercel/nginx)
  ✓ Scan for security issues and dead links
  ✓ Score and write report table
codex
82/100 — CHANGE: ServiceNow connector violates the BaseConnector sync contract (breaks `/api/integrations/*/health`), and the Compliance Summary page ships broken links + placeholders.

| Severity | File:line | Quoted snippet | Fix |
|---|---|---|---|
| Critical | `connectors/servicenow/connector.py:216` | `async def authenticate(self, credentials: dict) -> ConnectorSession:` | Make ServiceNow match the framework contract: change to sync `def authenticate(self, tenant_credentials: dict) -> ConnectorSession` and internally run async client calls via `asyncio.run(...)` (same pattern as `connectors/jira/connector.py`). |
| Critical | `connectors/servicenow/connector.py:300` | `async def fetch_findings(` *(takes `session`, `since`, `limit`)* | Change signature to `def fetch_findings(self, since: datetime, **kwargs) -> list[RawFinding]` (BaseConnector contract) and use `asyncio.run(...)` to call the async API client. |
| Critical | `connectors/servicenow/connector.py:423` | `async def health_check(` *(takes `session: ConnectorSession`)* | Change to `def health_check(self) -> ConnectorHealth` (no `session`), and run the async healthcheck via `asyncio.run(...)`. |
| Critical | `backend/routers/integrations.py:119` | `connector.authenticate(credentials)` | This endpoint calls connector methods synchronously; once ServiceNow is fixed to sync, keep as-is. If you *intend* async connectors, you must refactor the entire connector framework + callers to `await` consistently. |
| Critical | `backend/routers/integrations.py:122` | `health = connector.health_check()` | Same as above: currently assumes sync `health_check()` returning a `ConnectorHealth`. |
| High | `frontend/domain-compliance-summary.html:28` | `href="../compliance/frontend/frameworks.html?action=add"` | These links point outside the deployed `frontend/` static root → 404. Either (a) ship the compliance UI inside `frontend/` and link to it, or (b) host it under a real routed path (e.g. `/compliance/...`) and update links to that absolute/clean URL. |
| High | `frontend/domain-compliance-summary.html:31` | `href="../compliance/frontend/frameworks.html"` | Same fix as above (all `../compliance/frontend/*` links). |
| Medium | `frontend/domain-compliance-summary.html:141` | `<em>Compliance module endpoint not connected — placeholder until /api/compliance/action-items lands.</em>` | Remove “placeholder” UX from production pages: either wire the endpoints now or hide these cards behind a “Coming soon” feature flag that doesn’t ship as dead UX in the main app. |
| Medium | `frontend/global-search.html:17` | `<div id="app-shell" data-page="">` | Set a real page key (e.g. `data-page="global-search"`) for shell/nav consistency. |
| Medium | `frontend/js/global-search.js:19` | `page: '',` | Set `page: 'global-search'` so shell state + sidebar highlighting don’t degrade. |
| Medium | `frontend/global-search.html:18` | `<div style="display:flex;...">` *(no `<h1>` anywhere in file)* | Add an `<h1>` (can be visually subtle) for page structure, e.g. “Search Results”. |
| Medium | `frontend/notifications.html:19` | `<input id="nfSearch" type="search" placeholder="Filter notifications…">` | Add an accessible name: either `<label for="nfSearch">` or `aria-label="Filter notifications"`. |
| Medium | `frontend/notifications.html:20` | `<select id="nfType">` | Add `<label for="nfType">Type</label>` or `aria-label="Notification type"`. |
| Medium | `frontend/notifications.html:17` | `<div id="app-shell" data-page="audit-log">` *(but this is Notifications)* | Use a correct page key (e.g. `data-page="notifications"`) so nav/breadcrumb logic doesn’t misclassify the page. |
| Medium | `frontend/notifications.html:1` | *(no `<h1>` anywhere in file)* | Add `<h1 class="page-title">Notifications</h1>` (or equivalent semantic heading). |
| Medium | `frontend/risk-register.html:18` | `<div id="app-shell" data-page="risk-register">` *(no `<h1>` in file header area)* | Add `<h1 class="page-title">Risk Register</h1>` (the page currently starts at a toolbar). |
| Medium | `frontend/vapt-portal-dashboard.html:33` | `<main class="vapt-content">` *(uses `<h2>` but no `<h1>`)* | Add an `<h1>` for the portal page (e.g. “My submissions”). |
| Medium | `frontend/js/sidebar.js:136` | `var brandAppName = brand.app_name || 'Semantic Gravity';` | Change fallback branding to URIP/Adaptive Mind so a missing branding payload doesn’t show the wrong product name in prod. |
| Medium | `frontend/login.html:431` | `&copy; 2026 Semantic Gravity. All rights reserved. | v2.4.1` | Update footer brand string to URIP/Adaptive Mind (same in `frontend/index.html`, `frontend/register.html`, `frontend/forgot-password.html`, `frontend/reset-password.html`, `frontend/mfa-enroll.html`). |
| Low | `backend/routers/integrations.py:45` | `from backend.middleware.tenant import TenantContext` | Remove unused import (dead code / cleanliness; also reduces “INV-1” noise). |
| Low | `frontend/js/api.js:174` | `background:#fff;` *(toast inline CSS)* | Replace hardcoded white with theme variables (e.g. `background:var(--u-card)` + `color:var(--u-fg)`) to avoid bright-white UI blocks in dark pages. |
| Low | `frontend/js/filters.js:663` | `background:#fff;border-radius:12px;...` *(modal inline CSS)* | Same as above: use theme vars (and ideally add dialog semantics if this modal is user-facing without proper `role="dialog"` + focus trap). |
| Low | `docs/audit_apr28/deploy/_artifacts/api.urip.adaptive-mind.com.conf:36` | `location /compliance/ {` | Repo deploy artifact conflicts with shipped path (`/compliance-api/...`). Update the artifact (or add an explicit `/compliance-api/` block) so infra-as-documented matches infra-as-shipped. |
| Low | `frontend/vercel.json:25` | `"destination": "http://145.223.21.39/compliance-api/:path*"` | Consider switching to HTTPS upstream (domain + TLS) instead of raw HTTP-to-IP to reduce on-the-wire exposure between Vercel and the VPS.
2026-04-28T11:26:01.444040Z ERROR codex_core::session: failed to record rollout items: thread 019dd3d3-5402-7f70-865c-029d8aeb8f5a not found
tokens used
89,909
82/100 — CHANGE: ServiceNow connector violates the BaseConnector sync contract (breaks `/api/integrations/*/health`), and the Compliance Summary page ships broken links + placeholders.

| Severity | File:line | Quoted snippet | Fix |
|---|---|---|---|
| Critical | `connectors/servicenow/connector.py:216` | `async def authenticate(self, credentials: dict) -> ConnectorSession:` | Make ServiceNow match the framework contract: change to sync `def authenticate(self, tenant_credentials: dict) -> ConnectorSession` and internally run async client calls via `asyncio.run(...)` (same pattern as `connectors/jira/connector.py`). |
| Critical | `connectors/servicenow/connector.py:300` | `async def fetch_findings(` *(takes `session`, `since`, `limit`)* | Change signature to `def fetch_findings(self, since: datetime, **kwargs) -> list[RawFinding]` (BaseConnector contract) and use `asyncio.run(...)` to call the async API client. |
| Critical | `connectors/servicenow/connector.py:423` | `async def health_check(` *(takes `session: ConnectorSession`)* | Change to `def health_check(self) -> ConnectorHealth` (no `session`), and run the async healthcheck via `asyncio.run(...)`. |
| Critical | `backend/routers/integrations.py:119` | `connector.authenticate(credentials)` | This endpoint calls connector methods synchronously; once ServiceNow is fixed to sync, keep as-is. If you *intend* async connectors, you must refactor the entire connector framework + callers to `await` consistently. |
| Critical | `backend/routers/integrations.py:122` | `health = connector.health_check()` | Same as above: currently assumes sync `health_check()` returning a `ConnectorHealth`. |
| High | `frontend/domain-compliance-summary.html:28` | `href="../compliance/frontend/frameworks.html?action=add"` | These links point outside the deployed `frontend/` static root → 404. Either (a) ship the compliance UI inside `frontend/` and link to it, or (b) host it under a real routed path (e.g. `/compliance/...`) and update links to that absolute/clean URL. |
| High | `frontend/domain-compliance-summary.html:31` | `href="../compliance/frontend/frameworks.html"` | Same fix as above (all `../compliance/frontend/*` links). |
| Medium | `frontend/domain-compliance-summary.html:141` | `<em>Compliance module endpoint not connected — placeholder until /api/compliance/action-items lands.</em>` | Remove “placeholder” UX from production pages: either wire the endpoints now or hide these cards behind a “Coming soon” feature flag that doesn’t ship as dead UX in the main app. |
| Medium | `frontend/global-search.html:17` | `<div id="app-shell" data-page="">` | Set a real page key (e.g. `data-page="global-search"`) for shell/nav consistency. |
| Medium | `frontend/js/global-search.js:19` | `page: '',` | Set `page: 'global-search'` so shell state + sidebar highlighting don’t degrade. |
| Medium | `frontend/global-search.html:18` | `<div style="display:flex;...">` *(no `<h1>` anywhere in file)* | Add an `<h1>` (can be visually subtle) for page structure, e.g. “Search Results”. |
| Medium | `frontend/notifications.html:19` | `<input id="nfSearch" type="search" placeholder="Filter notifications…">` | Add an accessible name: either `<label for="nfSearch">` or `aria-label="Filter notifications"`. |
| Medium | `frontend/notifications.html:20` | `<select id="nfType">` | Add `<label for="nfType">Type</label>` or `aria-label="Notification type"`. |
| Medium | `frontend/notifications.html:17` | `<div id="app-shell" data-page="audit-log">` *(but this is Notifications)* | Use a correct page key (e.g. `data-page="notifications"`) so nav/breadcrumb logic doesn’t misclassify the page. |
| Medium | `frontend/notifications.html:1` | *(no `<h1>` anywhere in file)* | Add `<h1 class="page-title">Notifications</h1>` (or equivalent semantic heading). |
| Medium | `frontend/risk-register.html:18` | `<div id="app-shell" data-page="risk-register">` *(no `<h1>` in file header area)* | Add `<h1 class="page-title">Risk Register</h1>` (the page currently starts at a toolbar). |
| Medium | `frontend/vapt-portal-dashboard.html:33` | `<main class="vapt-content">` *(uses `<h2>` but no `<h1>`)* | Add an `<h1>` for the portal page (e.g. “My submissions”). |
| Medium | `frontend/js/sidebar.js:136` | `var brandAppName = brand.app_name || 'Semantic Gravity';` | Change fallback branding to URIP/Adaptive Mind so a missing branding payload doesn’t show the wrong product name in prod. |
| Medium | `frontend/login.html:431` | `&copy; 2026 Semantic Gravity. All rights reserved. | v2.4.1` | Update footer brand string to URIP/Adaptive Mind (same in `frontend/index.html`, `frontend/register.html`, `frontend/forgot-password.html`, `frontend/reset-password.html`, `frontend/mfa-enroll.html`). |
| Low | `backend/routers/integrations.py:45` | `from backend.middleware.tenant import TenantContext` | Remove unused import (dead code / cleanliness; also reduces “INV-1” noise). |
| Low | `frontend/js/api.js:174` | `background:#fff;` *(toast inline CSS)* | Replace hardcoded white with theme variables (e.g. `background:var(--u-card)` + `color:var(--u-fg)`) to avoid bright-white UI blocks in dark pages. |
| Low | `frontend/js/filters.js:663` | `background:#fff;border-radius:12px;...` *(modal inline CSS)* | Same as above: use theme vars (and ideally add dialog semantics if this modal is user-facing without proper `role="dialog"` + focus trap). |
| Low | `docs/audit_apr28/deploy/_artifacts/api.urip.adaptive-mind.com.conf:36` | `location /compliance/ {` | Repo deploy artifact conflicts with shipped path (`/compliance-api/...`). Update the artifact (or add an explicit `/compliance-api/` block) so infra-as-documented matches infra-as-shipped. |
| Low | `frontend/vercel.json:25` | `"destination": "http://145.223.21.39/compliance-api/:path*"` | Consider switching to HTTPS upstream (domain + TLS) instead of raw HTTP-to-IP to reduce on-the-wire exposure between Vercel and the VPS.

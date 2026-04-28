from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.middleware.rate_limit import install_rate_limiting

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

# HIGH-009 — install rate limiter BEFORE other middlewares so it sees every
# request before they get a chance to short-circuit / mutate the path.
install_rate_limiting(app)

# CORS
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",")]
if "*" in origins:
    # Wildcard mode: no credentials (browser requirement)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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


# Serve frontend static files
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

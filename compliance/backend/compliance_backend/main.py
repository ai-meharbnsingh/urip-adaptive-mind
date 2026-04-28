"""
Compliance Service — FastAPI application entry point.

Port: 8001 (configurable via PORT env var)
Health: GET /health

Auth mode set via COMPLIANCE_AUTH_MODE:
  STANDALONE  — verifies Compliance-issued JWTs
  INTEGRATED  — verifies URIP-issued JWTs (shared secret)

CORS is configured for local development defaults; override via CORS_ORIGINS env var.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from compliance_backend.config import settings
from compliance_backend.middleware.rate_limit import install_rate_limiting
from compliance_backend.routers import frameworks as frameworks_router
from compliance_backend.routers import controls as controls_router
from compliance_backend.routers import evidence as evidence_router
from compliance_backend.routers import policies as policies_router
from compliance_backend.routers import auditor_invitations as auditor_invitations_router
from compliance_backend.routers import auditor as auditor_router
from compliance_backend.routers import compliance_score as compliance_score_router
from compliance_backend.routers import admin_auditor_activity as admin_auditor_activity_router
from compliance_backend.routers import admin_evidence_requests as admin_evidence_requests_router
from compliance_backend.routers import vendors as vendors_router  # NEW-4 — was unregistered
from compliance_backend.routers import framework_reports as framework_reports_router
from compliance_backend.routers import training_bgv_rollup as training_bgv_rollup_router

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Compliance & Audit-Readiness Service",
    description=(
        "Sprinto-equivalent compliance automation. "
        "Standalone or integrated with URIP. "
        f"Auth mode: {settings.COMPLIANCE_AUTH_MODE}"
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Rate limiting — HIGH-2 audit fix.
# Caps auditor invitation accept (5/min/IP) + all writes (60/min/IP).
# ---------------------------------------------------------------------------
install_rate_limiting(app)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(frameworks_router.router)
app.include_router(controls_router.router)
app.include_router(evidence_router.router)
app.include_router(policies_router.router)
app.include_router(auditor_invitations_router.router)
app.include_router(auditor_router.router)
app.include_router(compliance_score_router.router)
app.include_router(admin_auditor_activity_router.router)
app.include_router(admin_evidence_requests_router.router)
app.include_router(vendors_router.router)  # NEW-4 — vendors API now reachable
app.include_router(framework_reports_router.router)  # PART 1 — framework-specific reports
app.include_router(training_bgv_rollup_router.router)  # PART 4 — LMS/BGV dashboard widget


# ---------------------------------------------------------------------------
# Health endpoint — no auth required
# ---------------------------------------------------------------------------

@app.get("/health", tags=["health"])
async def health() -> dict:
    """Service health check. Returns 200 OK with service identity."""
    return {
        "status": "ok",
        "service": "compliance",
        "auth_mode": settings.COMPLIANCE_AUTH_MODE,
    }

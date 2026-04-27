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
from compliance_backend.routers import frameworks as frameworks_router

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
# Routers
# ---------------------------------------------------------------------------

app.include_router(frameworks_router.router)


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

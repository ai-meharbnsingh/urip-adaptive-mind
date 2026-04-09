from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings

app = FastAPI(
    title="URIP - Unified Risk Intelligence Platform",
    description="Cybersecurity risk aggregation and management platform by Semantic Gravity",
    version="1.0.0",
)

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
from backend.routers import acceptance, audit_log, auth, dashboard, remediation, reports, risks, settings as settings_router  # noqa: E402

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(risks.router, prefix="/api/risks", tags=["Risks"])
app.include_router(acceptance.router, prefix="/api/acceptance", tags=["Acceptance"])
app.include_router(remediation.router, prefix="/api/remediation", tags=["Remediation"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(audit_log.router, prefix="/api/audit-log", tags=["Audit Log"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["Settings"])

# Serve frontend static files
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

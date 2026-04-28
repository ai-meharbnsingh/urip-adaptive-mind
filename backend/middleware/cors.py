from __future__ import annotations

from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings


# Gemini LOW finding (AUDIT_GEMINI_TRI_A.md:11) — renamed to _DEV_DEFAULT_ORIGINS
# (private, underscore prefix) to signal that this is only a dev convenience
# fallback.  Production deployments MUST set CORS_ORIGINS in .env.prod
# (see .env.prod.template) — the env-driven path is always preferred.
_DEV_DEFAULT_ORIGINS = [
    "http://localhost:8088",
    "https://urip.adaptive-mind.com",
]


def _parse_origins(raw: str) -> list[str]:
    parts = [p.strip() for p in (raw or "").split(",")]
    return [p for p in parts if p and p != "*"]


def install_cors(app) -> None:
    origins = _parse_origins(settings.CORS_ORIGINS)
    if not origins:
        # Fall back to dev defaults only when no env-driven config is present.
        origins = list(_DEV_DEFAULT_ORIGINS)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

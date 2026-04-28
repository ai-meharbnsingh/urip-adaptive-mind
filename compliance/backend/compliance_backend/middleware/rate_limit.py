"""
HIGH-2 — Compliance backend rate limiting.

Ports the URIP-side ``backend/middleware/rate_limit.py`` policy to the
Compliance service so:
  * auth-shaped endpoints (the public ``/auditor-invitations/accept``) are
    capped at 5 requests / minute / real-client IP — slows down brute-force
    enumeration of invitation tokens.
  * all writes (POST/PUT/PATCH/DELETE under ``/...`` apart from ``/health``)
    are capped at 60 / minute / real-client IP — defends every state-changing
    surface against accidental floods.

Trusted-proxy handling matches URIP: ``X-Forwarded-For`` is honoured ONLY
when the immediate TCP peer is in ``TRUSTED_PROXY_IPS`` (CIDR list, or ``*``
for "trust everything" — tests/dev only).

When the underlying limits storage backend errors, we **fail open** with a
warning log. Failing closed would convert a Redis blip into an outage on
every compliance write.

Failure mode on quota exceeded → 429 JSON + ``Retry-After`` header.
"""
from __future__ import annotations

import ipaddress
import logging
import os
from typing import Iterable, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler  # noqa: F401
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trusted-proxy-aware real-IP extractor — copy-equivalent to URIP backend.
# We deliberately duplicate (rather than import from `backend.middleware`)
# because the compliance service is its own deployable; coupling the import
# graph would create a build-time dependency on the URIP backend package.
# ---------------------------------------------------------------------------

def _trusted_proxies() -> list[str]:
    raw = os.environ.get("TRUSTED_PROXY_IPS", "").strip()
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def _is_peer_trusted(peer_ip: str, trust_list: Iterable[str]) -> bool:
    for entry in trust_list:
        if entry == "*":
            return True
        if "/" in entry:
            try:
                if ipaddress.ip_address(peer_ip) in ipaddress.ip_network(
                    entry, strict=False
                ):
                    return True
            except ValueError:
                continue
        else:
            if peer_ip == entry:
                return True
    return False


def real_client_ip(request: Request) -> str:
    """Real-client IP, honouring XFF only when the peer is trusted."""
    peer_ip = request.client.host if request.client else "unknown"
    trust = _trusted_proxies()
    if trust and _is_peer_trusted(peer_ip, trust):
        xff = request.headers.get("x-forwarded-for")
        if xff:
            candidate = xff.split(",")[0].strip()
            if candidate:
                return candidate
    return peer_ip


# ---------------------------------------------------------------------------
# Limiter
# ---------------------------------------------------------------------------

_DEFAULT_STORAGE = os.environ.get(
    "COMPLIANCE_RATE_LIMIT_STORAGE_URI", "memory://"
)

limiter = Limiter(
    key_func=real_client_ip,
    storage_uri=_DEFAULT_STORAGE,
    default_limits=[],
    headers_enabled=True,
)


# ---------------------------------------------------------------------------
# Per-path policy
# ---------------------------------------------------------------------------

# (method, path_prefix, limit_string) — first match wins.
# /auditor-invitations/accept is the public token-exchange endpoint — the
# closest analogue to a login on the compliance side, so it gets the
# auth-style 5/minute cap.
_PATH_POLICIES: list[tuple[str, str, str]] = [
    ("POST", "/auditor-invitations/accept", "5/minute"),
    # Generic write cap — applies to every POST/PUT/PATCH/DELETE on the
    # compliance API. Exempting /health is unnecessary because /health is
    # GET-only.
    ("POST",   "/", "60/minute"),
    ("PUT",    "/", "60/minute"),
    ("PATCH",  "/", "60/minute"),
    ("DELETE", "/", "60/minute"),
]


def _match_policy(method: str, path: str) -> Optional[tuple[str, str]]:
    """Return (limit_str, policy_prefix_for_namespacing) or None."""
    for m, prefix, limit_str in _PATH_POLICIES:
        if m.upper() != method.upper():
            continue
        if path.startswith(prefix):
            return limit_str, prefix
    return None


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class ComplianceRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-request rate-limit gate for the Compliance service.

    Delegates to slowapi's lower-level limits storage so individual routers
    don't need to be decorated.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        method = request.method
        path = request.url.path
        match = _match_policy(method, path)
        if match is None:
            return await call_next(request)

        limit_str, scope_prefix = match

        from limits import parse
        try:
            limit_obj = parse(limit_str)
        except Exception as exc:
            logger.warning(
                "compliance rate-limit: bad limit string %r — failing open: %s",
                limit_str, exc,
            )
            return await call_next(request)

        key = real_client_ip(request)
        scope = f"{method}:{scope_prefix}"
        try:
            allowed = limiter.limiter.hit(limit_obj, scope, key)
        except Exception as exc:
            logger.warning(
                "compliance rate-limit storage error: %s — failing open", exc,
            )
            return await call_next(request)

        if not allowed:
            try:
                window = limiter.limiter.get_window_stats(limit_obj, scope, key)
                reset_at = int(window[0])
            except Exception:
                reset_at = 0
            seconds = max(1, reset_at - _now()) if reset_at else 60
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        f"Rate limit exceeded for {method} {path}. "
                        f"Try again in {seconds}s."
                    ),
                },
                headers={"Retry-After": str(seconds)},
            )
        return await call_next(request)


def _now() -> int:
    import time
    return int(time.time())


# ---------------------------------------------------------------------------
# Public helper for main.py wiring
# ---------------------------------------------------------------------------

def install_rate_limiting(app) -> None:
    """Attach limiter + middleware + 429 handler to a FastAPI app (idempotent)."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(ComplianceRateLimitMiddleware)

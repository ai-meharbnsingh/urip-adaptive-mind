"""
HIGH-009 — Rate limiting that survives a reverse proxy.

Why this exists
---------------
The legacy in-router limiter keys on ``request.client.host``. Behind nginx,
cloudflare, vercel, k8s ingress etc. this is always the proxy's IP, so every
attacker shares one bucket and the limiter is effectively global.

What this module does
---------------------
1. Builds a single :class:`slowapi.Limiter` keyed by the *real* client IP.
2. The real-IP extractor reads ``X-Forwarded-For`` ONLY when the immediate
   peer is in the ``TRUSTED_PROXY_IPS`` env var (comma-separated CIDRs / IPs
   or ``*`` for "trust everything" — ``*`` is intended for tests + dev only).
3. Provides per-path rate-limit configuration applied via a small
   ``BaseHTTPMiddleware`` so individual routers do not need to change.

Limits applied (HIGH-009 brief)
-------------------------------
* ``POST /api/auth/login``       — 5 / minute / IP
* ``GET  /api/auth/me``          — 60 / minute / user (or IP)
* All write methods (POST/PUT/PATCH/DELETE) — 60 / minute / user (or IP)

Failure mode
------------
On limit exceeded the middleware short-circuits with a 429 JSON response. We
register slowapi's :func:`_rate_limit_exceeded_handler` so consumers also get a
``Retry-After`` header.
"""
from __future__ import annotations

import ipaddress
import logging
import os
from typing import Iterable, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler  # noqa: F401 — re-exported
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address  # noqa: F401 — kept for parity
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trusted-proxy-aware real-IP extractor
# ---------------------------------------------------------------------------

def _trusted_proxies() -> list[str]:
    raw = os.environ.get("TRUSTED_PROXY_IPS", "").strip()
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def _is_peer_trusted(peer_ip: str, trust_list: Iterable[str]) -> bool:
    """
    True if ``peer_ip`` (the immediate TCP peer) is in the trust list.
    ``*`` means "trust everything" — only safe for tests / single-process dev.
    Each entry may be a plain IP or CIDR.
    """
    for entry in trust_list:
        if entry == "*":
            return True
        if "/" in entry:
            try:
                if ipaddress.ip_address(peer_ip) in ipaddress.ip_network(entry, strict=False):
                    return True
            except ValueError:
                continue
        else:
            if peer_ip == entry:
                return True
    return False


def real_client_ip(request: Request) -> str:
    """
    Return the real client IP, honouring X-Forwarded-For only when the
    immediate peer is in ``TRUSTED_PROXY_IPS``.
    """
    peer_ip = request.client.host if request.client else "unknown"
    trust = _trusted_proxies()
    if trust and _is_peer_trusted(peer_ip, trust):
        xff = request.headers.get("x-forwarded-for")
        if xff:
            # leftmost IP = the original client (RFC 7239 / Forwarded-For convention)
            candidate = xff.split(",")[0].strip()
            if candidate:
                return candidate
    return peer_ip


# ---------------------------------------------------------------------------
# Limiter
# ---------------------------------------------------------------------------

# Configurable storage backend.
#
# Dev/test default: "memory://" — rate-limit state is process-local and resets
# on every restart.  This is intentional for local development.
#
# PRODUCTION REQUIREMENT: set RATE_LIMIT_STORAGE_URI=redis://redis:6379/1 in
# your .env.prod file (see .env.prod.template in the project root).  Without
# Redis the limiter resets on every pod restart — an attacker can brute-force
# /api/auth/login by simply waiting for a deploy.
#
# Gemini MEDIUM finding (AUDIT_GEMINI_TRI_A.md:65): ensure prod uses Redis.
# Codex round-B CRIT (AUDIT_CODEX_TRI_B.md): tests reference rl._DEFAULT_STORAGE
# in teardown — expose the dev default as a stable module attribute so test
# fixtures can restore limiter state without coupling to private internals.
_DEFAULT_STORAGE = "memory://"
_RATE_LIMIT_STORAGE_URI = os.environ.get("RATE_LIMIT_STORAGE_URI", _DEFAULT_STORAGE)

# Emit a runtime warning when running in production-like conditions without
# a durable rate-limit backend.  URIP_ENV=production triggers this guard.
if _RATE_LIMIT_STORAGE_URI == "memory://":
    _env = os.environ.get("URIP_ENV", "").lower()
    if _env in ("production", "prod", "staging"):
        logger.warning(
            "rate_limit: storage backend is 'memory://' in env=%s — "
            "rate limits will reset on every restart. "
            "Set RATE_LIMIT_STORAGE_URI=redis://redis:6379/1 in .env.prod.",
            _env,
        )

limiter = Limiter(
    key_func=real_client_ip,
    storage_uri=_RATE_LIMIT_STORAGE_URI,
    default_limits=[],  # no implicit global limit; explicit per-path
    headers_enabled=True,
)


# ---------------------------------------------------------------------------
# Per-path policy
# ---------------------------------------------------------------------------

# (method_or_*, path_prefix, limit_string) — first match wins.
_PATH_POLICIES: list[tuple[str, str, str]] = [
    ("POST", "/api/auth/login", "5/minute"),
    ("POST", "/api/auth/register", "3/minute"),
    ("POST", "/api/auth/forgot-password", "3/minute"),
    ("GET",  "/api/auth/me",    "60/minute"),
    # Generic write cap — applied to any POST/PUT/PATCH/DELETE under /api/
    ("POST",   "/api/", "60/minute"),
    ("PUT",    "/api/", "60/minute"),
    ("PATCH",  "/api/", "60/minute"),
    ("DELETE", "/api/", "60/minute"),
]


def _match_policy(method: str, path: str) -> Optional[str]:
    for m, prefix, limit_str in _PATH_POLICIES:
        if m != "*" and m.upper() != method.upper():
            continue
        if path.startswith(prefix):
            return limit_str
    return None


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-request rate-limit gate.

    Implementation note: slowapi's ``Limiter.limit`` decorator is the usual
    integration point, but it has to wrap each route. Touching the auth router
    is off-limits for this fix, so we drive the underlying ``limits``
    storage directly via :meth:`Limiter.limit`'s ``hit`` semantics through
    a synthetic LimitItem.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        method = request.method
        path = request.url.path
        limit_str = _match_policy(method, path)
        if limit_str is None:
            return await call_next(request)

        # Use slowapi's lower-level interface: parse the limit string and call
        # the underlying limiter storage to test+hit atomically.
        from limits import parse
        limit_obj = parse(limit_str)
        key = real_client_ip(request)
        # Namespace the bucket by (method, path-prefix, key) so /auth/login and
        # the generic write cap maintain independent counters.
        scope = f"{method}:{_policy_scope(method, path)}"
        try:
            allowed = limiter.limiter.hit(limit_obj, scope, key)
        except Exception as exc:
            # M10 (Codex MED-005) — Storage backend failure used to FAIL-OPEN
            # (allow the request through). That is precisely the wrong default
            # for the auth-login bucket: during a Redis outage an attacker
            # gets unlimited brute-force attempts on /api/auth/login.
            #
            # New behaviour:
            #   * High-risk endpoints (auth/login)        → FAIL-CLOSED (503)
            #   * Generic write cap (POST/PUT/PATCH/DEL)  → fail-open + warn
            #     (preserves availability of the bulk of the API during a
            #     limiter outage; the auth bucket carries the security-
            #     critical brute-force protection on its own).
            logger.warning("rate-limit storage error: %s", exc)
            if path.startswith("/api/auth/login") and method.upper() == "POST":
                return JSONResponse(
                    status_code=503,
                    content={
                        "detail": (
                            "Rate-limit backend unavailable; refusing login "
                            "to prevent brute-force during outage."
                        ),
                    },
                    headers={"Retry-After": "60"},
                )
            logger.warning("rate-limit fail-open for %s %s", method, path)
            return await call_next(request)

        if not allowed:
            retry_after = limiter.limiter.get_window_stats(limit_obj, scope, key)
            # get_window_stats returns (reset_at_epoch, remaining)
            seconds = max(1, int(retry_after[0] - _now()))
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


def _policy_scope(method: str, path: str) -> str:
    """Return the path-prefix that matched for namespacing the bucket."""
    for m, prefix, _ in _PATH_POLICIES:
        if m != "*" and m.upper() != method.upper():
            continue
        if path.startswith(prefix):
            return prefix
    return path


def _now() -> int:
    import time
    return int(time.time())


# ---------------------------------------------------------------------------
# Helper exposed to main.py for app wiring
# ---------------------------------------------------------------------------

def install_rate_limiting(app) -> None:
    """
    Attach the limiter + middleware + 429 handler to a FastAPI app.

    Idempotent: calling twice will simply re-register, which is harmless for
    Starlette's middleware stack but should be avoided by callers.
    """
    # Allow explicit opt-out for dev harnesses.
    if os.environ.get("URIP_DISABLE_RATE_LIMITING") in {"1", "true", "True"}:
        return
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(RateLimitMiddleware)

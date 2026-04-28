"""
Settings for the Compliance Service.

Two auth modes:
  STANDALONE  — Compliance issues + verifies its own JWTs (COMPLIANCE_JWT_SECRET)
  INTEGRATED  — URIP issues JWT; Compliance verifies using shared secret (URIP_JWT_SECRET)

DB:
  Separate Postgres at localhost:5434 (different from URIP's 5433) in production.
  In tests overridden to SQLite via COMPLIANCE_DB_URL env var.

Audit-fix CRIT-G2 / CODEX-CRIT-001 / KIMI-CRIT-002 / CLAUDE-CRIT-B
-------------------------------------------------------------------
The previous version shipped both JWT secrets with default placeholder
values (`change-me-in-production`, `urip-shared-secret`) and had NO startup
gate. A misconfigured production deployment that forgot to set the env
vars would silently mint forgeable JWTs — anyone who can read this repo
could forge tokens with arbitrary `tenant_id` and `role`. This file now
implements `_enforce_jwt_secret_policy()` mirroring `backend/config.py`:
  - In production-like envs (COMPLIANCE_ENV in {prod, production, staging})
    we raise ConfigError on import if either secret equals its default or
    is empty.
  - In dev we warn loudly so the operator cannot miss the rotation step.
"""
import os
import sys
import warnings

from pydantic_settings import BaseSettings


class ConfigError(RuntimeError):
    """Raised when the compliance backend configuration is unsafe / inconsistent."""


# Sentinel default values that MUST NOT ship to production. Detected on
# startup; presence in a production-like env triggers ConfigError.
DEV_DEFAULT_COMPLIANCE_SECRET = "change-me-in-production"
DEV_DEFAULT_URIP_SECRET = "urip-shared-secret"
PRODUCTION_LIKE_ENVS = {"prod", "production", "staging"}


class Settings(BaseSettings):
    # Service identity
    SERVICE_NAME: str = "compliance"
    PORT: int = 8001

    # Deployment environment marker — used by _enforce_jwt_secret_policy to
    # decide whether the dev defaults are acceptable (dev only).
    COMPLIANCE_ENV: str = "dev"

    # Auth mode
    COMPLIANCE_AUTH_MODE: str = "STANDALONE"  # STANDALONE | INTEGRATED

    # Secrets
    # NOTE: Defaults are intentionally the historical placeholder strings so
    # `_enforce_jwt_secret_policy` can detect "operator forgot to set the env
    # var" reliably. In any production-like env, startup REFUSES to proceed
    # with these values. In dev, a loud warning is emitted.
    COMPLIANCE_JWT_SECRET: str = DEV_DEFAULT_COMPLIANCE_SECRET
    URIP_JWT_SECRET: str = DEV_DEFAULT_URIP_SECRET

    # Database — default points at compliance_db on port 5434
    # Tests override this with sqlite+aiosqlite:///:memory:
    COMPLIANCE_DB_URL: str = (
        "postgresql+asyncpg://compliance:compliance@localhost:5434/compliance_db"
    )

    # CORS — M3 (Gemini MED, Kimi MED-005, Codex MED-006).
    # Was: hardcoded localhost defaults that quietly applied in production.
    # Now: empty list by default; in production-like envs we REFUSE to start
    # without an explicit `COMPLIANCE_CORS_ORIGINS` env var (deny-all is the
    # only safe default).  Dev keeps localhost convenience by reading
    # COMPLIANCE_CORS_ORIGINS (comma-separated) or falling back to localhost.
    # Field name aliases the prod-style env var so deployers do not have to
    # learn yet another var name.
    COMPLIANCE_CORS_ORIGINS: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def CORS_ORIGINS(self) -> list[str]:
        """Resolve allowed origins per environment.

        - production-like: must be set via COMPLIANCE_CORS_ORIGINS, else [].
          (`_enforce_cors_policy()` further refuses `*` in prod since
          `allow_credentials=True` would expose authenticated endpoints.)
        - dev: COMPLIANCE_CORS_ORIGINS if set, else localhost defaults.
        """
        env = (
            os.getenv("COMPLIANCE_ENV") or self.COMPLIANCE_ENV or ""
        ).strip().lower()
        raw = (self.COMPLIANCE_CORS_ORIGINS or "").strip()
        if raw:
            return [o.strip() for o in raw.split(",") if o.strip()]
        if env in PRODUCTION_LIKE_ENVS:
            # Deny-all: no defaults in production. Operator MUST set the env
            # var explicitly. Better a CORS error than silently letting a
            # forgotten origin through.
            return []
        # Dev convenience: legacy local frontends.
        return ["http://localhost:3001", "http://localhost:3000"]


def _enforce_jwt_secret_policy(s: Settings) -> None:
    """Refuse to start in production-like envs with unrotated dev secrets.

    Loudly warn in dev so the operator cannot miss the rotation requirement.
    Mirror of `backend.config._enforce_jwt_secret_policy` for the URIP side.
    """
    env = (os.getenv("COMPLIANCE_ENV") or s.COMPLIANCE_ENV or "").strip().lower()
    compliance_secret = s.COMPLIANCE_JWT_SECRET or ""
    urip_secret = s.URIP_JWT_SECRET or ""

    compliance_is_default = compliance_secret == DEV_DEFAULT_COMPLIANCE_SECRET
    compliance_is_empty = compliance_secret == ""
    urip_is_default = urip_secret == DEV_DEFAULT_URIP_SECRET
    urip_is_empty = urip_secret == ""

    if env in PRODUCTION_LIKE_ENVS:
        if compliance_is_empty:
            raise ConfigError(
                "COMPLIANCE_JWT_SECRET is empty in production-like environment "
                f"(COMPLIANCE_ENV={env!r}). Refusing to start. "
                "Generate a strong secret and set COMPLIANCE_JWT_SECRET before deploying."
            )
        if compliance_is_default:
            raise ConfigError(
                "COMPLIANCE_JWT_SECRET is set to the well-known default "
                f"({DEV_DEFAULT_COMPLIANCE_SECRET!r}) in a production-like "
                f"environment (COMPLIANCE_ENV={env!r}). Refusing to start. "
                "Rotate the secret before deploying."
            )
        if urip_is_empty:
            raise ConfigError(
                "URIP_JWT_SECRET is empty in production-like environment "
                f"(COMPLIANCE_ENV={env!r}). Refusing to start. "
                "Set URIP_JWT_SECRET to the same value used by the URIP backend."
            )
        if urip_is_default:
            raise ConfigError(
                "URIP_JWT_SECRET is set to the well-known default "
                f"({DEV_DEFAULT_URIP_SECRET!r}) in a production-like "
                f"environment (COMPLIANCE_ENV={env!r}). Refusing to start. "
                "Rotate the secret before deploying (must match URIP backend)."
            )
        # Defence-in-depth: distinct secrets so a leak of one does not
        # forge tokens accepted by the other auth mode.
        if compliance_secret == urip_secret:
            raise ConfigError(
                "COMPLIANCE_JWT_SECRET and URIP_JWT_SECRET must be DIFFERENT "
                "in production-like environments. A leaked URIP token signing "
                "key must not be sufficient to forge auditor-portal JWTs."
            )
        return

    # Dev / unset env — allow but warn loudly
    issues: list[str] = []
    if compliance_is_default or compliance_is_empty:
        issues.append("COMPLIANCE_JWT_SECRET")
    if urip_is_default or urip_is_empty:
        issues.append("URIP_JWT_SECRET")
    if issues:
        msg = (
            f"[COMPLIANCE CONFIG WARNING] {' and '.join(issues)} is using a "
            "default / empty value. Acceptable in dev ONLY. You MUST rotate "
            "before any prod / staging deployment (set COMPLIANCE_ENV=production "
            "and supply real secrets)."
        )
        # stderr so it shows up in container logs, plus the warnings module
        # so tests can see it.
        print(msg, file=sys.stderr, flush=True)
        warnings.warn(msg, RuntimeWarning, stacklevel=2)


def _enforce_cors_policy(s: Settings) -> None:
    """M3 / Kimi MED-005 / Codex MED-006 — refuse unsafe CORS in production.

    Wildcard origins combined with `allow_credentials=True` would let any
    site read authenticated responses. We refuse to start when both apply.
    """
    env = (os.getenv("COMPLIANCE_ENV") or s.COMPLIANCE_ENV or "").strip().lower()
    origins = s.CORS_ORIGINS
    if env in PRODUCTION_LIKE_ENVS:
        if "*" in origins:
            raise ConfigError(
                "COMPLIANCE_CORS_ORIGINS contains '*' in production-like "
                f"environment (COMPLIANCE_ENV={env!r}). Wildcard origins "
                "with allow_credentials=True expose authenticated endpoints "
                "to any site. Refusing to start. Set explicit origins."
            )


# Singleton — re-read from env each module load so tests can monkeypatch
def get_settings() -> Settings:
    s = Settings()
    _enforce_jwt_secret_policy(s)
    _enforce_cors_policy(s)
    return s


settings = get_settings()

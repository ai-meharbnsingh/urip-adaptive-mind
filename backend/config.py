"""
URIP backend configuration.

Security note (CRIT-004):
- The dev default JWT_SECRET_KEY is `urip-dev-secret-change-in-production`.
  This MUST be rotated before any production-like deployment.  We refuse to
  start if URIP_ENV is one of {prod, production, staging} AND the secret is
  empty or equal to the dev default.  In dev (URIP_ENV unset or = dev /
  development) the dev default is allowed but a loud warning is emitted to
  stderr so the operator can never miss the rotation requirement.
"""

import os
import sys
import warnings

from pydantic_settings import BaseSettings


class ConfigError(RuntimeError):
    """Raised when the backend configuration is unsafe / inconsistent."""


# Sentinel for the well-known dev default that MUST NOT ship to production
DEV_DEFAULT_JWT_SECRET = "urip-dev-secret-change-in-production"
PRODUCTION_LIKE_ENVS = {"prod", "production", "staging"}


class Settings(BaseSettings):
    # Deployment environment marker — used by _enforce_jwt_secret_policy to
    # decide whether the dev default secret is acceptable (dev only).
    URIP_ENV: str = "dev"

    DATABASE_URL: str = "postgresql+asyncpg://urip:urip_dev@localhost:5432/urip"
    DATABASE_URL_SYNC: str = "postgresql://urip:urip_dev@localhost:5432/urip"
    REDIS_URL: str = ""
    JWT_SECRET_KEY: str = DEV_DEFAULT_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 8
    URIP_FERNET_KEY: str = ""
    CORS_ORIGINS: str = "http://localhost:8000,http://localhost:3000"

    # Connector API Keys (populated when RE provides access)
    CROWDSTRIKE_CLIENT_ID: str = ""
    CROWDSTRIKE_CLIENT_SECRET: str = ""
    ARMIS_API_KEY: str = ""
    ZSCALER_API_KEY: str = ""
    CYBERARK_API_KEY: str = ""
    OTX_API_KEY: str = ""
    VIRUSTOTAL_API_KEY: str = ""
    JIRA_URL: str = ""
    JIRA_API_TOKEN: str = ""
    SERVICENOW_URL: str = ""
    SERVICENOW_API_TOKEN: str = ""

    # ─── Scoring Configuration (overridable via env vars) ─────
    # Composite formula weights
    COMPOSITE_CVSS_WEIGHT: float = 0.55
    COMPOSITE_EPSS_WEIGHT: float = 2.5
    COMPOSITE_KEV_BONUS: float = 2.0

    # Asset tier bonuses
    TIER_1_BONUS: float = 1.0
    TIER_2_BONUS: float = 0.5
    TIER_3_BONUS: float = 0.0
    TIER_4_BONUS: float = -0.5

    # EPSS defaults when no CVE data
    EPSS_DEFAULT_CRITICAL: float = 0.30
    EPSS_DEFAULT_HIGH: float = 0.20
    EPSS_DEFAULT_MEDIUM: float = 0.10
    EPSS_DEFAULT_LOW: float = 0.05

    # Exploit status thresholds
    EXPLOIT_ACTIVE_THRESHOLD: float = 0.5
    EXPLOIT_POC_THRESHOLD: float = 0.1

    # CVSS severity breakpoints
    CVSS_CRITICAL_THRESHOLD: float = 9.0
    CVSS_HIGH_THRESHOLD: float = 7.0
    CVSS_MEDIUM_THRESHOLD: float = 4.0

    # SLA hours per severity
    SLA_HOURS_CRITICAL: int = 72
    SLA_HOURS_HIGH: int = 168
    SLA_HOURS_MEDIUM: int = 720
    SLA_HOURS_LOW: int = 2160

    # External API URLs
    EPSS_API_URL: str = "https://api.first.org/data/v1/epss"
    KEV_CATALOG_URL: str = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    MITRE_ATTACK_URL: str = "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"

    # Cache TTLs (seconds)
    KEV_CACHE_TTL_SECONDS: int = 86400
    MITRE_CACHE_TTL_SECONDS: int = 86400

    # Relevance scoring weights (threat intel)
    RELEVANCE_BRAND_SCORE: float = 40.0
    RELEVANCE_COUNTRY_SCORE: float = 25.0
    RELEVANCE_SECTOR_SCORE: float = 20.0
    RELEVANCE_RANSOMWARE_SCORE: float = 10.0

    # Acceptance review period
    ACCEPTANCE_REVIEW_PERIOD_DAYS: int = 90

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Accept and ignore unknown env keys so newly-added settings on .env
        # do not crash this loader (e.g. cross-worker config drift).
        extra = "ignore"


def _enforce_jwt_secret_policy(s: Settings) -> None:
    """Refuse to start in production-like envs with the unrotated dev secret.

    Loudly warn in dev so the operator cannot miss the requirement.
    """
    urip_env = (os.getenv("URIP_ENV") or "").strip().lower()
    secret = s.JWT_SECRET_KEY or ""

    is_default = secret == DEV_DEFAULT_JWT_SECRET
    is_empty = secret == ""

    if urip_env in PRODUCTION_LIKE_ENVS:
        if is_empty:
            raise ConfigError(
                "JWT_SECRET_KEY is empty in production-like environment "
                f"(URIP_ENV={urip_env!r}). Refusing to start. "
                "Generate a long random secret and set JWT_SECRET_KEY before deploying."
            )
        if is_default:
            raise ConfigError(
                "JWT_SECRET_KEY is set to the well-known dev default value "
                "(urip-dev-secret-change-in-production) in a production-like "
                f"environment (URIP_ENV={urip_env!r}). Refusing to start. "
                "Rotate the secret before deploying."
            )
        return

    # Dev / unset env — allow but warn loudly
    if is_default or is_empty:
        msg = (
            "[URIP CONFIG WARNING] JWT_SECRET_KEY is using the dev default "
            "(urip-dev-secret-change-in-production). This is acceptable in dev "
            "ONLY. You MUST rotate this secret before any prod / staging "
            "deployment (set URIP_ENV=production and a real JWT_SECRET_KEY)."
        )
        # stderr so it shows in container logs, plus the warnings module so
        # tests / pytest can see it via the warnings mechanism.
        print(msg, file=sys.stderr, flush=True)
        warnings.warn(msg, RuntimeWarning, stacklevel=2)


settings = Settings()
_enforce_jwt_secret_policy(settings)

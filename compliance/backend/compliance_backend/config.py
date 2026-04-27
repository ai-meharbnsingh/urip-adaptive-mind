"""
Settings for the Compliance Service.

Two auth modes:
  STANDALONE  — Compliance issues + verifies its own JWTs (COMPLIANCE_JWT_SECRET)
  INTEGRATED  — URIP issues JWT; Compliance verifies using shared secret (URIP_JWT_SECRET)

DB:
  Separate Postgres at localhost:5434 (different from URIP's 5433) in production.
  In tests overridden to SQLite via COMPLIANCE_DB_URL env var.
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Service identity
    SERVICE_NAME: str = "compliance"
    PORT: int = 8001

    # Auth mode
    COMPLIANCE_AUTH_MODE: str = "STANDALONE"  # STANDALONE | INTEGRATED

    # Secrets
    COMPLIANCE_JWT_SECRET: str = "change-me-in-production"
    URIP_JWT_SECRET: str = "urip-shared-secret"

    # Database — default points at compliance_db on port 5434
    # Tests override this with sqlite+aiosqlite:///:memory:
    COMPLIANCE_DB_URL: str = (
        "postgresql+asyncpg://compliance:compliance@localhost:5434/compliance_db"
    )

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3001", "http://localhost:3000"]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Singleton — re-read from env each module load so tests can monkeypatch
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

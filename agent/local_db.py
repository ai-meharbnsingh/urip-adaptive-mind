"""
agent/local_db.py — Local Postgres helper for the on-prem URIP agent.

Owns ONLY the tenant-data tables (risks, audit_log, connector data).
The cloud-side compliance / tenant-mgmt tables (Tenant, User, Subscriptions,
ComplianceFramework, etc.) are NOT part of the agent — they live in the cloud.

On first boot the agent calls `init_db()` which creates the minimal schema
required for raw findings + audit log if those tables don't exist.

Notes
-----
- We deliberately reuse the existing SQLAlchemy models (`backend.models.risk.Risk`,
  `backend.models.audit_log.AuditLog`, `backend.models.connector.ConnectorConfig`,
  `backend.models.tenant_connector_credential.TenantConnectorCredential`) so
  there is ONE schema definition.  But we filter `Base.metadata.tables` to only
  create the data-tier tables — never compliance, never tenant management.
- LOCAL_DB_URL is taken from env.  Default is the docker-compose-managed Postgres
  bundled with the agent (postgresql+asyncpg://urip:urip_dev@postgres:5432/urip_agent).
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

# Tables the agent owns (raw, sensitive data — stays on customer network forever).
# Anything NOT in this set is cloud-only and must not be created on the agent.
AGENT_OWNED_TABLES = frozenset(
    {
        "risks",
        "risk_history",
        "audit_log",
        "connector_configs",
        "tenant_connector_credentials",
    }
)


def get_local_db_url() -> str:
    """Resolve the local agent DB URL from env."""
    return os.getenv(
        "LOCAL_DB_URL",
        "postgresql+asyncpg://urip:urip_dev@postgres:5432/urip_agent",
    )


def make_engine(db_url: Optional[str] = None) -> AsyncEngine:
    """Build the async engine.  Caller owns disposal."""
    return create_async_engine(db_url or get_local_db_url(), echo=False)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> list[str]:
    """
    Create the agent-owned tables on first boot.

    Reads `Base.metadata` from backend.database (the SAME metadata used in
    the cloud build), then filters to only AGENT_OWNED_TABLES.  Tables that
    already exist are left untouched.

    Returns
    -------
    list[str]
        Names of tables actually created in this run.
    """
    # Import models so they register against Base.metadata
    from backend.database import Base
    import backend.models  # noqa: F401  — triggers all model imports

    owned = [
        t for name, t in Base.metadata.tables.items() if name in AGENT_OWNED_TABLES
    ]
    if not owned:
        logger.warning("No agent-owned tables found in metadata — nothing to create.")
        return []

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(sync_conn, tables=owned)
        )
    created = [t.name for t in owned]
    logger.info("Agent local DB ready — owned tables: %s", created)
    return created

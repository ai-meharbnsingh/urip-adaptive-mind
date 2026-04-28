"""
TDD tests — backend/seed_simulators/connector_credential_simulator.

Verifies:
  - Creates TenantConnectorCredential rows for the Acme stack.
  - Encrypted blobs are bytes (Fernet ciphertext), not plaintext.
  - One row per (tenant, connector_name) — UniqueConstraint respected.
  - Tenant isolation; idempotent.
"""
from __future__ import annotations

import os
import uuid

# Set Fernet key BEFORE importing crypto
os.environ.setdefault(
    "URIP_FERNET_KEY",
    "M3JKpUVOfx1nPLQYMRrxnVZsJq3cJ5vXq7bOe6jfXok=",
)

import pytest
from sqlalchemy import select, func

from backend.models.tenant import Tenant
from backend.models.tenant_connector_credential import TenantConnectorCredential
from backend.seed_simulators.connector_credential_simulator import (
    simulate_connector_credentials,
)


@pytest.mark.anyio
async def test_creates_credential_rows_for_all_connectors(db_session, default_tenant):
    summary = await simulate_connector_credentials(
        db_session, tenant_id=default_tenant.id, seed=42
    )
    assert summary["created"] >= 12  # 12 Acme connectors
    rows = (await db_session.execute(
        select(TenantConnectorCredential).where(
            TenantConnectorCredential.tenant_id == default_tenant.id
        )
    )).scalars().all()
    assert len(rows) >= 12


@pytest.mark.anyio
async def test_encrypted_blob_is_bytes_not_plaintext(db_session, default_tenant):
    await simulate_connector_credentials(
        db_session, tenant_id=default_tenant.id, seed=42
    )
    rows = (await db_session.execute(
        select(TenantConnectorCredential).where(
            TenantConnectorCredential.tenant_id == default_tenant.id
        ).limit(5)
    )).scalars().all()
    for r in rows:
        assert isinstance(r.encrypted_blob, bytes)
        # No raw "DEMO-" plaintext should appear in the blob (Fernet encrypts)
        assert b"DEMO-" not in r.encrypted_blob, (
            f"connector {r.connector_name}: blob contains plaintext"
        )


@pytest.mark.anyio
async def test_unique_constraint_per_tenant_connector(db_session, default_tenant):
    """Re-running should NOT raise UniqueConstraint violation."""
    await simulate_connector_credentials(
        db_session, tenant_id=default_tenant.id, seed=42
    )
    # Re-run — must be idempotent
    await simulate_connector_credentials(
        db_session, tenant_id=default_tenant.id, seed=42
    )

    # Each connector_name appears exactly once
    rows = (await db_session.execute(
        select(TenantConnectorCredential).where(
            TenantConnectorCredential.tenant_id == default_tenant.id
        )
    )).scalars().all()
    names = [r.connector_name for r in rows]
    assert len(names) == len(set(names)), (
        f"duplicate connector_name detected: {names}"
    )


@pytest.mark.anyio
async def test_tenant_isolation(db_session, default_tenant):
    other_tenant = Tenant(
        id=uuid.uuid4(),
        name="Other Tenant",
        slug="other-test",
        domain="other.test",
        is_active=True,
        settings={},
    )
    db_session.add(other_tenant)
    await db_session.commit()

    await simulate_connector_credentials(
        db_session, tenant_id=default_tenant.id, seed=42
    )
    # Other tenant should have ZERO credentials
    other_count = (await db_session.execute(
        select(func.count()).select_from(TenantConnectorCredential).where(
            TenantConnectorCredential.tenant_id == other_tenant.id
        )
    )).scalar()
    assert other_count == 0

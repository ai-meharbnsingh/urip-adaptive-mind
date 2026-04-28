"""
backend/seed_simulators/connector_credential_simulator.py

Seed encrypted dummy credentials so each tenant connector "appears configured"
in the demo. The credentials are real Fernet ciphertexts of dummy payloads —
the API endpoints that decrypt and use them will succeed at decryption but
hit the simulator path (since simulator_mode=extended), so no real network
calls are made.

Idempotent: ON CONFLICT (tenant_id, connector_name) DO NOTHING via SELECT-first.

NEW-5 — `fernet_key` parameter
------------------------------
Historically the simulator delegated entirely to
``backend.services.crypto_service.encrypt_credentials``, which reads
``settings.URIP_FERNET_KEY`` at call-time.  Tests that imported anything from
``backend`` BEFORE setting ``URIP_FERNET_KEY`` would get an empty Settings
object cached, and crypto_service would raise.

Cleanest fix: accept an optional ``fernet_key`` argument.  When supplied it is
used to drive a local :class:`cryptography.fernet.Fernet` instance directly,
bypassing settings entirely.  When omitted, behaviour is unchanged — we still
delegate to ``encrypt_credentials`` so production seed scripts work as before.
"""
from __future__ import annotations

import json
import uuid
from typing import Optional, Union

from cryptography.fernet import Fernet
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.tenant_connector_credential import TenantConnectorCredential
from backend.services.crypto_service import encrypt_credentials
from backend.seed_simulators._common import (
    EXTENDED_CONNECTORS,
    DUMMY_CREDENTIALS_BY_CONNECTOR,
    now_utc,
    stable_uuid_obj,
)


def _encrypt_with_explicit_key(payload: dict, fernet_key: Union[str, bytes]) -> bytes:
    """
    Encrypt ``payload`` using a caller-supplied Fernet key.  This deliberately
    does NOT touch :mod:`backend.config` so it is safe to use from tests that
    cannot rely on env-var ordering.
    """
    key = fernet_key.encode() if isinstance(fernet_key, str) else fernet_key
    return Fernet(key).encrypt(json.dumps(payload).encode())


async def simulate_connector_credentials(
    session: AsyncSession,
    *,
    tenant_id: Union[str, uuid.UUID],
    seed: int = 42,
    fernet_key: Optional[Union[str, bytes]] = None,
) -> dict:
    """
    Seed TenantConnectorCredential rows for a tenant.

    Args:
        tenant_id:  Tenant UUID (string or UUID).
        seed:       RNG seed (kept for parity; current impl is deterministic).
        fernet_key: Optional Fernet key to use for encryption.  When None
                    (the default) we fall back to
                    ``backend.services.crypto_service.encrypt_credentials``
                    which reads ``settings.URIP_FERNET_KEY`` from env.

    Returns:
        Summary dict {created, skipped_existing, tenant_id}.
    """
    if isinstance(tenant_id, str):
        tenant_uuid = uuid.UUID(tenant_id)
    else:
        tenant_uuid = tenant_id

    # Pre-fetch existing connector_names for this tenant
    existing_rows = (await session.execute(
        select(TenantConnectorCredential.connector_name).where(
            TenantConnectorCredential.tenant_id == tenant_uuid
        )
    )).scalars().all()
    existing_set = set(existing_rows)

    created = 0
    skipped = 0

    def _encrypt(payload: dict) -> bytes:
        if fernet_key is not None:
            return _encrypt_with_explicit_key(payload, fernet_key)
        return encrypt_credentials(payload)

    for connector_name in EXTENDED_CONNECTORS:
        if connector_name in existing_set:
            skipped += 1
            continue

        payload = DUMMY_CREDENTIALS_BY_CONNECTOR.get(
            connector_name,
            {"note": f"Dummy credentials for {connector_name}"},
        )
        encrypted_blob = _encrypt(payload)

        row = TenantConnectorCredential(
            id=stable_uuid_obj(str(tenant_uuid), "tcc", connector_name),
            tenant_id=tenant_uuid,
            connector_name=connector_name,
            encrypted_blob=encrypted_blob,
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        session.add(row)
        created += 1

    await session.flush()
    return {
        "created": created,
        "skipped_existing": skipped,
        "tenant_id": str(tenant_uuid),
    }

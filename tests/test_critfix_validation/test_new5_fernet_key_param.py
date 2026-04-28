"""
NEW-5 — URIP_FERNET_KEY env-var ordering bug in test_seed_simulators_credentials.

The simulator depends on backend.services.crypto_service.get_fernet(), which
reads settings.URIP_FERNET_KEY at call-time. If the env var is not set BEFORE
backend.config is imported (which happens transitively from fixtures), the
Settings object captures the default empty string and crypto_service raises
ValueError("URIP_FERNET_KEY is not set...").

Cleanest fix: simulate_connector_credentials() accepts an optional
`fernet_key` parameter; when supplied it is used directly; otherwise the
function falls back to the environment / settings.

This test:
  1. Verifies the new parameter exists (signature contract).
  2. Verifies the key passed via parameter actually drives the encryption
     (regardless of what settings.URIP_FERNET_KEY contains).
  3. Verifies env-var fallback still works.
"""
from __future__ import annotations

import inspect
import os
import uuid

import pytest

# Set env var BEFORE any backend imports, mirroring what production seed
# scripts do.
os.environ.setdefault(
    "URIP_FERNET_KEY",
    "M3JKpUVOfx1nPLQYMRrxnVZsJq3cJ5vXq7bOe6jfXok=",
)

from cryptography.fernet import Fernet  # noqa: E402

from backend.seed_simulators.connector_credential_simulator import (  # noqa: E402
    simulate_connector_credentials,
)
from backend.models.tenant_connector_credential import (  # noqa: E402
    TenantConnectorCredential,
)
from sqlalchemy import select  # noqa: E402


def test_simulator_signature_accepts_fernet_key():
    """The function must expose a `fernet_key` keyword parameter."""
    sig = inspect.signature(simulate_connector_credentials)
    assert "fernet_key" in sig.parameters, (
        "simulate_connector_credentials must accept a `fernet_key` kwarg "
        "so tests can inject the key without depending on env-var import "
        "ordering."
    )
    p = sig.parameters["fernet_key"]
    assert p.default is None or p.default == inspect.Parameter.empty or isinstance(
        p.default, (str, bytes, type(None))
    ), "fernet_key default should be None / str / bytes"


@pytest.mark.anyio
async def test_explicit_fernet_key_drives_encryption(db_session, default_tenant):
    """
    When a key is passed explicitly, it must be the key actually used for
    encryption — proven by decrypting a row's blob with the same key.
    """
    explicit_key = Fernet.generate_key().decode()
    summary = await simulate_connector_credentials(
        db_session,
        tenant_id=default_tenant.id,
        seed=42,
        fernet_key=explicit_key,
    )
    assert summary["created"] >= 12

    rows = (
        await db_session.execute(
            select(TenantConnectorCredential).where(
                TenantConnectorCredential.tenant_id == default_tenant.id
            ).limit(1)
        )
    ).scalars().all()
    assert rows, "expected at least one credential row"
    f = Fernet(explicit_key.encode())
    plaintext = f.decrypt(rows[0].encrypted_blob)
    # Plaintext is JSON of the dummy creds — must contain at least a curly brace
    assert plaintext.startswith(b"{")


@pytest.mark.anyio
async def test_env_var_fallback_still_works(db_session, default_tenant, monkeypatch):
    """
    With no `fernet_key` argument, the function falls back to the env var /
    settings exactly as before — preserving the legacy code path.

    Note: ``backend.config.settings`` is built once at import time, so we
    monkey-patch the live ``settings`` object's URIP_FERNET_KEY attribute
    to simulate "the env var was set before settings was constructed".  This
    is the only fully-deterministic way to exercise the legacy path from a
    test that runs after the conftest has already imported the app.
    """
    from backend import config as _cfg
    test_key = "M3JKpUVOfx1nPLQYMRrxnVZsJq3cJ5vXq7bOe6jfXok="
    monkeypatch.setattr(_cfg.settings, "URIP_FERNET_KEY", test_key)

    summary = await simulate_connector_credentials(
        db_session,
        tenant_id=default_tenant.id,
        seed=42,
    )
    assert summary["created"] >= 12

"""
TDD tests — backend/connector_loader.py

Verifies the INV-1 fix: importing the backend (or the loader directly) MUST
register all 9 production-and-simulator connectors in the global registry.

Before the loader was wired in, `from backend.main import app` left the registry
empty (0 entries) — meaning all 9 connector modules were dead code.  This test
locks in the fix so a future refactor can't silently re-introduce that bug.

Expected registered keys (alphabetical):
    extended_simulator, cloudsek, manageengine_sdp, ms_entra, netskope,
    sentinelone, simulator, tenable, zscaler
"""
from __future__ import annotations

import os

# Set Fernet key BEFORE backend imports so crypto_service has a valid key.
os.environ.setdefault(
    "URIP_FERNET_KEY",
    "M3JKpUVOfx1nPLQYMRrxnVZsJq3cJ5vXq7bOe6jfXok=",
)
# Disable the background scheduler so importing main.py doesn't try to spawn
# tasks during synchronous test collection.
os.environ.setdefault("DISABLE_CONNECTOR_SCHEDULER", "true")


EXPECTED_CONNECTORS = {
    "tenable",
    "sentinelone",
    "zscaler",
    "netskope",
    "ms_entra",
    "manageengine_sdp",
    "cloudsek",
    "simulator",
    "extended_simulator",
}


def test_connector_loader_registers_all_nine_connectors():
    """Importing the loader module triggers @register_connector for all 9."""
    # Importing the loader is the public mechanism that fixes INV-1.
    from backend import connector_loader  # noqa: F401
    from connectors.base.registry import _global_registry

    registered = set(_global_registry.list_names())
    missing = EXPECTED_CONNECTORS - registered
    assert not missing, f"Connector loader did not register: {sorted(missing)}"


def test_main_app_import_registers_all_nine_connectors():
    """
    Importing backend.main MUST also trigger registration so the running
    FastAPI app sees all 9 connectors — this is the INV-1 guarantee.
    """
    from backend.main import app  # noqa: F401  (import side-effect)
    from connectors.base.registry import _global_registry

    registered = set(_global_registry.list_names())
    missing = EXPECTED_CONNECTORS - registered
    assert not missing, (
        f"backend.main import did not register: {sorted(missing)}. "
        "This is the INV-1 (no dead code) violation that the loader was "
        "introduced to fix."
    )


def test_loader_exposes_helper_listing_registered_connectors():
    """The loader should expose a helper listing what got registered."""
    from backend.connector_loader import get_registered_connector_names

    names = get_registered_connector_names()
    assert set(names) >= EXPECTED_CONNECTORS
    assert names == sorted(names), "Helper must return sorted names"


def test_each_connector_is_instantiable_via_registry():
    """Every registered connector must be instantiable (no abstract class leaks)."""
    from backend import connector_loader  # noqa: F401
    from connectors.base.connector import BaseConnector
    from connectors.base.registry import _global_registry

    for name in EXPECTED_CONNECTORS:
        factory = _global_registry.get(name)
        instance = factory()
        assert isinstance(instance, BaseConnector), (
            f"Connector '{name}' factory did not produce a BaseConnector."
        )

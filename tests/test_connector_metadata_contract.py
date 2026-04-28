"""
TDD — Connector metadata contract (P33-Z3 / Tool Catalog).

Verifies that EVERY registered "real" connector (the 9 in connector_loader)
declares all required class-level metadata so the dynamic Tool Catalog UI can
render its tile without falling back to placeholder values.

Required class attributes (set on the connector class — NOT instance):
    DISPLAY_NAME, CATEGORY, SHORT_DESCRIPTION, STATUS, MODULE_CODE,
    CREDENTIAL_FIELDS

CATEGORY must be in the canonical CONNECTOR_CATEGORIES allow-list.
STATUS must be one of {"live", "building", "simulated", "roadmap"}.

This test is the FIRST line of defence — if a parallel worker lands a new
connector without filling metadata, this fails before the UI is asked to
render an empty tile.
"""
from __future__ import annotations

import os

os.environ.setdefault(
    "URIP_FERNET_KEY",
    "M3JKpUVOfx1nPLQYMRrxnVZsJq3cJ5vXq7bOe6jfXok=",
)
os.environ.setdefault("DISABLE_CONNECTOR_SCHEDULER", "true")

import pytest

from connectors.base.connector import (
    CONNECTOR_CATEGORIES,
    BaseConnector,
    CredentialFieldSpec,
)


# Connectors loaded by backend.connector_loader.  Touched by THIS worker.
REAL_CONNECTORS = {
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

VALID_STATUSES = {"live", "building", "simulated", "roadmap"}


@pytest.fixture(scope="module")
def registry():
    # Force loader → registry filled.
    from backend import connector_loader  # noqa: F401
    from connectors.base.registry import _global_registry

    return _global_registry


@pytest.mark.parametrize("conn_name", sorted(REAL_CONNECTORS))
def test_connector_has_display_name(registry, conn_name):
    factory = registry.get(conn_name)
    assert getattr(factory, "DISPLAY_NAME", ""), (
        f"{conn_name}: DISPLAY_NAME must be set on the class"
    )


@pytest.mark.parametrize("conn_name", sorted(REAL_CONNECTORS))
def test_connector_category_in_allow_list(registry, conn_name):
    factory = registry.get(conn_name)
    cat = getattr(factory, "CATEGORY", "")
    assert cat, f"{conn_name}: CATEGORY must be set"
    assert cat in CONNECTOR_CATEGORIES, (
        f"{conn_name}: CATEGORY={cat!r} is not in {CONNECTOR_CATEGORIES}"
    )


@pytest.mark.parametrize("conn_name", sorted(REAL_CONNECTORS))
def test_connector_short_description_present(registry, conn_name):
    factory = registry.get(conn_name)
    desc = getattr(factory, "SHORT_DESCRIPTION", "")
    assert desc, f"{conn_name}: SHORT_DESCRIPTION must be a non-empty string"
    # Catalog UI expects something compact — sanity-cap at 250 chars.
    assert len(desc) <= 250, (
        f"{conn_name}: SHORT_DESCRIPTION too long ({len(desc)} chars); "
        "keep it tile-sized"
    )


@pytest.mark.parametrize("conn_name", sorted(REAL_CONNECTORS))
def test_connector_status_valid(registry, conn_name):
    factory = registry.get(conn_name)
    status = getattr(factory, "STATUS", "")
    assert status in VALID_STATUSES, (
        f"{conn_name}: STATUS={status!r} not in {VALID_STATUSES}"
    )


@pytest.mark.parametrize("conn_name", sorted(REAL_CONNECTORS))
def test_connector_module_code_set(registry, conn_name):
    factory = registry.get(conn_name)
    mc = getattr(factory, "MODULE_CODE", "")
    assert mc, f"{conn_name}: MODULE_CODE must be set"


@pytest.mark.parametrize("conn_name", sorted(REAL_CONNECTORS))
def test_connector_credential_fields_typed(registry, conn_name):
    """Every entry in CREDENTIAL_FIELDS is a CredentialFieldSpec."""
    factory = registry.get(conn_name)
    fields = getattr(factory, "CREDENTIAL_FIELDS", None)
    assert isinstance(fields, list), (
        f"{conn_name}: CREDENTIAL_FIELDS must be a list, got {type(fields).__name__}"
    )
    assert len(fields) >= 1, (
        f"{conn_name}: CREDENTIAL_FIELDS must contain at least one field"
    )
    for f in fields:
        assert isinstance(f, CredentialFieldSpec), (
            f"{conn_name}: CREDENTIAL_FIELDS entries must be CredentialFieldSpec, "
            f"got {type(f).__name__}"
        )


def test_simulators_marked_simulated(registry):
    for name in ("simulator", "extended_simulator"):
        factory = registry.get(name)
        assert factory.STATUS == "simulated", (
            f"{name}: simulator connectors must declare STATUS='simulated'"
        )
        assert factory.CATEGORY == "SIMULATOR", (
            f"{name}: simulator connectors must declare CATEGORY='SIMULATOR'"
        )


def test_real_connectors_marked_live(registry):
    """The 7 production connectors must all be 'live'."""
    live_expected = {
        "tenable", "sentinelone", "zscaler", "netskope",
        "ms_entra", "manageengine_sdp", "cloudsek",
    }
    for name in live_expected:
        factory = registry.get(name)
        assert factory.STATUS == "live", (
            f"{name}: production connector must declare STATUS='live'"
        )


def test_registry_metadata_dump_is_complete(registry):
    """list_connectors_with_metadata returns all 9 with non-empty fields."""
    items = registry.list_connectors_with_metadata()
    names = {item["name"] for item in items}
    assert REAL_CONNECTORS <= names, (
        f"Missing from registry dump: {REAL_CONNECTORS - names}"
    )

    by_name = {item["name"]: item for item in items}
    for name in REAL_CONNECTORS:
        meta = by_name[name]
        for required in (
            "display_name", "category", "short_description",
            "status", "module_code",
        ):
            assert meta[required], (
                f"{name}: registry metadata missing '{required}'"
            )
        # credential_fields renders to a list of dicts
        assert isinstance(meta["credential_fields"], list)
        for f in meta["credential_fields"]:
            assert "name" in f and "label" in f and "type" in f


def test_get_connector_metadata_returns_single_entry(registry):
    meta = registry.get_connector_metadata("tenable")
    assert meta["name"] == "tenable"
    assert meta["display_name"] == "Tenable Vulnerability Manager"
    assert meta["category"] == "VM"


def test_get_connector_metadata_unknown_raises(registry):
    with pytest.raises(KeyError):
        registry.get_connector_metadata("does_not_exist_42")


def test_credential_field_spec_to_dict_drops_none_keys():
    """Empty optional fields shouldn't bloat the JSON response."""
    spec = CredentialFieldSpec(name="api_key", label="API Key", required=True)
    d = spec.to_dict()
    assert d["name"] == "api_key"
    assert "placeholder" not in d
    assert "options" not in d

    spec2 = CredentialFieldSpec(
        name="cloud", label="Cloud", type="select",
        options=[{"value": "us", "label": "US"}],
    )
    assert spec2.to_dict()["options"] == [{"value": "us", "label": "US"}]

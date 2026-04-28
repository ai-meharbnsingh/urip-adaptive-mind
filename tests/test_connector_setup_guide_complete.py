"""
TDD — Setup-guide completeness for every connector (P33-Z3 revised).

Goal: customer-facing inline onboarding content must be present, structurally
valid, and complete for every connector that ships with URIP.  This test is the
last gate before the Tool Catalog renders an empty drawer — if a connector's
SETUP_GUIDE is missing or thin, this fails before the UI surface does.

For each of the 25 production connectors + 2 simulators we assert:
  - SETUP_GUIDE is not None
  - len(steps) >= 4
  - len(prerequisites) >= 3
  - len(common_errors) >= 3
  - quick_facts.vendor_docs_url is a valid HTTPS URL (or None for simulators)
  - sample_data is a non-empty dict
  - SetupGuideSpec.validate() returns no problems

Why we test the data module directly (not via class import)
----------------------------------------------------------
A few connectors (notably the cloud-CSPM trio) import optional vendor SDKs
(boto3, azure-mgmt-*, google-cloud-*) at module-load time.  Those SDKs are not
listed in the core ``requirements.txt`` because they're heavy and the related
modules are loaded lazily from the scheduler / dedicated tests.  Importing
those connector classes inside this test would raise ModuleNotFoundError on
clean machines and turn a documentation-completeness check into a packaging
test.

We therefore assert against the canonical ``SETUP_GUIDES`` dict in
``connectors.base.setup_guides_data`` — the same object every connector class
references via ``SETUP_GUIDE = SETUP_GUIDES["..."]``.  We separately verify
that every importable connector class wires the same underlying spec.
"""
from __future__ import annotations

import importlib
import os

os.environ.setdefault(
    "URIP_FERNET_KEY",
    "M3JKpUVOfx1nPLQYMRrxnVZsJq3cJ5vXq7bOe6jfXok=",
)
os.environ.setdefault("DISABLE_CONNECTOR_SCHEDULER", "true")

import pytest

from connectors.base.setup_guide import SetupGuideSpec
from connectors.base.setup_guides_data import SETUP_GUIDES


# Every connector that ships with URIP — 25 production + 2 simulators.
ALL_CONNECTORS: tuple[str, ...] = (
    "tenable",
    "sentinelone",
    "zscaler",
    "netskope",
    "ms_entra",
    "manageengine_sdp",
    "cloudsek",
    "aws_cspm",
    "azure_cspm",
    "gcp_cspm",
    "cert_in",
    "siem",
    "email_security",
    "bug_bounty",
    "crowdstrike",
    "easm",
    "armis_ot",
    "forescout_nac",
    "cyberark_pam",
    "fortiguard_fw",
    "m365_collab",
    "manageengine_ec",
    "manageengine_mdm",
    "burp_enterprise",
    "gtb",
    "simulator",
    "extended_simulator",
)


# Map connector NAME → (module_path, class_name) for the wiring check.
# These connectors are import-light; the rest are validated by SETUP_GUIDES
# dict membership only (see module docstring).
LIGHT_CLASS_PATHS: dict[str, tuple[str, str]] = {
    "tenable": ("connectors.tenable.connector", "TenableConnector"),
    "sentinelone": ("connectors.sentinelone.connector", "SentinelOneConnector"),
    "zscaler": ("connectors.zscaler.connector", "ZscalerConnector"),
    "netskope": ("connectors.netskope.connector", "NetskopeConnector"),
    "ms_entra": ("connectors.ms_entra.connector", "MsEntraConnector"),
    "manageengine_sdp": (
        "connectors.manageengine_sdp.connector",
        "ManageEngineSdpConnector",
    ),
    "cloudsek": ("connectors.cloudsek.connector", "CloudSekConnector"),
    "simulator": ("connectors.simulator_connector", "SimulatorConnector"),
    "extended_simulator": (
        "connectors.extended_simulator",
        "ExtendedSimulatorConnector",
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_every_connector_has_a_setup_guide_entry() -> None:
    """SETUP_GUIDES must contain an entry for every shipped connector."""
    missing = [n for n in ALL_CONNECTORS if n not in SETUP_GUIDES]
    assert not missing, f"SETUP_GUIDES missing entries for: {missing}"


@pytest.mark.parametrize("connector_name", ALL_CONNECTORS)
def test_setup_guide_is_not_none(connector_name: str) -> None:
    guide = SETUP_GUIDES.get(connector_name)
    assert guide is not None, f"{connector_name}: SETUP_GUIDE missing"
    assert isinstance(guide, SetupGuideSpec)


@pytest.mark.parametrize("connector_name", ALL_CONNECTORS)
def test_steps_at_least_four(connector_name: str) -> None:
    guide = SETUP_GUIDES[connector_name]
    assert len(guide.steps) >= 4, (
        f"{connector_name}: only {len(guide.steps)} steps; need >= 4"
    )


@pytest.mark.parametrize("connector_name", ALL_CONNECTORS)
def test_prerequisites_at_least_three(connector_name: str) -> None:
    guide = SETUP_GUIDES[connector_name]
    assert len(guide.prerequisites) >= 3, (
        f"{connector_name}: only {len(guide.prerequisites)} prerequisites; need >= 3"
    )


@pytest.mark.parametrize("connector_name", ALL_CONNECTORS)
def test_common_errors_at_least_three(connector_name: str) -> None:
    guide = SETUP_GUIDES[connector_name]
    assert len(guide.common_errors) >= 3, (
        f"{connector_name}: only {len(guide.common_errors)} errors; need >= 3"
    )


@pytest.mark.parametrize("connector_name", ALL_CONNECTORS)
def test_vendor_docs_url_https(connector_name: str) -> None:
    """
    quick_facts.vendor_docs_url must be a valid HTTPS URL.

    The two simulator connectors are exempt — they have no upstream vendor.
    """
    guide = SETUP_GUIDES[connector_name]
    url = guide.quick_facts.vendor_docs_url
    if connector_name in ("simulator", "extended_simulator"):
        # Simulators legitimately have no vendor docs URL.
        assert url is None or url.startswith("https://"), (
            f"{connector_name}: simulator vendor_docs_url must be None or HTTPS"
        )
        return
    assert isinstance(url, str), (
        f"{connector_name}: vendor_docs_url is missing"
    )
    assert url.startswith("https://"), (
        f"{connector_name}: vendor_docs_url={url!r} must be HTTPS"
    )


@pytest.mark.parametrize("connector_name", ALL_CONNECTORS)
def test_sample_data_non_empty_dict(connector_name: str) -> None:
    guide = SETUP_GUIDES[connector_name]
    assert isinstance(guide.sample_data, dict), (
        f"{connector_name}: sample_data must be a dict"
    )
    assert guide.sample_data, (
        f"{connector_name}: sample_data is empty"
    )


@pytest.mark.parametrize("connector_name", ALL_CONNECTORS)
def test_validate_returns_no_problems(connector_name: str) -> None:
    """
    SetupGuideSpec.validate() runs the full structural check (ordered steps,
    valid difficulty, polling/refresh defined, …).  Empty list = perfect spec.
    """
    guide = SETUP_GUIDES[connector_name]
    problems = guide.validate()
    assert problems == [], (
        f"{connector_name}: SETUP_GUIDE validation problems: {problems}"
    )


@pytest.mark.parametrize("connector_name", ALL_CONNECTORS)
def test_to_dict_serialises_cleanly(connector_name: str) -> None:
    """The frontend renders this dict — it must contain the expected keys."""
    guide = SETUP_GUIDES[connector_name]
    d = guide.to_dict()
    expected_keys = {
        "quick_facts",
        "what_pulled",
        "prerequisites",
        "steps",
        "required_scopes",
        "sample_data",
        "not_collected",
        "common_errors",
        "polling",
        "disconnect_steps",
        "references",
    }
    assert expected_keys <= set(d), (
        f"{connector_name}: missing keys in to_dict: {expected_keys - set(d)}"
    )


@pytest.mark.parametrize("connector_name", sorted(LIGHT_CLASS_PATHS.keys()))
def test_connector_class_wires_setup_guide(connector_name: str) -> None:
    """
    Every connector class assigns ``SETUP_GUIDE = SETUP_GUIDES["<name>"]``.

    Validated only for connectors with no heavy optional-SDK imports — see
    module docstring.  The other connectors are wired identically (same one-line
    pattern) and their SETUP_GUIDE membership is asserted above.
    """
    module_path, class_name = LIGHT_CLASS_PATHS[connector_name]
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    assert cls.SETUP_GUIDE is SETUP_GUIDES[connector_name], (
        f"{connector_name}: class {class_name} does not reference "
        "SETUP_GUIDES[name]"
    )

"""
backend/connector_loader.py — Force-import every connector module on backend boot.

Why this exists (INV-1 fix)
---------------------------
Each connector class is decorated with ``@register_connector("name")``.  The
decorator runs at import time — meaning the class is registered in the global
registry only if its module is actually imported somewhere in the running
process.

Before this loader was introduced, `backend/main.py` did NOT import the
connector packages.  That left the global registry EMPTY at runtime, even
though ``connectors/tenable/connector.py`` etc. were unit-tested and looked
"alive" in source.  The 7 production connectors were therefore dead code in
the running app — a textbook INV-1 violation (no dead code).

By importing this module from ``backend/main.py``, every connector's
``@register_connector`` runs once at process start, and all 9 connectors
(7 production + 2 simulators) become callable through the registry, the
scheduler, and the new /api/connectors router.

Design decisions
----------------
- Plain `import` statements (no dynamic discovery via importlib) keep the
  static-analysis tools happy and make the dependency obvious.  If a new
  connector is added, this list MUST be updated — that's intentional, the
  rule is enforced by ``tests/test_connector_loader.py``.
- ``# noqa: F401`` because we want the import side-effect, not the name binding.
- ``get_registered_connector_names()`` is a thin convenience wrapper around the
  global registry, exposed primarily for the new connectors router and tests.
"""

from __future__ import annotations

# ── Production connectors (all 30 with @register_connector) ────────────────
# VM / EDR / EASM
import connectors.tenable.connector  # noqa: F401
import connectors.sentinelone.connector  # noqa: F401
import connectors.crowdstrike.connector  # noqa: F401
import connectors.easm.connector  # noqa: F401
# CASB / SWG / DLP / Firewall
import connectors.zscaler.connector  # noqa: F401
import connectors.netskope.connector  # noqa: F401
import connectors.fortiguard_fw.connector  # noqa: F401
import connectors.gtb.connector  # noqa: F401
# Identity / NAC / PAM
import connectors.ms_entra.connector  # noqa: F401
import connectors.forescout_nac.connector  # noqa: F401
import connectors.cyberark_pam.connector  # noqa: F401
# Cloud (CSPM)
import connectors.aws_cspm.connector  # noqa: F401
import connectors.azure_cspm.connector  # noqa: F401
import connectors.gcp_cspm.connector  # noqa: F401
# Endpoint / Mobile management
import connectors.manageengine_ec.connector  # noqa: F401
import connectors.manageengine_mdm.connector  # noqa: F401
import connectors.manageengine_sdp.connector  # noqa: F401
import connectors.servicenow.connector  # noqa: F401
# Email / Collab
import connectors.email_security.connector  # noqa: F401
import connectors.m365_collab.connector  # noqa: F401
# OT
import connectors.armis_ot.connector  # noqa: F401
# DAST
import connectors.burp_enterprise.connector  # noqa: F401
# SIEM / Advisory / Bug Bounty
import connectors.siem.connector  # noqa: F401
import connectors.cert_in.connector  # noqa: F401
import connectors.bug_bounty.connector  # noqa: F401
# External Threat / Dark Web
import connectors.cloudsek.connector  # noqa: F401
# LMS (security awareness)
import connectors.knowbe4.connector  # noqa: F401
import connectors.hoxhunt.connector  # noqa: F401
# BGV (background verification)
import connectors.authbridge.connector  # noqa: F401
import connectors.ongrid.connector  # noqa: F401
# ITSM — Jira Cloud + Data Center
import connectors.jira.connector  # noqa: F401

# ── Simulators (used for demos + the test-connection path) ──────────────────
import connectors.simulator_connector  # noqa: F401
import connectors.extended_simulator  # noqa: F401

from connectors.base.registry import _global_registry


def get_registered_connector_names() -> list[str]:
    """Return the sorted list of all registered connector names."""
    return _global_registry.list_names()

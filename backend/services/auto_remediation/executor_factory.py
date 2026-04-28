"""
backend.services.auto_remediation.executor_factory — per-tenant executor wiring.

The auto-remediation framework is opt-in per tenant + per executor kind.  Each
tenant configures credentials for the vendors they actually use (CrowdStrike
RTR, Fortinet, Ansible, CyberArk).  Credentials are stored in the same Fernet
vault used by the connector framework.

Vault key convention
--------------------
    (tenant_id, executor_kind)

where executor_kind ∈ {"crowdstrike_rtr", "fortinet", "ansible", "cyberark"}.

Each kind expects a different credential dict:

    crowdstrike_rtr:  {base_url, client_id, client_secret}
    fortinet:         {base_url, api_token, block_group_name?}
    cyberark:         {base_url, auth_token}
    ansible:          {playbook_path, inventory_path?, extra_vars?, timeout_seconds?}

If no row exists for (tenant, kind) we return None — the caller (router) maps
that to a 400/501 telling the admin to configure credentials first.

This module does NOT make HTTP calls; it just hands back a fully-constructed
executor.  The executor's `execute()` method is the place where the real HTTP
happens.
"""
from __future__ import annotations

import logging
from typing import Optional

from backend.services.auto_remediation.ansible import AnsibleExecutor
from backend.services.auto_remediation.base import RemediationExecutorBase
from backend.services.auto_remediation.crowdstrike_rtr import CrowdStrikeRTRExecutor
from backend.services.auto_remediation.cyberark import CyberArkExecutor
from backend.services.auto_remediation.fortinet import FortinetExecutor

logger = logging.getLogger(__name__)


KNOWN_EXECUTORS = {"crowdstrike_rtr", "fortinet", "ansible", "cyberark"}


def _build(kind: str, creds: dict) -> RemediationExecutorBase:
    """Construct an executor of the given kind from a creds dict."""
    if kind == "crowdstrike_rtr":
        return CrowdStrikeRTRExecutor(
            base_url=creds.get("base_url", "https://api.crowdstrike.com"),
            client_id=creds.get("client_id", ""),
            client_secret=creds.get("client_secret", ""),
        )
    if kind == "fortinet":
        return FortinetExecutor(
            base_url=creds.get("base_url", ""),
            api_token=creds.get("api_token", ""),
            block_group_name=creds.get("block_group_name", "urip-blocklist"),
        )
    if kind == "cyberark":
        return CyberArkExecutor(
            base_url=creds.get("base_url", ""),
            auth_token=creds.get("auth_token", ""),
        )
    if kind == "ansible":
        if not creds.get("playbook_path"):
            raise ValueError("Ansible credentials must include playbook_path")
        return AnsibleExecutor(
            playbook_path=creds["playbook_path"],
            inventory_path=creds.get("inventory_path"),
            extra_vars=creds.get("extra_vars"),
            timeout_seconds=int(creds.get("timeout_seconds", 600)),
        )
    raise ValueError(f"Unknown executor kind: {kind!r}")


def load_executor_for_tenant(
    tenant_id: str,
    executor_kind: str,
    vault,  # CredentialsVault
) -> Optional[RemediationExecutorBase]:
    """
    Pull credentials for (tenant, executor_kind) from the vault and return a
    pre-configured executor.  Returns None if no credentials are stored.

    Raises ValueError if executor_kind is unknown.
    """
    if executor_kind not in KNOWN_EXECUTORS:
        raise ValueError(
            f"Unknown executor kind {executor_kind!r}; "
            f"valid: {sorted(KNOWN_EXECUTORS)}"
        )
    creds = vault.retrieve_from_memory(tenant_id, executor_kind)
    if creds is None:
        logger.debug(
            "load_executor_for_tenant: no creds for tenant=%s kind=%s",
            tenant_id, executor_kind,
        )
        return None
    return _build(executor_kind, creds)

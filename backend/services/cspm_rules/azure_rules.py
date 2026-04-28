"""
Top 20 CIS/Azure rule implementations.

Each function receives connector_data dict shaped like:
  {
    "aad_users": [...],
    "aad_directory_settings": [...],
    "defender_plans": [...],
    "storage_accounts": [...],
    "sql_servers": [...],
    "nsgs": [...],
    "app_gateways": [...],
    "vms": [...],
    "key_vaults": [...],
    "app_services": [...],
    "aks_clusters": [...],
  }
"""
from __future__ import annotations

from backend.services.cspm_rules import register_cspm_rule, CspmRuleResult


# ---------------------------------------------------------------------------
# AAD / Identity
# ---------------------------------------------------------------------------

@register_cspm_rule("check_azure_privileged_mfa")
def check_azure_privileged_mfa(connector_data: dict) -> CspmRuleResult:
    """Ensure privileged AAD users (Global Administrator, Privileged Role Administrator, etc.) have MFA enabled."""
    users = connector_data.get("aad_users")
    if users is None:
        return CspmRuleResult(status="inconclusive", evidence={"reason": "aad_users data missing"})

    privileged_roles = {"Global Administrator", "Privileged Role Administrator"}
    failing = []
    for user in users:
        roles = set(user.get("assigned_roles", []))
        if roles & privileged_roles and not user.get("mfa_enabled"):
            failing.append(user.get("user_principal_name", user.get("id", "unknown")))

    if failing:
        return CspmRuleResult(
            status="fail",
            evidence={"privileged_users_without_mfa": failing},
            failing_resource_ids=failing,
        )
    return CspmRuleResult(status="pass", evidence={"checked_users": len(users)})


@register_cspm_rule("check_azure_app_consent_disabled")
def check_azure_app_consent_disabled(connector_data: dict) -> CspmRuleResult:
    """Ensure user consent for applications is disabled or restricted."""
    settings = connector_data.get("aad_directory_settings")
    if settings is None:
        return CspmRuleResult(status="inconclusive", evidence={"reason": "aad_directory_settings data missing"})

    # settings may be a list of setting objects or a single dict
    items = settings if isinstance(settings, list) else [settings]
    for item in items:
        consent = item.get("allow_user_consent")
        if consent is False:
            return CspmRuleResult(status="pass", evidence={"allow_user_consent": False})
        if consent is True:
            return CspmRuleResult(
                status="fail",
                evidence={"allow_user_consent": True},
                failing_resource_ids=[item.get("id", "global")],
            )
    return CspmRuleResult(status="inconclusive", evidence={"reason": "consent setting not found"})


@register_cspm_rule("check_azure_guest_permissions_limited")
def check_azure_guest_permissions_limited(connector_data: dict) -> CspmRuleResult:
    """Ensure guest user permissions are limited."""
    settings = connector_data.get("aad_directory_settings")
    if settings is None:
        return CspmRuleResult(status="inconclusive", evidence={"reason": "aad_directory_settings data missing"})

    items = settings if isinstance(settings, list) else [settings]
    for item in items:
        guest = item.get("guest_permissions")
        if guest == "limited":
            return CspmRuleResult(status="pass", evidence={"guest_permissions": "limited"})
        if guest == "unrestricted":
            return CspmRuleResult(
                status="fail",
                evidence={"guest_permissions": "unrestricted"},
                failing_resource_ids=[item.get("id", "global")],
            )
    return CspmRuleResult(status="inconclusive", evidence={"reason": "guest_permissions setting not found"})


# ---------------------------------------------------------------------------
# Microsoft Defender for Cloud
# ---------------------------------------------------------------------------

@register_cspm_rule("check_defender_servers_on")
def check_defender_servers_on(connector_data: dict) -> CspmRuleResult:
    """Ensure Defender for Servers is enabled."""
    plans = connector_data.get("defender_plans")
    if plans is None:
        return CspmRuleResult(status="inconclusive", evidence={"reason": "defender_plans data missing"})

    for plan in plans:
        if plan.get("plan_name") == "Servers" or plan.get("resource_type") == "VirtualMachines":
            if plan.get("pricing_tier") == "Standard" or plan.get("status") == "enabled":
                return CspmRuleResult(status="pass", evidence={"defender_servers": plan})
            return CspmRuleResult(
                status="fail",
                evidence={"defender_servers": plan},
                failing_resource_ids=[plan.get("id", "global")],
            )
    return CspmRuleResult(status="inconclusive", evidence={"reason": "Defender for Servers plan not found"})


@register_cspm_rule("check_defender_databases_on")
def check_defender_databases_on(connector_data: dict) -> CspmRuleResult:
    """Ensure Defender for Databases is enabled."""
    plans = connector_data.get("defender_plans")
    if plans is None:
        return CspmRuleResult(status="inconclusive", evidence={"reason": "defender_plans data missing"})

    for plan in plans:
        if plan.get("plan_name") == "Databases" or plan.get("resource_type") == "SqlServers":
            if plan.get("pricing_tier") == "Standard" or plan.get("status") == "enabled":
                return CspmRuleResult(status="pass", evidence={"defender_databases": plan})
            return CspmRuleResult(
                status="fail",
                evidence={"defender_databases": plan},
                failing_resource_ids=[plan.get("id", "global")],
            )
    return CspmRuleResult(status="inconclusive", evidence={"reason": "Defender for Databases plan not found"})


@register_cspm_rule("check_defender_storage_on")
def check_defender_storage_on(connector_data: dict) -> CspmRuleResult:
    """Ensure Defender for Storage is enabled."""
    plans = connector_data.get("defender_plans")
    if plans is None:
        return CspmRuleResult(status="inconclusive", evidence={"reason": "defender_plans data missing"})

    for plan in plans:
        if plan.get("plan_name") == "Storage" or plan.get("resource_type") == "StorageAccounts":
            if plan.get("pricing_tier") == "Standard" or plan.get("status") == "enabled":
                return CspmRuleResult(status="pass", evidence={"defender_storage": plan})
            return CspmRuleResult(
                status="fail",
                evidence={"defender_storage": plan},
                failing_resource_ids=[plan.get("id", "global")],
            )
    return CspmRuleResult(status="inconclusive", evidence={"reason": "Defender for Storage plan not found"})


# ---------------------------------------------------------------------------
# Storage Accounts
# ---------------------------------------------------------------------------

@register_cspm_rule("check_storage_secure_transfer")
def check_storage_secure_transfer(connector_data: dict) -> CspmRuleResult:
    """Ensure storage accounts require secure transfer (HTTPS only)."""
    accounts = connector_data.get("storage_accounts")
    if accounts is None:
        return CspmRuleResult(status="inconclusive", evidence={"reason": "storage_accounts data missing"})

    failing = [
        sa.get("name", sa.get("id", "unknown"))
        for sa in accounts
        if not sa.get("enable_https_traffic_only")
    ]
    if failing:
        return CspmRuleResult(
            status="fail",
            evidence={"storage_without_https": failing},
            failing_resource_ids=failing,
        )
    return CspmRuleResult(status="pass", evidence={"total_storage_accounts": len(accounts)})


@register_cspm_rule("check_storage_public_access_disabled")
def check_storage_public_access_disabled(connector_data: dict) -> CspmRuleResult:
    """Ensure public blob access is disabled on storage accounts."""
    accounts = connector_data.get("storage_accounts")
    if accounts is None:
        return CspmRuleResult(status="inconclusive", evidence={"reason": "storage_accounts data missing"})

    failing = [
        sa.get("name", sa.get("id", "unknown"))
        for sa in accounts
        if sa.get("allow_blob_public_access") is True
    ]
    if failing:
        return CspmRuleResult(
            status="fail",
            evidence={"storage_with_public_access": failing},
            failing_resource_ids=failing,
        )
    return CspmRuleResult(status="pass", evidence={"total_storage_accounts": len(accounts)})


@register_cspm_rule("check_storage_min_tls")
def check_storage_min_tls(connector_data: dict) -> CspmRuleResult:
    """Ensure storage accounts enforce a minimum TLS version of 1.2."""
    accounts = connector_data.get("storage_accounts")
    if accounts is None:
        return CspmRuleResult(status="inconclusive", evidence={"reason": "storage_accounts data missing"})

    failing = [
        sa.get("name", sa.get("id", "unknown"))
        for sa in accounts
        if sa.get("minimum_tls_version", "TLS1_0") != "TLS1_2"
    ]
    if failing:
        return CspmRuleResult(
            status="fail",
            evidence={"storage_with_old_tls": failing},
            failing_resource_ids=failing,
        )
    return CspmRuleResult(status="pass", evidence={"total_storage_accounts": len(accounts)})


# ---------------------------------------------------------------------------
# SQL Servers
# ---------------------------------------------------------------------------

@register_cspm_rule("check_sql_auditing_enabled")
def check_sql_auditing_enabled(connector_data: dict) -> CspmRuleResult:
    """Ensure SQL Server auditing is enabled."""
    servers = connector_data.get("sql_servers")
    if servers is None:
        return CspmRuleResult(status="inconclusive", evidence={"reason": "sql_servers data missing"})

    failing = []
    for server in servers:
        auditing = server.get("auditing_settings", {})
        state = auditing.get("state", "Disabled")
        if state != "Enabled":
            failing.append(server.get("name", server.get("id", "unknown")))

    if failing:
        return CspmRuleResult(
            status="fail",
            evidence={"sql_servers_without_auditing": failing},
            failing_resource_ids=failing,
        )
    return CspmRuleResult(status="pass", evidence={"total_sql_servers": len(servers)})


@register_cspm_rule("check_sql_tde_enabled")
def check_sql_tde_enabled(connector_data: dict) -> CspmRuleResult:
    """Ensure Transparent Data Encryption (TDE) is enabled on SQL databases."""
    servers = connector_data.get("sql_servers")
    if servers is None:
        return CspmRuleResult(status="inconclusive", evidence={"reason": "sql_servers data missing"})

    failing = []
    for server in servers:
        tde = server.get("transparent_data_encryption", {})
        state = tde.get("state", "Disabled")
        if state != "Enabled":
            failing.append(server.get("name", server.get("id", "unknown")))

    if failing:
        return CspmRuleResult(
            status="fail",
            evidence={"sql_servers_without_tde": failing},
            failing_resource_ids=failing,
        )
    return CspmRuleResult(status="pass", evidence={"total_sql_servers": len(servers)})


# ---------------------------------------------------------------------------
# Network Security Groups
# ---------------------------------------------------------------------------

@register_cspm_rule("check_nsg_no_rdp_internet")
def check_nsg_no_rdp_internet(connector_data: dict) -> CspmRuleResult:
    """Ensure NSGs do not allow inbound RDP (port 3389) from the Internet."""
    nsgs = connector_data.get("nsgs")
    if nsgs is None:
        return CspmRuleResult(status="inconclusive", evidence={"reason": "nsgs data missing"})

    failing = []
    for nsg in nsgs:
        for rule in nsg.get("security_rules", []):
            if (
                rule.get("direction") == "Inbound"
                and rule.get("access") == "Allow"
                and rule.get("source_address_prefix") in {"*", "Internet", "0.0.0.0/0"}
                and rule.get("protocol") in {"Tcp", "*"}
            ):
                dest_ports = str(rule.get("destination_port_range", ""))
                if dest_ports == "3389" or "3389" in dest_ports:
                    failing.append(nsg.get("name", nsg.get("id", "unknown")))
                    break

    if failing:
        return CspmRuleResult(
            status="fail",
            evidence={"nsgs_with_rdp_from_internet": failing},
            failing_resource_ids=failing,
        )
    return CspmRuleResult(status="pass", evidence={"total_nsgs": len(nsgs)})


@register_cspm_rule("check_nsg_no_ssh_internet")
def check_nsg_no_ssh_internet(connector_data: dict) -> CspmRuleResult:
    """Ensure NSGs do not allow inbound SSH (port 22) from the Internet."""
    nsgs = connector_data.get("nsgs")
    if nsgs is None:
        return CspmRuleResult(status="inconclusive", evidence={"reason": "nsgs data missing"})

    failing = []
    for nsg in nsgs:
        for rule in nsg.get("security_rules", []):
            if (
                rule.get("direction") == "Inbound"
                and rule.get("access") == "Allow"
                and rule.get("source_address_prefix") in {"*", "Internet", "0.0.0.0/0"}
                and rule.get("protocol") in {"Tcp", "*"}
            ):
                dest_ports = str(rule.get("destination_port_range", ""))
                if dest_ports == "22" or "22" in dest_ports:
                    failing.append(nsg.get("name", nsg.get("id", "unknown")))
                    break

    if failing:
        return CspmRuleResult(
            status="fail",
            evidence={"nsgs_with_ssh_from_internet": failing},
            failing_resource_ids=failing,
        )
    return CspmRuleResult(status="pass", evidence={"total_nsgs": len(nsgs)})


# ---------------------------------------------------------------------------
# Application Gateway
# ---------------------------------------------------------------------------

@register_cspm_rule("check_appgw_waf_enabled")
def check_appgw_waf_enabled(connector_data: dict) -> CspmRuleResult:
    """Ensure Application Gateway WAF is enabled."""
    gateways = connector_data.get("app_gateways")
    if gateways is None:
        return CspmRuleResult(status="inconclusive", evidence={"reason": "app_gateways data missing"})

    failing = []
    for gw in gateways:
        waf = gw.get("web_application_firewall_configuration", {})
        if not waf or waf.get("enabled") is not True:
            failing.append(gw.get("name", gw.get("id", "unknown")))

    if failing:
        return CspmRuleResult(
            status="fail",
            evidence={"app_gateways_without_waf": failing},
            failing_resource_ids=failing,
        )
    return CspmRuleResult(status="pass", evidence={"total_app_gateways": len(gateways)})


# ---------------------------------------------------------------------------
# Virtual Machines
# ---------------------------------------------------------------------------

@register_cspm_rule("check_vm_disk_encryption")
def check_vm_disk_encryption(connector_data: dict) -> CspmRuleResult:
    """Ensure VM OS and data disks are encrypted."""
    vms = connector_data.get("vms")
    if vms is None:
        return CspmRuleResult(status="inconclusive", evidence={"reason": "vms data missing"})

    failing = []
    for vm in vms:
        os_disk = vm.get("os_disk", {})
        encryption = os_disk.get("encryption", {})
        if encryption.get("type") is None:
            failing.append(vm.get("name", vm.get("id", "unknown")))
            continue
        data_disks = vm.get("data_disks", [])
        for dd in data_disks:
            if dd.get("encryption", {}).get("type") is None:
                failing.append(vm.get("name", vm.get("id", "unknown")))
                break

    if failing:
        return CspmRuleResult(
            status="fail",
            evidence={"vms_with_unencrypted_disks": failing},
            failing_resource_ids=failing,
        )
    return CspmRuleResult(status="pass", evidence={"total_vms": len(vms)})


# ---------------------------------------------------------------------------
# Key Vault
# ---------------------------------------------------------------------------

@register_cspm_rule("check_keyvault_purge_protection")
def check_keyvault_purge_protection(connector_data: dict) -> CspmRuleResult:
    """Ensure Key Vault purge protection is enabled."""
    vaults = connector_data.get("key_vaults")
    if vaults is None:
        return CspmRuleResult(status="inconclusive", evidence={"reason": "key_vaults data missing"})

    failing = [
        kv.get("name", kv.get("id", "unknown"))
        for kv in vaults
        if not kv.get("enable_purge_protection")
    ]
    if failing:
        return CspmRuleResult(
            status="fail",
            evidence={"keyvaults_without_purge_protection": failing},
            failing_resource_ids=failing,
        )
    return CspmRuleResult(status="pass", evidence={"total_key_vaults": len(vaults)})


@register_cspm_rule("check_keyvault_soft_delete")
def check_keyvault_soft_delete(connector_data: dict) -> CspmRuleResult:
    """Ensure Key Vault soft delete is enabled."""
    vaults = connector_data.get("key_vaults")
    if vaults is None:
        return CspmRuleResult(status="inconclusive", evidence={"reason": "key_vaults data missing"})

    failing = [
        kv.get("name", kv.get("id", "unknown"))
        for kv in vaults
        if not kv.get("enable_soft_delete")
    ]
    if failing:
        return CspmRuleResult(
            status="fail",
            evidence={"keyvaults_without_soft_delete": failing},
            failing_resource_ids=failing,
        )
    return CspmRuleResult(status="pass", evidence={"total_key_vaults": len(vaults)})


# ---------------------------------------------------------------------------
# App Service
# ---------------------------------------------------------------------------

@register_cspm_rule("check_appservice_https_only")
def check_appservice_https_only(connector_data: dict) -> CspmRuleResult:
    """Ensure App Services enforce HTTPS only."""
    apps = connector_data.get("app_services")
    if apps is None:
        return CspmRuleResult(status="inconclusive", evidence={"reason": "app_services data missing"})

    failing = [
        app.get("name", app.get("id", "unknown"))
        for app in apps
        if not app.get("https_only")
    ]
    if failing:
        return CspmRuleResult(
            status="fail",
            evidence={"app_services_without_https_only": failing},
            failing_resource_ids=failing,
        )
    return CspmRuleResult(status="pass", evidence={"total_app_services": len(apps)})


# ---------------------------------------------------------------------------
# AKS
# ---------------------------------------------------------------------------

@register_cspm_rule("check_aks_rbac_enabled")
def check_aks_rbac_enabled(connector_data: dict) -> CspmRuleResult:
    """Ensure AKS clusters have RBAC enabled."""
    clusters = connector_data.get("aks_clusters")
    if clusters is None:
        return CspmRuleResult(status="inconclusive", evidence={"reason": "aks_clusters data missing"})

    failing = [
        cluster.get("name", cluster.get("id", "unknown"))
        for cluster in clusters
        if not cluster.get("enable_rbac")
    ]
    if failing:
        return CspmRuleResult(
            status="fail",
            evidence={"aks_clusters_without_rbac": failing},
            failing_resource_ids=failing,
        )
    return CspmRuleResult(status="pass", evidence={"total_aks_clusters": len(clusters)})


@register_cspm_rule("check_aks_network_policy")
def check_aks_network_policy(connector_data: dict) -> CspmRuleResult:
    """Ensure AKS clusters have a network policy enabled."""
    clusters = connector_data.get("aks_clusters")
    if clusters is None:
        return CspmRuleResult(status="inconclusive", evidence={"reason": "aks_clusters data missing"})

    failing = []
    for cluster in clusters:
        network_profile = cluster.get("network_profile", {})
        policy = network_profile.get("network_policy")
        if not policy:
            failing.append(cluster.get("name", cluster.get("id", "unknown")))

    if failing:
        return CspmRuleResult(
            status="fail",
            evidence={"aks_clusters_without_network_policy": failing},
            failing_resource_ids=failing,
        )
    return CspmRuleResult(status="pass", evidence={"total_aks_clusters": len(clusters)})

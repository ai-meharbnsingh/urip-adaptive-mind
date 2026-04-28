"""
CIS Microsoft Azure Benchmark v2.0 seeder.

~120 controls across categories:
  1.x Identity and Access Management
  2.x Microsoft Defender
  3.x Storage Accounts
  4.x Database Services
  5.x Logging and Monitoring
  6.x Networking
  7.x Virtual Machines
  8.x Other Security Considerations
"""
from __future__ import annotations

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.cspm import CspmFramework, CspmControl


CIS_AZURE_CONTROLS: list[tuple[str, str, str, str, str | None, list[str]]] = [
    # 1.x Identity and Access Management (18)
    ("CIS-Azure-1.1", "Ensure that multi-factor authentication is enabled for all privileged users", "Privileged accounts must use MFA.", "critical", "check_azure_privileged_mfa", ["aad"]),
    ("CIS-Azure-1.2", "Ensure that multi-factor authentication is enabled for all non-privileged users", "All users should use MFA.", "high", "check_azure_all_mfa", ["aad"]),
    ("CIS-Azure-1.3", "Ensure that there are no guest users", "Guest users expand the attack surface.", "medium", "check_azure_no_guest_users", ["aad"]),
    ("CIS-Azure-1.4", "Ensure that 'Allow users to remember multi-factor authentication on devices they trust' is disabled", "Remembering MFA weakens the control.", "medium", "check_azure_mfa_remember_disabled", ["aad"]),
    ("CIS-Azure-1.5", "Ensure that password reset registration is monitored", "Self-service password reset must be tracked.", "medium", "check_azure_sspr_monitored", ["aad"]),
    ("CIS-Azure-1.6", "Ensure that 'Users can consent to apps accessing company data on their behalf' is disabled", "App consent can lead to data leakage.", "high", "check_azure_app_consent_disabled", ["aad"]),
    ("CIS-Azure-1.7", "Ensure that 'Users can add gallery apps to their Access Panel' is disabled", "Unvetted app additions are risky.", "medium", "check_azure_gallery_apps_disabled", ["aad"]),
    ("CIS-Azure-1.8", "Ensure that 'Users can register applications' is disabled", "Uncontrolled app registration is risky.", "medium", "check_azure_app_registration_disabled", ["aad"]),
    ("CIS-Azure-1.9", "Ensure that 'Guest users permissions are limited' is set to 'Yes'", "Guest permissions must be restricted.", "high", "check_azure_guest_permissions_limited", ["aad"]),
    ("CIS-Azure-1.10", "Ensure that 'Members can invite' is set to 'No'", "Restrict member invitation privileges.", "medium", "check_azure_members_invite_disabled", ["aad"]),
    ("CIS-Azure-1.11", "Ensure that 'Guests can invite' is set to 'No'", "Guests must not invite other guests.", "medium", "check_azure_guests_invite_disabled", ["aad"]),
    ("CIS-Azure-1.12", "Ensure that 'Restrict access to Azure AD administration portal' is set to 'Yes'", "Limit portal access to admins.", "medium", "check_azure_portal_restricted", ["aad"]),
    ("CIS-Azure-1.13", "Ensure that 'Enable client secret expiry' is set", "Secrets should expire to limit exposure.", "medium", "check_azure_client_secret_expiry", ["aad"]),
    ("CIS-Azure-1.14", "Ensure that 'Password policy' enforces complexity", "Complex passwords resist brute force.", "medium", "check_azure_password_complexity", ["aad"]),
    ("CIS-Azure-1.15", "Ensure that 'Password expiration' is set to 90 days", "Regular expiry forces rotation.", "medium", "check_azure_password_expiry", ["aad"]),
    ("CIS-Azure-1.16", "Ensure that 'Lockout threshold' is configured", "Account lockout mitigates brute force.", "medium", "check_azure_lockout_threshold", ["aad"]),
    ("CIS-Azure-1.17", "Ensure custom banned passwords list is used", "Banned passwords stop common weak choices.", "medium", "check_azure_banned_passwords", ["aad"]),
    ("CIS-Azure-1.18", "Ensure that 'Password protection mode' is set to 'Enforced'", "Enforce password protection globally.", "high", "check_azure_password_protection_enforced", ["aad"]),
    # 2.x Microsoft Defender (8)
    ("CIS-Azure-2.1", "Ensure that Microsoft Defender for Cloud is set to 'On' for Servers", "Servers must be protected by Defender.", "high", "check_defender_servers_on", ["security"]),
    ("CIS-Azure-2.2", "Ensure that Microsoft Defender for Cloud is set to 'On' for App Service", "App Services must be protected.", "high", "check_defender_appservice_on", ["security"]),
    ("CIS-Azure-2.3", "Ensure that Microsoft Defender for Cloud is set to 'On' for Databases", "Databases must be protected.", "high", "check_defender_databases_on", ["security"]),
    ("CIS-Azure-2.4", "Ensure that Microsoft Defender for Cloud is set to 'On' for Storage", "Storage must be protected.", "high", "check_defender_storage_on", ["security"]),
    ("CIS-Azure-2.5", "Ensure that Microsoft Defender for Cloud is set to 'On' for Containers", "Containers must be protected.", "high", "check_defender_containers_on", ["security"]),
    ("CIS-Azure-2.6", "Ensure that Microsoft Defender for Cloud is set to 'On' for Key Vault", "Key Vault must be protected.", "high", "check_defender_keyvault_on", ["security"]),
    ("CIS-Azure-2.7", "Ensure that Microsoft Defender for Cloud is set to 'On' for Resource Manager", "Resource Manager must be protected.", "medium", "check_defender_arm_on", ["security"]),
    ("CIS-Azure-2.8", "Ensure that Microsoft Defender for Cloud is set to 'On' for DNS", "DNS must be protected.", "medium", "check_defender_dns_on", ["security"]),
    # 3.x Storage Accounts (10)
    ("CIS-Azure-3.1", "Ensure that 'Secure transfer required' is set to 'Enabled'", "Enforce HTTPS for storage.", "high", "check_storage_secure_transfer", ["storage"]),
    ("CIS-Azure-3.2", "Ensure that 'Storage account public access' is set to 'Disabled'", "Disable public blob access.", "critical", "check_storage_public_access_disabled", ["storage"]),
    ("CIS-Azure-3.3", "Ensure that 'Storage account encryption' uses customer-managed keys", "CMK provides data sovereignty.", "medium", "check_storage_cmk", ["storage", "keyvault"]),
    ("CIS-Azure-3.4", "Ensure that 'Soft delete for blobs' is enabled", "Soft delete protects against accidental deletion.", "medium", "check_storage_soft_delete_blobs", ["storage"]),
    ("CIS-Azure-3.5", "Ensure that 'Soft delete for containers' is enabled", "Container soft delete protects data.", "medium", "check_storage_soft_delete_containers", ["storage"]),
    ("CIS-Azure-3.6", "Ensure that 'Network rule default action' is set to 'Deny'", "Default deny reduces exposure.", "high", "check_storage_network_deny", ["storage", "network"]),
    ("CIS-Azure-3.7", "Ensure that 'Trusted Microsoft services' exception is enabled", "Allow Azure services to access storage.", "low", "check_storage_trusted_services", ["storage"]),
    ("CIS-Azure-3.8", "Ensure that 'Private endpoint' is used for storage access", "Private endpoints limit network exposure.", "medium", "check_storage_private_endpoint", ["storage", "network"]),
    ("CIS-Azure-3.9", "Ensure that 'Blob anonymous access' is disabled", "Anonymous blob access is high risk.", "critical", "check_storage_blob_anonymous_disabled", ["storage"]),
    ("CIS-Azure-3.10", "Ensure that 'Minimum TLS version' is set to 'TLS1_2'", "TLS 1.2 is the minimum secure version.", "high", "check_storage_min_tls", ["storage"]),
    # 4.x Database Services (12)
    ("CIS-Azure-4.1", "Ensure that 'SQL Server auditing' is enabled", "Auditing tracks database activity.", "high", "check_sql_auditing_enabled", ["sql"]),
    ("CIS-Azure-4.2", "Ensure that 'SQL Server threat detection' is enabled", "Threat detection alerts on anomalies.", "high", "check_sql_threat_detection", ["sql"]),
    ("CIS-Azure-4.3", "Ensure that 'SQL Server TDE' is enabled", "TDE encrypts data at rest.", "high", "check_sql_tde_enabled", ["sql"]),
    ("CIS-Azure-4.4", "Ensure that 'SQL Server AD authentication' is enabled", "AAD auth replaces weaker SQL auth.", "medium", "check_sql_aad_auth", ["sql", "aad"]),
    ("CIS-Azure-4.5", "Ensure that 'PostgreSQL SSL enforcement' is enabled", "Enforce TLS for PostgreSQL.", "high", "check_postgres_ssl_enforced", ["postgres"]),
    ("CIS-Azure-4.6", "Ensure that 'MySQL SSL enforcement' is enabled", "Enforce TLS for MySQL.", "high", "check_mysql_ssl_enforced", ["mysql"]),
    ("CIS-Azure-4.7", "Ensure that 'Cosmos DB firewall' is configured", "Firewall limits Cosmos DB exposure.", "medium", "check_cosmos_firewall", ["cosmos"]),
    ("CIS-Azure-4.8", "Ensure that 'Cosmos DB private endpoint' is used", "Private endpoints for Cosmos DB.", "medium", "check_cosmos_private_endpoint", ["cosmos", "network"]),
    ("CIS-Azure-4.9", "Ensure that 'Redis SSL' is enabled", "Encrypt Redis traffic.", "high", "check_redis_ssl_enabled", ["redis"]),
    ("CIS-Azure-4.10", "Ensure that 'Redis firewall' is configured", "Restrict Redis network access.", "medium", "check_redis_firewall", ["redis"]),
    ("CIS-Azure-4.11", "Ensure that 'MariaDB SSL' is enabled", "Enforce TLS for MariaDB.", "high", "check_mariadb_ssl_enforced", ["mariadb"]),
    ("CIS-Azure-4.12", "Ensure that 'SQL Server private endpoint' is used", "Private endpoints for SQL Server.", "medium", "check_sql_private_endpoint", ["sql", "network"]),
    # 5.x Logging and Monitoring (14)
    ("CIS-Azure-5.1", "Ensure that 'Activity Log' retention is set to 365 days", "Long retention supports investigations.", "medium", "check_activity_log_retention", ["monitor"]),
    ("CIS-Azure-5.2", "Ensure that 'Activity Log' alert for 'Create policy assignment' exists", "Detect policy changes.", "medium", "check_activity_log_alert_policy", ["monitor"]),
    ("CIS-Azure-5.3", "Ensure that 'Activity Log' alert for 'Delete policy assignment' exists", "Detect policy deletion.", "medium", "check_activity_log_alert_policy_delete", ["monitor"]),
    ("CIS-Azure-5.4", "Ensure that 'Activity Log' alert for 'Create or update NSG' exists", "Detect network changes.", "medium", "check_activity_log_alert_nsg", ["monitor"]),
    ("CIS-Azure-5.5", "Ensure that 'Activity Log' alert for 'Delete NSG' exists", "Detect NSG deletion.", "medium", "check_activity_log_alert_nsg_delete", ["monitor"]),
    ("CIS-Azure-5.6", "Ensure that 'Activity Log' alert for 'Create or update route table' exists", "Detect routing changes.", "medium", "check_activity_log_alert_route", ["monitor"]),
    ("CIS-Azure-5.7", "Ensure that 'Activity Log' alert for 'Delete route table' exists", "Detect route deletion.", "medium", "check_activity_log_alert_route_delete", ["monitor"]),
    ("CIS-Azure-5.8", "Ensure that 'Diagnostic Settings' capture all categories", "Capture all log categories.", "medium", "check_diagnostic_settings_all_categories", ["monitor"]),
    ("CIS-Azure-5.9", "Ensure that 'Log Analytics' workspace retention is 365 days", "Long retention for analytics.", "medium", "check_log_analytics_retention", ["monitor"]),
    ("CIS-Azure-5.10", "Ensure that 'Log Analytics' workspace is encrypted with CMK", "CMK for log analytics.", "medium", "check_log_analytics_cmk", ["monitor", "keyvault"]),
    ("CIS-Azure-5.11", "Ensure that 'App Insights' sampling is configured", "Sampling controls cost and performance.", "low", "check_app_insights_sampling", ["monitor"]),
    ("CIS-Azure-5.12", "Ensure that 'Network Watcher' is enabled in all regions", "Network diagnostics require watcher.", "medium", "check_network_watcher_enabled", ["network"]),
    ("CIS-Azure-5.13", "Ensure that 'Azure Monitor' alert for high CPU exists", "Detect resource exhaustion.", "medium", "check_monitor_alert_cpu", ["monitor"]),
    ("CIS-Azure-5.14", "Ensure that 'Azure Monitor' alert for disk usage exists", "Detect storage exhaustion.", "medium", "check_monitor_alert_disk", ["monitor"]),
    # 6.x Networking (16)
    ("CIS-Azure-6.1", "Ensure that 'RDP' access is restricted from the internet", "Block RDP from 0.0.0.0/0.", "critical", "check_nsg_no_rdp_internet", ["network"]),
    ("CIS-Azure-6.2", "Ensure that 'SSH' access is restricted from the internet", "Block SSH from 0.0.0.0/0.", "critical", "check_nsg_no_ssh_internet", ["network"]),
    ("CIS-Azure-6.3", "Ensure that 'SQL' access is restricted from the internet", "Block SQL ports from internet.", "high", "check_nsg_no_sql_internet", ["network"]),
    ("CIS-Azure-6.4", "Ensure that 'DNS' ports are not exposed to the internet", "Limit DNS exposure.", "medium", "check_nsg_no_dns_internet", ["network"]),
    ("CIS-Azure-6.5", "Ensure that 'FTP' ports are not exposed to the internet", "Block FTP from internet.", "high", "check_nsg_no_ftp_internet", ["network"]),
    ("CIS-Azure-6.6", "Ensure that 'UDP' high ports are not exposed to the internet", "Limit UDP exposure.", "medium", "check_nsg_no_udp_internet", ["network"]),
    ("CIS-Azure-6.7", "Ensure that 'Virtual Network' peering is monitored", "Monitor peering for lateral movement.", "medium", "check_vnet_peering_monitored", ["network"]),
    ("CIS-Azure-6.8", "Ensure that 'Application Gateway' WAF is enabled", "WAF protects web apps.", "high", "check_appgw_waf_enabled", ["network", "appgw"]),
    ("CIS-Azure-6.9", "Ensure that 'Application Gateway' uses HTTPS", "Encrypt gateway traffic.", "high", "check_appgw_https", ["network", "appgw"]),
    ("CIS-Azure-6.10", "Ensure that 'Front Door' WAF is enabled", "WAF on Front Door.", "high", "check_frontdoor_waf_enabled", ["network", "frontdoor"]),
    ("CIS-Azure-6.11", "Ensure that 'DDoS Protection' standard is enabled", "DDoS standard protects all resources.", "medium", "check_ddos_standard_enabled", ["network"]),
    ("CIS-Azure-6.12", "Ensure that 'Private Link' is used where available", "Private Link reduces exposure.", "medium", "check_private_link_used", ["network"]),
    ("CIS-Azure-6.13", "Ensure that 'Load Balancer' health probes are configured", "Health probes enable reliability.", "low", "check_lb_health_probes", ["network"]),
    ("CIS-Azure-6.14", "Ensure that 'ExpressRoute' encryption is enabled", "Encrypt ExpressRoute traffic.", "medium", "check_expressroute_encryption", ["network"]),
    ("CIS-Azure-6.15", "Ensure that 'VPN Gateway' uses IKEv2", "IKEv2 is the secure protocol.", "medium", "check_vpn_ikev2", ["network"]),
    ("CIS-Azure-6.16", "Ensure that 'Firewall' rules are logged", "Log all firewall actions.", "medium", "check_firewall_logging", ["network", "monitor"]),
    # 7.x Virtual Machines (12)
    ("CIS-Azure-7.1", "Ensure that 'VM disk encryption' is enabled", "Encrypt VM disks at rest.", "high", "check_vm_disk_encryption", ["compute"]),
    ("CIS-Azure-7.2", "Ensure that 'VM backup' is enabled", "Backups protect against data loss.", "medium", "check_vm_backup_enabled", ["compute"]),
    ("CIS-Azure-7.3", "Ensure that 'VM antimalware' is enabled", "Antimalware protects workloads.", "high", "check_vm_antimalware", ["compute"]),
    ("CIS-Azure-7.4", "Ensure that 'VM OS patching' is automated", "Automated patching reduces vulnerability.", "high", "check_vm_os_patching", ["compute"]),
    ("CIS-Azure-7.5", "Ensure that 'VM diagnostic logs' are enabled", "Logs enable troubleshooting and forensics.", "medium", "check_vm_diagnostics", ["compute", "monitor"]),
    ("CIS-Azure-7.6", "Ensure that 'VM boot diagnostics' are enabled", "Boot diagnostics aid troubleshooting.", "low", "check_vm_boot_diagnostics", ["compute"]),
    ("CIS-Azure-7.7", "Ensure that 'VM managed identity' is used", "Managed identities avoid credential exposure.", "medium", "check_vm_managed_identity", ["compute", "aad"]),
    ("CIS-Azure-7.8", "Ensure that 'VM JIT access' is enabled", "JIT limits management port exposure.", "high", "check_vm_jit_enabled", ["compute", "security"]),
    ("CIS-Azure-7.9", "Ensure that 'VM NSG' is attached", "Every VM must have an NSG.", "high", "check_vm_nsg_attached", ["compute", "network"]),
    ("CIS-Azure-7.10", "Ensure that 'VM public IP' is justified", "Public IPs increase attack surface.", "medium", "check_vm_public_ip_justified", ["compute", "network"]),
    ("CIS-Azure-7.11", "Ensure that 'VM scale set' health extension is enabled", "Health extension improves reliability.", "low", "check_vmss_health_extension", ["compute"]),
    ("CIS-Azure-7.12", "Ensure that 'VM image' is from trusted publisher", "Untrusted images may be compromised.", "high", "check_vm_trusted_image", ["compute"]),
    # 8.x Other Security Considerations (30)
    ("CIS-Azure-8.1", "Ensure that 'Key Vault' purge protection is enabled", "Purge protection prevents key destruction.", "high", "check_keyvault_purge_protection", ["keyvault"]),
    ("CIS-Azure-8.2", "Ensure that 'Key Vault' soft delete is enabled", "Soft delete protects keys.", "high", "check_keyvault_soft_delete", ["keyvault"]),
    ("CIS-Azure-8.3", "Ensure that 'Key Vault' private endpoint is used", "Private endpoints for Key Vault.", "medium", "check_keyvault_private_endpoint", ["keyvault", "network"]),
    ("CIS-Azure-8.4", "Ensure that 'Key Vault' firewall is configured", "Restrict Key Vault network access.", "medium", "check_keyvault_firewall", ["keyvault"]),
    ("CIS-Azure-8.5", "Ensure that 'App Service' HTTPS only is enabled", "Force HTTPS on App Service.", "high", "check_appservice_https_only", ["appservice"]),
    ("CIS-Azure-8.6", "Ensure that 'App Service' minimum TLS is 1.2", "TLS 1.2 minimum for App Service.", "high", "check_appservice_min_tls", ["appservice"]),
    ("CIS-Azure-8.7", "Ensure that 'App Service' client certificates are required", "Mutual TLS for App Service.", "medium", "check_appservice_client_certs", ["appservice"]),
    ("CIS-Azure-8.8", "Ensure that 'App Service' remote debugging is disabled", "Remote debugging is a backdoor.", "high", "check_appservice_remote_debug_disabled", ["appservice"]),
    ("CIS-Azure-8.9", "Ensure that 'Function App' HTTPS only is enabled", "Force HTTPS on Functions.", "high", "check_functionapp_https_only", ["functionapp"]),
    ("CIS-Azure-8.10", "Ensure that 'Function App' authentication is enabled", "Require auth for Functions.", "medium", "check_functionapp_auth_enabled", ["functionapp", "aad"]),
    ("CIS-Azure-8.11", "Ensure that 'AKS' RBAC is enabled", "RBAC restricts cluster access.", "high", "check_aks_rbac_enabled", ["aks", "aad"]),
    ("CIS-Azure-8.12", "Ensure that 'AKS' network policy is enabled", "Network policies segment pods.", "high", "check_aks_network_policy", ["aks", "network"]),
    ("CIS-Azure-8.13", "Ensure that 'AKS' private cluster is enabled", "Private clusters limit exposure.", "medium", "check_aks_private_cluster", ["aks", "network"]),
    ("CIS-Azure-8.14", "Ensure that 'AKS' audit logging is enabled", "Audit logs track cluster changes.", "medium", "check_aks_audit_logging", ["aks", "monitor"]),
    ("CIS-Azure-8.15", "Ensure that 'AKS' pod security policy is enforced", "Pod security limits privileges.", "high", "check_aks_pod_security", ["aks"]),
    ("CIS-Azure-8.16", "Ensure that 'Container Registry' content trust is enabled", "Content trust validates images.", "medium", "check_acr_content_trust", ["acr"]),
    ("CIS-Azure-8.17", "Ensure that 'Container Registry' quarantine is enabled", "Quarantine blocks untrusted images.", "medium", "check_acr_quarantine", ["acr"]),
    ("CIS-Azure-8.18", "Ensure that 'Container Registry' private endpoint is used", "Private endpoints for ACR.", "medium", "check_acr_private_endpoint", ["acr", "network"]),
    ("CIS-Azure-8.19", "Ensure that 'Service Bus' encryption is enabled", "Encrypt Service Bus data.", "medium", "check_servicebus_encryption", ["servicebus"]),
    ("CIS-Azure-8.20", "Ensure that 'Service Bus' private endpoint is used", "Private endpoints for Service Bus.", "medium", "check_servicebus_private_endpoint", ["servicebus", "network"]),
    ("CIS-Azure-8.21", "Ensure that 'Event Hub' encryption is enabled", "Encrypt Event Hub data.", "medium", "check_eventhub_encryption", ["eventhub"]),
    ("CIS-Azure-8.22", "Ensure that 'Event Hub' capture is encrypted", "Encrypt captured data.", "medium", "check_eventhub_capture_encryption", ["eventhub"]),
    ("CIS-Azure-8.23", "Ensure that 'Logic App' HTTPS only is enabled", "Force HTTPS on Logic Apps.", "high", "check_logicapp_https_only", ["logicapp"]),
    ("CIS-Azure-8.24", "Ensure that 'Logic App' workflow logging is enabled", "Log Logic App executions.", "low", "check_logicapp_logging", ["logicapp", "monitor"]),
    ("CIS-Azure-8.25", "Ensure that 'API Management' HTTPS only is enabled", "Force HTTPS on APIM.", "high", "check_apim_https_only", ["apim"]),
    ("CIS-Azure-8.26", "Ensure that 'API Management' client certificate is required", "mTLS for APIM.", "medium", "check_apim_client_cert", ["apim"]),
    ("CIS-Azure-8.27", "Ensure that 'Data Factory' git integration is enabled", "Git enables change tracking.", "low", "check_adf_git_integration", ["datafactory"]),
    ("CIS-Azure-8.28", "Ensure that 'Data Factory' managed VNet is used", "Managed VNet isolates pipelines.", "medium", "check_adf_managed_vnet", ["datafactory", "network"]),
    ("CIS-Azure-8.29", "Ensure that 'Search Service' private endpoint is used", "Private endpoints for Search.", "medium", "check_search_private_endpoint", ["search", "network"]),
    ("CIS-Azure-8.30", "Ensure that 'Batch Account' encryption is enabled", "Encrypt Batch data.", "medium", "check_batch_encryption", ["batch"]),
]


async def seed_cis_azure_v2(session: AsyncSession) -> None:
    result = await session.execute(
        select(CspmFramework).where(CspmFramework.name == "CIS Azure Foundations v2.0")
    )
    if result.scalars().first():
        return

    framework = CspmFramework(
        id=str(uuid.uuid4()),
        name="CIS Azure Foundations v2.0",
        cloud_provider="azure",
        version="2.0",
        description="CIS Microsoft Azure Benchmark v2.0 covering Identity, Defender, Storage, Database, Logging, Networking, VMs, and Other Security.",
    )
    session.add(framework)
    await session.flush()

    for code, title, desc, sev, rule_fn, services in CIS_AZURE_CONTROLS:
        ctrl = CspmControl(
            id=str(uuid.uuid4()),
            framework_id=framework.id,
            control_code=code,
            title=title,
            description=desc,
            severity=sev,
            rule_function=rule_fn,
            affected_services=services,
        )
        session.add(ctrl)

    await session.flush()

"""
CIS GCP Foundations Benchmark v3.0 seeder.

~110 controls across categories:
  1.x Identity and Access Management
  2.x Logging and Monitoring
  3.x Networking
  4.x Virtual Machines
  5.x Storage
  6.x Cloud SQL
  7.x BigQuery
  8.x Other Security Considerations
"""
from __future__ import annotations

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.cspm import CspmFramework, CspmControl


CIS_GCP_CONTROLS: list[tuple[str, str, str, str, str | None, list[str]]] = [
    # 1.x Identity and Access Management (16)
    ("CIS-GCP-1.1", "Ensure that corporate login credentials are used", "Avoid using Gmail accounts for organization access.", "high", "check_gcp_corporate_credentials", ["iam"]),
    ("CIS-GCP-1.2", "Ensure that multi-factor authentication is enabled for all non-service accounts", "All human users must use MFA.", "critical", "check_gcp_mfa_enabled", ["iam"]),
    ("CIS-GCP-1.3", "Ensure that Security Key Enforcement is enabled for admin accounts", "Hardware keys for admins.", "critical", "check_gcp_security_key_enforcement", ["iam"]),
    ("CIS-GCP-1.4", "Ensure that IAM policies do not allow overly permissive access", "Principle of least privilege.", "high", "check_gcp_least_privilege", ["iam"]),
    ("CIS-GCP-1.5", "Ensure that service account keys are rotated", "Rotate SA keys regularly.", "medium", "check_gcp_sa_key_rotation", ["iam"]),
    ("CIS-GCP-1.6", "Ensure that user-managed/external keys for service accounts are rotated", "External SA keys must be rotated.", "medium", "check_gcp_external_sa_key_rotation", ["iam"]),
    ("CIS-GCP-1.7", "Ensure that Separation of Duties is enforced while assigning service account related roles", "No single user should have full SA control.", "medium", "check_gcp_sa_separation_duties", ["iam"]),
    ("CIS-GCP-1.8", "Ensure that Separation of Duties is enforced while assigning KMS related roles", "Split KMS admin and user roles.", "medium", "check_gcp_kms_separation_duties", ["iam", "kms"]),
    ("CIS-GCP-1.9", "Ensure that Separation of Duties is enforced while assigning Cloud SQL related roles", "Split SQL admin and user roles.", "medium", "check_gcp_sql_separation_duties", ["iam", "sql"]),
    ("CIS-GCP-1.10", "Ensure KMS encryption keys are rotated", "Rotate KMS keys regularly.", "medium", "check_gcp_kms_key_rotation", ["kms"]),
    ("CIS-GCP-1.11", "Ensure IAM bindings for guest users are removed", "No guest user bindings.", "high", "check_gcp_no_guest_bindings", ["iam"]),
    ("CIS-GCP-1.12", "Ensure IAM bindings for stale users are removed", "Remove stale IAM bindings.", "medium", "check_gcp_no_stale_bindings", ["iam"]),
    ("CIS-GCP-1.13", "Ensure IAM policies on projects are monitored", "Monitor IAM policy changes.", "medium", "check_gcp_iam_monitoring", ["iam", "monitoring"]),
    ("CIS-GCP-1.14", "Ensure custom IAM roles are used instead of primitive roles", "Avoid Owner/Editor/Viewer roles.", "high", "check_gcp_custom_roles", ["iam"]),
    ("CIS-GCP-1.15", "Ensure that Organization Policies are enforced", "Organization policies restrict resource usage.", "high", "check_gcp_org_policies_enforced", ["iam", "orgpolicy"]),
    ("CIS-GCP-1.16", "Ensure that Access Transparency is enabled", "Access Transparency logs admin actions.", "medium", "check_gcp_access_transparency", ["iam", "logging"]),
    # 2.x Logging and Monitoring (14)
    ("CIS-GCP-2.1", "Ensure that Cloud Audit Logging is configured properly across all services", "Audit logs capture admin activity.", "high", "check_gcp_audit_logging_all", ["logging"]),
    ("CIS-GCP-2.2", "Ensure that sinks are configured for all log entries", "Sinks export logs for analysis.", "medium", "check_gcp_log_sinks", ["logging"]),
    ("CIS-GCP-2.3", "Ensure that retention policies on log buckets are configured", "Retention preserves logs for investigations.", "medium", "check_gcp_log_retention", ["logging"]),
    ("CIS-GCP-2.4", "Ensure log metric filters and alerts exist for project ownership assignments", "Alert on project ownership changes.", "medium", "check_gcp_alert_project_ownership", ["logging", "monitoring"]),
    ("CIS-GCP-2.5", "Ensure log metric filters and alerts exist for audit configuration changes", "Alert on audit config changes.", "medium", "check_gcp_alert_audit_changes", ["logging", "monitoring"]),
    ("CIS-GCP-2.6", "Ensure log metric filters and alerts exist for custom role changes", "Alert on custom role changes.", "medium", "check_gcp_alert_custom_role_changes", ["logging", "monitoring"]),
    ("CIS-GCP-2.7", "Ensure log metric filters and alerts exist for VPC network firewall rule changes", "Alert on firewall changes.", "medium", "check_gcp_alert_firewall_changes", ["logging", "monitoring"]),
    ("CIS-GCP-2.8", "Ensure log metric filters and alerts exist for VPC network route changes", "Alert on route changes.", "medium", "check_gcp_alert_route_changes", ["logging", "monitoring"]),
    ("CIS-GCP-2.9", "Ensure log metric filters and alerts exist for VPC network changes", "Alert on VPC changes.", "medium", "check_gcp_alert_vpc_changes", ["logging", "monitoring"]),
    ("CIS-GCP-2.10", "Ensure log metric filters and alerts exist for Cloud Storage IAM changes", "Alert on storage IAM changes.", "medium", "check_gcp_alert_storage_iam_changes", ["logging", "monitoring"]),
    ("CIS-GCP-2.11", "Ensure log metric filters and alerts exist for SQL instance configuration changes", "Alert on SQL config changes.", "medium", "check_gcp_alert_sql_changes", ["logging", "monitoring"]),
    ("CIS-GCP-2.12", "Ensure Cloud Monitoring is enabled for all services", "Monitoring provides operational visibility.", "medium", "check_gcp_monitoring_enabled", ["monitoring"]),
    ("CIS-GCP-2.13", "Ensure that uptime checks are configured for critical services", "Uptime checks detect outages.", "medium", "check_gcp_uptime_checks", ["monitoring"]),
    ("CIS-GCP-2.14", "Ensure alerting policies are configured for critical metrics", "Alerts on anomalies.", "medium", "check_gcp_alerting_policies", ["monitoring"]),
    # 3.x Networking (16)
    ("CIS-GCP-3.1", "Ensure that the default network does not exist in a project", "Default VPC lacks segmentation.", "high", "check_gcp_default_network_removed", ["vpc"]),
    ("CIS-GCP-3.2", "Ensure legacy networks do not exist", "Legacy networks lack subnet controls.", "high", "check_gcp_no_legacy_networks", ["vpc"]),
    ("CIS-GCP-3.3", "Ensure that DNSSEC is enabled for Cloud DNS", "DNSSEC prevents cache poisoning.", "high", "check_gcp_dnssec_enabled", ["dns"]),
    ("CIS-GCP-3.4", "Ensure that RSASHA1 is not used for DNSSEC", "RSASHA1 is weak for DNSSEC.", "medium", "check_gcp_dnssec_no_rsasha1", ["dns"]),
    ("CIS-GCP-3.5", "Ensure that DNSSEC key signing uses recommended algorithms", "Strong algorithms for DNSSEC.", "medium", "check_gcp_dnssec_strong_algorithms", ["dns"]),
    ("CIS-GCP-3.6", "Ensure that SSH access is restricted from the internet", "Block SSH from 0.0.0.0/0.", "critical", "check_gcp_ssh_restricted", ["vpc", "compute"]),
    ("CIS-GCP-3.7", "Ensure that RDP access is restricted from the internet", "Block RDP from 0.0.0.0/0.", "critical", "check_gcp_rdp_restricted", ["vpc", "compute"]),
    ("CIS-GCP-3.8", "Ensure that VPC Flow Logs are enabled for every subnet", "Flow logs enable forensics.", "medium", "check_gcp_vpc_flow_logs_enabled", ["vpc", "logging"]),
    ("CIS-GCP-3.9", "Ensure that firewall rules do not allow unrestricted ingress", "Restrict ingress to necessary sources.", "high", "check_gcp_firewall_no_unrestricted_ingress", ["vpc"]),
    ("CIS-GCP-3.10", "Ensure that firewall rules do not allow unrestricted ingress on port 22", "Block port 22 from internet.", "critical", "check_gcp_firewall_no_ssh_internet", ["vpc"]),
    ("CIS-GCP-3.11", "Ensure that firewall rules do not allow unrestricted ingress on port 3389", "Block port 3389 from internet.", "critical", "check_gcp_firewall_no_rdp_internet", ["vpc"]),
    ("CIS-GCP-3.12", "Ensure that Cloud NAT is used for outbound internet access", "NAT hides VM IPs.", "medium", "check_gcp_cloud_nat_enabled", ["vpc"]),
    ("CIS-GCP-3.13", "Ensure that VPC Service Controls are configured", "VPC SC limit data exfiltration.", "high", "check_gcp_vpc_sc_enabled", ["vpc", "accesscontextmanager"]),
    ("CIS-GCP-3.14", "Ensure that Private Google Access is enabled on subnets", "Private Access avoids public IPs for Google APIs.", "medium", "check_gcp_private_google_access", ["vpc"]),
    ("CIS-GCP-3.15", "Ensure that Cloud Router BGP is secured", "Secure BGP sessions.", "medium", "check_gcp_cloud_router_bgp_secured", ["vpc"]),
    ("CIS-GCP-3.16", "Ensure that Shared VPC is used for multi-project networks", "Shared VPC centralizes network management.", "medium", "check_gcp_shared_vpc_used", ["vpc"]),
    # 4.x Virtual Machines (14)
    ("CIS-GCP-4.1", "Ensure that instances are not configured to use the default service account", "Default SA is overprivileged.", "high", "check_gcp_no_default_sa", ["compute", "iam"]),
    ("CIS-GCP-4.2", "Ensure that instances are configured with service account scopes", "Limit SA scopes to least privilege.", "medium", "check_gcp_sa_scopes_limited", ["compute", "iam"]),
    ("CIS-GCP-4.3", "Ensure 'Block Project-wide SSH keys' is enabled for VM instances", "Block project-wide SSH keys.", "medium", "check_gcp_block_project_ssh_keys", ["compute"]),
    ("CIS-GCP-4.4", "Ensure OS Login is enabled for VM instances", "OS Login centralizes SSH key management.", "medium", "check_gcp_oslogin_enabled", ["compute", "iam"]),
    ("CIS-GCP-4.5", "Ensure 'Enable connecting to serial ports' is not enabled", "Serial port access is a backdoor.", "high", "check_gcp_serial_ports_disabled", ["compute"]),
    ("CIS-GCP-4.6", "Ensure that IP forwarding is not enabled on VM instances", "IP forwarding can be used for pivoting.", "high", "check_gcp_ip_forwarding_disabled", ["compute"]),
    ("CIS-GCP-4.7", "Ensure VM disks for critical VMs are encrypted with CSEK", "Customer-supplied encryption keys.", "medium", "check_gcp_disk_csek", ["compute", "kms"]),
    ("CIS-GCP-4.8", "Ensure VM disks are encrypted with CMEK", "Customer-managed encryption keys.", "medium", "check_gcp_disk_cmek", ["compute", "kms"]),
    ("CIS-GCP-4.9", "Ensure 'Confidential Computing' is enabled where supported", "Confidential Computing protects data in use.", "medium", "check_gcp_confidential_computing", ["compute"]),
    ("CIS-GCP-4.10", "Ensure that shielded VM is enabled", "Shielded VMs protect against boot-level malware.", "high", "check_gcp_shielded_vm_enabled", ["compute"]),
    ("CIS-GCP-4.11", "Ensure that integrity monitoring is enabled", "Integrity monitoring detects boot changes.", "high", "check_gcp_integrity_monitoring_enabled", ["compute"]),
    ("CIS-GCP-4.12", "Ensure that secure boot is enabled", "Secure boot prevents unauthorized bootloaders.", "high", "check_gcp_secure_boot_enabled", ["compute"]),
    ("CIS-GCP-4.13", "Ensure that preemptible VMs are not used for production", "Preemptible VMs are not reliable.", "low", "check_gcp_no_preemptible_production", ["compute"]),
    ("CIS-GCP-4.14", "Ensure that VM Manager is enabled", "VM Manager provides patch and inventory management.", "medium", "check_gcp_vm_manager_enabled", ["compute"]),
    # 5.x Storage (10)
    ("CIS-GCP-5.1", "Ensure that Cloud Storage buckets are not anonymously accessible", "Anonymous access exposes data.", "critical", "check_gcp_storage_not_public", ["storage"]),
    ("CIS-GCP-5.2", "Ensure that Cloud Storage buckets have uniform bucket-level access enabled", "Uniform access simplifies IAM.", "medium", "check_gcp_storage_uniform_access", ["storage"]),
    ("CIS-GCP-5.3", "Ensure that Cloud Storage buckets are encrypted with CMEK", "CMEK for storage.", "medium", "check_gcp_storage_cmek", ["storage", "kms"]),
    ("CIS-GCP-5.4", "Ensure that Cloud Storage retention policies are enabled", "Retention prevents deletion.", "medium", "check_gcp_storage_retention", ["storage"]),
    ("CIS-GCP-5.5", "Ensure that Cloud Storage buckets have logging enabled", "Logging tracks access.", "medium", "check_gcp_storage_logging", ["storage", "logging"]),
    ("CIS-GCP-5.6", "Ensure that Cloud Storage buckets have versioning enabled", "Versioning protects against overwrite.", "medium", "check_gcp_storage_versioning", ["storage"]),
    ("CIS-GCP-5.7", "Ensure that Cloud Storage buckets have lifecycle policies", "Lifecycle manages cost and retention.", "low", "check_gcp_storage_lifecycle", ["storage"]),
    ("CIS-GCP-5.8", "Ensure that Cloud Storage buckets have cors configured restrictively", "Restrictive CORS limits exposure.", "low", "check_gcp_storage_cors_restrictive", ["storage"]),
    ("CIS-GCP-5.9", "Ensure that Cloud Storage buckets have public access prevention enforced", "Prevent public access.", "high", "check_gcp_storage_public_access_prevention", ["storage"]),
    ("CIS-GCP-5.10", "Ensure that Cloud Storage transfer jobs are encrypted", "Encrypt transfer jobs.", "medium", "check_gcp_storage_transfer_encryption", ["storage"]),
    # 6.x Cloud SQL (12)
    ("CIS-GCP-6.1", "Ensure that Cloud SQL instances are not open to the world", "Restrict SQL network access.", "critical", "check_gcp_sql_not_open", ["sql", "vpc"]),
    ("CIS-GCP-6.2", "Ensure that Cloud SQL instances use SSL", "Enforce SSL for SQL.", "high", "check_gcp_sql_ssl_required", ["sql"]),
    ("CIS-GCP-6.3", "Ensure that Cloud SQL instances do not have public IP", "Private IP only for SQL.", "high", "check_gcp_sql_no_public_ip", ["sql", "vpc"]),
    ("CIS-GCP-6.4", "Ensure that Cloud SQL instance names do not expose sensitive info", "Naming should not leak data.", "low", "check_gcp_sql_naming", ["sql"]),
    ("CIS-GCP-6.5", "Ensure that Cloud SQL backups are enabled", "Backups protect data.", "medium", "check_gcp_sql_backups_enabled", ["sql"]),
    ("CIS-GCP-6.6", "Ensure that Cloud SQL automated backups are encrypted", "Encrypt backups.", "medium", "check_gcp_sql_backup_encryption", ["sql", "kms"]),
    ("CIS-GCP-6.7", "Ensure that Cloud SQL binary logging is enabled", "Binary logging enables PITR.", "medium", "check_gcp_sql_binary_logging", ["sql"]),
    ("CIS-GCP-6.8", "Ensure that Cloud SQL audit logging is enabled", "Audit logs track SQL activity.", "medium", "check_gcp_sql_audit_logging", ["sql", "logging"]),
    ("CIS-GCP-6.9", "Ensure that Cloud SQL temporary files are encrypted", "Encrypt temp files.", "medium", "check_gcp_sql_temp_encryption", ["sql"]),
    ("CIS-GCP-6.10", "Ensure that Cloud SQL user passwords are strong", "Strong passwords resist brute force.", "medium", "check_gcp_sql_password_policy", ["sql"]),
    ("CIS-GCP-6.11", "Ensure that Cloud SQL IAM authentication is enabled", "IAM auth is more secure.", "medium", "check_gcp_sql_iam_auth", ["sql", "iam"]),
    ("CIS-GCP-6.12", "Ensure that Cloud SQL deletion protection is enabled", "Prevent accidental deletion.", "medium", "check_gcp_sql_deletion_protection", ["sql"]),
    # 7.x BigQuery (10)
    ("CIS-GCP-7.1", "Ensure that BigQuery datasets are not publicly accessible", "Public datasets expose data.", "critical", "check_gcp_bq_not_public", ["bigquery"]),
    ("CIS-GCP-7.2", "Ensure that BigQuery datasets are encrypted with CMEK", "CMEK for BigQuery.", "medium", "check_gcp_bq_cmek", ["bigquery", "kms"]),
    ("CIS-GCP-7.3", "Ensure that BigQuery audit logging is enabled", "Audit logs track queries.", "medium", "check_gcp_bq_audit_logging", ["bigquery", "logging"]),
    ("CIS-GCP-7.4", "Ensure that BigQuery data transfer jobs are encrypted", "Encrypt transfer jobs.", "medium", "check_gcp_bq_transfer_encryption", ["bigquery"]),
    ("CIS-GCP-7.5", "Ensure that BigQuery table expiration is configured", "Expiration limits data retention.", "low", "check_gcp_bq_table_expiration", ["bigquery"]),
    ("CIS-GCP-7.6", "Ensure that BigQuery reservations are monitored", "Monitor reservation usage.", "low", "check_gcp_bq_reservation_monitoring", ["bigquery", "monitoring"]),
    ("CIS-GCP-7.7", "Ensure that BigQuery authorized views are used appropriately", "Authorized views limit exposure.", "medium", "check_gcp_bq_authorized_views", ["bigquery"]),
    ("CIS-GCP-7.8", "Ensure that BigQuery row-level security is used where needed", "RLS restricts row access.", "medium", "check_gcp_bq_row_level_security", ["bigquery"]),
    ("CIS-GCP-7.9", "Ensure that BigQuery column-level security is used where needed", "Column security restricts fields.", "medium", "check_gcp_bq_column_security", ["bigquery"]),
    ("CIS-GCP-7.10", "Ensure that BigQuery data masking is configured", "Masking protects PII.", "medium", "check_gcp_bq_data_masking", ["bigquery"]),
    # 8.x Other Security Considerations (18)
    ("CIS-GCP-8.1", "Ensure that Cloud Functions are not publicly accessible", "Public functions expose logic.", "critical", "check_gcp_functions_not_public", ["functions", "iam"]),
    ("CIS-GCP-8.2", "Ensure that Cloud Functions use least privilege service accounts", "Limit function permissions.", "high", "check_gcp_functions_least_privilege", ["functions", "iam"]),
    ("CIS-GCP-8.3", "Ensure that Cloud Functions ingress settings are restricted", "Restrict function ingress.", "high", "check_gcp_functions_ingress_restricted", ["functions"]),
    ("CIS-GCP-8.4", "Ensure that Cloud Functions runtime is up to date", "Old runtimes have vulnerabilities.", "medium", "check_gcp_functions_runtime_updated", ["functions"]),
    ("CIS-GCP-8.5", "Ensure that Cloud Run services are not publicly accessible", "Public Cloud Run exposes apps.", "critical", "check_gcp_cloudrun_not_public", ["run", "iam"]),
    ("CIS-GCP-8.6", "Ensure that Cloud Run uses least privilege service accounts", "Limit Cloud Run permissions.", "high", "check_gcp_cloudrun_least_privilege", ["run", "iam"]),
    ("CIS-GCP-8.7", "Ensure that GKE clusters are not publicly accessible", "Public control planes are high risk.", "critical", "check_gcp_gke_not_public", ["gke", "vpc"]),
    ("CIS-GCP-8.8", "Ensure that GKE clusters have workload identity enabled", "Workload identity avoids SA keys.", "high", "check_gcp_gke_workload_identity", ["gke", "iam"]),
    ("CIS-GCP-8.9", "Ensure that GKE clusters have network policy enabled", "Network policies segment pods.", "high", "check_gcp_gke_network_policy", ["gke", "vpc"]),
    ("CIS-GCP-8.10", "Ensure that GKE clusters have private nodes enabled", "Private nodes limit exposure.", "high", "check_gcp_gke_private_nodes", ["gke", "vpc"]),
    ("CIS-GCP-8.11", "Ensure that GKE clusters have auto-repair enabled", "Auto-repair fixes unhealthy nodes.", "medium", "check_gcp_gke_auto_repair", ["gke"]),
    ("CIS-GCP-8.12", "Ensure that GKE clusters have auto-upgrade enabled", "Auto-upgrade patches nodes.", "high", "check_gcp_gke_auto_upgrade", ["gke"]),
    ("CIS-GCP-8.13", "Ensure that GKE pod security policy is enabled", "Pod security limits privileges.", "high", "check_gcp_gke_pod_security", ["gke"]),
    ("CIS-GCP-8.14", "Ensure that GKE shielded nodes are enabled", "Shielded nodes protect boot integrity.", "high", "check_gcp_gke_shielded_nodes", ["gke"]),
    ("CIS-GCP-8.15", "Ensure that GKE legacy ABAC is disabled", "ABAC is coarse-grained and deprecated.", "high", "check_gcp_gke_legacy_abac_disabled", ["gke"]),
    ("CIS-GCP-8.16", "Ensure that Cloud KMS key rings are properly labeled", "Labeling aids management.", "low", "check_gcp_kms_labels", ["kms"]),
    ("CIS-GCP-8.17", "Ensure that Cloud KMS keys have expiration", "Key expiration limits exposure.", "medium", "check_gcp_kms_key_expiration", ["kms"]),
    ("CIS-GCP-8.18", "Ensure that Cloud KMS keys are not in plain text exportable", "Prevent key export.", "high", "check_gcp_kms_no_plaintext_export", ["kms"]),
]


async def seed_cis_gcp_v3(session: AsyncSession) -> None:
    result = await session.execute(
        select(CspmFramework).where(CspmFramework.name == "CIS GCP Foundations v3.0")
    )
    if result.scalars().first():
        return

    framework = CspmFramework(
        id=str(uuid.uuid4()),
        name="CIS GCP Foundations v3.0",
        cloud_provider="gcp",
        version="3.0",
        description="CIS GCP Foundations Benchmark v3.0 covering Identity, Logging, Networking, VMs, Storage, SQL, BigQuery, and Other Security.",
    )
    session.add(framework)
    await session.flush()

    for code, title, desc, sev, rule_fn, services in CIS_GCP_CONTROLS:
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

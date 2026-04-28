"""
Top 20 CIS GCP rule implementations.

Each function receives connector_data dict shaped like:
  {
    "iam_bindings": [...],
    "vpc_networks": [...],
    "firewall_rules": [...],
    "subnets": [...],
    "compute_instances": [...],
    "storage_buckets": [...],
    "cloud_sql_instances": [...],
    "bigquery_datasets": [...],
    "gke_clusters": [...],
    "dns_managed_zones": [...],
    "log_sinks": [...],
    "audit_configs": [...],
  }
"""
from __future__ import annotations

from backend.services.cspm_rules import register_cspm_rule, CspmRuleResult


@register_cspm_rule("check_gcp_mfa_enabled")
def check_gcp_mfa_enabled(connector_data: dict) -> CspmRuleResult:
    bindings = connector_data.get("iam_bindings", [])
    bad = []
    for b in bindings:
        if b.get("role") in ("roles/owner", "roles/editor") and not b.get("mfa_enforced"):
            bad.append(b.get("member", "unknown"))
    if bad:
        return CspmRuleResult(status="fail", evidence={"no_mfa_members": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"bindings_checked": len(bindings)})


@register_cspm_rule("check_gcp_least_privilege")
def check_gcp_least_privilege(connector_data: dict) -> CspmRuleResult:
    bindings = connector_data.get("iam_bindings", [])
    bad = []
    for b in bindings:
        if b.get("member") in ("allUsers", "allAuthenticatedUsers") and b.get("role") != "roles/browser":
            bad.append(f"{b.get('member')}:{b.get('role')}")
    if bad:
        return CspmRuleResult(status="fail", evidence={"overly_permissive": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"bindings_checked": len(bindings)})


@register_cspm_rule("check_gcp_custom_roles")
def check_gcp_custom_roles(connector_data: dict) -> CspmRuleResult:
    bindings = connector_data.get("iam_bindings", [])
    bad = []
    for b in bindings:
        if b.get("role") in ("roles/owner", "roles/editor", "roles/viewer"):
            bad.append(f"{b.get('member')}:{b.get('role')}")
    if bad:
        return CspmRuleResult(status="fail", evidence={"primitive_roles": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"bindings_checked": len(bindings)})


@register_cspm_rule("check_gcp_audit_logging_all")
def check_gcp_audit_logging_all(connector_data: dict) -> CspmRuleResult:
    configs = connector_data.get("audit_configs", [])
    log_types = {c.get("log_type") for c in configs if c.get("log_type")}
    required = {"ADMIN_READ", "DATA_WRITE", "DATA_READ"}
    if required <= log_types:
        return CspmRuleResult(status="pass", evidence={"log_types": list(log_types)})
    return CspmRuleResult(status="fail", evidence={"log_types": list(log_types)}, failing_resource_ids=["global"])


@register_cspm_rule("check_gcp_log_sinks")
def check_gcp_log_sinks(connector_data: dict) -> CspmRuleResult:
    sinks = connector_data.get("log_sinks", [])
    if sinks:
        return CspmRuleResult(status="pass", evidence={"sink_count": len(sinks)})
    return CspmRuleResult(status="fail", evidence={"reason": "no log sinks configured"}, failing_resource_ids=["global"])


@register_cspm_rule("check_gcp_default_network_removed")
def check_gcp_default_network_removed(connector_data: dict) -> CspmRuleResult:
    networks = connector_data.get("vpc_networks", [])
    for n in networks:
        if n.get("name") == "default":
            return CspmRuleResult(status="fail", evidence={"default_network_exists": True}, failing_resource_ids=[n.get("name", "default")])
    return CspmRuleResult(status="pass", evidence={"networks_checked": len(networks)})


@register_cspm_rule("check_gcp_dnssec_enabled")
def check_gcp_dnssec_enabled(connector_data: dict) -> CspmRuleResult:
    zones = connector_data.get("dns_managed_zones", [])
    bad = [z.get("name", "unknown") for z in zones if not z.get("dnssec_config", {}).get("state") == "on"]
    if bad:
        return CspmRuleResult(status="fail", evidence={"dnssec_disabled_zones": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"zones_checked": len(zones)})


@register_cspm_rule("check_gcp_ssh_restricted")
def check_gcp_ssh_restricted(connector_data: dict) -> CspmRuleResult:
    rules = connector_data.get("firewall_rules", [])
    bad = []
    for r in rules:
        if r.get("direction") == "INGRESS" and r.get("allowed", []):
            for a in r.get("allowed", []):
                if "tcp" in a.get("IPProtocol", "") and 22 in a.get("ports", []) and "0.0.0.0/0" in r.get("sourceRanges", []):
                    bad.append(r.get("name", "unknown"))
                    break
    if bad:
        return CspmRuleResult(status="fail", evidence={"open_ssh_firewalls": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"firewalls_checked": len(rules)})


@register_cspm_rule("check_gcp_rdp_restricted")
def check_gcp_rdp_restricted(connector_data: dict) -> CspmRuleResult:
    rules = connector_data.get("firewall_rules", [])
    bad = []
    for r in rules:
        if r.get("direction") == "INGRESS" and r.get("allowed", []):
            for a in r.get("allowed", []):
                ports = [str(p) for p in a.get("ports", [])]
                if "tcp" in a.get("IPProtocol", "") and "3389" in ports and "0.0.0.0/0" in r.get("sourceRanges", []):
                    bad.append(r.get("name", "unknown"))
                    break
    if bad:
        return CspmRuleResult(status="fail", evidence={"open_rdp_firewalls": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"firewalls_checked": len(rules)})


@register_cspm_rule("check_gcp_vpc_flow_logs_enabled")
def check_gcp_vpc_flow_logs_enabled(connector_data: dict) -> CspmRuleResult:
    subnets = connector_data.get("subnets", [])
    bad = [s.get("name", "unknown") for s in subnets if not s.get("enableFlowLogs")]
    if bad:
        return CspmRuleResult(status="fail", evidence={"subnets_without_flow_logs": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"subnets_checked": len(subnets)})


@register_cspm_rule("check_gcp_firewall_no_unrestricted_ingress")
def check_gcp_firewall_no_unrestricted_ingress(connector_data: dict) -> CspmRuleResult:
    rules = connector_data.get("firewall_rules", [])
    bad = []
    for r in rules:
        if r.get("direction") == "INGRESS" and "0.0.0.0/0" in r.get("sourceRanges", []):
            bad.append(r.get("name", "unknown"))
    if bad:
        return CspmRuleResult(status="fail", evidence={"unrestricted_ingress_firewalls": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"firewalls_checked": len(rules)})


@register_cspm_rule("check_gcp_no_default_sa")
def check_gcp_no_default_sa(connector_data: dict) -> CspmRuleResult:
    vms = connector_data.get("compute_instances", [])
    bad = []
    for vm in vms:
        sa = vm.get("serviceAccounts", [{}])[0].get("email", "")
        if sa.endswith("-compute@developer.gserviceaccount.com"):
            bad.append(vm.get("name", "unknown"))
    if bad:
        return CspmRuleResult(status="fail", evidence={"vms_with_default_sa": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"vms_checked": len(vms)})


@register_cspm_rule("check_gcp_shielded_vm_enabled")
def check_gcp_shielded_vm_enabled(connector_data: dict) -> CspmRuleResult:
    vms = connector_data.get("compute_instances", [])
    bad = [vm.get("name", "unknown") for vm in vms if not vm.get("shieldedInstanceConfig", {}).get("enableIntegrityMonitoring")]
    if bad:
        return CspmRuleResult(status="fail", evidence={"vms_without_shielded": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"vms_checked": len(vms)})


@register_cspm_rule("check_gcp_storage_not_public")
def check_gcp_storage_not_public(connector_data: dict) -> CspmRuleResult:
    buckets = connector_data.get("storage_buckets", [])
    bad = []
    for b in buckets:
        for member in b.get("iam_bindings", []):
            if member.get("member") in ("allUsers", "allAuthenticatedUsers"):
                bad.append(b.get("name", "unknown"))
                break
    if bad:
        return CspmRuleResult(status="fail", evidence={"public_buckets": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"buckets_checked": len(buckets)})


@register_cspm_rule("check_gcp_storage_cmek")
def check_gcp_storage_cmek(connector_data: dict) -> CspmRuleResult:
    buckets = connector_data.get("storage_buckets", [])
    bad = [b.get("name", "unknown") for b in buckets if not b.get("encryption", {}).get("defaultKmsKeyName")]
    if bad:
        return CspmRuleResult(status="fail", evidence={"buckets_without_cmek": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"buckets_checked": len(buckets)})


@register_cspm_rule("check_gcp_sql_not_open")
def check_gcp_sql_not_open(connector_data: dict) -> CspmRuleResult:
    instances = connector_data.get("cloud_sql_instances", [])
    bad = []
    for i in instances:
        for acl in i.get("ipConfiguration", {}).get("authorizedNetworks", []):
            if acl.get("value") == "0.0.0.0/0":
                bad.append(i.get("name", "unknown"))
                break
    if bad:
        return CspmRuleResult(status="fail", evidence={"open_sql_instances": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"instances_checked": len(instances)})


@register_cspm_rule("check_gcp_sql_ssl_required")
def check_gcp_sql_ssl_required(connector_data: dict) -> CspmRuleResult:
    instances = connector_data.get("cloud_sql_instances", [])
    bad = [i.get("name", "unknown") for i in instances if not i.get("ipConfiguration", {}).get("requireSsl")]
    if bad:
        return CspmRuleResult(status="fail", evidence={"sql_without_ssl": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"instances_checked": len(instances)})


@register_cspm_rule("check_gcp_bq_not_public")
def check_gcp_bq_not_public(connector_data: dict) -> CspmRuleResult:
    datasets = connector_data.get("bigquery_datasets", [])
    bad = []
    for d in datasets:
        for entry in d.get("access", []):
            if entry.get("specialGroup") in ("allUsers", "allAuthenticatedUsers"):
                bad.append(d.get("datasetReference", {}).get("datasetId", "unknown"))
                break
    if bad:
        return CspmRuleResult(status="fail", evidence={"public_datasets": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"datasets_checked": len(datasets)})


@register_cspm_rule("check_gcp_gke_not_public")
def check_gcp_gke_not_public(connector_data: dict) -> CspmRuleResult:
    clusters = connector_data.get("gke_clusters", [])
    bad = [c.get("name", "unknown") for c in clusters if c.get("masterAuthorizedNetworksConfig", {}).get("cidrBlocks", [{}])[0].get("cidrBlock") == "0.0.0.0/0"]
    if bad:
        return CspmRuleResult(status="fail", evidence={"public_clusters": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"clusters_checked": len(clusters)})


@register_cspm_rule("check_gcp_gke_workload_identity")
def check_gcp_gke_workload_identity(connector_data: dict) -> CspmRuleResult:
    clusters = connector_data.get("gke_clusters", [])
    bad = [c.get("name", "unknown") for c in clusters if not c.get("workloadIdentityConfig", {}).get("workloadPool")]
    if bad:
        return CspmRuleResult(status="fail", evidence={"clusters_without_workload_identity": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"clusters_checked": len(clusters)})

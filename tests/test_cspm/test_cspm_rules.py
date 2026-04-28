"""
Tests for CSPM rule implementations (60 rules total: 20 per cloud).

Each test feeds representative connector_data to a rule and asserts the result.
"""
from __future__ import annotations

import pytest

# Import all rule modules so they register themselves
import backend.services.cspm_rules.aws_rules  # noqa: F401
import backend.services.cspm_rules.azure_rules  # noqa: F401
import backend.services.cspm_rules.gcp_rules  # noqa: F401
from backend.services.cspm_rules import get_cspm_rule, CspmRuleResult


# ---------------------------------------------------------------------------
# AWS Rules (20)
# ---------------------------------------------------------------------------

def test_check_root_mfa_enabled_pass():
    rule = get_cspm_rule("check_root_mfa_enabled")
    data = {"iam_users": [{"user_name": "root", "mfa_enabled": True, "arn": "arn:aws:iam::123:root"}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_root_mfa_enabled_fail():
    rule = get_cspm_rule("check_root_mfa_enabled")
    data = {"iam_users": [{"user_name": "root", "mfa_enabled": False, "arn": "arn:aws:iam::123:root"}]}
    result = rule(data)
    assert result.status == "fail"
    assert result.failing_resource_ids


def test_check_s3_buckets_not_public_pass():
    rule = get_cspm_rule("check_s3_buckets_not_public")
    data = {"s3_buckets": [{"name": "bucket1", "public_read": False, "public_access_block": {"block_public_acls": True}}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_s3_buckets_not_public_fail():
    rule = get_cspm_rule("check_s3_buckets_not_public")
    data = {"s3_buckets": [{"name": "bucket1", "public_read": True, "public_access_block": {"block_public_acls": False}}]}
    result = rule(data)
    assert result.status == "fail"
    assert "bucket1" in result.failing_resource_ids


def test_check_cloudtrail_enabled_all_regions_pass():
    rule = get_cspm_rule("check_cloudtrail_enabled_all_regions")
    data = {"cloudtrail_trails": [{"name": "trail1", "is_multi_region_trail": True}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_cloudtrail_enabled_all_regions_fail():
    rule = get_cspm_rule("check_cloudtrail_enabled_all_regions")
    data = {"cloudtrail_trails": [{"name": "trail1", "is_multi_region_trail": False}]}
    result = rule(data)
    assert result.status == "fail"


def test_check_ebs_volumes_encrypted_pass():
    rule = get_cspm_rule("check_ebs_volumes_encrypted")
    data = {"ec2_volumes": [{"volume_id": "vol-1", "encrypted": True}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_ebs_volumes_encrypted_fail():
    rule = get_cspm_rule("check_ebs_volumes_encrypted")
    data = {"ec2_volumes": [{"volume_id": "vol-1", "encrypted": False}]}
    result = rule(data)
    assert result.status == "fail"


def test_check_security_groups_no_inbound_22_pass():
    rule = get_cspm_rule("check_security_groups_no_inbound_22")
    data = {"ec2_security_groups": [{"group_id": "sg-1", "ingress_rules": [{"from_port": 80, "to_port": 80, "cidr": "0.0.0.0/0"}]}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_security_groups_no_inbound_22_fail():
    rule = get_cspm_rule("check_security_groups_no_inbound_22")
    data = {"ec2_security_groups": [{"group_id": "sg-1", "ingress_rules": [{"from_port": 22, "to_port": 22, "cidr": "0.0.0.0/0"}]}]}
    result = rule(data)
    assert result.status == "fail"


def test_check_security_groups_no_inbound_3389_fail():
    rule = get_cspm_rule("check_security_groups_no_inbound_3389")
    data = {"ec2_security_groups": [{"group_id": "sg-1", "ingress_rules": [{"from_port": 3389, "to_port": 3389, "cidr": "0.0.0.0/0"}]}]}
    result = rule(data)
    assert result.status == "fail"


def test_check_iam_password_policy_pass():
    rule = get_cspm_rule("check_iam_password_policy")
    data = {"iam_password_policy": {"minimum_password_length": 14, "require_symbols": True, "require_numbers": True, "require_uppercase": True, "require_lowercase": True}}
    result = rule(data)
    assert result.status == "pass"


def test_check_iam_password_policy_fail():
    rule = get_cspm_rule("check_iam_password_policy")
    data = {"iam_password_policy": {"minimum_password_length": 8, "require_symbols": False}}
    result = rule(data)
    assert result.status == "fail"


def test_check_access_key_rotation_fail():
    rule = get_cspm_rule("check_access_key_rotation")
    data = {"iam_users": [{"access_keys": [{"access_key_id": "AKIA", "age_days": 120}]}]}
    result = rule(data)
    assert result.status == "fail"


def test_check_unused_credentials_disabled_fail():
    rule = get_cspm_rule("check_unused_credentials_disabled")
    data = {"iam_users": [{"user_name": "alice", "password_last_used_days": 120}]}
    result = rule(data)
    assert result.status == "fail"


def test_check_config_enabled_all_regions_pass():
    rule = get_cspm_rule("check_config_enabled_all_regions")
    data = {"config_rules": [{"ConfigRuleName": "rule1"}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_vpc_flow_logging_enabled_pass():
    rule = get_cspm_rule("check_vpc_flow_logging_enabled")
    data = {"vpcs": [{"vpc_id": "vpc-1"}], "vpc_flow_logs": [{"vpc_id": "vpc-1"}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_s3_encryption_enabled_pass():
    rule = get_cspm_rule("check_s3_encryption_enabled")
    data = {"s3_buckets": [{"name": "b1", "encryption": {"algorithm": "AES256"}}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_rds_encryption_enabled_pass():
    rule = get_cspm_rule("check_rds_encryption_enabled")
    data = {"rds_instances": [{"db_instance_identifier": "db1", "storage_encrypted": True}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_default_security_groups_restricted_pass():
    rule = get_cspm_rule("check_default_security_groups_restricted")
    data = {"ec2_security_groups": [{"group_name": "default", "ingress_rules": []}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_kms_key_rotation_fail():
    rule = get_cspm_rule("check_kms_key_rotation")
    data = {"kms_keys": [{"key_id": "key-1", "key_rotation_enabled": False}]}
    result = rule(data)
    assert result.status == "fail"


def test_check_s3_versioning_enabled_pass():
    rule = get_cspm_rule("check_s3_versioning_enabled")
    data = {"s3_buckets": [{"name": "b1", "versioning_enabled": True}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_waf_enabled_alb_pass():
    rule = get_cspm_rule("check_waf_enabled_alb")
    data = {"elbv2_load_balancers": [{"load_balancer_arn": "alb1", "type": "application"}], "waf_web_acls": [{"resource_arn": "alb1"}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_nacls_no_inbound_22_pass():
    rule = get_cspm_rule("check_nacls_no_inbound_22")
    data = {"nacls": [{"network_acl_id": "nacl-1", "entries": [{"rule_action": "allow", "egress": False, "cidr_block": "10.0.0.0/8", "port_range": {"from": 22}}]}]}
    result = rule(data)
    assert result.status == "pass"


# ---------------------------------------------------------------------------
# Azure Rules (20)
# ---------------------------------------------------------------------------

def test_check_azure_privileged_mfa_pass():
    rule = get_cspm_rule("check_azure_privileged_mfa")
    data = {"aad_users": [{"displayName": "Admin", "assigned_roles": ["Global Administrator"], "mfa_enabled": True}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_azure_privileged_mfa_fail():
    rule = get_cspm_rule("check_azure_privileged_mfa")
    data = {"aad_users": [{"displayName": "Admin", "assigned_roles": ["Global Administrator"], "mfa_enabled": False}]}
    result = rule(data)
    assert result.status == "fail"


def test_check_azure_app_consent_disabled_pass():
    rule = get_cspm_rule("check_azure_app_consent_disabled")
    data = {"aad_directory_settings": {"allow_user_consent": False}}
    result = rule(data)
    assert result.status == "pass"


def test_check_defender_servers_on_pass():
    rule = get_cspm_rule("check_defender_servers_on")
    data = {"defender_plans": [{"plan_name": "Servers", "pricing_tier": "Standard"}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_storage_public_access_disabled_pass():
    rule = get_cspm_rule("check_storage_public_access_disabled")
    data = {"storage_accounts": [{"name": "sa1", "allow_blob_public_access": False}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_storage_public_access_disabled_fail():
    rule = get_cspm_rule("check_storage_public_access_disabled")
    data = {"storage_accounts": [{"name": "sa1", "allow_blob_public_access": True}]}
    result = rule(data)
    assert result.status == "fail"


def test_check_sql_auditing_enabled_pass():
    rule = get_cspm_rule("check_sql_auditing_enabled")
    data = {"sql_servers": [{"name": "sql1", "auditing_settings": {"state": "Enabled"}}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_nsg_no_rdp_internet_fail():
    rule = get_cspm_rule("check_nsg_no_rdp_internet")
    data = {"nsgs": [{"name": "nsg1", "security_rules": [{"direction": "Inbound", "access": "Allow", "protocol": "Tcp", "destination_port_range": "3389", "source_address_prefix": "*"}]}]}
    result = rule(data)
    assert result.status == "fail"


def test_check_appgw_waf_enabled_pass():
    rule = get_cspm_rule("check_appgw_waf_enabled")
    data = {"app_gateways": [{"name": "gw1", "web_application_firewall_configuration": {"enabled": True}}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_vm_disk_encryption_pass():
    rule = get_cspm_rule("check_vm_disk_encryption")
    data = {"vms": [{"name": "vm1", "os_disk": {"encryption": {"type": "AzureDiskEncryption"}}, "data_disks": []}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_keyvault_purge_protection_pass():
    rule = get_cspm_rule("check_keyvault_purge_protection")
    data = {"key_vaults": [{"name": "kv1", "enable_purge_protection": True}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_appservice_https_only_pass():
    rule = get_cspm_rule("check_appservice_https_only")
    data = {"app_services": [{"name": "app1", "https_only": True}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_aks_rbac_enabled_pass():
    rule = get_cspm_rule("check_aks_rbac_enabled")
    data = {"aks_clusters": [{"name": "aks1", "enable_rbac": True}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_aks_network_policy_pass():
    rule = get_cspm_rule("check_aks_network_policy")
    data = {"aks_clusters": [{"name": "aks1", "network_profile": {"network_policy": "calico"}}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_azure_guest_permissions_limited_pass():
    rule = get_cspm_rule("check_azure_guest_permissions_limited")
    data = {"aad_directory_settings": {"guest_permissions": "limited"}}
    result = rule(data)
    assert result.status == "pass"


def test_check_defender_databases_on_pass():
    rule = get_cspm_rule("check_defender_databases_on")
    data = {"defender_plans": [{"plan_name": "Databases", "pricing_tier": "Standard"}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_storage_min_tls_pass():
    rule = get_cspm_rule("check_storage_min_tls")
    data = {"storage_accounts": [{"name": "sa1", "minimum_tls_version": "TLS1_2"}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_sql_tde_enabled_pass():
    rule = get_cspm_rule("check_sql_tde_enabled")
    data = {"sql_servers": [{"name": "sql1", "transparent_data_encryption": {"state": "Enabled"}}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_nsg_no_ssh_internet_fail():
    rule = get_cspm_rule("check_nsg_no_ssh_internet")
    data = {"nsgs": [{"name": "nsg1", "security_rules": [{"direction": "Inbound", "access": "Allow", "protocol": "Tcp", "destination_port_range": "22", "source_address_prefix": "*"}]}]}
    result = rule(data)
    assert result.status == "fail"


def test_check_keyvault_soft_delete_pass():
    rule = get_cspm_rule("check_keyvault_soft_delete")
    data = {"key_vaults": [{"name": "kv1", "enable_soft_delete": True}]}
    result = rule(data)
    assert result.status == "pass"


# ---------------------------------------------------------------------------
# GCP Rules (20)
# ---------------------------------------------------------------------------

def test_check_gcp_mfa_enabled_pass():
    rule = get_cspm_rule("check_gcp_mfa_enabled")
    data = {"iam_bindings": [{"role": "roles/owner", "member": "user:alice@example.com", "mfa_enforced": True}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_gcp_least_privilege_pass():
    rule = get_cspm_rule("check_gcp_least_privilege")
    data = {"iam_bindings": [{"member": "user:alice@example.com", "role": "roles/viewer"}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_gcp_least_privilege_fail():
    rule = get_cspm_rule("check_gcp_least_privilege")
    data = {"iam_bindings": [{"member": "allUsers", "role": "roles/storage.objectViewer"}]}
    result = rule(data)
    assert result.status == "fail"


def test_check_gcp_custom_roles_pass():
    rule = get_cspm_rule("check_gcp_custom_roles")
    data = {"iam_bindings": [{"member": "user:alice@example.com", "role": "projects/p/roles/customRole"}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_gcp_audit_logging_all_pass():
    rule = get_cspm_rule("check_gcp_audit_logging_all")
    data = {"audit_configs": [{"service": "allServices", "log_type": "ADMIN_READ"}, {"service": "allServices", "log_type": "DATA_WRITE"}, {"service": "allServices", "log_type": "DATA_READ"}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_gcp_log_sinks_pass():
    rule = get_cspm_rule("check_gcp_log_sinks")
    data = {"log_sinks": [{"name": "sink1", "destination": "bigquery.googleapis.com/projects/p/datasets/d"}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_gcp_default_network_removed_pass():
    rule = get_cspm_rule("check_gcp_default_network_removed")
    data = {"vpc_networks": [{"name": "prod-vpc"}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_gcp_default_network_removed_fail():
    rule = get_cspm_rule("check_gcp_default_network_removed")
    data = {"vpc_networks": [{"name": "default"}]}
    result = rule(data)
    assert result.status == "fail"


def test_check_gcp_dnssec_enabled_pass():
    rule = get_cspm_rule("check_gcp_dnssec_enabled")
    data = {"dns_managed_zones": [{"name": "zone1", "dnssec_config": {"state": "on"}}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_gcp_ssh_restricted_pass():
    rule = get_cspm_rule("check_gcp_ssh_restricted")
    data = {"firewall_rules": [{"name": "fw1", "direction": "INGRESS", "allowed": [{"IPProtocol": "tcp", "ports": ["22"]}], "sourceRanges": ["10.0.0.0/8"]}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_gcp_rdp_restricted_fail():
    rule = get_cspm_rule("check_gcp_rdp_restricted")
    data = {"firewall_rules": [{"name": "fw1", "direction": "INGRESS", "allowed": [{"IPProtocol": "tcp", "ports": ["3389"]}], "sourceRanges": ["0.0.0.0/0"]}]}
    result = rule(data)
    assert result.status == "fail"


def test_check_gcp_vpc_flow_logs_enabled_pass():
    rule = get_cspm_rule("check_gcp_vpc_flow_logs_enabled")
    data = {"subnets": [{"name": "subnet1", "enableFlowLogs": True}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_gcp_firewall_no_unrestricted_ingress_pass():
    rule = get_cspm_rule("check_gcp_firewall_no_unrestricted_ingress")
    data = {"firewall_rules": [{"name": "fw1", "direction": "INGRESS", "sourceRanges": ["10.0.0.0/8"]}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_gcp_no_default_sa_pass():
    rule = get_cspm_rule("check_gcp_no_default_sa")
    data = {"compute_instances": [{"name": "vm1", "serviceAccounts": [{"email": "custom@project.iam.gserviceaccount.com"}]}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_gcp_shielded_vm_enabled_pass():
    rule = get_cspm_rule("check_gcp_shielded_vm_enabled")
    data = {"compute_instances": [{"name": "vm1", "shieldedInstanceConfig": {"enableIntegrityMonitoring": True}}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_gcp_storage_not_public_pass():
    rule = get_cspm_rule("check_gcp_storage_not_public")
    data = {"storage_buckets": [{"name": "b1", "iam_bindings": [{"member": "user:alice@example.com", "role": "roles/storage.objectViewer"}]}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_gcp_storage_cmek_pass():
    rule = get_cspm_rule("check_gcp_storage_cmek")
    data = {"storage_buckets": [{"name": "b1", "encryption": {"defaultKmsKeyName": "projects/p/locations/global/keyRings/r/cryptoKeys/k"}}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_gcp_sql_not_open_pass():
    rule = get_cspm_rule("check_gcp_sql_not_open")
    data = {"cloud_sql_instances": [{"name": "db1", "ipConfiguration": {"authorizedNetworks": [{"value": "10.0.0.0/8"}]}}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_gcp_bq_not_public_pass():
    rule = get_cspm_rule("check_gcp_bq_not_public")
    data = {"bigquery_datasets": [{"datasetReference": {"datasetId": "ds1"}, "access": [{"role": "READER", "userByEmail": "alice@example.com"}]}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_gcp_gke_not_public_pass():
    rule = get_cspm_rule("check_gcp_gke_not_public")
    data = {"gke_clusters": [{"name": "gke1", "masterAuthorizedNetworksConfig": {"cidrBlocks": [{"cidrBlock": "10.0.0.0/8"}]}}]}
    result = rule(data)
    assert result.status == "pass"


def test_check_gcp_gke_workload_identity_pass():
    rule = get_cspm_rule("check_gcp_gke_workload_identity")
    data = {"gke_clusters": [{"name": "gke1", "workloadIdentityConfig": {"workloadPool": "project.svc.id.goog"}}]}
    result = rule(data)
    assert result.status == "pass"

"""
Top 20 CIS AWS rule implementations.

Each function receives connector_data dict shaped like:
  {
    "iam_users": [...],
    "s3_buckets": [...],
    "ec2_security_groups": [...],
    "ec2_volumes": [...],
    "cloudtrail_trails": [...],
    "rds_instances": [...],
    "kms_keys": [...],
    "vpc_flow_logs": [...],
    "config_rules": [...],
    "waf_web_acls": [...],
    "elbv2_load_balancers": [...],
    "nacls": [...],
  }
"""
from __future__ import annotations

from backend.services.cspm_rules import register_cspm_rule, CspmRuleResult


@register_cspm_rule("check_root_mfa_enabled")
def check_root_mfa_enabled(connector_data: dict) -> CspmRuleResult:
    users = connector_data.get("iam_users", [])
    for u in users:
        if u.get("user_name") == "root" or u.get("arn", "").endswith(":root"):
            if not u.get("mfa_enabled"):
                return CspmRuleResult(
                    status="fail",
                    evidence={"missing_mfa": "root account"},
                    failing_resource_ids=[u.get("arn", "root")],
                )
            return CspmRuleResult(status="pass", evidence={"mfa_enabled": "root account"})
    return CspmRuleResult(status="inconclusive", evidence={"reason": "root account not found"})


@register_cspm_rule("check_s3_buckets_not_public")
def check_s3_buckets_not_public(connector_data: dict) -> CspmRuleResult:
    buckets = connector_data.get("s3_buckets", [])
    public = []
    for b in buckets:
        acl = b.get("acl", {})
        if acl.get("public_read") or b.get("public_access_block", {}).get("block_public_acls") is False:
            public.append(b.get("name", "unknown"))
    if public:
        return CspmRuleResult(status="fail", evidence={"public_buckets": public}, failing_resource_ids=public)
    return CspmRuleResult(status="pass", evidence={"total_buckets": len(buckets)})


@register_cspm_rule("check_cloudtrail_enabled_all_regions")
def check_cloudtrail_enabled_all_regions(connector_data: dict) -> CspmRuleResult:
    trails = connector_data.get("cloudtrail_trails", [])
    multi_region = any(t.get("is_multi_region_trail") for t in trails)
    if multi_region:
        return CspmRuleResult(status="pass", evidence={"multi_region_trails": [t.get("name") for t in trails if t.get("is_multi_region_trail")]})
    if trails:
        return CspmRuleResult(status="fail", evidence={"reason": "no multi-region trail", "trails": [t.get("name") for t in trails]}, failing_resource_ids=[t.get("name") for t in trails])
    return CspmRuleResult(status="fail", evidence={"reason": "no cloudtrail trails found"}, failing_resource_ids=["global"])


@register_cspm_rule("check_ebs_volumes_encrypted")
def check_ebs_volumes_encrypted(connector_data: dict) -> CspmRuleResult:
    volumes = connector_data.get("ec2_volumes", [])
    unencrypted = [v.get("volume_id", "unknown") for v in volumes if not v.get("encrypted")]
    if unencrypted:
        return CspmRuleResult(status="fail", evidence={"unencrypted_volumes": unencrypted}, failing_resource_ids=unencrypted)
    return CspmRuleResult(status="pass", evidence={"total_volumes": len(volumes)})


@register_cspm_rule("check_security_groups_no_inbound_22")
def check_security_groups_no_inbound_22(connector_data: dict) -> CspmRuleResult:
    sgs = connector_data.get("ec2_security_groups", [])
    bad = []
    for sg in sgs:
        for rule in sg.get("ingress_rules", []):
            if rule.get("from_port", 0) <= 22 <= rule.get("to_port", 0) and rule.get("cidr") == "0.0.0.0/0":
                bad.append(sg.get("group_id", "unknown"))
                break
    if bad:
        return CspmRuleResult(status="fail", evidence={"open_ssh_sgs": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"total_sgs": len(sgs)})


@register_cspm_rule("check_security_groups_no_inbound_3389")
def check_security_groups_no_inbound_3389(connector_data: dict) -> CspmRuleResult:
    sgs = connector_data.get("ec2_security_groups", [])
    bad = []
    for sg in sgs:
        for rule in sg.get("ingress_rules", []):
            if rule.get("from_port", 0) <= 3389 <= rule.get("to_port", 0) and rule.get("cidr") == "0.0.0.0/0":
                bad.append(sg.get("group_id", "unknown"))
                break
    if bad:
        return CspmRuleResult(status="fail", evidence={"open_rdp_sgs": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"total_sgs": len(sgs)})


@register_cspm_rule("check_iam_password_policy")
def check_iam_password_policy(connector_data: dict) -> CspmRuleResult:
    policy = connector_data.get("iam_password_policy", {})
    if not policy:
        return CspmRuleResult(status="fail", evidence={"reason": "no password policy found"}, failing_resource_ids=["global"])
    checks = [
        policy.get("minimum_password_length", 0) >= 14,
        policy.get("require_symbols") is True,
        policy.get("require_numbers") is True,
        policy.get("require_uppercase") is True,
        policy.get("require_lowercase") is True,
    ]
    if all(checks):
        return CspmRuleResult(status="pass", evidence={"policy": policy})
    return CspmRuleResult(status="fail", evidence={"policy": policy, "failed_checks": checks}, failing_resource_ids=["global"])


@register_cspm_rule("check_access_key_rotation")
def check_access_key_rotation(connector_data: dict) -> CspmRuleResult:
    users = connector_data.get("iam_users", [])
    stale = []
    for u in users:
        for key in u.get("access_keys", []):
            if key.get("age_days", 0) > 90:
                stale.append(key.get("access_key_id", "unknown"))
    if stale:
        return CspmRuleResult(status="fail", evidence={"stale_keys": stale}, failing_resource_ids=stale)
    return CspmRuleResult(status="pass", evidence={"checked_users": len(users)})


@register_cspm_rule("check_unused_credentials_disabled")
def check_unused_credentials_disabled(connector_data: dict) -> CspmRuleResult:
    users = connector_data.get("iam_users", [])
    bad = []
    for u in users:
        if u.get("password_last_used_days", 0) > 90 or u.get("access_key_last_used_days", 0) > 90:
            bad.append(u.get("user_name", "unknown"))
    if bad:
        return CspmRuleResult(status="fail", evidence={"unused_credentials": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"checked_users": len(users)})


@register_cspm_rule("check_config_enabled_all_regions")
def check_config_enabled_all_regions(connector_data: dict) -> CspmRuleResult:
    rules = connector_data.get("config_rules", [])
    if rules:
        return CspmRuleResult(status="pass", evidence={"config_rules_count": len(rules)})
    return CspmRuleResult(status="fail", evidence={"reason": "no config rules found"}, failing_resource_ids=["global"])


@register_cspm_rule("check_vpc_flow_logging_enabled")
def check_vpc_flow_logging_enabled(connector_data: dict) -> CspmRuleResult:
    vpcs = connector_data.get("vpcs", [])
    logs = connector_data.get("vpc_flow_logs", [])
    logged_vpc_ids = {l.get("vpc_id") for l in logs if l.get("vpc_id")}
    missing = [v.get("vpc_id", "unknown") for v in vpcs if v.get("vpc_id") not in logged_vpc_ids]
    if missing:
        return CspmRuleResult(status="fail", evidence={"vpcs_without_flow_logs": missing}, failing_resource_ids=missing)
    return CspmRuleResult(status="pass", evidence={"vpcs_with_flow_logs": len(vpcs)})


@register_cspm_rule("check_s3_encryption_enabled")
def check_s3_encryption_enabled(connector_data: dict) -> CspmRuleResult:
    buckets = connector_data.get("s3_buckets", [])
    unencrypted = [b.get("name", "unknown") for b in buckets if not b.get("encryption")]
    if unencrypted:
        return CspmRuleResult(status="fail", evidence={"unencrypted_buckets": unencrypted}, failing_resource_ids=unencrypted)
    return CspmRuleResult(status="pass", evidence={"total_buckets": len(buckets)})


@register_cspm_rule("check_rds_encryption_enabled")
def check_rds_encryption_enabled(connector_data: dict) -> CspmRuleResult:
    instances = connector_data.get("rds_instances", [])
    unencrypted = [i.get("db_instance_identifier", "unknown") for i in instances if not i.get("storage_encrypted")]
    if unencrypted:
        return CspmRuleResult(status="fail", evidence={"unencrypted_rds": unencrypted}, failing_resource_ids=unencrypted)
    return CspmRuleResult(status="pass", evidence={"total_rds": len(instances)})


@register_cspm_rule("check_cloudtrail_log_validation")
def check_cloudtrail_log_validation(connector_data: dict) -> CspmRuleResult:
    trails = connector_data.get("cloudtrail_trails", [])
    bad = [t.get("name", "unknown") for t in trails if not t.get("log_file_validation_enabled")]
    if bad:
        return CspmRuleResult(status="fail", evidence={"trails_without_validation": bad}, failing_resource_ids=bad)
    if trails:
        return CspmRuleResult(status="pass", evidence={"validated_trails": [t.get("name") for t in trails]})
    return CspmRuleResult(status="fail", evidence={"reason": "no trails found"}, failing_resource_ids=["global"])


@register_cspm_rule("check_default_security_groups_restricted")
def check_default_security_groups_restricted(connector_data: dict) -> CspmRuleResult:
    sgs = connector_data.get("ec2_security_groups", [])
    bad = [sg.get("group_id", "unknown") for sg in sgs if sg.get("group_name") == "default" and sg.get("ingress_rules", [])]
    if bad:
        return CspmRuleResult(status="fail", evidence={"default_sgs_with_rules": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"default_sgs_checked": len([sg for sg in sgs if sg.get("group_name") == "default"])})


@register_cspm_rule("check_root_not_used")
def check_root_not_used(connector_data: dict) -> CspmRuleResult:
    users = connector_data.get("iam_users", [])
    for u in users:
        if u.get("user_name") == "root" or u.get("arn", "").endswith(":root"):
            if u.get("password_last_used_days", 0) > 0 or u.get("access_key_last_used_days", 0) > 0:
                return CspmRuleResult(status="fail", evidence={"root_used": True}, failing_resource_ids=[u.get("arn", "root")])
            return CspmRuleResult(status="pass", evidence={"root_unused": True})
    return CspmRuleResult(status="inconclusive", evidence={"reason": "root account not found"})


@register_cspm_rule("check_kms_key_rotation")
def check_kms_key_rotation(connector_data: dict) -> CspmRuleResult:
    keys = connector_data.get("kms_keys", [])
    bad = [k.get("key_id", "unknown") for k in keys if not k.get("key_rotation_enabled")]
    if bad:
        return CspmRuleResult(status="fail", evidence={"keys_without_rotation": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"total_keys": len(keys)})


@register_cspm_rule("check_s3_versioning_enabled")
def check_s3_versioning_enabled(connector_data: dict) -> CspmRuleResult:
    buckets = connector_data.get("s3_buckets", [])
    bad = [b.get("name", "unknown") for b in buckets if not b.get("versioning_enabled")]
    if bad:
        return CspmRuleResult(status="fail", evidence={"buckets_without_versioning": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"total_buckets": len(buckets)})


@register_cspm_rule("check_waf_enabled_alb")
def check_waf_enabled_alb(connector_data: dict) -> CspmRuleResult:
    albs = connector_data.get("elbv2_load_balancers", [])
    wafs = connector_data.get("waf_web_acls", [])
    waf_alb_arns = {w.get("resource_arn") for w in wafs if w.get("resource_arn")}
    bad = [a.get("load_balancer_arn", "unknown") for a in albs if a.get("type") == "application" and a.get("load_balancer_arn") not in waf_alb_arns]
    if bad:
        return CspmRuleResult(status="fail", evidence={"albs_without_waf": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"albs_checked": len(albs)})


@register_cspm_rule("check_nacls_no_inbound_22")
def check_nacls_no_inbound_22(connector_data: dict) -> CspmRuleResult:
    nacls = connector_data.get("nacls", [])
    bad = []
    for nacl in nacls:
        for entry in nacl.get("entries", []):
            if entry.get("rule_action") == "allow" and entry.get("egress") is False and entry.get("cidr_block") == "0.0.0.0/0" and entry.get("port_range", {}).get("from") == 22:
                bad.append(nacl.get("network_acl_id", "unknown"))
                break
    if bad:
        return CspmRuleResult(status="fail", evidence={"open_ssh_nacls": bad}, failing_resource_ids=bad)
    return CspmRuleResult(status="pass", evidence={"nacls_checked": len(nacls)})

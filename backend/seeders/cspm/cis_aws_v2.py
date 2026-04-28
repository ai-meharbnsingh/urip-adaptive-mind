"""
CIS AWS Foundations Benchmark v2.0 seeder.

~58 controls across 5 categories:
  1.x Identity and Access Management
  2.x Storage
  3.x Logging
  4.x Monitoring
  5.x Networking
"""
from __future__ import annotations

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.cspm import CspmFramework, CspmControl


# (control_code, title, description, severity, rule_function, affected_services)
CIS_AWS_CONTROLS: list[tuple[str, str, str, str, str | None, list[str]]] = [
    # 1.x Identity and Access Management
    ("CIS-AWS-1.1", "Avoid the use of the root account", "The root account should not be used for everyday tasks.", "critical", "check_root_not_used", ["iam"]),
    ("CIS-AWS-1.2", "Ensure MFA is enabled for the root account", "Multi-factor authentication adds an extra layer of protection.", "critical", "check_root_mfa_enabled", ["iam"]),
    ("CIS-AWS-1.3", "Ensure credentials unused for 90 days are disabled", "Unused credentials increase the attack surface.", "high", "check_unused_credentials_disabled", ["iam"]),
    ("CIS-AWS-1.4", "Ensure access keys are rotated every 90 days", "Regular key rotation limits exposure.", "high", "check_access_key_rotation", ["iam"]),
    ("CIS-AWS-1.5", "Ensure IAM password policy requires minimum length", "Strong password policies reduce brute-force risk.", "medium", "check_password_policy_min_length", ["iam"]),
    ("CIS-AWS-1.6", "Ensure IAM password policy requires symbols", "Password complexity improves resilience.", "medium", "check_password_policy_symbols", ["iam"]),
    ("CIS-AWS-1.7", "Ensure IAM password policy requires numbers", "Password complexity improves resilience.", "medium", "check_password_policy_numbers", ["iam"]),
    ("CIS-AWS-1.8", "Ensure IAM password policy requires uppercase letters", "Password complexity improves resilience.", "medium", "check_password_policy_uppercase", ["iam"]),
    ("CIS-AWS-1.9", "Ensure IAM password policy requires lowercase letters", "Password complexity improves resilience.", "medium", "check_password_policy_lowercase", ["iam"]),
    ("CIS-AWS-1.10", "Ensure IAM password policy prevents reuse", "Preventing reuse stops credential stuffing.", "medium", "check_password_policy_reuse", ["iam"]),
    ("CIS-AWS-1.11", "Ensure IAM password policy expires passwords", "Password expiry forces regular updates.", "medium", "check_password_policy_expiry", ["iam"]),
    ("CIS-AWS-1.12", "Ensure no root account access keys exist", "Root access keys are high-risk.", "critical", "check_root_no_access_keys", ["iam"]),
    ("CIS-AWS-1.13", "Ensure MFA is enabled for all IAM users with console access", "Console users must have MFA.", "high", "check_users_mfa_enabled", ["iam"]),
    ("CIS-AWS-1.14", "Ensure IAM policies are attached only to groups or roles", "Direct user policies are harder to audit.", "medium", "check_policies_attached_to_groups", ["iam"]),
    ("CIS-AWS-1.15", "Ensure IAM users have only the necessary permissions", "Least privilege reduces blast radius.", "medium", "check_least_privilege_iam", ["iam"]),
    ("CIS-AWS-1.16", "Ensure IAM policies do not allow full administrative privileges", "Wildcard policies are dangerous.", "high", "check_no_wildcard_iam_policies", ["iam"]),
    # 2.x Storage
    ("CIS-AWS-2.1", "Ensure S3 buckets are not publicly readable", "Public read access exposes data.", "critical", "check_s3_buckets_not_public", ["s3"]),
    ("CIS-AWS-2.2", "Ensure S3 buckets are not publicly writable", "Public write access allows data tampering.", "critical", "check_s3_buckets_not_public_write", ["s3"]),
    ("CIS-AWS-2.3", "Ensure S3 bucket versioning is enabled", "Versioning protects against accidental deletion.", "medium", "check_s3_versioning_enabled", ["s3"]),
    ("CIS-AWS-2.4", "Ensure S3 buckets have logging enabled", "Logging enables audit and forensics.", "medium", "check_s3_logging_enabled", ["s3"]),
    ("CIS-AWS-2.5", "Ensure S3 buckets have encryption enabled", "Encryption protects data at rest.", "high", "check_s3_encryption_enabled", ["s3", "kms"]),
    ("CIS-AWS-2.6", "Ensure S3 bucket policies restrict HTTPS", "TLS in transit prevents eavesdropping.", "medium", "check_s3_https_only", ["s3"]),
    ("CIS-AWS-2.7", "Ensure EBS volumes are encrypted", "Unencrypted EBS leaks data if accessed.", "high", "check_ebs_volumes_encrypted", ["ec2", "ebs"]),
    ("CIS-AWS-2.8", "Ensure RDS instances are encrypted", "Database encryption protects sensitive data.", "high", "check_rds_encryption_enabled", ["rds", "kms"]),
    ("CIS-AWS-2.9", "Ensure RDS snapshots are encrypted", "Snapshot encryption prevents data leakage.", "high", "check_rds_snapshots_encrypted", ["rds", "kms"]),
    ("CIS-AWS-2.10", "Ensure S3 block public access is enabled at account level", "Account-level block stops accidental exposure.", "high", "check_s3_block_public_access_account", ["s3"]),
    # 3.x Logging
    ("CIS-AWS-3.1", "Ensure CloudTrail is enabled in all regions", "CloudTrail records API activity globally.", "high", "check_cloudtrail_enabled_all_regions", ["cloudtrail"]),
    ("CIS-AWS-3.2", "Ensure CloudTrail log file validation is enabled", "Validation detects tampering.", "medium", "check_cloudtrail_log_validation", ["cloudtrail"]),
    ("CIS-AWS-3.3", "Ensure CloudTrail logs are encrypted with KMS", "Encryption protects audit logs.", "medium", "check_cloudtrail_kms_encryption", ["cloudtrail", "kms"]),
    ("CIS-AWS-3.4", "Ensure CloudTrail logs are sent to CloudWatch", "Real-time monitoring requires CloudWatch integration.", "medium", "check_cloudtrail_cloudwatch_logs", ["cloudtrail", "logs"]),
    ("CIS-AWS-3.5", "Ensure AWS Config is enabled in all regions", "Config tracks resource changes globally.", "high", "check_config_enabled_all_regions", ["config"]),
    ("CIS-AWS-3.6", "Ensure S3 bucket access logging is enabled for CloudTrail", "CloudTrail bucket access must be logged.", "medium", "check_cloudtrail_s3_access_logging", ["s3", "cloudtrail"]),
    ("CIS-AWS-3.7", "Ensure VPC flow logging is enabled", "Flow logs enable network forensics.", "medium", "check_vpc_flow_logging_enabled", ["vpc", "logs"]),
    ("CIS-AWS-3.8", "Ensure log metric filter for unauthorized API calls exists", "Detect brute-force or credential abuse.", "high", "check_log_metric_unauthorized_api", ["logs", "cloudwatch"]),
    ("CIS-AWS-3.9", "Ensure log metric filter for root account usage exists", "Alert when root is used.", "high", "check_log_metric_root_usage", ["logs", "cloudwatch"]),
    ("CIS-AWS-3.10", "Ensure log metric filter for IAM policy changes exists", "Detect privilege escalation.", "medium", "check_log_metric_iam_changes", ["logs", "cloudwatch"]),
    # 4.x Monitoring
    ("CIS-AWS-4.1", "Ensure a log metric filter and alarm exist for VPC changes", "Detect unauthorized network changes.", "medium", "check_alarm_vpc_changes", ["logs", "cloudwatch"]),
    ("CIS-AWS-4.2", "Ensure a log metric filter and alarm exist for S3 policy changes", "Detect data exposure changes.", "medium", "check_alarm_s3_policy_changes", ["logs", "cloudwatch"]),
    ("CIS-AWS-4.3", "Ensure a log metric filter and alarm exist for root account usage", "Alert on root usage.", "high", "check_alarm_root_usage", ["logs", "cloudwatch"]),
    ("CIS-AWS-4.4", "Ensure a log metric filter and alarm exist for IAM changes", "Detect privilege escalation.", "medium", "check_alarm_iam_changes", ["logs", "cloudwatch"]),
    ("CIS-AWS-4.5", "Ensure a log metric filter and alarm exist for CloudTrail changes", "Detect audit log tampering.", "high", "check_alarm_cloudtrail_changes", ["logs", "cloudwatch"]),
    ("CIS-AWS-4.6", "Ensure a log metric filter and alarm exist for console sign-in failures", "Detect brute force.", "medium", "check_alarm_console_failures", ["logs", "cloudwatch"]),
    ("CIS-AWS-4.7", "Ensure a log metric filter and alarm exist for disabling deletion of KMS keys", "Detect key destruction attempts.", "high", "check_alarm_kms_deletion", ["logs", "cloudwatch", "kms"]),
    ("CIS-AWS-4.8", "Ensure a log metric filter and alarm exist for AWS Config changes", "Detect compliance tampering.", "medium", "check_alarm_config_changes", ["logs", "cloudwatch", "config"]),
    ("CIS-AWS-4.9", "Ensure a log metric filter and alarm exist for security group changes", "Detect unauthorized network access.", "medium", "check_alarm_sg_changes", ["logs", "cloudwatch", "ec2"]),
    ("CIS-AWS-4.10", "Ensure a log metric filter and alarm exist for NACL changes", "Detect network ACL tampering.", "medium", "check_alarm_nacl_changes", ["logs", "cloudwatch", "ec2"]),
    ("CIS-AWS-4.11", "Ensure a log metric filter and alarm exist for network gateway changes", "Detect exfiltration paths.", "medium", "check_alarm_gateway_changes", ["logs", "cloudwatch", "ec2"]),
    ("CIS-AWS-4.12", "Ensure a log metric filter and alarm exist for route table changes", "Detect traffic hijacking.", "medium", "check_alarm_route_table_changes", ["logs", "cloudwatch", "ec2"]),
    ("CIS-AWS-4.13", "Ensure a log metric filter and alarm exist for VPC peering changes", "Detect lateral movement paths.", "medium", "check_alarm_vpc_peering_changes", ["logs", "cloudwatch", "ec2"]),
    # 5.x Networking
    ("CIS-AWS-5.1", "Ensure no security groups allow unrestricted ingress on port 22", "SSH open to 0.0.0.0/0 is a major risk.", "critical", "check_security_groups_no_inbound_22", ["ec2"]),
    ("CIS-AWS-5.2", "Ensure no security groups allow unrestricted ingress on port 3389", "RDP open to 0.0.0.0/0 is a major risk.", "critical", "check_security_groups_no_inbound_3389", ["ec2"]),
    ("CIS-AWS-5.3", "Ensure default security groups restrict all traffic", "Default SGs should deny by default.", "high", "check_default_security_groups_restricted", ["ec2"]),
    ("CIS-AWS-5.4", "Ensure VPC default is not used for production", "Default VPC lacks segmentation.", "medium", "check_default_vpc_not_used", ["vpc", "ec2"]),
    ("CIS-AWS-5.5", "Ensure Network ACLs do not allow unrestricted ingress on port 22", "NACLs should be restrictive.", "high", "check_nacls_no_inbound_22", ["vpc", "ec2"]),
    ("CIS-AWS-5.6", "Ensure Network ACLs do not allow unrestricted ingress on port 3389", "NACLs should be restrictive.", "high", "check_nacls_no_inbound_3389", ["vpc", "ec2"]),
    ("CIS-AWS-5.7", "Ensure VPC flow logging is enabled for all VPCs", "Flow logs are essential for forensics.", "medium", "check_vpc_flow_logging_all", ["vpc", "logs"]),
    ("CIS-AWS-5.8", "Ensure AWS WAF is enabled on CloudFront distributions", "WAF protects edge traffic.", "medium", "check_waf_enabled_cloudfront", ["cloudfront", "waf"]),
    ("CIS-AWS-5.9", "Ensure AWS WAF is enabled on ALBs", "WAF protects application traffic.", "medium", "check_waf_enabled_alb", ["elb", "waf"]),
]


async def seed_cis_aws_v2(session: AsyncSession) -> None:
    result = await session.execute(
        select(CspmFramework).where(CspmFramework.name == "CIS AWS Foundations v2.0")
    )
    if result.scalars().first():
        return

    framework = CspmFramework(
        id=str(uuid.uuid4()),
        name="CIS AWS Foundations v2.0",
        cloud_provider="aws",
        version="2.0",
        description="CIS AWS Foundations Benchmark v2.0 covering Identity, Storage, Logging, Monitoring, and Networking.",
    )
    session.add(framework)
    await session.flush()

    for code, title, desc, sev, rule_fn, services in CIS_AWS_CONTROLS:
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

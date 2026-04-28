"""
Rule: encryption_at_rest_configured — P2B.3

Checks that encryption at rest is configured for the tenant's primary data stores.

Maps to:
  SOC 2:    CC6.7 (Encryption at rest)
  ISO 27001: 8.24 (Use of cryptography)

tenant_config keys used:
  encryption_at_rest_enabled (bool) — whether encryption is enabled on primary DB
  encryption_algorithm (str, optional) — e.g. "AES-256", "AES-128"
  kms_key_managed (bool, optional) — whether customer manages the KMS key

TODO: Integrate with URIP cloud connector to verify actual AWS/GCP/Azure
      encryption settings on RDS/GCS/Azure SQL instances.
"""
from compliance_backend.services.control_rules import register_control_rule
from compliance_backend.services.control_rules.base import (
    BaseControlRule,
    ControlContext,
    ControlCheckResult,
    EvidenceSpec,
)

REQUIRED_ALGORITHMS = {"AES-256", "AES-128"}


@register_control_rule("encryption_at_rest_configured")
class EncryptionAtRestRule(BaseControlRule):
    name = "Encryption at Rest Configured"
    description = (
        "Verifies that encryption at rest is enabled on primary data stores "
        "using an approved algorithm (AES-128 or AES-256)."
    )

    def check(self, tenant_id: str, context: ControlContext) -> ControlCheckResult:
        cfg = context.tenant_config
        enabled = cfg.get("encryption_at_rest_enabled", False)
        algorithm = cfg.get("encryption_algorithm", "")

        evidence = [
            EvidenceSpec(
                type="config",
                content={
                    "encryption_at_rest_enabled": enabled,
                    "encryption_algorithm": algorithm,
                },
                metadata={"rule": "encryption_at_rest_configured", "tenant_id": tenant_id},
            )
        ]

        if not enabled:
            return ControlCheckResult(
                status="fail",
                evidence=evidence,
                failure_reason=(
                    "Encryption at rest is not enabled. "
                    "Enable database-level encryption on all primary data stores."
                ),
            )

        if algorithm and algorithm not in REQUIRED_ALGORITHMS:
            return ControlCheckResult(
                status="fail",
                evidence=evidence,
                failure_reason=(
                    f"Encryption algorithm '{algorithm}' is not in the approved set "
                    f"{REQUIRED_ALGORITHMS}."
                ),
            )

        return ControlCheckResult(status="pass", evidence=evidence)

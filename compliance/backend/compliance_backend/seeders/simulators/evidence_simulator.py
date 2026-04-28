"""
evidence_simulator — generate Evidence records + actual placeholder files.

Behavior:
  - For each Control: create `per_control` evidence rows (default 2).
  - Evidence type rotates through: screenshot, config, log, ticket, document.
  - Real bytes written via the FilesystemStorage backend so storage_uri
    points to an actual file the API can serve.
  - File contents are realistic JSON/CSV/text snippets, not "placeholder".
  - metadata_json includes source tool, region, captured-by, etc.

Idempotency: skip if any Evidence rows exist for tenant.
"""
from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.models.evidence import Evidence
from compliance_backend.models.framework import Control, FrameworkVersion
from compliance_backend.services.storage import get_storage
from compliance_backend.seeders.simulators._common import (
    make_rng,
    stable_uuid,
    now_utc,
)


EVIDENCE_TYPES = ("screenshot", "config", "log", "ticket", "document")


# ─────────────────────────────────────────────────────────────────────────────
# Realistic content generators per evidence type
# ─────────────────────────────────────────────────────────────────────────────


def _generate_config_content(rule: Optional[str], rng: random.Random) -> tuple[str, bytes, dict]:
    """Return (filename, bytes, metadata) for a config-type evidence."""
    if rule == "mfa_enforced":
        payload = {
            "tenant_id": "adverb.in",
            "mfa_enabled": True,
            "mfa_enforcement": "all_users",
            "exempted_users": [],
            "factors_required": ["sms_otp", "totp", "fido2"],
            "minimum_factors": 2,
            "captured_at": now_utc().isoformat(),
        }
        return ("entra_mfa_settings.json", json.dumps(payload, indent=2).encode(), {
            "source": "azure_entra",
            "rule": rule,
            "endpoint": "/policies/identitySecurityDefaultsEnforcementPolicy",
        })
    if rule == "encryption_at_rest":
        payload = {
            "aws_account": "adverb-prod-master",
            "rds_instances": [
                {"id": "prod-billing-db", "engine": "aurora-postgresql", "encrypted": True, "kms_key": "arn:aws:kms:us-east-1:111122223333:key/abc"},
                {"id": "prod-crm-db", "engine": "postgres", "encrypted": True, "kms_key": "arn:aws:kms:us-east-1:111122223333:key/xyz"},
            ],
            "s3_buckets_with_default_encryption": 47,
            "s3_buckets_total": 47,
        }
        return ("aws_encryption_inventory.json", json.dumps(payload, indent=2).encode(), {
            "source": "aws_config",
            "region": "us-east-1",
            "rule": rule,
        })
    if rule == "audit_logging_enabled":
        payload = {
            "cloudtrail": {
                "trail_name": "adverb-org-trail",
                "is_multi_region_trail": True,
                "is_organization_trail": True,
                "log_file_validation_enabled": True,
                "kms_encrypted": True,
                "s3_bucket": "adverb-cloudtrail-logs-prod",
                "retention_days": 730,
            },
            "azure_ad": {
                "diagnostic_settings_enabled": True,
                "log_analytics_workspace": "law-adverb-prod",
                "retention_days": 365,
            },
        }
        return ("audit_logging_config.json", json.dumps(payload, indent=2).encode(), {
            "source": "aws_cloudtrail+azure_ad",
            "rule": rule,
        })
    # Generic
    payload = {
        "rule": rule or "manual",
        "checked_at": now_utc().isoformat(),
        "config_snapshot": {
            "compliant": True,
            "drift_detected": False,
            "last_change": (now_utc() - timedelta(days=rng.randint(1, 30))).isoformat(),
        },
    }
    return ("config_snapshot.json", json.dumps(payload, indent=2).encode(), {
        "source": "control_engine",
        "rule": rule,
    })


def _generate_log_content(rule: Optional[str], rng: random.Random) -> tuple[str, bytes, dict]:
    """Return (filename, bytes, metadata) for a log-type evidence."""
    if rule == "access_review_completed":
        rows = [
            "user_id,email,reviewer,decision,decided_at,justification",
        ]
        for i in range(20):
            rows.append(
                f"u{1000+i},employee{i}@adverb.in,manager{i%5}@adverb.in,"
                f"{rng.choice(['keep', 'keep', 'keep', 'revoke'])},"
                f"{(now_utc() - timedelta(days=rng.randint(1, 30))).isoformat()},"
                f"{'role-still-required' if rng.random() < 0.95 else 'departing-2026-Q3'}"
            )
        body = "\n".join(rows).encode()
        return ("access_review_export_2026Q1.csv", body, {
            "source": "iga_export",
            "rule": rule,
            "rows": 20,
        })
    # Generic audit log excerpt
    lines = []
    for i in range(15):
        ts = (now_utc() - timedelta(minutes=rng.randint(0, 1440))).isoformat()
        actor = f"user-{rng.randint(100, 999)}@adverb.in"
        action = rng.choice(["read", "update", "create", "delete", "list"])
        resource = rng.choice(["policy/AUP", "control/CC6.1", "evidence/123", "vendor/aws"])
        lines.append(f"{ts}\t{actor}\t{action}\t{resource}")
    body = "\n".join(lines).encode()
    return ("audit_log_excerpt.tsv", body, {
        "source": "audit_service",
        "rule": rule,
        "lines": len(lines),
    })


def _generate_ticket_content(rule: Optional[str], rng: random.Random) -> tuple[str, bytes, dict]:
    """Return (filename, bytes, metadata) for a ticket-export evidence."""
    payload = {
        "system": "Atlassian JIRA",
        "project": "ADV-OPS",
        "exported_at": now_utc().isoformat(),
        "tickets": [
            {
                "id": f"ADV-OPS-{rng.randint(1000, 9999)}",
                "title": rng.choice([
                    "Quarterly access review — Q1 2026 — AWS Production",
                    "Patch CVE-2024-3400 across PAN-OS firewalls",
                    "Renew Cloudflare WAF subscription (annual)",
                    "Review and approve new vendor: PixelWave Design Studio",
                    "Tabletop exercise — ransomware scenario — H1 2026",
                ]),
                "status": rng.choice(["Done", "Done", "In Progress", "To Do"]),
                "assignee": f"user-{rng.randint(100, 999)}@adverb.in",
                "created": (now_utc() - timedelta(days=rng.randint(15, 90))).isoformat(),
                "resolved": (now_utc() - timedelta(days=rng.randint(1, 14))).isoformat()
                if rng.random() < 0.7 else None,
            }
            for _ in range(8)
        ],
    }
    body = json.dumps(payload, indent=2).encode()
    return ("jira_ticket_export.json", body, {
        "source": "jira",
        "rule": rule,
        "ticket_count": len(payload["tickets"]),
    })


def _generate_screenshot_content(rule: Optional[str], rng: random.Random) -> tuple[str, bytes, dict]:
    """
    Return a valid 1x1 PNG (smallest legal PNG) with metadata describing
    the captured screen. Real screenshots are out of scope; the contract
    is "a real file exists with valid bytes".
    """
    # 67-byte minimal PNG (1×1 transparent pixel).
    png_bytes = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c63000100000005000100"
        "0d0a2db40000000049454e44ae426082"
    )
    metadata = {
        "source": "screen_capture",
        "rule": rule,
        "tool": rng.choice(["AWS Console", "Azure Portal", "Okta Admin", "GitHub Settings"]),
        "captured_view": rng.choice([
            "IAM Users — MFA column shows 'Enabled' for all rows",
            "S3 Bucket Properties — Default encryption enabled (SSE-KMS)",
            "Azure Conditional Access — Require MFA policy enabled",
            "GitHub Org → Security → 2FA requirement enforced",
        ]),
        "image_format": "PNG",
        "image_dimensions": "1x1",
    }
    return ("settings_screenshot.png", png_bytes, metadata)


def _generate_document_content(rule: Optional[str], rng: random.Random) -> tuple[str, bytes, dict]:
    """Return (filename, bytes, metadata) for a document evidence."""
    text = (
        "ADVERB TECHNOLOGIES — Policy Attestation Document\n"
        "==================================================\n\n"
        f"Policy: {rng.choice(['Acceptable Use', 'Data Classification', 'Incident Response Plan', 'Backup & Recovery'])}\n"
        f"Version: 2.0\n"
        f"Effective Date: {(now_utc() - timedelta(days=rng.randint(30, 180))).date().isoformat()}\n"
        f"Owner: CISO Office\n\n"
        f"This document attests that the above policy has been reviewed and approved\n"
        f"by senior leadership for the current audit period. The policy is published\n"
        f"in the corporate handbook and acknowledged by all employees as part of\n"
        f"annual security training.\n\n"
        f"Approver: Vikram Mehta (CISO)\n"
        f"Approval Date: {(now_utc() - timedelta(days=rng.randint(15, 90))).isoformat()}\n"
    )
    return ("policy_attestation.txt", text.encode(), {
        "source": "policy_management",
        "rule": rule,
        "format": "text/plain",
    })


CONTENT_GENERATORS = {
    "config": _generate_config_content,
    "log": _generate_log_content,
    "ticket": _generate_ticket_content,
    "screenshot": _generate_screenshot_content,
    "document": _generate_document_content,
}


def _audit_period_for(dt: datetime) -> str:
    """Format an audit period string from a date."""
    quarter = (dt.month - 1) // 3 + 1
    return f"{dt.year}-Q{quarter}"


async def simulate_evidence(
    session: AsyncSession,
    *,
    tenant_id: str,
    per_control: int = 2,
    seed: int = 42,
    skip_if_existing: bool = True,
) -> dict[str, int]:
    """
    Generate Evidence rows + write real placeholder files via configured storage.

    Args:
        tenant_id:        Tenant scope.
        per_control:      Evidence rows per control (default 2).
        seed:             RNG seed.
        skip_if_existing: If any Evidence rows exist for tenant, no-op.
    """
    rng = make_rng(seed)

    if skip_if_existing:
        existing = (await session.execute(
            select(func.count()).select_from(Evidence).where(Evidence.tenant_id == tenant_id)
        )).scalar() or 0
        if existing > 0:
            return {"created": 0, "files_written": 0, "skipped": existing, "tenant_id": tenant_id}

    controls = (await session.execute(select(Control))).scalars().all()
    if not controls:
        return {"created": 0, "files_written": 0, "tenant_id": tenant_id, "warning": "no controls"}

    # Pre-compute control_id -> framework_id mapping
    fws = (await session.execute(select(FrameworkVersion))).scalars().all()
    fv_map = {fv.id: fv.framework_id for fv in fws}

    storage = get_storage()
    created = 0
    files_written = 0

    for control in controls:
        for i in range(per_control):
            etype = EVIDENCE_TYPES[(hash(control.id) + i) % len(EVIDENCE_TYPES)]
            generator = CONTENT_GENERATORS[etype]
            filename, content, metadata = generator(control.rule_function, rng)

            captured_at = now_utc() - timedelta(days=rng.randint(0, 90), hours=rng.randint(0, 23))
            audit_period = _audit_period_for(captured_at)

            # Write file to storage
            try:
                storage_uri = await storage.write(tenant_id, audit_period, filename, content)
                files_written += 1
            except Exception as exc:
                # Storage failure should not block DB row creation in demo mode
                storage_uri = f"file:///dev/null/{filename}"

            framework_id = fv_map.get(control.framework_version_id)
            metadata = {
                **metadata,
                "control_code": control.control_code,
                "tenant_id": tenant_id,
            }

            ev = Evidence(
                id=stable_uuid(tenant_id, "evidence", control.id, str(i)),
                control_id=control.id,
                framework_id=framework_id,
                tenant_id=tenant_id,
                type=etype,
                storage_uri=storage_uri,
                audit_period=audit_period,
                captured_at=captured_at,
                captured_by="system",
                metadata_json=metadata,
            )
            session.add(ev)
            created += 1

    await session.flush()
    return {
        "created": created,
        "files_written": files_written,
        "skipped": 0,
        "tenant_id": tenant_id,
    }

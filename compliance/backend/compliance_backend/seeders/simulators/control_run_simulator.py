"""
control_run_simulator — synthesize ControlCheckRun history for a tenant.

Output characteristics:
  - For each Control in the tenant's seeded frameworks, generates 8-16 runs
    spanning the last `days` days (default 90).
  - Status mix: ~75% pass / ~15% fail / ~10% inconclusive.
  - Failure reasons match the rule logic the control would actually exercise
    (e.g. mfa_enforced control fails with "MFA not enforced for 3 admin users").
  - Passing runs reference 1-2 evidence_ids (placeholder UUIDs — the
    evidence_simulator wires real Evidence records on a separate pass).

Idempotency strategy:
  Detects existing runs by (tenant_id) and short-circuits if any are found.
  Reset is performed by the master orchestrator (run_simulators.py) which
  moves rows to a backup table — never DELETEs.

Realism:
  Failure messages are drawn from a curated FAILURE_REASONS_BY_RULE dict.
  Each entry is a paragraph-length explanation a real auditor would write.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.models.control_run import ControlCheckRun
from compliance_backend.models.framework import Control, Framework, FrameworkVersion
from compliance_backend.seeders.simulators._common import (
    make_rng,
    stable_uuid,
    now_utc,
)


# ─────────────────────────────────────────────────────────────────────────────
# Realistic failure reasons — keyed on control rule_function (when set) or by
# control_code prefix as fallback.
# ─────────────────────────────────────────────────────────────────────────────

FAILURE_REASONS_BY_RULE: dict[str, list[str]] = {
    "mfa_enforced": [
        "MFA enforcement is set to 'admins_only' but the policy requires 'all_users'. 17 standard users currently bypass MFA via legacy auth.",
        "MFA is not enforced for 3 service accounts (svc-billing-sync, svc-crm-integration, svc-okta-bridge). Service principals must use certificate-based auth or vault-backed secrets.",
        "Conditional Access policy 'Require MFA for all users' has 12 named exclusions. Re-evaluate exclusions or migrate to break-glass account model.",
        "Legacy authentication (POP3/IMAP/SMTP basic) remains enabled for 5 mailboxes — MFA cannot protect these protocols.",
    ],
    "encryption_at_rest": [
        "AWS RDS instance prod-billing-db is unencrypted. Snapshot, restore as encrypted, then cut over.",
        "S3 bucket adverb-logs-staging has default encryption disabled. Apply bucket policy with aws:kms encryption requirement.",
        "Azure SQL database adverb-hr-prod uses TDE but with service-managed key — required policy is customer-managed key (CMK).",
        "BitLocker is not enabled on 5 laptops issued in the last 30 days. IT enrollment script omitted bdeServiceKey provisioning.",
    ],
    "audit_logging_enabled": [
        "AWS CloudTrail is enabled in us-east-1 only. Multi-region trail required for SOC 2 CC7.2 — apply organization trail.",
        "Azure AD audit log retention is 30 days (default). Compliance requires 365 days — enable Azure Monitor + Log Analytics archive.",
        "GitHub audit log streaming is not configured. Enable streaming to S3 to satisfy 12-month retention.",
        "Salesforce Event Monitoring is unlicensed — purchase Shield or use Event Log File API for daily extraction.",
    ],
    "backup_configured": [
        "AWS RDS automated backups disabled on prod-crm-db (manual snapshot last taken 2026-01-12). Enable PITR with 14-day retention.",
        "Backup verification has not run in 47 days. Restore drills required quarterly per SOC 2 A1.2.",
        "Azure Backup is not configured for 3 IaaS VMs in the analytics resource group.",
        "GCP backup policy missing for 2 BigQuery datasets containing customer data.",
    ],
    "access_review_completed": [
        "Q1 2026 access review for AWS Production accounts has not started — due 2026-04-15, currently 12 days overdue.",
        "Q4 2025 access review completed but 8 decisions are missing reviewer attestation. Re-open campaign and request Director sign-off.",
        "Service account inventory not reconciled with quarterly review (3 accounts missing from review scope).",
        "GitHub org owner role review skipped for Q1 2026 — required for SOC 2 CC6.3 evidence.",
    ],
    "incident_response_plan": [
        "Incident response plan has not been reviewed in 13 months — required annually per SOC 2 CC7.4.",
        "Tabletop exercise log shows last simulation was 2024-11. Required cadence: bi-annual.",
        "On-call rotation gaps identified for nights of 2026-04-12 through 2026-04-18.",
        "IR plan does not include the new GitHub Enterprise integration onboarded in Q4 2025.",
    ],
    "vendor_risk_review": [
        "5 critical vendors have expired SOC 2 reports (>15 months old): AWS, Salesforce, Okta, Workday, GitHub.",
        "Annual vendor risk reassessment overdue for 8 vendors (deadline 2026-03-31).",
        "DPA missing for 3 GDPR-relevant vendors: Datadog, Twilio, Zoom.",
        "Vendor questionnaire for Sentinel Security Vendor returned with 4 unsatisfactory responses (no MFA, no encryption-in-transit attestation).",
    ],
    "vulnerability_scanning": [
        "Tenable Nessus scan has not completed against the Production VPC in 12 days — required weekly per PCI DSS 11.3.1.",
        "Authenticated scan coverage is 78% of in-scope assets (target: 95%). 23 endpoints have stale agents.",
        "Critical CVE-2024-3400 (PAN-OS) detected on ADV-FW-EDGE-01 — 9 days past 7-day SLA.",
        "Container image scan (Trivy) reports 4 critical CVEs in production images deployed last week.",
    ],
    "password_policy": [
        "Password policy permits 8-character minimum (compliance baseline: 12 characters).",
        "Password reuse history is 5 (target: 24) — increase via Group Policy / Conditional Access.",
        "12 service accounts have non-expiring passwords. Migrate to managed identities or rotate on a 180-day schedule.",
        "Account lockout threshold is 10 failed attempts (target: 5).",
    ],
    "security_training_completed": [
        "Security awareness training completion rate is 76% (target: 95%) for 2026 annual cycle. 47 employees have not completed by deadline.",
        "Phishing simulation Q1 2026 click rate is 14% (target: <5%). Schedule remedial training for 19 high-risk users.",
        "New-hire security training compliance is 88% within 30-day onboarding window. 6 new hires past 30 days without completion.",
        "Privileged user training (annual) overdue for 4 SREs and 2 platform engineers.",
    ],
}

GENERIC_FAILURE_REASONS: list[str] = [
    "Control evidence collection produced incomplete results — automated rule evaluation could not confirm compliance. Manual verification required.",
    "Sample test against control population revealed 3 exceptions (out of 25 sampled). Exceptions documented in evidence package; remediation plan owed.",
    "Control owner has not attested to operating effectiveness in the current period. Attestation due quarterly.",
    "Detective control fired but compensating control evidence is missing for the current audit period.",
    "Configuration drift detected between approved baseline and current state — investigation in progress.",
]

INCONCLUSIVE_REASONS: list[str] = [
    "Connector failed to reach upstream system (timeout after 30s). Retry scheduled at next cadence.",
    "Tenant configuration is missing required key — control rule cannot evaluate without it. Treating as inconclusive (not failure) pending admin input.",
    "Insufficient sample population for statistical confidence — control will be re-evaluated at next quarterly review.",
    "Upstream identity provider returned an error during evidence collection (HTTP 503 from Okta /api/v1/groups).",
    "Manual control — automated check skipped; awaiting reviewer attestation.",
]


def _failure_reason_for(rule: Optional[str], rng: random.Random) -> str:
    """Return a realistic failure reason tied to the control's rule function."""
    if rule and rule in FAILURE_REASONS_BY_RULE:
        return rng.choice(FAILURE_REASONS_BY_RULE[rule])
    return rng.choice(GENERIC_FAILURE_REASONS)


def _evidence_ref_uuid(tenant_id: str, control_id: str, run_idx: int, seq: int) -> str:
    """
    Stable evidence ID referenced by this run.
    Real Evidence rows are created by evidence_simulator and the IDs may match
    these references if both simulators run with the same tenant_slug — that's
    the contract that lets controls "show their evidence".
    """
    return stable_uuid(tenant_id, "evidence", control_id, str(run_idx), str(seq))


async def simulate_control_runs(
    session: AsyncSession,
    *,
    tenant_id: str,
    days: int = 90,
    seed: int = 42,
    runs_per_control: tuple[int, int] = (8, 16),
    pass_pct: float = 0.75,
    fail_pct: float = 0.15,
    skip_if_existing: bool = True,
) -> dict[str, int]:
    """
    Generate ControlCheckRun history for a tenant.

    Args:
        session:           AsyncSession bound to compliance DB.
        tenant_id:         Target tenant_id (slug or UUID).
        days:              Window to spread runs over (1..365).
        seed:              RNG seed for deterministic output.
        runs_per_control:  Min/max runs per control (random per control).
        pass_pct:          Target pass ratio (default 0.75).
        fail_pct:          Target fail ratio (default 0.15).
                           Inconclusive ratio is the remainder.
        skip_if_existing:  If True (default), no-op when any rows already
                           exist for this tenant — guarantees idempotency.

    Returns:
        Dict with counts: {"created": N, "skipped": M, "tenant_id": ...}
    """
    rng = make_rng(seed)

    if skip_if_existing:
        existing = (await session.execute(
            select(func.count()).select_from(ControlCheckRun).where(
                ControlCheckRun.tenant_id == tenant_id
            )
        )).scalar() or 0
        if existing > 0:
            return {"created": 0, "skipped": existing, "tenant_id": tenant_id}

    # Pull all controls — assumes seeders have run already
    controls = (await session.execute(select(Control))).scalars().all()
    if not controls:
        return {"created": 0, "skipped": 0, "tenant_id": tenant_id, "warning": "no controls; run framework seeders first"}

    now = now_utc()
    created = 0
    incon_pct = 1.0 - pass_pct - fail_pct

    for control in controls:
        n_runs = rng.randint(*runs_per_control)
        for run_idx in range(n_runs):
            day_offset = rng.randint(0, days)
            run_at = now - timedelta(days=day_offset, hours=rng.randint(0, 23), minutes=rng.randint(0, 59))

            r = rng.random()
            if r < pass_pct:
                status = "pass"
                failure_reason = None
                # 80% of passing runs reference 1-2 evidence ids
                if rng.random() < 0.8:
                    n_ev = rng.randint(1, 2)
                    evidence_ids = [
                        _evidence_ref_uuid(tenant_id, control.id, run_idx, i)
                        for i in range(n_ev)
                    ]
                else:
                    evidence_ids = []
            elif r < pass_pct + fail_pct:
                status = "fail"
                failure_reason = _failure_reason_for(control.rule_function, rng)
                evidence_ids = [
                    _evidence_ref_uuid(tenant_id, control.id, run_idx, 0)
                ]
            else:
                status = "inconclusive"
                failure_reason = rng.choice(INCONCLUSIVE_REASONS)
                evidence_ids = []

            row = ControlCheckRun(
                id=stable_uuid(tenant_id, "control_run", control.id, str(run_idx)),
                control_id=control.id,
                tenant_id=tenant_id,
                run_at=run_at,
                status=status,
                evidence_ids=evidence_ids,
                failure_reason=failure_reason,
            )
            session.add(row)
            created += 1

    await session.flush()
    return {"created": created, "skipped": 0, "tenant_id": tenant_id}

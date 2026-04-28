"""
Control Monitoring Engine — P2B.3 orchestrator.

Responsibilities:
  1. Discover all registered control rules (via the plugin registry)
  2. Run a single control check for a given control + tenant
  3. Write the result as a ControlCheckRun record
  4. Auto-capture evidence via EvidenceService (bridge: P2B.3 → P2B.4)

Scheduling note:
  Scheduled (cron-like) execution is handled by APScheduler or Celery Beat
  in the production deployment. This module provides the core run logic only.
  See TODO below for scheduling integration.

Usage:
    from compliance_backend.services.control_engine import ControlEngine

    engine = ControlEngine(db)
    run = await engine.run_control(control_id="...", tenant_id="tenant-123")
    print(run.status)  # "pass" | "fail" | "inconclusive"

TODO P2B.3.2:
  - Wire APScheduler to call run_control() on a cron schedule per tenant.
  - Schedule frequency should be configurable per control (daily / weekly / monthly).
  - Emit compliance.control.failed event on shared Redis bus when status == "fail" (P2B.3.4).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.models.control_run import ControlCheckRun
from compliance_backend.models.framework import Control, FrameworkVersion
from compliance_backend.models.tenant_state import TenantConfig, ConnectorPull
from compliance_backend.services.control_rules import (
    get_rule,
    load_builtin_rules,
)
from compliance_backend.services.control_rules.base import ControlContext
from compliance_backend.services.evidence_service import EvidenceService

logger = logging.getLogger(__name__)

# Load all built-in rules into the registry at module import time.
# This is safe to call multiple times (idempotent).
load_builtin_rules()


class ControlEngine:
    """
    Orchestrates control rule execution and result persistence.

    Args:
        db: Async SQLAlchemy session. Caller owns the transaction.
            ControlEngine.run_control() flushes but does NOT commit.
            Commit after calling run_control() if you want durable writes.

        evidence_service: Optional pre-built EvidenceService.
                          Defaults to EvidenceService(db) using the env-configured storage.
    """

    def __init__(
        self,
        db: AsyncSession,
        evidence_service: Optional[EvidenceService] = None,
    ) -> None:
        self.db = db
        self.evidence_service = evidence_service or EvidenceService(db)

    async def run_control(
        self,
        control_id: str,
        tenant_id: str,
        tenant_config: Optional[dict] = None,
        connector_data: Optional[dict] = None,
        audit_period: Optional[str] = None,
    ) -> ControlCheckRun:
        """
        Execute the rule attached to a control and persist the run result.

        Args:
            control_id:     ID of the Control record to check
            tenant_id:      Tenant being checked
            tenant_config:  OPTIONAL — internal callers (tests, scheduled runs)
                            may pass an explicit dict. The HTTP route MUST NOT
                            (CRIT-006). When None, derived from TenantConfig table.
            connector_data: OPTIONAL — same security note as tenant_config.
                            When None, derived from ConnectorPull rows.
            audit_period:   ISO period string for evidence tagging (default: current year)

        Returns:
            ControlCheckRun ORM object (flushed, not committed)

        Raises:
            ValueError: if control_id does not exist in the database
        """
        # 1. Load the control record
        control = await self._load_control(control_id)
        if control is None:
            raise ValueError(f"Control with id='{control_id}' not found.")

        # 2. Derive framework_id for evidence tagging
        framework_id = await self._get_framework_id(control)

        # CRIT-006 — when caller did not supply explicit overrides, derive
        # rule inputs from server-side state. The HTTP route ALWAYS leaves
        # these as None so user-controlled inputs cannot influence the rule.
        if tenant_config is None:
            tenant_config = await self._load_tenant_config(tenant_id)
        if connector_data is None:
            connector_data = await self._load_connector_data(tenant_id)

        # 3. Look up the rule plugin
        rule_name = control.rule_function
        rule = get_rule(rule_name) if rule_name else None

        # 4. Execute the rule (or produce inconclusive if no rule is wired)
        if rule is None:
            logger.info(
                "ControlEngine: no rule for control=%s (rule_function=%r) — inconclusive",
                control_id, rule_name,
            )
            run_status = "inconclusive"
            failure_reason: Optional[str] = (
                f"No automated rule is registered for rule_function='{rule_name}'. "
                "This control requires manual assessment."
            )
            evidence_specs = []
        else:
            context = ControlContext(
                tenant_config=tenant_config or {},
                connector_data=connector_data or {},
            )
            try:
                result = rule.check(tenant_id=tenant_id, context=context)
                run_status = result.status
                failure_reason = result.failure_reason
                evidence_specs = result.evidence
            except Exception as exc:
                logger.exception(
                    "ControlEngine: rule %s raised exception for tenant %s: %s",
                    rule_name, tenant_id, exc,
                )
                run_status = "inconclusive"
                failure_reason = f"Rule execution error: {exc}"
                evidence_specs = []

        # 5. Auto-capture evidence (bridge P2B.3 → P2B.4)
        evidence_ids = []
        for spec in evidence_specs:
            try:
                ev = await self.evidence_service.capture_evidence(
                    control_id=control_id,
                    tenant_id=tenant_id,
                    evidence_type=spec.type,
                    content=spec.content,
                    metadata=spec.metadata,
                    framework_id=framework_id,
                    audit_period=audit_period,
                )
                evidence_ids.append(ev.id)
            except Exception as exc:
                logger.warning(
                    "ControlEngine: failed to capture evidence spec for control=%s: %s",
                    control_id, exc,
                )

        # 6. Create run record
        # NEW-2 — naive UTC datetime (matches DB column convention).
        run = ControlCheckRun(
            control_id=control_id,
            tenant_id=tenant_id,
            run_at=datetime.now(timezone.utc).replace(tzinfo=None),
            status=run_status,
            evidence_ids=evidence_ids,
            failure_reason=failure_reason,
        )
        self.db.add(run)
        await self.db.flush()

        logger.info(
            "ControlEngine.run_control: id=%s control=%s tenant=%s status=%s",
            run.id, control_id, tenant_id, run_status,
        )

        # 7. Cross-service event emission — compliance.control.failed
        # Published only on `fail` results.  Best-effort: if the shared bus is
        # unavailable (e.g. in a compliance-only deployment) we log and move on.
        if run_status == "fail":
            try:
                from shared.events import TOPIC_CONTROL_FAILED, get_event_bus
                from shared.events.topics import ControlFailedPayload

                payload = ControlFailedPayload(
                    control_id=str(control_id),
                    tenant_id=str(tenant_id),
                    control_name=str(control.description or rule_name or "control"),
                    framework=str(framework_id or ""),
                    failed_at=datetime.now(timezone.utc).isoformat(),
                    details=failure_reason,
                ).model_dump()
                bus = get_event_bus()
                # Don't await — keep run_control synchronous w.r.t the request.
                # The bus publish itself is async; schedule it as a task.
                import asyncio
                asyncio.create_task(bus.publish(TOPIC_CONTROL_FAILED, payload))
            except Exception as exc:  # pragma: no cover — defensive
                logger.warning(
                    "control.failed publish skipped (bus unavailable): %s", exc
                )
        return run

    # ------------------------------------------------------------------ #
    #  Private helpers
    # ------------------------------------------------------------------ #

    async def _load_control(self, control_id: str) -> Optional[Control]:
        result = await self.db.execute(
            select(Control).where(Control.id == control_id)
        )
        return result.scalars().first()

    async def _get_framework_id(self, control: Control) -> Optional[str]:
        """Traverse control → framework_version → framework to get framework_id."""
        result = await self.db.execute(
            select(FrameworkVersion).where(
                FrameworkVersion.id == control.framework_version_id
            )
        )
        version = result.scalars().first()
        if version is None:
            return None
        return version.framework_id

    async def _load_tenant_config(self, tenant_id: str) -> dict:
        """CRIT-006: load server-side tenant settings; never trust the caller."""
        row = (await self.db.execute(
            select(TenantConfig).where(TenantConfig.tenant_id == tenant_id)
        )).scalars().first()
        if row is None or not row.settings:
            return {}
        # Defensive copy so a rule cannot mutate the persisted row
        return dict(row.settings)

    async def _load_connector_data(self, tenant_id: str) -> dict:
        """CRIT-006: assemble latest connector pulls for this tenant — server-side only."""
        rows = (await self.db.execute(
            select(ConnectorPull).where(ConnectorPull.tenant_id == tenant_id)
        )).scalars().all()
        return {row.connector_kind: dict(row.payload or {}) for row in rows}

"""
CSPM Check Engine.

Orchestrates CIS control evaluation for cloud providers.
Usage:
    engine = CspmEngine(db)
    results = await engine.run_cspm_checks(tenant_id, "aws", connector_data={...})
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.cspm import CspmCheckResult, CspmControl, CspmFramework, CspmScoreSnapshot
from backend.services.cspm_rules import CspmRuleResult, get_cspm_rule

logger = logging.getLogger(__name__)


class CspmEngine:
    """Runs CSPM checks and persists results + score snapshots."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def run_cspm_checks(
        self,
        tenant_id: str,
        cloud_provider: str,
        connector_data: Optional[dict] = None,
    ) -> list[CspmCheckResult]:
        """
        Evaluate all CIS controls for a cloud provider against connector_data.

        Args:
            tenant_id: UUID string of the tenant.
            cloud_provider: 'aws', 'azure', or 'gcp'.
            connector_data: Optional dict of pre-fetched cloud resources.

        Returns:
            List of persisted CspmCheckResult rows.
        """
        connector_data = connector_data or {}

        # 1. Load framework
        framework = await self._load_framework(cloud_provider)
        if framework is None:
            logger.warning("No CSPM framework found for provider=%s", cloud_provider)
            return []

        # 2. Load controls
        controls = await self._load_controls(framework.id)

        results: list[CspmCheckResult] = []
        pass_count = 0
        fail_count = 0
        inconclusive_count = 0

        now = datetime.now(timezone.utc)

        for control in controls:
            rule_name = control.rule_function
            if not rule_name:
                result = CspmCheckResult(
                    id=uuid.uuid4(),
                    tenant_id=uuid.UUID(tenant_id),
                    control_id=control.id,
                    cloud_account_id=None,
                    status="inconclusive",
                    evidence_json={"reason": "no rule function mapped"},
                    run_at=now,
                    failing_resource_ids=None,
                )
                self.db.add(result)
                results.append(result)
                inconclusive_count += 1
                continue

            rule = get_cspm_rule(rule_name)
            if rule is None:
                logger.debug("No rule registered for %s", rule_name)
                result = CspmCheckResult(
                    id=uuid.uuid4(),
                    tenant_id=uuid.UUID(tenant_id),
                    control_id=control.id,
                    cloud_account_id=None,
                    status="inconclusive",
                    evidence_json={"reason": f"rule {rule_name} not registered"},
                    run_at=now,
                    failing_resource_ids=None,
                )
                self.db.add(result)
                results.append(result)
                inconclusive_count += 1
                continue

            try:
                rule_result = rule(connector_data)
            except Exception as exc:
                logger.exception("Rule %s raised for tenant %s", rule_name, tenant_id)
                rule_result = CspmRuleResult(
                    status="inconclusive",
                    evidence={"error": str(exc)},
                )

            result = CspmCheckResult(
                id=uuid.uuid4(),
                tenant_id=uuid.UUID(tenant_id),
                control_id=control.id,
                cloud_account_id=None,
                status=rule_result.status,
                evidence_json=rule_result.evidence,
                run_at=now,
                failing_resource_ids=rule_result.failing_resource_ids,
            )
            self.db.add(result)
            results.append(result)

            if rule_result.status == "pass":
                pass_count += 1
            elif rule_result.status == "fail":
                fail_count += 1
            else:
                inconclusive_count += 1

        # 3. Compute score
        total = pass_count + fail_count + inconclusive_count
        score = 0.0
        if total > 0:
            score = round((pass_count / total) * 100, 2)

        snapshot = CspmScoreSnapshot(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(tenant_id),
            cloud_provider=cloud_provider,
            snapshot_at=now,
            score=score,
            pass_count=pass_count,
            fail_count=fail_count,
            inconclusive_count=inconclusive_count,
        )
        self.db.add(snapshot)
        await self.db.flush()

        logger.info(
            "CspmEngine: tenant=%s provider=%s controls=%d pass=%d fail=%d inconclusive=%d score=%.1f",
            tenant_id, cloud_provider, total, pass_count, fail_count, inconclusive_count, score,
        )
        return results

    async def _load_framework(self, cloud_provider: str) -> Optional[CspmFramework]:
        result = await self.db.execute(
            select(CspmFramework).where(
                CspmFramework.cloud_provider == cloud_provider
            )
        )
        return result.scalars().first()

    async def _load_controls(self, framework_id: uuid.UUID) -> list[CspmControl]:
        result = await self.db.execute(
            select(CspmControl).where(CspmControl.framework_id == framework_id)
        )
        return list(result.scalars().all())

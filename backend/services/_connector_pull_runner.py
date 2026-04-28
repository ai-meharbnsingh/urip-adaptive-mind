"""
backend/services/_connector_pull_runner.py — Service-layer ingest runner
shared by the FastAPI /api/connectors/{name}/run endpoint and the Celery
``connector_pull_task`` worker.

Why this module exists
----------------------
Before this file landed, the only place that authenticated a connector,
fetched findings, normalized them, and persisted via the Universal
Intelligence Engine pipeline was inside ``backend/routers/connectors.py``.
That worked for the API path but tied the ingest contract to the FastAPI
request/response cycle — the Celery worker would have had to fake an
``AsyncSession`` and a ``TenantContext`` to reuse the router code.

Pulling the orchestration into a service-layer function lets us:

  * Run the same code path from a beat-scheduled Celery task and from a
    user-triggered API call ("Run Now" button).
  * Unit-test the logic without spinning up FastAPI.
  * Keep the router thin (it just wraps this function and returns HTTP
    status codes).

The function is intentionally small — most of the heavy lifting is still
done by ``connector_runner.preprocess_connector_record`` (de-dup +
enrichment) and the connector class itself.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from backend.database import async_session
from backend.models.risk import Risk
from backend.models.tenant_connector_credential import TenantConnectorCredential
from backend.services.connector_runner import preprocess_connector_record
from backend.services.crypto_service import decrypt_credentials
from connectors.base.connector import BaseConnector
from connectors.base.registry import _global_registry


logger = logging.getLogger(__name__)


def _instantiate(name: str) -> BaseConnector:
    """Instantiate a registered connector by name."""
    factory = _global_registry.get(name)
    return factory()


def _next_risk_id(prefix: str = "RISK") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


async def run_connector_pull(tenant_id: str, connector_name: str) -> dict[str, Any]:
    """
    Authenticate the connector for ``tenant_id``, pull the last 15 minutes of
    findings, normalize them, and persist new ones via the Intelligence
    Engine pipeline. Existing risks (de-dup hit) are merged in place.

    Returns ``{"tenant_id", "connector", "ingested", "skipped", "errors"}``.
    """
    if connector_name not in _global_registry:
        return {
            "tenant_id": tenant_id,
            "connector": connector_name,
            "ingested": 0,
            "skipped": 0,
            "errors": 1,
            "error": f"connector '{connector_name}' is not registered",
        }

    try:
        tenant_uuid = uuid.UUID(str(tenant_id))
    except (ValueError, TypeError):
        return {
            "tenant_id": tenant_id,
            "connector": connector_name,
            "ingested": 0,
            "skipped": 0,
            "errors": 1,
            "error": f"invalid tenant_id: {tenant_id!r}",
        }

    instance = _instantiate(connector_name)
    ingested = 0
    skipped = 0
    errors = 0

    async with async_session() as db:
        cred_row = (
            await db.execute(
                select(TenantConnectorCredential).where(
                    TenantConnectorCredential.tenant_id == tenant_uuid,
                    TenantConnectorCredential.connector_name == connector_name,
                )
            )
        ).scalar_one_or_none()
        if cred_row is None:
            return {
                "tenant_id": tenant_id,
                "connector": connector_name,
                "ingested": 0,
                "skipped": 0,
                "errors": 1,
                "error": "no credentials configured",
            }

        creds = decrypt_credentials(cred_row.encrypted_blob)

        try:
            instance.authenticate(creds)
        except Exception:
            logger.exception(
                "connector_pull authenticate() failed (tenant=%s, connector=%s)",
                tenant_id, connector_name,
            )
            return {
                "tenant_id": tenant_id,
                "connector": connector_name,
                "ingested": 0,
                "skipped": 0,
                "errors": 1,
                "error": "authentication failed",
            }

        since = datetime.now(timezone.utc) - timedelta(minutes=15)
        try:
            try:
                raw_findings = instance.fetch_findings(since, tenant_id=str(tenant_uuid))
            except TypeError:
                raw_findings = instance.fetch_findings(since)
        except Exception:
            logger.exception(
                "connector_pull fetch_findings() failed (tenant=%s, connector=%s)",
                tenant_id, connector_name,
            )
            return {
                "tenant_id": tenant_id,
                "connector": connector_name,
                "ingested": 0,
                "skipped": 0,
                "errors": 1,
                "error": "fetch failed",
            }

        for raw in raw_findings:
            try:
                record = instance.normalize(raw)
            except (KeyError, ValueError, TypeError, AttributeError):
                errors += 1
                continue

            try:
                existing, enriched = await preprocess_connector_record(
                    db,
                    tenant_id=tenant_uuid,
                    raw=raw,
                    record=record,
                )
            except Exception:
                logger.exception(
                    "connector_pull preprocess failed (tenant=%s, connector=%s)",
                    tenant_id, connector_name,
                )
                errors += 1
                continue

            if existing is not None:
                skipped += 1
                continue

            sla_days = {"critical": 3, "high": 7, "medium": 30, "low": 90}.get(
                (record.severity or "low").lower(), 30,
            )
            risk = Risk(
                id=uuid.uuid4(),
                risk_id=_next_risk_id(),
                finding=record.finding,
                description=record.description,
                source=record.source,
                domain=record.domain,
                cvss_score=float(enriched["cvss_score"]),
                severity=record.severity,
                asset=record.asset,
                owner_team=record.owner_team,
                status="open",
                sla_deadline=datetime.now(timezone.utc) + timedelta(days=sla_days),
                cve_id=record.cve_id,
                composite_score=enriched.get("composite_score"),
                tenant_id=tenant_uuid,
                fingerprint_key=enriched.get("fingerprint_key"),
                sources_attributed=[record.source],
            )
            db.add(risk)
            ingested += 1

        await db.commit()

    return {
        "tenant_id": tenant_id,
        "connector": connector_name,
        "ingested": ingested,
        "skipped": skipped,
        "errors": errors,
    }


async def list_configured_pairs() -> list[tuple[str, str]]:
    """
    Return every (tenant_id, connector_name) pair that has stored
    credentials. The Beat scheduler uses this to fan out one
    ``connector_pull_task`` per pair every 15 minutes.
    """
    async with async_session() as db:
        rows = (
            await db.execute(
                select(
                    TenantConnectorCredential.tenant_id,
                    TenantConnectorCredential.connector_name,
                )
            )
        ).all()
    return [(str(t), str(n)) for (t, n) in rows]


__all__ = ["run_connector_pull", "list_configured_pairs"]

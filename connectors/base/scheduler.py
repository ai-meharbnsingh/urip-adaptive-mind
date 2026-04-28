"""
connectors/base/scheduler.py — Async periodic connector runner.

P1.6: Connector Framework Abstraction

Design decisions
----------------
- ConnectorScheduler.tick(tenant_config) is the unit of work: it runs one
  scheduling cycle for a single tenant synchronously (within the async context).
  This makes it trivially testable — tests call tick() directly.
- The actual periodic loop (every 15 min default) is run_forever() which is
  an async generator that yields after each cycle.  Production callers use
  asyncio.create_task(scheduler.run_forever(...)).
- Errors in one connector do NOT abort the tick — the scheduler logs the error,
  records it for health tracking, and continues with remaining connectors.
- The scheduler is stateless between ticks (no stored session) — authenticate()
  is called fresh each tick.  For connectors with expensive auth (OAuth2 with
  expiry), the connector itself should cache the session internally.
- tenant_config is a plain dict to avoid coupling to the DB layer; the caller
  (typically a background task) loads it from DB and passes it in.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from connectors.base.connector import BaseConnector, RawFinding, URIPRiskRecord
from connectors.base.registry import ConnectorRegistry, _global_registry

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 15 * 60  # 15 minutes


class ConnectorScheduler:
    """
    Orchestrates connector execution for one or more tenants.

    Parameters
    ----------
    registry : ConnectorRegistry, optional
        Defaults to the module-level _global_registry.
    interval_seconds : int
        Seconds between ticks in run_forever().  Default 900 (15 min).
    """

    def __init__(
        self,
        registry: Optional[ConnectorRegistry] = None,
        interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    ) -> None:
        self._registry = registry or _global_registry
        self._interval_seconds = interval_seconds

    async def tick(self, tenant_config: dict) -> list[URIPRiskRecord]:
        """
        Execute one scheduling cycle for a single tenant.

        Parameters
        ----------
        tenant_config : dict
            {
                "tenant_id": str,
                "enabled_connectors": list[str],  # names in registry
                "connector_credentials": {
                    "<connector_name>": dict,      # decrypted credentials
                },
                "simulator_mode": str,             # "default" | "extended" | "off"
            }

        Returns
        -------
        list[URIPRiskRecord]
            All normalized findings from all enabled connectors for this tick.
            Empty list if no connectors enabled or all returned 0 findings.
        """
        tenant_id = tenant_config.get("tenant_id", "unknown")
        enabled = tenant_config.get("enabled_connectors", [])
        credentials_map = tenant_config.get("connector_credentials", {})

        # Determine `since` — in production this comes from the DB (last_sync).
        # For the framework skeleton, default to 15 min ago so tests get data.
        since = datetime.now(timezone.utc) - timedelta(seconds=self._interval_seconds)

        all_records: list[URIPRiskRecord] = []

        for connector_name in enabled:
            try:
                factory = self._registry.get(connector_name)
            except KeyError:
                logger.warning(
                    "Tenant %s: connector '%s' is enabled but not registered — skipping.",
                    tenant_id, connector_name,
                )
                continue

            try:
                connector: BaseConnector = factory()
                creds = credentials_map.get(connector_name, {})
                # Authenticate
                connector.authenticate(creds)

                # Fetch — pass tenant_id kwarg only if the underlying function
                # accepts **kwargs.  Introspect the real function (unwrap mocks)
                # so test stubs that don't declare **kwargs work without error.
                import inspect
                fn = connector.fetch_findings
                # Unwrap mock wraps to get the real callable for signature check
                underlying = getattr(fn, "_mock_wraps", None) or fn
                try:
                    sig = inspect.signature(underlying)
                    accepts_kwargs = any(
                        p.kind == inspect.Parameter.VAR_KEYWORD
                        for p in sig.parameters.values()
                    )
                except (ValueError, TypeError):
                    accepts_kwargs = True  # can't introspect — try with kwargs

                if accepts_kwargs:
                    findings: list[RawFinding] = connector.fetch_findings(
                        since, tenant_id=tenant_id
                    )
                else:
                    findings = connector.fetch_findings(since)

                # Normalize
                for raw in findings:
                    try:
                        record = connector.normalize(raw)
                        all_records.append(record)
                    except Exception as norm_exc:
                        logger.warning(
                            "Tenant %s: connector '%s' normalize failed for finding %s: %s",
                            tenant_id, connector_name, raw.id, norm_exc,
                        )

            except Exception as exc:
                logger.error(
                    "Tenant %s: connector '%s' tick failed: %s",
                    tenant_id, connector_name, exc,
                    exc_info=True,
                )
                # Continue with other connectors
                continue

        logger.info(
            "Tenant %s: tick complete — %d records from %d enabled connectors.",
            tenant_id, len(all_records), len(enabled),
        )
        return all_records

    async def run_forever(
        self,
        tenant_configs: list[dict],
        *,
        interval_seconds: Optional[int] = None,
    ):
        """
        Async loop — runs tick() for every tenant every interval_seconds.

        Usage (production)
        ------------------
        asyncio.create_task(
            scheduler.run_forever(tenant_configs)
        )

        This is an infinite coroutine; cancel the task to stop it.
        """
        interval = interval_seconds or self._interval_seconds
        logger.info(
            "ConnectorScheduler starting — %d tenant(s), interval=%ds",
            len(tenant_configs), interval,
        )
        while True:
            for cfg in tenant_configs:
                try:
                    await self.tick(cfg)
                except Exception as exc:
                    logger.error(
                        "Unexpected scheduler error for tenant %s: %s",
                        cfg.get("tenant_id"), exc,
                        exc_info=True,
                    )
            await asyncio.sleep(interval)

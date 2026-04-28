"""
agent/heartbeat.py — periodic agent → cloud heartbeat.

Runs every 5 minutes (configurable).  Snapshots per-connector health from the
in-memory ConnectorHealth cache and posts via the encrypted reporter.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from agent.reporter import EncryptedReporter

logger = logging.getLogger(__name__)

DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 5 * 60


class HeartbeatLoop:
    """Background heartbeat that runs forever until cancelled."""

    def __init__(
        self,
        reporter: EncryptedReporter,
        connector_health_provider,  # callable() → dict
        *,
        interval_seconds: int = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    ) -> None:
        self._reporter = reporter
        self._provider = connector_health_provider
        self._interval = interval_seconds

    async def run_once(self) -> dict[str, Any]:
        """Send one heartbeat and return the dict that was sent."""
        connector_health = self._provider() or {}
        connector_health.setdefault(
            "_meta",
            {
                "agent_version": self._reporter.agent_version,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        try:
            self._reporter.send_heartbeat(connector_health)
        except Exception as exc:
            # Don't kill the loop on a single failure; reporter already retried.
            logger.warning("Heartbeat send failed (non-fatal): %s", exc)
        return connector_health

    async def run_forever(self) -> None:
        logger.info("HeartbeatLoop starting (interval=%ds)", self._interval)
        while True:
            await self.run_once()
            await asyncio.sleep(self._interval)

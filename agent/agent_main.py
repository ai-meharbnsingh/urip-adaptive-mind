"""
agent/agent_main.py — entrypoint for the on-prem URIP Docker agent.

Boot sequence
-------------
1. Read env vars (AGENT_TENANT_SLUG, AGENT_LICENSE_KEY, CLOUD_PORTAL_URL,
   LOCAL_DB_URL, FERNET_KEY).
2. Initialise the local DB (creates raw-finding tables on first boot).
3. Register with the cloud (POST /agent-ingest/register).  Persist the
   one-time shared_secret to disk (chmod 600) so subsequent boots reuse it.
4. Start the connector scheduler (every 15 min) — runs each enabled connector,
   normalises findings, writes to local DB.
5. Start the periodic metadata pusher (every 15 min after a successful tick).
6. Start the heartbeat loop (every 5 min).
7. Start the drilldown responder loop (polls cloud every 2 s).

Async runtime: a single asyncio.gather of these long-running coroutines.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# Connectors come from the existing package
import connectors.tenable.connector  # noqa: F401  — registers connector
import connectors.sentinelone.connector  # noqa: F401  — registers connector
import connectors.simulator_connector  # noqa: F401  — registers simulator
from agent import AGENT_VERSION
from agent.drilldown_responder import DrilldownResponder
from agent.heartbeat import HeartbeatLoop
from agent.local_db import get_local_db_url, init_db, make_engine, make_session_factory
from agent.reporter import EncryptedReporter
from connectors.base.credentials_vault import CredentialsVault
from connectors.base.scheduler import ConnectorScheduler

logging.basicConfig(
    level=os.getenv("AGENT_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("agent.main")


SHARED_SECRET_FILE_DEFAULT = "/var/lib/urip-agent/shared_secret.json"


# ─────────────────────────────────────────────────────────────────────────────
# Env / config
# ─────────────────────────────────────────────────────────────────────────────


class AgentConfig:
    def __init__(self) -> None:
        self.tenant_slug = self._require("AGENT_TENANT_SLUG")
        self.license_key = self._require("AGENT_LICENSE_KEY")
        self.cloud_portal_url = self._require("CLOUD_PORTAL_URL")
        self.local_db_url = os.getenv("LOCAL_DB_URL", get_local_db_url())
        self.fernet_key = os.getenv("FERNET_KEY", "")
        self.shared_secret_file = os.getenv(
            "AGENT_SHARED_SECRET_FILE", SHARED_SECRET_FILE_DEFAULT
        )
        self.scheduler_interval_seconds = int(
            os.getenv("AGENT_SCHEDULER_INTERVAL_SECONDS", "900")
        )
        self.heartbeat_interval_seconds = int(
            os.getenv("AGENT_HEARTBEAT_INTERVAL_SECONDS", "300")
        )
        self.metadata_push_interval_seconds = int(
            os.getenv("AGENT_METADATA_INTERVAL_SECONDS", "900")
        )
        self.drilldown_poll_seconds = float(
            os.getenv("AGENT_DRILLDOWN_POLL_SECONDS", "2.0")
        )

    @staticmethod
    def _require(name: str) -> str:
        v = os.getenv(name)
        if not v:
            raise RuntimeError(f"Required env var {name} is not set")
        return v


# ─────────────────────────────────────────────────────────────────────────────
# Registration + secret persistence
# ─────────────────────────────────────────────────────────────────────────────


def _load_secret_from_disk(path: str) -> str | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text()).get("shared_secret")
    except Exception as exc:
        logger.warning("Could not read shared_secret from %s: %s", path, exc)
        return None


def _persist_secret_to_disk(path: str, secret: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"shared_secret": secret}))
    try:
        os.chmod(p, 0o600)
    except OSError:
        # Windows / non-POSIX volumes — best effort
        pass


def register_with_cloud(cfg: AgentConfig) -> str:
    """Hit /api/agent-ingest/register and return the shared_secret."""
    cached = _load_secret_from_disk(cfg.shared_secret_file)
    if cached:
        logger.info("Using cached shared_secret from %s", cfg.shared_secret_file)
        return cached

    url = f"{cfg.cloud_portal_url.rstrip('/')}/api/agent-ingest/register"
    payload = {
        "tenant_slug": cfg.tenant_slug,
        "license_key": cfg.license_key,
        "agent_version": AGENT_VERSION,
        "capabilities": {
            "connectors": ["tenable", "sentinelone", "simulator"],
            "drilldown": True,
            "heartbeat": True,
        },
    }
    logger.info("Registering with cloud at %s", url)
    response = httpx.post(url, json=payload, timeout=15.0)
    if response.status_code != 200:
        raise RuntimeError(
            f"Registration failed: HTTP {response.status_code} — {response.text}"
        )
    body = response.json()
    secret = body["shared_secret"]
    _persist_secret_to_disk(cfg.shared_secret_file, secret)
    logger.info(
        "Registered as tenant_id=%s; shared_secret persisted to %s",
        body["tenant_id"],
        cfg.shared_secret_file,
    )
    return secret


# ─────────────────────────────────────────────────────────────────────────────
# Scheduler + metadata loop
# ─────────────────────────────────────────────────────────────────────────────


class AgentRuntime:
    """Holds long-lived state shared across the loops."""

    def __init__(self, cfg: AgentConfig, reporter: EncryptedReporter) -> None:
        self.cfg = cfg
        self.reporter = reporter
        self.engine = make_engine(cfg.local_db_url)
        self.session_factory = make_session_factory(self.engine)
        self.scheduler = ConnectorScheduler(interval_seconds=cfg.scheduler_interval_seconds)
        # Connector health is updated by the scheduler tick wrapper below.
        self.connector_health: dict[str, dict[str, Any]] = {}
        # Latest metadata snapshot — pushed periodically by the metadata loop.
        self.latest_summary: dict[str, Any] = self._empty_summary()

    @staticmethod
    def _empty_summary() -> dict[str, Any]:
        return {
            "total_risks": 0,
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "exploit_active_count": 0,
            "kev_active_count": 0,
        }

    async def init(self) -> None:
        await init_db(self.engine)
        logger.info("Local DB ready at %s", self.cfg.local_db_url)

    async def load_tenant_configs(self) -> list[dict]:
        """Load enabled connectors from the local DB."""
        from sqlalchemy import select
        from backend.models.connector import ConnectorConfig
        from backend.models.tenant_connector_credential import (
            TenantConnectorCredential,
        )

        async with self.session_factory() as session:
            cfgs = (
                await session.execute(
                    select(ConnectorConfig).where(ConnectorConfig.is_active == True)  # noqa: E712
                )
            ).scalars().all()

            if not cfgs:
                # First-boot fallback — run only the simulator so we can prove end-to-end
                logger.warning(
                    "No connector_configs in local DB — running simulator-only mode."
                )
                return [
                    {
                        "tenant_id": self.cfg.tenant_slug,
                        "enabled_connectors": ["simulator"],
                        "connector_credentials": {"simulator": {}},
                        "simulator_mode": "default",
                    }
                ]

            # Resolve credentials per (tenant, connector)
            vault = (
                CredentialsVault(self.cfg.fernet_key) if self.cfg.fernet_key else None
            )
            tenant_buckets: dict[str, dict[str, Any]] = {}
            for c in cfgs:
                t_id = str(c.tenant_id) if c.tenant_id else self.cfg.tenant_slug
                bucket = tenant_buckets.setdefault(
                    t_id,
                    {
                        "tenant_id": t_id,
                        "enabled_connectors": [],
                        "connector_credentials": {},
                        "simulator_mode": "off",
                    },
                )
                bucket["enabled_connectors"].append(c.source_type)

                # Decrypt creds if available
                creds = {}
                if vault is not None:
                    cred_row = (
                        await session.execute(
                            select(TenantConnectorCredential).where(
                                TenantConnectorCredential.tenant_id == c.tenant_id,
                                TenantConnectorCredential.connector_name
                                == c.source_type,
                            )
                        )
                    ).scalar_one_or_none()
                    if cred_row and cred_row.encrypted_blob:
                        try:
                            creds = vault.decrypt(cred_row.encrypted_blob)
                        except Exception as exc:
                            logger.warning(
                                "Could not decrypt creds for %s/%s: %s",
                                t_id,
                                c.source_type,
                                exc,
                            )
                bucket["connector_credentials"][c.source_type] = creds
            return list(tenant_buckets.values())

    async def scheduler_loop(self) -> None:
        """Run the connector scheduler tick every interval, write findings to local DB."""
        from backend.models.risk import Risk
        import uuid as _uuid
        from datetime import timedelta

        while True:
            tenant_configs = await self.load_tenant_configs()
            for tcfg in tenant_configs:
                try:
                    records = await self.scheduler.tick(tcfg)
                    await self._persist_records(tcfg["tenant_id"], records)
                    # Update health
                    for cname in tcfg["enabled_connectors"]:
                        self.connector_health[cname] = {
                            "name": cname,
                            "status": "ok",
                            "last_poll_at": datetime.now(timezone.utc).isoformat(),
                            "error_count_24h": 0,
                        }
                    # Recompute summary so the metadata loop has current data
                    self.latest_summary = await self._compute_summary(
                        tcfg["tenant_id"]
                    )
                except Exception as exc:
                    logger.exception(
                        "scheduler_loop tick failed for %s: %s", tcfg["tenant_id"], exc
                    )
                    for cname in tcfg["enabled_connectors"]:
                        self.connector_health[cname] = {
                            "name": cname,
                            "status": "error",
                            "last_poll_at": datetime.now(timezone.utc).isoformat(),
                            "error_count_24h": (
                                self.connector_health.get(cname, {}).get(
                                    "error_count_24h", 0
                                )
                                + 1
                            ),
                            "last_error": str(exc),
                        }
            await asyncio.sleep(self.cfg.scheduler_interval_seconds)

    async def _persist_records(self, tenant_id: str, records: list) -> int:
        """Persist normalized URIPRiskRecord list to the LOCAL Risk table."""
        if not records:
            return 0
        from backend.models.risk import Risk
        import uuid as _uuid
        from datetime import timedelta

        async with self.session_factory() as session:
            n = 0
            now = datetime.now(timezone.utc)
            for rec in records:
                try:
                    risk = Risk(
                        id=_uuid.uuid4(),
                        risk_id=f"AG-{int(now.timestamp())}-{n:04d}",
                        finding=rec.finding,
                        description=rec.description,
                        source=rec.source,
                        domain=rec.domain,
                        cvss_score=rec.cvss_score,
                        severity=rec.severity,
                        asset=rec.asset,
                        owner_team=rec.owner_team,
                        cve_id=rec.cve_id,
                        epss_score=rec.epss_score,
                        in_kev_catalog=rec.in_kev_catalog,
                        exploit_status=rec.exploit_status,
                        asset_tier=rec.asset_tier,
                        composite_score=rec.composite_score,
                        sla_deadline=now + timedelta(days=7),
                    )
                    session.add(risk)
                    n += 1
                except Exception as exc:
                    logger.warning("Persist risk failed: %s", exc)
            await session.commit()
            logger.info("Persisted %d risks to local DB", n)
            return n

    async def _compute_summary(self, tenant_id: str) -> dict[str, Any]:
        """Compute aggregate metadata from the local Risk table — no raw fields."""
        from sqlalchemy import select, func
        from backend.models.risk import Risk

        async with self.session_factory() as session:
            total = (
                await session.execute(select(func.count()).select_from(Risk))
            ).scalar_one()
            crit = (
                await session.execute(
                    select(func.count())
                    .select_from(Risk)
                    .where(Risk.severity == "critical")
                )
            ).scalar_one()
            high = (
                await session.execute(
                    select(func.count())
                    .select_from(Risk)
                    .where(Risk.severity == "high")
                )
            ).scalar_one()
            med = (
                await session.execute(
                    select(func.count())
                    .select_from(Risk)
                    .where(Risk.severity == "medium")
                )
            ).scalar_one()
            low = (
                await session.execute(
                    select(func.count())
                    .select_from(Risk)
                    .where(Risk.severity == "low")
                )
            ).scalar_one()
            kev = (
                await session.execute(
                    select(func.count())
                    .select_from(Risk)
                    .where(Risk.in_kev_catalog == True)  # noqa: E712
                )
            ).scalar_one()
        return {
            "total_risks": int(total or 0),
            "critical_count": int(crit or 0),
            "high_count": int(high or 0),
            "medium_count": int(med or 0),
            "low_count": int(low or 0),
            "kev_active_count": int(kev or 0),
            "exploit_active_count": int(kev or 0),
        }

    async def metadata_loop(self) -> None:
        """Periodically push the latest summary to the cloud."""
        while True:
            try:
                payload = {
                    "risk_summary": dict(self.latest_summary),
                    "control_summary": {
                        "connectors": list(self.connector_health.values())
                    },
                    "score_history_delta": {},
                }
                self.reporter.send_metadata(payload)
                logger.info("Pushed metadata: %s", payload["risk_summary"])
            except Exception as exc:
                logger.warning("metadata push failed: %s", exc)
            await asyncio.sleep(self.cfg.metadata_push_interval_seconds)


# ─────────────────────────────────────────────────────────────────────────────
# Drilldown handlers — sample implementations
# ─────────────────────────────────────────────────────────────────────────────


def _make_drilldown_handlers(runtime: AgentRuntime):
    """Return a dict of request_type → async handler for drill-down requests."""

    async def fetch_risk_by_id(request_type: str, payload: dict) -> dict:
        from sqlalchemy import select
        from backend.models.risk import Risk

        risk_id = payload.get("risk_id") or payload.get("id")
        if not risk_id:
            return {"error": "missing risk_id in request_payload"}
        async with runtime.session_factory() as session:
            row = (
                await session.execute(select(Risk).where(Risk.risk_id == risk_id))
            ).scalar_one_or_none()
            if row is None:
                return {"error": f"risk_id {risk_id} not found"}
            return {
                "risk_id": row.risk_id,
                "finding": row.finding,
                "description": row.description,
                "asset": row.asset,
                "owner_team": row.owner_team,
                "cvss_score": float(row.cvss_score) if row.cvss_score is not None else None,
                "severity": row.severity,
                "cve_id": row.cve_id,
                "source": row.source,
            }

    return {"fetch_risk_by_id": fetch_risk_by_id}


# ─────────────────────────────────────────────────────────────────────────────
# Main async entry
# ─────────────────────────────────────────────────────────────────────────────


async def amain() -> int:
    cfg = AgentConfig()
    secret = register_with_cloud(cfg)
    reporter = EncryptedReporter(
        cloud_portal_url=cfg.cloud_portal_url,
        tenant_slug=cfg.tenant_slug,
        shared_secret=secret,
        agent_version=AGENT_VERSION,
    )

    runtime = AgentRuntime(cfg, reporter)
    await runtime.init()

    heartbeat = HeartbeatLoop(
        reporter,
        connector_health_provider=lambda: dict(runtime.connector_health),
        interval_seconds=cfg.heartbeat_interval_seconds,
    )

    drilldown = DrilldownResponder(
        reporter,
        handlers=_make_drilldown_handlers(runtime),
        poll_interval_seconds=cfg.drilldown_poll_seconds,
    )

    logger.info("URIP Agent %s starting all loops…", AGENT_VERSION)
    await asyncio.gather(
        runtime.scheduler_loop(),
        runtime.metadata_loop(),
        heartbeat.run_forever(),
        drilldown.run_forever(),
    )
    return 0


def main() -> None:
    try:
        rc = asyncio.run(amain())
    except KeyboardInterrupt:
        logger.info("Shutdown requested.")
        rc = 0
    except Exception as exc:
        logger.exception("Fatal: %s", exc)
        rc = 1
    sys.exit(rc)


if __name__ == "__main__":
    main()

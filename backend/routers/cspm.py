"""
backend/routers/cspm.py — CSPM REST API.

Endpoints
---------
GET    /api/cspm/clouds
POST   /api/cspm/clouds
GET    /api/cspm/score
GET    /api/cspm/score/{cloud_provider}
GET    /api/cspm/findings
GET    /api/cspm/findings/{id}
POST   /api/cspm/scan-now
GET    /api/cspm/trend
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.module_gate import require_module
from backend.middleware.rbac import role_required
from backend.middleware.tenant import TenantContext
from backend.models.cspm import CspmCheckResult, CspmControl, CspmFramework, CspmScoreSnapshot
from backend.models.tenant_connector_credential import TenantConnectorCredential
from backend.services.cspm_engine import CspmEngine
from backend.services.crypto_service import decrypt_credentials
from connectors.base.registry import _global_registry

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_module("CSPM"))])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CloudAccountItem(BaseModel):
    connector: str
    configured: bool
    last_scan: datetime | None = None


class CloudAccountListResponse(BaseModel):
    items: list[CloudAccountItem]


class ConnectCloudRequest(BaseModel):
    credentials: dict = Field(..., description="Connector-specific credentials dict")


class ConnectCloudResponse(BaseModel):
    status: str
    connector: str


class ScoreItem(BaseModel):
    cloud_provider: str
    score: float
    pass_count: int
    fail_count: int
    inconclusive_count: int
    snapshot_at: datetime


class ScoreResponse(BaseModel):
    items: list[ScoreItem]


class ControlBreakdownItem(BaseModel):
    control_code: str
    title: str
    severity: str
    status: str
    run_at: datetime


class ProviderScoreResponse(BaseModel):
    cloud_provider: str
    score: float
    controls: list[ControlBreakdownItem]


class FindingItem(BaseModel):
    id: str
    control_code: str
    title: str
    status: str
    severity: str
    cloud_account_id: str | None
    run_at: datetime


class FindingsResponse(BaseModel):
    items: list[FindingItem]
    total: int
    limit: int
    offset: int


class FindingDetailResponse(BaseModel):
    id: str
    control_code: str
    title: str
    description: str
    status: str
    severity: str
    cloud_account_id: str | None
    evidence: dict | None
    failing_resource_ids: list[str] | None
    run_at: datetime


class ScanNowResponse(BaseModel):
    status: str
    scanned: list[str]
    summary: dict[str, Any]


class TrendPoint(BaseModel):
    snapshot_at: datetime
    score: float
    pass_count: int
    fail_count: int
    inconclusive_count: int


class TrendResponse(BaseModel):
    cloud_provider: str
    points: list[TrendPoint]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CLOUD_CONNECTORS = {"aws": "aws_cspm", "azure": "azure_cspm", "gcp": "gcp_cspm"}


async def _load_credentials(
    db: AsyncSession, tenant_id: uuid.UUID, connector_name: str
) -> dict | None:
    row = (
        await db.execute(
            select(TenantConnectorCredential).where(
                TenantConnectorCredential.tenant_id == tenant_id,
                TenantConnectorCredential.connector_name == connector_name,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return decrypt_credentials(row.encrypted_blob)


def _instantiate_connector(name: str):
    factory = _global_registry.get(name)
    return factory()


def _build_connector_data_from_findings(findings: list[Any]) -> dict[str, Any]:
    """Best-effort transform of RawFindings into rule-shaped connector_data."""
    data: dict[str, Any] = {
        "iam_users": [],
        "s3_buckets": [],
        "ec2_security_groups": [],
        "ec2_volumes": [],
        "cloudtrail_trails": [],
        "rds_instances": [],
        "kms_keys": [],
        "vpc_flow_logs": [],
        "config_rules": [],
        "waf_web_acls": [],
        "elbv2_load_balancers": [],
        "vpcs": [],
        "nacls": [],
        "iam_password_policy": {},
        "aad_users": [],
        "aad_directory_settings": {},
        "defender_plans": [],
        "storage_accounts": [],
        "sql_servers": [],
        "nsgs": [],
        "app_gateways": [],
        "vms": [],
        "key_vaults": [],
        "app_services": [],
        "aks_clusters": [],
        "iam_bindings": [],
        "vpc_networks": [],
        "firewall_rules": [],
        "subnets": [],
        "compute_instances": [],
        "cloud_sql_instances": [],
        "bigquery_datasets": [],
        "gke_clusters": [],
        "dns_managed_zones": [],
        "log_sinks": [],
        "audit_configs": [],
    }
    for raw in findings:
        rd = raw.raw_data if hasattr(raw, "raw_data") else {}
        ftype = rd.get("type", "unknown") if isinstance(rd, dict) else "unknown"
        payload = rd.get("data", {}) if isinstance(rd, dict) else {}
        # Minimal heuristics — production would have a richer mapper
        if ftype == "config":
            data["config_rules"].append(payload)
        elif ftype == "securityhub":
            # Try to infer resource type from finding
            title = (payload.get("Title") or "").lower()
            if "s3" in title:
                data["s3_buckets"].append({"name": "inferred-s3", "public_read": True})
            elif "security group" in title:
                data["ec2_security_groups"].append({"group_id": "inferred-sg", "ingress_rules": []})
        elif ftype == "policy":
            data["config_rules"].append(payload)
        elif ftype == "defender-rec":
            data["defender_plans"].append(payload)
        elif ftype == "scc":
            data["config_rules"].append(payload)
    return data


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/clouds", response_model=CloudAccountListResponse)
async def list_cloud_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
):
    tenant_id = TenantContext.get()
    items = []
    for provider, conn_name in CLOUD_CONNECTORS.items():
        creds = await _load_credentials(db, tenant_id, conn_name)
        items.append(CloudAccountItem(connector=provider, configured=creds is not None))
    return CloudAccountListResponse(items=items)


@router.post("/clouds", response_model=ConnectCloudResponse)
async def connect_cloud(
    payload: ConnectCloudRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
):
    """Connect a cloud by storing encrypted credentials."""
    tenant_id = TenantContext.get()
    # Determine connector from credentials (expect 'provider' key)
    provider = payload.credentials.get("provider", "aws")
    connector_name = CLOUD_CONNECTORS.get(provider, "aws_cspm")

    # Inline the credential upsert (same pattern as connectors router)
    from backend.services.crypto_service import encrypt_credentials
    from backend.models.audit_log import AuditLog

    encrypted = encrypt_credentials(payload.credentials)
    existing = (
        await db.execute(
            select(TenantConnectorCredential).where(
                TenantConnectorCredential.tenant_id == tenant_id,
                TenantConnectorCredential.connector_name == connector_name,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        row = TenantConnectorCredential(
            tenant_id=tenant_id,
            connector_name=connector_name,
            encrypted_blob=encrypted,
        )
        db.add(row)
        action = "cspm_cloud_connected"
    else:
        existing.encrypted_blob = encrypted
        existing.updated_at = datetime.now(timezone.utc)
        action = "cspm_cloud_updated"

    db.add(
        AuditLog(
            user_id=current_user.id,
            action=action,
            resource_type="cspm_cloud",
            resource_id=None,
            details={"connector": connector_name, "provider": provider},
            tenant_id=tenant_id,
        )
    )
    await db.commit()
    return ConnectCloudResponse(status="configured", connector=provider)


@router.get("/score", response_model=ScoreResponse)
async def get_cspm_score(
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
):
    tenant_id = TenantContext.get()
    subq = (
        select(
            CspmScoreSnapshot.cloud_provider,
            func.max(CspmScoreSnapshot.snapshot_at).label("max_at"),
        )
        .where(CspmScoreSnapshot.tenant_id == tenant_id)
        .group_by(CspmScoreSnapshot.cloud_provider)
        .subquery()
    )
    result = await db.execute(
        select(CspmScoreSnapshot)
        .join(
            subq,
            (CspmScoreSnapshot.cloud_provider == subq.c.cloud_provider)
            & (CspmScoreSnapshot.snapshot_at == subq.c.max_at),
        )
        .where(CspmScoreSnapshot.tenant_id == tenant_id)
    )
    rows = result.scalars().all()
    items = [
        ScoreItem(
            cloud_provider=r.cloud_provider,
            score=float(r.score),
            pass_count=r.pass_count,
            fail_count=r.fail_count,
            inconclusive_count=r.inconclusive_count,
            snapshot_at=r.snapshot_at,
        )
        for r in rows
    ]
    return ScoreResponse(items=items)


@router.get("/score/{cloud_provider}", response_model=ProviderScoreResponse)
async def get_provider_score(
    cloud_provider: str,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
):
    tenant_id = TenantContext.get()
    # Latest snapshot
    snap = (
        await db.execute(
            select(CspmScoreSnapshot)
            .where(
                CspmScoreSnapshot.tenant_id == tenant_id,
                CspmScoreSnapshot.cloud_provider == cloud_provider,
            )
            .order_by(desc(CspmScoreSnapshot.snapshot_at))
            .limit(1)
        )
    ).scalar_one_or_none()

    if snap is None:
        raise HTTPException(status_code=404, detail="No score snapshot for this provider.")

    # Control breakdown
    results = (
        await db.execute(
            select(CspmCheckResult, CspmControl)
            .join(CspmControl, CspmCheckResult.control_id == CspmControl.id)
            .where(
                CspmCheckResult.tenant_id == tenant_id,
                CspmControl.control_code.startswith(f"CIS-{cloud_provider.upper()}"),
            )
            .order_by(desc(CspmCheckResult.run_at))
        )
    ).all()

    controls = []
    seen = set()
    for r, c in results:
        if c.id in seen:
            continue
        seen.add(c.id)
        controls.append(
            ControlBreakdownItem(
                control_code=c.control_code,
                title=c.title,
                severity=c.severity,
                status=r.status,
                run_at=r.run_at,
            )
        )

    return ProviderScoreResponse(
        cloud_provider=cloud_provider,
        score=float(snap.score),
        controls=controls,
    )


@router.get("/findings", response_model=FindingsResponse)
async def list_findings(
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    cloud_provider: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
):
    tenant_id = TenantContext.get()
    stmt = (
        select(CspmCheckResult, CspmControl)
        .join(CspmControl, CspmCheckResult.control_id == CspmControl.id)
        .where(CspmCheckResult.tenant_id == tenant_id)
    )

    if status:
        stmt = stmt.where(CspmCheckResult.status == status)
    if severity:
        stmt = stmt.where(CspmControl.severity == severity)
    if cloud_provider:
        stmt = stmt.where(CspmControl.control_code.startswith(f"CIS-{cloud_provider.upper()}"))

    count_result = await db.execute(
        select(func.count()).select_from(stmt.subquery())
    )
    total = count_result.scalar() or 0

    stmt = stmt.order_by(desc(CspmCheckResult.run_at)).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).all()

    items = []
    for r, c in rows:
        items.append(
            FindingItem(
                id=str(r.id),
                control_code=c.control_code,
                title=c.title,
                status=r.status,
                severity=c.severity,
                cloud_account_id=r.cloud_account_id,
                run_at=r.run_at,
            )
        )

    return FindingsResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/findings/{finding_id}", response_model=FindingDetailResponse)
async def get_finding_detail(
    finding_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
):
    tenant_id = TenantContext.get()
    row = (
        await db.execute(
            select(CspmCheckResult, CspmControl)
            .join(CspmControl, CspmCheckResult.control_id == CspmControl.id)
            .where(
                CspmCheckResult.id == finding_id,
                CspmCheckResult.tenant_id == tenant_id,
            )
        )
    ).first()

    if not row:
        raise HTTPException(status_code=404, detail="Finding not found.")

    r, c = row
    return FindingDetailResponse(
        id=str(r.id),
        control_code=c.control_code,
        title=c.title,
        description=c.description,
        status=r.status,
        severity=c.severity,
        cloud_account_id=r.cloud_account_id,
        evidence=r.evidence_json,
        failing_resource_ids=r.failing_resource_ids,
        run_at=r.run_at,
    )


@router.post("/scan-now", response_model=ScanNowResponse)
async def scan_now(
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
):
    tenant_id = str(TenantContext.get())
    engine = CspmEngine(db)
    scanned = []
    summary: dict[str, Any] = {}

    for provider, conn_name in CLOUD_CONNECTORS.items():
        creds = await _load_credentials(db, uuid.UUID(tenant_id), conn_name)
        if creds is None:
            continue

        try:
            instance = _instantiate_connector(conn_name)
            instance.authenticate(creds)
            since = datetime.now(timezone.utc) - timedelta(hours=24)
            findings = instance.fetch_findings(since, tenant_id=tenant_id)
            connector_data = _build_connector_data_from_findings(findings)
            results = await engine.run_cspm_checks(tenant_id, provider, connector_data)
            scanned.append(provider)
            summary[provider] = {"controls_evaluated": len(results)}
        except Exception as exc:
            logger.exception("CSPM scan-now failed for %s", provider)
            summary[provider] = {"error": str(exc)}

    if not scanned:
        raise HTTPException(status_code=400, detail="No cloud accounts configured for CSPM.")

    await db.commit()
    return ScanNowResponse(status="ok", scanned=scanned, summary=summary)


@router.get("/trend", response_model=list[TrendResponse])
async def get_trend(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
):
    tenant_id = TenantContext.get()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(CspmScoreSnapshot)
        .where(
            CspmScoreSnapshot.tenant_id == tenant_id,
            CspmScoreSnapshot.snapshot_at >= since,
        )
        .order_by(CspmScoreSnapshot.snapshot_at)
    )
    rows = result.scalars().all()

    by_provider: dict[str, list[TrendPoint]] = {}
    for r in rows:
        by_provider.setdefault(r.cloud_provider, []).append(
            TrendPoint(
                snapshot_at=r.snapshot_at,
                score=float(r.score),
                pass_count=r.pass_count,
                fail_count=r.fail_count,
                inconclusive_count=r.inconclusive_count,
            )
        )

    return [
        TrendResponse(cloud_provider=provider, points=points)
        for provider, points in by_provider.items()
    ]

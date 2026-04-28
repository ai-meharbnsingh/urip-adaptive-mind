"""
DSPM scan service — Project_33a §13 LIVE (MVP scaffold).

Responsibilities
----------------
- Persist DataAsset, SensitiveDataDiscovery, DataAccessPath rows
- Provide read APIs (list_*) used by the router
- Ingest from existing connector outputs:
    * `ingest_from_cloud_assets`  — takes CSPM cloud-asset rows
                                    (S3 buckets, RDS instances, key vaults, …)
                                    or M365/Workspace collaboration objects
                                    and seeds DataAsset rows.

Honest depth note
-----------------
This is the MVP placeholder.  Real DSPM (Wiz, Cyera, BigID, Varonis) ships
ML classifiers, schema-aware scanning, lineage graphs and shadow-data
discovery.  This scaffold establishes:
  - the model + REST surface,
  - a deterministic ingest path so a customer sees rows,
  - hooks for the real classifier to be plugged in later.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.dspm import (
    DATA_CLASSIFICATION_VALUES,
    STORE_TYPE_VALUES,
    DataAccessPath,
    DataAsset,
    SensitiveDataDiscovery,
)

logger = logging.getLogger(__name__)


SCAN_SOURCE_CSPM = "cspm"
SCAN_SOURCE_COLLAB = "collaboration"

# Mapping from CSPM resource shapes to (store_type, default_classification).
_CSPM_TYPE_MAP: dict[str, tuple[str, str]] = {
    "s3_bucket": ("object_storage", "internal"),
    "rds_instance": ("database", "confidential"),
    "cloud_sql_instance": ("database", "confidential"),
    "bigquery_dataset": ("database", "confidential"),
    "storage_account": ("object_storage", "internal"),
    "sql_server": ("database", "confidential"),
}


# --------------------------------------------------------------------------- #
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #
def _validate_store_type(value: str) -> None:
    if value not in STORE_TYPE_VALUES:
        raise ValueError(
            f"Invalid store_type {value!r}; allowed: {sorted(STORE_TYPE_VALUES)}"
        )


def _validate_classification(value: str) -> None:
    if value not in DATA_CLASSIFICATION_VALUES:
        raise ValueError(
            f"Invalid data_classification {value!r}; allowed: {sorted(DATA_CLASSIFICATION_VALUES)}"
        )


# --------------------------------------------------------------------------- #
# Create / read DataAsset
# --------------------------------------------------------------------------- #
async def create_data_asset(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    store_type: str,
    location: str,
    data_classification: str = "internal",
    sensitive_data_types: Optional[list[str]] = None,
    owner: Optional[str] = None,
    notes: Optional[str] = None,
    last_scanned_at: Optional[datetime] = None,
) -> DataAsset:
    _validate_store_type(store_type)
    _validate_classification(data_classification)
    if not location or not location.strip():
        raise ValueError("location is required")

    asset = DataAsset(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        store_type=store_type,
        location=location.strip(),
        data_classification=data_classification,
        sensitive_data_types=sensitive_data_types,
        owner=owner,
        notes=notes,
        last_scanned_at=last_scanned_at,
    )
    db.add(asset)
    await db.flush()
    return asset


async def list_data_assets(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    store_type: Optional[str] = None,
    classification: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[DataAsset]:
    stmt = select(DataAsset).where(DataAsset.tenant_id == tenant_id)
    if store_type:
        _validate_store_type(store_type)
        stmt = stmt.where(DataAsset.store_type == store_type)
    if classification:
        _validate_classification(classification)
        stmt = stmt.where(DataAsset.data_classification == classification)
    stmt = stmt.order_by(DataAsset.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# --------------------------------------------------------------------------- #
# Sensitive discoveries
# --------------------------------------------------------------------------- #
async def record_sensitive_discovery(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    data_asset_id: uuid.UUID,
    sensitive_type: str,
    severity: str = "medium",
    sample_count: Optional[int] = None,
    evidence: Optional[dict[str, Any]] = None,
) -> SensitiveDataDiscovery:
    if severity not in {"critical", "high", "medium", "low"}:
        raise ValueError(f"Invalid severity {severity!r}")
    if not sensitive_type or not sensitive_type.strip():
        raise ValueError("sensitive_type is required")

    disc = SensitiveDataDiscovery(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        data_asset_id=data_asset_id,
        sensitive_type=sensitive_type.strip().lower(),
        severity=severity,
        sample_count=sample_count,
        evidence=evidence,
    )
    db.add(disc)
    await db.flush()
    return disc


async def list_sensitive_discoveries(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    data_asset_id: Optional[uuid.UUID] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[SensitiveDataDiscovery]:
    stmt = select(SensitiveDataDiscovery).where(SensitiveDataDiscovery.tenant_id == tenant_id)
    if data_asset_id:
        stmt = stmt.where(SensitiveDataDiscovery.data_asset_id == data_asset_id)
    if severity:
        stmt = stmt.where(SensitiveDataDiscovery.severity == severity)
    stmt = stmt.order_by(SensitiveDataDiscovery.detected_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# --------------------------------------------------------------------------- #
# Access paths
# --------------------------------------------------------------------------- #
async def record_access_path(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    data_asset_id: uuid.UUID,
    identity: str,
    identity_type: str = "user",
    access_type: str = "read",
    granted_via: Optional[str] = None,
) -> DataAccessPath:
    if identity_type not in {"user", "group", "role", "service"}:
        raise ValueError(f"Invalid identity_type {identity_type!r}")
    if access_type not in {"read", "write", "admin"}:
        raise ValueError(f"Invalid access_type {access_type!r}")
    if not identity or not identity.strip():
        raise ValueError("identity is required")

    path = DataAccessPath(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        data_asset_id=data_asset_id,
        identity=identity.strip(),
        identity_type=identity_type,
        access_type=access_type,
        granted_via=granted_via,
    )
    db.add(path)
    await db.flush()
    return path


async def list_access_paths(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    data_asset_id: Optional[uuid.UUID] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[DataAccessPath]:
    stmt = select(DataAccessPath).where(DataAccessPath.tenant_id == tenant_id)
    if data_asset_id:
        stmt = stmt.where(DataAccessPath.data_asset_id == data_asset_id)
    stmt = stmt.order_by(DataAccessPath.last_evaluated_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# --------------------------------------------------------------------------- #
# Connector ingest — best-effort transform, NOT an ML classifier.
# --------------------------------------------------------------------------- #
async def ingest_from_cloud_assets(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    cloud_assets: Iterable[dict[str, Any]],
    source: str = SCAN_SOURCE_CSPM,
) -> list[DataAsset]:
    """
    Best-effort import.  Each `cloud_assets` dict should contain at minimum:

        {"resource_type": "s3_bucket", "name": "acme-prod", "owner": "platform-team"}

    Or for collaboration-tool ingest:

        {"resource_type": "saas", "name": "Sharepoint:Finance", "owner": "finance"}

    Returns the persisted DataAsset rows so the caller can `db.commit()`.

    Honest note: this does NOT run a content classifier.  It seeds the asset
    inventory so a customer can see "DSPM is here" with their real cloud
    inventory.  Sensitive-data classification is roadmap.
    """
    out: list[DataAsset] = []
    now = _utcnow()
    for payload in cloud_assets:
        rtype = (payload.get("resource_type") or "").lower()
        name = (payload.get("name") or "").strip()
        if not name:
            continue
        if rtype in _CSPM_TYPE_MAP:
            store_type, default_class = _CSPM_TYPE_MAP[rtype]
        elif source == SCAN_SOURCE_COLLAB:
            store_type, default_class = "saas", "internal"
        else:
            # unknown — fall back to file_system bucket
            store_type, default_class = "file_system", "internal"

        asset = await create_data_asset(
            db,
            tenant_id,
            store_type=store_type,
            location=name,
            data_classification=payload.get("data_classification") or default_class,
            owner=payload.get("owner"),
            sensitive_data_types=payload.get("sensitive_data_types"),
            last_scanned_at=now,
        )
        out.append(asset)
    return out

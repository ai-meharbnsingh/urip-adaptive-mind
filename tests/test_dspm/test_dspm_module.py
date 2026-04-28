"""DSPM module — model + service + route tests (Project_33a §13 MVP scaffold)."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.auth import create_access_token, hash_password
from backend.models.dspm import (
    DATA_CLASSIFICATION_VALUES,
    STORE_TYPE_VALUES,
    DataAccessPath,
    DataAsset,
    SensitiveDataDiscovery,
)
from backend.models.subscription import TenantSubscription
from backend.models.user import User
from backend.services.dspm import (
    create_data_asset,
    ingest_from_cloud_assets,
    list_data_assets,
    record_access_path,
    record_sensitive_discovery,
)


# --------------------------------------------------------------------------- #
# Subscription + auth fixtures
# --------------------------------------------------------------------------- #
@pytest_asyncio.fixture
async def dspm_subscription(db_session: AsyncSession, default_tenant) -> TenantSubscription:
    sub = TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=default_tenant.id,
        module_code="DSPM",
        is_enabled=True,
        billing_tier="STANDARD",
    )
    db_session.add(sub)
    await db_session.commit()
    return sub


@pytest_asyncio.fixture
async def dspm_auth_headers(
    db_session: AsyncSession, default_tenant, dspm_subscription
) -> dict[str, str]:
    user = User(
        id=uuid.uuid4(),
        email="ciso-dspm@urip.test",
        hashed_password=hash_password("Secure#Pass1"),
        full_name="DSPM CISO",
        role="ciso",
        team="Security",
        is_active=True,
        tenant_id=default_tenant.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token = create_access_token(str(user.id), user.role, tenant_id=str(default_tenant.id))
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
# Model-layer
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_data_asset_persists_with_required_fields(db_session, default_tenant):
    asset = DataAsset(
        id=uuid.uuid4(),
        tenant_id=default_tenant.id,
        store_type="database",
        location="prod-rds.example.com",
        data_classification="confidential",
        sensitive_data_types=["pii", "phi"],
        owner="data-platform-team",
    )
    db_session.add(asset)
    await db_session.commit()
    rows = (await db_session.execute(select(DataAsset))).scalars().all()
    assert len(rows) == 1
    assert rows[0].store_type == "database"
    assert rows[0].sensitive_data_types == ["pii", "phi"]


def test_store_type_constant_includes_required_values():
    # MVP requirement: database / file_system / object_storage / saas all present.
    for v in {"database", "file_system", "object_storage", "saas"}:
        assert v in STORE_TYPE_VALUES


def test_classification_constant_has_4_levels():
    assert DATA_CLASSIFICATION_VALUES == {"public", "internal", "confidential", "restricted"}


# --------------------------------------------------------------------------- #
# Service-layer
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_create_data_asset_rejects_invalid_store_type(db_session, default_tenant):
    with pytest.raises(ValueError):
        await create_data_asset(
            db_session, default_tenant.id,
            store_type="cassettetape", location="x",
        )


@pytest.mark.asyncio
async def test_list_data_assets_filters_by_store_type(db_session, default_tenant):
    await create_data_asset(db_session, default_tenant.id, store_type="database", location="db1")
    await create_data_asset(db_session, default_tenant.id, store_type="object_storage", location="bucket1")
    await db_session.commit()
    only_db = await list_data_assets(db_session, default_tenant.id, store_type="database")
    assert len(only_db) == 1
    assert only_db[0].location == "db1"


@pytest.mark.asyncio
async def test_record_sensitive_discovery_links_to_asset(db_session, default_tenant):
    asset = await create_data_asset(
        db_session, default_tenant.id,
        store_type="database", location="users-table",
    )
    await db_session.commit()
    disc = await record_sensitive_discovery(
        db_session, default_tenant.id,
        data_asset_id=asset.id, sensitive_type="ssn", severity="high", sample_count=42,
    )
    await db_session.commit()
    assert disc.data_asset_id == asset.id
    assert disc.sensitive_type == "ssn"


@pytest.mark.asyncio
async def test_record_access_path_validates_identity_type(db_session, default_tenant):
    asset = await create_data_asset(
        db_session, default_tenant.id,
        store_type="object_storage", location="prod-data",
    )
    await db_session.commit()
    with pytest.raises(ValueError):
        await record_access_path(
            db_session, default_tenant.id,
            data_asset_id=asset.id, identity="alice", identity_type="alien",
        )


@pytest.mark.asyncio
async def test_ingest_from_cloud_assets_seeds_inventory(db_session, default_tenant):
    payloads = [
        {"resource_type": "s3_bucket", "name": "acme-prod-data", "owner": "ops"},
        {"resource_type": "rds_instance", "name": "users-rds", "owner": "data"},
        {"resource_type": "unknown", "name": "weird-thing"},
    ]
    rows = await ingest_from_cloud_assets(
        db_session, default_tenant.id, cloud_assets=payloads,
    )
    await db_session.commit()
    assert len(rows) == 3
    by_loc = {r.location: r for r in rows}
    assert by_loc["acme-prod-data"].store_type == "object_storage"
    assert by_loc["users-rds"].store_type == "database"
    assert by_loc["weird-thing"].store_type == "file_system"  # fallback


# --------------------------------------------------------------------------- #
# Route-layer
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_dspm_route_403_without_subscription(
    client: AsyncClient, db_session, default_tenant, auth_headers
):
    """auth_headers fixture has CORE+VM but NOT DSPM — must 403."""
    resp = await client.get("/api/dspm/data-assets", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_dspm_data_assets_endpoint_returns_seeded_rows(
    client: AsyncClient, db_session, default_tenant, dspm_auth_headers
):
    a = DataAsset(
        id=uuid.uuid4(),
        tenant_id=default_tenant.id,
        store_type="database",
        location="prod-pg",
        data_classification="confidential",
        sensitive_data_types=["pii"],
        owner="data",
    )
    db_session.add(a)
    await db_session.commit()
    resp = await client.get("/api/dspm/data-assets", headers=dspm_auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["location"] == "prod-pg"


@pytest.mark.asyncio
async def test_dspm_post_data_asset_validates_classification(
    client: AsyncClient, db_session, default_tenant, dspm_auth_headers
):
    resp = await client.post(
        "/api/dspm/data-assets",
        json={
            "store_type": "database",
            "location": "prod-mysql",
            "data_classification": "ULTRA_TOP_SECRET",
        },
        headers=dspm_auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_dspm_scan_endpoint_ingests_cloud_assets(
    client: AsyncClient, db_session, default_tenant, dspm_auth_headers
):
    resp = await client.post(
        "/api/dspm/scan",
        json={
            "cloud_assets": [
                {"resource_type": "s3_bucket", "name": "scan-bucket", "owner": "ops"},
            ],
            "source": "cspm",
        },
        headers=dspm_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ingested"] == 1
    assert data["assets"][0]["location"] == "scan-bucket"
    assert data["assets"][0]["store_type"] == "object_storage"


@pytest.mark.asyncio
async def test_dspm_access_paths_endpoint(
    client: AsyncClient, db_session, default_tenant, dspm_auth_headers
):
    asset = DataAsset(
        id=uuid.uuid4(),
        tenant_id=default_tenant.id,
        store_type="object_storage",
        location="ssn-bucket",
        data_classification="restricted",
    )
    db_session.add(asset)
    await db_session.flush()
    db_session.add(
        DataAccessPath(
            id=uuid.uuid4(),
            tenant_id=default_tenant.id,
            data_asset_id=asset.id,
            identity="alice@example.com",
            identity_type="user",
            access_type="read",
            granted_via="iam_policy:abc",
        )
    )
    await db_session.commit()
    resp = await client.get(
        f"/api/dspm/access-paths?data_asset_id={asset.id}",
        headers=dspm_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["identity"] == "alice@example.com"

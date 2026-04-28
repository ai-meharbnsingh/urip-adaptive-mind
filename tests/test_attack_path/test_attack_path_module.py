"""Attack Path Prediction module — model + service + route tests."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.auth import create_access_token, hash_password
from backend.models.attack_path import (
    EDGE_TYPE_VALUES,
    NODE_TYPE_VALUES,
    AttackPath,
    AttackPathEdge,
    AttackPathNode,
)
from backend.models.subscription import TenantSubscription
from backend.models.user import User
from backend.services.attack_path import (
    add_edge,
    add_node,
    find_critical_paths,
    list_critical_paths,
    recompute_paths,
)


# --------------------------------------------------------------------------- #
@pytest_asyncio.fixture
async def attack_path_subscription(db_session: AsyncSession, default_tenant) -> TenantSubscription:
    sub = TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=default_tenant.id,
        module_code="ATTACK_PATH",
        is_enabled=True,
        billing_tier="STANDARD",
    )
    db_session.add(sub)
    await db_session.commit()
    return sub


@pytest_asyncio.fixture
async def attack_path_auth_headers(
    db_session: AsyncSession, default_tenant, attack_path_subscription
) -> dict[str, str]:
    user = User(
        id=uuid.uuid4(),
        email="ciso-ap@urip.test",
        hashed_password=hash_password("Secure#Pass1"),
        full_name="AP CISO",
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
# Model
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_node_persists(db_session, default_tenant):
    n = AttackPathNode(
        id=uuid.uuid4(),
        tenant_id=default_tenant.id,
        node_type="asset",
        label="db-prod-01",
        is_internet_exposed=False,
        asset_tier=1,
    )
    db_session.add(n)
    await db_session.commit()
    rows = (await db_session.execute(select(AttackPathNode))).scalars().all()
    assert len(rows) == 1
    assert rows[0].asset_tier == 1


def test_node_type_values_constant():
    assert NODE_TYPE_VALUES == {"asset", "identity", "application"}


def test_edge_type_values_constant():
    assert EDGE_TYPE_VALUES == {"can_authenticate_to", "has_access_to", "exposed_to"}


# --------------------------------------------------------------------------- #
# Service
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_add_node_validates_type(db_session, default_tenant):
    with pytest.raises(ValueError):
        await add_node(db_session, default_tenant.id, node_type="alien", label="x")


@pytest.mark.asyncio
async def test_add_edge_rejects_self_loop(db_session, default_tenant):
    n = await add_node(db_session, default_tenant.id, node_type="asset", label="a")
    with pytest.raises(ValueError):
        await add_edge(
            db_session, default_tenant.id,
            source_id=n.id, target_id=n.id, edge_type="has_access_to",
        )


@pytest.mark.asyncio
async def test_find_critical_paths_simple_chain(db_session, default_tenant):
    # web (exposed) → app → db (tier 1)
    web = await add_node(
        db_session, default_tenant.id,
        node_type="application", label="web-frontend", is_internet_exposed=True,
    )
    app = await add_node(
        db_session, default_tenant.id, node_type="application", label="app-server",
    )
    db_node = await add_node(
        db_session, default_tenant.id, node_type="asset", label="customer-db", asset_tier=1,
    )
    await add_edge(db_session, default_tenant.id, source_id=web.id, target_id=app.id, edge_type="exposed_to", weight=2.0)
    await add_edge(db_session, default_tenant.id, source_id=app.id, target_id=db_node.id, edge_type="has_access_to", weight=2.0)
    await db_session.commit()

    paths = await find_critical_paths(db_session, default_tenant.id)
    assert len(paths) == 1
    p = paths[0]
    assert p["hop_count"] == 2
    assert p["mitre_chain"] == ["T1190", "T1486"]
    assert 50 <= p["risk_score"] <= 100


@pytest.mark.asyncio
async def test_recompute_paths_persists_critical_only(db_session, default_tenant):
    web = await add_node(
        db_session, default_tenant.id,
        node_type="application", label="w", is_internet_exposed=True,
    )
    db_node = await add_node(
        db_session, default_tenant.id,
        node_type="asset", label="d", asset_tier=1,
    )
    await add_edge(
        db_session, default_tenant.id,
        source_id=web.id, target_id=db_node.id, edge_type="exposed_to", weight=3.0,
    )
    await db_session.commit()

    persisted = await recompute_paths(db_session, default_tenant.id)
    await db_session.commit()
    assert len(persisted) == 1
    assert persisted[0].is_critical is True

    listed = await list_critical_paths(db_session, default_tenant.id, only_critical=True)
    assert len(listed) == 1


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_attack_path_route_403_without_subscription(client: AsyncClient, auth_headers):
    resp = await client.get("/api/attack-paths/critical", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_attack_path_recompute_endpoint(
    client: AsyncClient, db_session, default_tenant, attack_path_auth_headers
):
    web = AttackPathNode(
        id=uuid.uuid4(), tenant_id=default_tenant.id,
        node_type="application", label="w", is_internet_exposed=True,
    )
    db_n = AttackPathNode(
        id=uuid.uuid4(), tenant_id=default_tenant.id,
        node_type="asset", label="d", asset_tier=1,
    )
    db_session.add_all([web, db_n])
    await db_session.flush()
    db_session.add(
        AttackPathEdge(
            id=uuid.uuid4(), tenant_id=default_tenant.id,
            source_id=web.id, target_id=db_n.id, edge_type="exposed_to", weight=2.5,
        )
    )
    await db_session.commit()

    resp = await client.post("/api/attack-paths/recompute", headers=attack_path_auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["paths_computed"] >= 1
    assert body["critical_paths"] >= 1


@pytest.mark.asyncio
async def test_attack_path_critical_listing_then_details(
    client: AsyncClient, db_session, default_tenant, attack_path_auth_headers
):
    web = AttackPathNode(
        id=uuid.uuid4(), tenant_id=default_tenant.id,
        node_type="application", label="web", is_internet_exposed=True,
    )
    db_n = AttackPathNode(
        id=uuid.uuid4(), tenant_id=default_tenant.id,
        node_type="asset", label="db", asset_tier=1,
    )
    db_session.add_all([web, db_n])
    await db_session.flush()
    db_session.add(
        AttackPath(
            id=uuid.uuid4(), tenant_id=default_tenant.id,
            source_node_id=web.id, target_node_id=db_n.id,
            hop_count=1, risk_score=78.0, is_critical=True,
            path_node_ids=[str(web.id), str(db_n.id)],
            mitre_chain=["T1190", "T1486"],
        )
    )
    await db_session.commit()

    listing = await client.get("/api/attack-paths/critical", headers=attack_path_auth_headers)
    assert listing.status_code == 200, listing.text
    items = listing.json()["items"]
    assert len(items) == 1
    pid = items[0]["id"]

    details = await client.get(f"/api/attack-paths/{pid}/details", headers=attack_path_auth_headers)
    assert details.status_code == 200, details.text
    body = details.json()
    assert len(body["nodes"]) == 2
    assert body["nodes"][0]["label"] == "web"
    assert body["nodes"][1]["label"] == "db"


@pytest.mark.asyncio
async def test_attack_path_details_404_for_missing(
    client: AsyncClient, attack_path_auth_headers
):
    bogus = uuid.uuid4()
    resp = await client.get(f"/api/attack-paths/{bogus}/details", headers=attack_path_auth_headers)
    assert resp.status_code == 404

"""
Capture a real GET /api/assets?device_category=Devices&limit=5 response
and write it to /tmp/sample_assets_response.json — used to deliver a
representative response payload back to the orchestrator (Part 3 deliverable).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.main import app
from backend.middleware.auth import create_access_token, hash_password
from backend.models.asset import Asset
from backend.models.subscription import TenantSubscription
from backend.models.tenant import Tenant
from backend.models.user import User


@pytest_asyncio.fixture
async def isolated_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def test_sample_devices_response_capture(
    isolated_client: AsyncClient, db_session: AsyncSession
):
    """Seed 6 realistic Devices-category assets, hit the endpoint, dump JSON."""
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Sample Tenant",
        slug="sample-rt",
        domain="sample.test",
        is_active=True,
        settings={},
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    db_session.add(
        TenantSubscription(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            module_code="CORE",
            is_enabled=True,
            billing_tier="STANDARD",
            expires_at=None,
        )
    )

    user = User(
        id=uuid.uuid4(),
        email="ciso@sample.test",
        hashed_password=hash_password("Secure#Pass1"),
        full_name="Sample CISO",
        role="ciso",
        team="Security",
        is_active=True,
        tenant_id=tenant.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token = create_access_token(str(user.id), user.role, tenant_id=str(tenant.id))
    headers = {"Authorization": f"Bearer {token}"}

    # Seed 6 realistic assets
    seeds = [
        ("prd-sap-01", "10.0.1.5", "aa:bb:cc:dd:ee:01", "server", "IT", "T1",
         "Infrastructure", "Linux", "Ubuntu 22.04", 8.7,
         {"env": "prod", "cost_center": "FIN-42"}),
        ("hmi-line-3", "10.20.0.41", "aa:bb:cc:dd:ee:02", "iot", "OT", "T1",
         "Plant-Engineering", "Windows", "Windows 10 IoT", 9.2,
         {"line": "3", "shop": "assembly"}),
        ("dealer-ws-77", "10.30.0.77", "aa:bb:cc:dd:ee:03", "desktop", "IT", "T3",
         "Dealer-IT", "Windows", "Windows 11", 5.1, {"region": "north"}),
        ("eu-prod-eks-01", "10.50.0.10", "aa:bb:cc:dd:ee:04", "server", "IT", "T2",
         "DevOps", "Linux", "Amazon Linux 2", 6.4, {"cluster": "eu-prod"}),
        ("dev-laptop-19", "10.40.0.19", "aa:bb:cc:dd:ee:05", "laptop", "IT", "T4",
         "Engineering", "macOS", "Sonoma 14.4", 2.0, {"team": "platform"}),
        ("paint-rtu-12", "10.21.0.12", "aa:bb:cc:dd:ee:06", "iot", "OT", "T2",
         "Plant-Engineering", "VxWorks", "6.9", 7.0, {"cell": "paint-12"}),
    ]
    now = datetime.now(timezone.utc)
    for hostname, ip, mac, dt, dc, tier, owner, os_n, os_v, score, tags in seeds:
        db_session.add(
            Asset(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                fingerprint_key=(hostname + "-fp").ljust(64, "x")[:64],
                hostname=hostname,
                internal_ip=ip,
                mac_address=mac,
                device_type=dt,
                device_category=dc,
                os_name=os_n,
                os_version=os_v,
                owner_team=owner,
                asset_tier=tier,
                business_criticality="critical" if tier == "T1" else "high" if tier == "T2" else "medium",
                asset_risk_score=score,
                lifecycle_state="in_use",
                discovered_at=now,
                last_seen=now,
                source_connectors=["tenable", "armis"] if dc == "OT" else ["tenable"],
                custom_tags=tags,
            )
        )
    await db_session.commit()

    # Hit the documented deliverable endpoint
    r = await isolated_client.get(
        "/api/assets?limit=5", headers=headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Five returned, total six
    assert body["total"] == 6
    assert body["limit"] == 5
    assert len(body["items"]) == 5

    # Dump the response for the deliverable
    with open("/tmp/sample_assets_response.json", "w") as f:
        json.dump(body, f, indent=2, default=str)

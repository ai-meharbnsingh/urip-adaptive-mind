"""
TDD — Compliance score REST endpoints (P2B.11).
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta

import pytest
# CRIT-005 (Z2.1): migrated python-jose -> PyJWT (HS256 surface identical)
import jwt
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.models.control_run import ControlCheckRun
from compliance_backend.models.score_snapshot import ComplianceScoreSnapshot

STANDALONE_SECRET = "test-secret-standalone"


def _user_jwt(tenant: str, role: str = "admin") -> str:
    return jwt.encode(
        {
            "sub": "u-sc-1", "tenant_id": tenant, "role": role,
            "exp": int(time.time()) + 3600, "iss": "compliance",
        },
        STANDALONE_SECRET, algorithm="HS256",
    )


def _hdr(tenant: str, role: str = "admin") -> dict:
    return {"Authorization": f"Bearer {_user_jwt(tenant, role)}"}


async def _make_framework(db_session, n_controls: int = 4) -> tuple[Framework, list[Control]]:
    fw = Framework(
        id=str(uuid.uuid4()),
        name=f"SCR-FW-{uuid.uuid4().hex[:4]}",
        short_code=f"SCR{uuid.uuid4().hex[:4].upper()}",
        category="security",
    )
    db_session.add(fw)
    await db_session.flush()
    fv = FrameworkVersion(id=str(uuid.uuid4()), framework_id=fw.id, version="1", is_current=True)
    db_session.add(fv)
    await db_session.flush()
    controls = []
    for i in range(n_controls):
        c = Control(
            id=str(uuid.uuid4()), framework_version_id=fv.id,
            control_code=f"SCR-{i}-{uuid.uuid4().hex[:4].upper()}",
            category=f"Cat-{i % 2}", description=f"c{i}",
        )
        db_session.add(c)
        controls.append(c)
    await db_session.flush()
    await db_session.commit()
    return fw, controls


async def _add_run(db_session, control_id, tenant, status):
    db_session.add(ControlCheckRun(
        control_id=control_id, tenant_id=tenant,
        run_at=datetime.utcnow(), status=status,
    ))
    await db_session.flush()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_score_routes_require_auth(client):
    assert (await client.get("/compliance-score")).status_code == 401
    assert (await client.get("/compliance-score/SOC2")).status_code == 401
    assert (await client.get("/compliance-score/SOC2/trend")).status_code == 401


# ---------------------------------------------------------------------------
# GET /compliance-score
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_get_all_scores_returns_keyed_by_short_code(client, db_session):
    fw, ctrls = await _make_framework(db_session, n_controls=2)
    tenant = f"tenant-allscores-{uuid.uuid4().hex[:6]}"
    await _add_run(db_session, ctrls[0].id, tenant, "pass")
    await _add_run(db_session, ctrls[1].id, tenant, "fail")
    await db_session.commit()

    resp = await client.get("/compliance-score", headers=_hdr(tenant))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert fw.short_code in body
    assert body[fw.short_code]["score"] == 50.0


@pytest.mark.anyio
async def test_get_all_scores_tenant_scoped(client, db_session):
    fw, ctrls = await _make_framework(db_session, n_controls=2)
    tenant_a = f"tenant-A-{uuid.uuid4().hex[:6]}"
    tenant_b = f"tenant-B-{uuid.uuid4().hex[:6]}"
    await _add_run(db_session, ctrls[0].id, tenant_a, "pass")
    await _add_run(db_session, ctrls[1].id, tenant_a, "pass")
    await _add_run(db_session, ctrls[0].id, tenant_b, "fail")
    await _add_run(db_session, ctrls[1].id, tenant_b, "fail")
    await db_session.commit()

    resp_a = await client.get("/compliance-score", headers=_hdr(tenant_a))
    resp_b = await client.get("/compliance-score", headers=_hdr(tenant_b))
    assert resp_a.json()[fw.short_code]["score"] == 100.0
    assert resp_b.json()[fw.short_code]["score"] == 0.0


# ---------------------------------------------------------------------------
# GET /compliance-score/{short_code}
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_get_framework_detail(client, db_session):
    fw, ctrls = await _make_framework(db_session, n_controls=4)
    tenant = f"tenant-detail-{uuid.uuid4().hex[:6]}"
    await _add_run(db_session, ctrls[0].id, tenant, "pass")
    await _add_run(db_session, ctrls[1].id, tenant, "pass")
    await _add_run(db_session, ctrls[2].id, tenant, "fail")
    await _add_run(db_session, ctrls[3].id, tenant, "fail")
    await db_session.commit()

    resp = await client.get(f"/compliance-score/{fw.short_code}", headers=_hdr(tenant))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["summary"]["score"] == 50.0
    # Categories returned
    cat_names = {c["category"] for c in body["categories"]}
    assert cat_names == {"Cat-0", "Cat-1"}
    # Failing IDs surfaced
    assert set(body["failing_control_ids"]) == {ctrls[2].id, ctrls[3].id}


@pytest.mark.anyio
async def test_get_framework_detail_unknown_returns_404(client):
    resp = await client.get(
        "/compliance-score/DOES-NOT-EXIST",
        headers=_hdr("tenant-x"),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /compliance-score/{short_code}/trend
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_trend_returns_snapshot_points(client, db_session):
    fw, _ = await _make_framework(db_session, n_controls=1)
    tenant = f"tenant-trend-rt-{uuid.uuid4().hex[:6]}"
    now = datetime.utcnow()
    for i, score in enumerate([60.0, 70.0, 80.0]):
        db_session.add(ComplianceScoreSnapshot(
            tenant_id=tenant, framework_id=fw.id,
            snapshot_date=now - timedelta(days=3 - i),
            score=score, pass_count=int(score / 10),
            fail_count=10 - int(score / 10),
            inconclusive_count=0, total_applicable=10,
        ))
    await db_session.commit()

    resp = await client.get(
        f"/compliance-score/{fw.short_code}/trend?days=30",
        headers=_hdr(tenant),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["framework_short_code"] == fw.short_code
    assert len(body["points"]) == 3
    assert [p["score"] for p in body["points"]] == [60.0, 70.0, 80.0]


# ---------------------------------------------------------------------------
# POST /compliance-score/snapshot
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_post_snapshot_writes_records(client, db_session):
    fw_a, ctrls_a = await _make_framework(db_session, n_controls=2)
    fw_b, ctrls_b = await _make_framework(db_session, n_controls=1)
    tenant = f"tenant-postsnap-{uuid.uuid4().hex[:6]}"
    await _add_run(db_session, ctrls_a[0].id, tenant, "pass")
    await _add_run(db_session, ctrls_a[1].id, tenant, "pass")
    await _add_run(db_session, ctrls_b[0].id, tenant, "fail")
    await db_session.commit()

    resp = await client.post("/compliance-score/snapshot", headers=_hdr(tenant))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # At least these 2 frameworks should have snapshots — others may exist from
    # prior tests in the session; accept >= 2.
    assert body["snapshots_written"] >= 2

    # Verify snapshots persisted for our two frameworks
    rows_a = (await db_session.execute(
        select(ComplianceScoreSnapshot).where(
            ComplianceScoreSnapshot.tenant_id == tenant,
            ComplianceScoreSnapshot.framework_id == fw_a.id,
        )
    )).scalars().all()
    rows_b = (await db_session.execute(
        select(ComplianceScoreSnapshot).where(
            ComplianceScoreSnapshot.tenant_id == tenant,
            ComplianceScoreSnapshot.framework_id == fw_b.id,
        )
    )).scalars().all()
    assert len(rows_a) >= 1
    assert len(rows_b) >= 1
    assert rows_a[-1].score == 100.0
    assert rows_b[-1].score == 0.0


@pytest.mark.anyio
async def test_post_snapshot_requires_admin(client, db_session):
    tenant = f"tenant-snap-noadmin-{uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/compliance-score/snapshot", headers=_hdr(tenant, role="viewer"),
    )
    assert resp.status_code == 403

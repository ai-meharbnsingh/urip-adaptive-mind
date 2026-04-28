"""
WORKFLOW 11 — Compliance scoring + trend (Compliance service).

Covers:
  1. Seed a Framework + N controls + a few ControlCheckRuns so the scoring
     engine has real data to operate on.
  2. Seed 30 days of ComplianceScoreSnapshot rows (synthetic but plausible
     numbers — increasing pass_count over time).
  3. GET /compliance-score → returns a current score per framework
     (per ScoringEngine.calculate_all_frameworks).
  4. GET /compliance-score/{short_code}/trend?days=30 → returns historical
     score points in chronological order.
  5. Score change > SCORE_DROP_WARN_THRESHOLD (10pp) triggers a warning
     log (we capture caplog and assert the warning was emitted).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

import pytest

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.models.control_run import ControlCheckRun
from compliance_backend.models.score_snapshot import ComplianceScoreSnapshot


def _admin_headers(jwt_factory, tenant_id: str) -> dict:
    return {"Authorization": f"Bearer {jwt_factory(tenant_id, role='admin')}"}


@pytest.mark.asyncio
async def test_workflow_11_score_endpoint_returns_per_framework(
    compliance_client, compliance_session, make_compliance_jwt
):
    tenant_id = "score-tenant-e2e"
    h = _admin_headers(make_compliance_jwt, tenant_id)

    # Build a framework with 4 controls — 3 pass, 1 fail
    fw = Framework(
        id=str(uuid.uuid4()),
        name="Test Framework E2E",
        short_code=f"TFE{uuid.uuid4().hex[:4].upper()}",
        category="security",
    )
    fv = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=fw.id,
        version="2024",
        is_current=True,
    )
    compliance_session.add_all([fw, fv])
    await compliance_session.flush()

    controls: list[Control] = []
    for i in range(4):
        c = Control(
            id=str(uuid.uuid4()),
            framework_version_id=fv.id,
            control_code=f"C-{i:02d}-{uuid.uuid4().hex[:3]}",
            category="Access" if i < 2 else "Operations",
            description=f"Control #{i}",
            rule_function=None,
        )
        controls.append(c)
        compliance_session.add(c)
    await compliance_session.flush()

    # Add runs: 3 pass + 1 fail
    now = datetime.utcnow()
    for c, status_str in zip(controls, ["pass", "pass", "pass", "fail"]):
        compliance_session.add(ControlCheckRun(
            id=str(uuid.uuid4()),
            control_id=c.id,
            tenant_id=tenant_id,
            run_at=now,
            status=status_str,
            evidence_ids=[],
            failure_reason=None if status_str == "pass" else "synthetic fail",
        ))
    await compliance_session.flush()

    # GET /compliance-score → all frameworks
    resp = await compliance_client.get("/compliance-score", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert fw.short_code in body, f"Framework {fw.short_code} not in response: {list(body)}"

    score = body[fw.short_code]
    assert score["pass_count"] == 3
    assert score["fail_count"] == 1
    assert score["total_controls"] == 4
    assert score["total_applicable"] == 4  # pass + fail
    # 3 / (3+1) * 100 = 75.0
    assert score["score"] == 75.0


@pytest.mark.asyncio
async def test_workflow_11_trend_returns_chronological_points(
    compliance_client, compliance_session, make_compliance_jwt
):
    tenant_id = "score-trend-tenant"
    h = _admin_headers(make_compliance_jwt, tenant_id)

    fw = Framework(
        id=str(uuid.uuid4()),
        name="Trend Framework",
        short_code=f"TR{uuid.uuid4().hex[:4].upper()}",
        category="security",
    )
    fv = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=fw.id,
        version="2024",
        is_current=True,
    )
    compliance_session.add_all([fw, fv])
    await compliance_session.flush()

    # 30 daily snapshots, score climbing from 50 → 80 (in steps of 1.0)
    now = datetime.utcnow()
    for i in range(30):
        compliance_session.add(ComplianceScoreSnapshot(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            framework_id=fw.id,
            snapshot_date=now - timedelta(days=29 - i),
            score=50.0 + i,
            pass_count=10 + i,
            fail_count=10,
            inconclusive_count=0,
            total_applicable=20 + i,
        ))
    await compliance_session.flush()

    resp = await compliance_client.get(
        f"/compliance-score/{fw.short_code}/trend?days=30", headers=h
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["framework_short_code"] == fw.short_code
    assert body["days"] == 30
    pts = body["points"]
    assert len(pts) == 30, f"expected 30 trend points, got {len(pts)}"
    # Strictly chronological + increasing scores
    scores = [p["score"] for p in pts]
    assert scores == sorted(scores), "trend must be chronological"
    assert scores[0] == 50.0
    assert scores[-1] == 79.0


@pytest.mark.asyncio
async def test_workflow_11_score_drop_emits_warning(
    compliance_client, compliance_session, make_compliance_jwt, caplog
):
    """
    The scoring engine logs a warning when the calculated score has dropped
    by more than SCORE_DROP_WARN_THRESHOLD (10pp) compared to the most recent
    snapshot. We seed a snapshot at 90, then drive the live calculation down
    to 50 and capture the warning via caplog.
    """
    tenant_id = "score-drop-tenant"
    h = _admin_headers(make_compliance_jwt, tenant_id)

    fw = Framework(
        id=str(uuid.uuid4()),
        name="Drop Framework",
        short_code=f"DR{uuid.uuid4().hex[:4].upper()}",
        category="security",
    )
    fv = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=fw.id,
        version="2024",
        is_current=True,
    )
    compliance_session.add_all([fw, fv])
    await compliance_session.flush()

    # Two controls — both will be marked "fail" so live score = 0.0
    c1 = Control(
        id=str(uuid.uuid4()),
        framework_version_id=fv.id,
        control_code="DROP-1",
        category="Access",
        description="Will fail",
        rule_function=None,
    )
    c2 = Control(
        id=str(uuid.uuid4()),
        framework_version_id=fv.id,
        control_code="DROP-2",
        category="Access",
        description="Will fail",
        rule_function=None,
    )
    compliance_session.add_all([c1, c2])
    await compliance_session.flush()

    now = datetime.utcnow()
    for c in (c1, c2):
        compliance_session.add(ControlCheckRun(
            id=str(uuid.uuid4()),
            control_id=c.id,
            tenant_id=tenant_id,
            run_at=now,
            status="fail",
            evidence_ids=[],
            failure_reason="synthetic",
        ))
    # Previous snapshot at 90 → drop to 0 = 90pp delta, > threshold
    compliance_session.add(ComplianceScoreSnapshot(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        framework_id=fw.id,
        snapshot_date=now - timedelta(days=1),
        score=90.0,
        pass_count=9,
        fail_count=1,
        inconclusive_count=0,
        total_applicable=10,
    ))
    await compliance_session.flush()

    # Capture warning during the live calc
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="compliance_backend.services.scoring_engine"):
        resp = await compliance_client.get(
            f"/compliance-score/{fw.short_code}", headers=h
        )
    assert resp.status_code == 200, resp.text
    detail = resp.json()
    assert detail["summary"]["score"] == 0.0  # 0 pass / 2 applicable

    # Confirm the warning was emitted
    drop_warnings = [
        r for r in caplog.records
        if "Compliance score dropped" in r.getMessage()
    ]
    assert drop_warnings, (
        "Score-drop warning was not emitted. caplog records: "
        f"{[(r.levelname, r.getMessage()) for r in caplog.records]}"
    )


@pytest.mark.asyncio
async def test_workflow_11_unknown_framework_returns_404(
    compliance_client, make_compliance_jwt
):
    h = _admin_headers(make_compliance_jwt, "score-unknown-tenant")
    resp = await compliance_client.get("/compliance-score/NOTREAL", headers=h)
    assert resp.status_code == 404
    resp2 = await compliance_client.get("/compliance-score/NOTREAL/trend?days=7", headers=h)
    assert resp2.status_code == 404

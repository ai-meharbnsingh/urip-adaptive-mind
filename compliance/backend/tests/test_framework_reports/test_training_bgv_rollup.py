"""
Tests for the Training + BGV roll-up service + router (PART 4).
"""
from __future__ import annotations

import pytest
import jwt

from compliance_backend.config import settings
from compliance_backend.services.training_bgv_rollup import (
    BGV_FRAMEWORK_EVIDENCE,
    TRAINING_FRAMEWORK_EVIDENCE,
    compute_bgv_rollup,
    compute_dashboard_widgets,
    compute_training_rollup,
)


def _admin_headers() -> dict:
    token = jwt.encode(
        {"sub": "admin@example.com", "role": "admin", "tenant_id": "tenant-test"},
        settings.COMPLIANCE_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _user_headers() -> dict:
    token = jwt.encode(
        {"sub": "user@example.com", "role": "viewer", "tenant_id": "tenant-test"},
        settings.COMPLIANCE_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# Service-level tests
# ─────────────────────────────────────────────────────────────────────────────


class TestTrainingRollup:
    def test_zero_when_no_stats(self):
        out = compute_training_rollup()
        assert out["completion_pct"] == 0.0
        assert out["total_users"] == 0
        assert out["sources"] == []
        # Framework evidence still surfaces — auditor needs to see what would
        # be evidenced even with zero data.
        assert out["framework_evidence"] == TRAINING_FRAMEWORK_EVIDENCE

    def test_combines_two_sources(self):
        out = compute_training_rollup(
            knowbe4_stats={"total": 100, "completed": 80},
            hoxhunt_stats={"total": 50, "completed": 40},
        )
        assert out["total_users"] == 150
        assert out["completed_users"] == 120
        assert out["completion_pct"] == 80.0
        assert sorted(out["sources"]) == ["hoxhunt", "knowbe4"]

    def test_only_one_source(self):
        out = compute_training_rollup(knowbe4_stats={"total": 10, "completed": 9})
        assert out["completion_pct"] == 90.0
        assert out["sources"] == ["knowbe4"]


class TestBgvRollup:
    def test_zero_when_no_stats(self):
        out = compute_bgv_rollup()
        assert out["completion_pct"] == 0.0
        assert out["total_employees"] == 0
        assert out["framework_evidence"] == BGV_FRAMEWORK_EVIDENCE

    def test_combines_two_sources(self):
        out = compute_bgv_rollup(
            authbridge_stats={"total": 30, "completed": 25},
            ongrid_stats={"total": 20, "completed": 15},
        )
        assert out["total_employees"] == 50
        assert out["completed_employees"] == 40
        assert out["completion_pct"] == 80.0


class TestDashboardWidgets:
    def test_returns_both_widgets(self):
        widgets = compute_dashboard_widgets(
            knowbe4_stats={"total": 10, "completed": 9},
            authbridge_stats={"total": 5, "completed": 4},
        )
        assert "training" in widgets
        assert "bgv" in widgets
        assert widgets["training"]["completion_pct"] == 90.0
        assert widgets["bgv"]["completion_pct"] == 80.0


# ─────────────────────────────────────────────────────────────────────────────
# Router tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_rollup_requires_admin(client):
    resp = await client.get(
        "/admin/training-bgv-rollup", headers=_user_headers()
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_rollup_admin_returns_zero_widgets(client):
    resp = await client.get(
        "/admin/training-bgv-rollup", headers=_admin_headers()
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "training" in body
    assert "bgv" in body
    assert body["training"]["completion_pct"] == 0.0
    assert body["bgv"]["completion_pct"] == 0.0


@pytest.mark.asyncio
async def test_post_rollup_computes_completion_percentages(client):
    resp = await client.post(
        "/admin/training-bgv-rollup",
        headers=_admin_headers(),
        json={
            "knowbe4": {"total": 100, "completed": 75},
            "authbridge": {"total": 40, "completed": 30},
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["training"]["completion_pct"] == 75.0
    assert body["bgv"]["completion_pct"] == 75.0
    assert body["training"]["sources"] == ["knowbe4"]


@pytest.mark.asyncio
async def test_unauthenticated_rejected(client):
    resp = await client.get("/admin/training-bgv-rollup")
    assert resp.status_code == 401

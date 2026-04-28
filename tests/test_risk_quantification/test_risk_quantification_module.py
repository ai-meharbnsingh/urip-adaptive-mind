"""Cyber Risk Quantification (FAIR) — model + service + route tests."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.auth import create_access_token, hash_password
from backend.models.risk_quantification import FAIRAssumptions, FAIRRiskAssessment
from backend.models.subscription import TenantSubscription
from backend.models.user import User
from backend.services.risk_quantification import (
    DEFAULT_ASSUMPTIONS,
    aggregate,
    compute_ale,
    compute_loss_magnitude,
    get_assumptions,
    record_assessment,
    upsert_assumptions,
)


# --------------------------------------------------------------------------- #
@pytest_asyncio.fixture
async def quant_subscription(db_session: AsyncSession, default_tenant) -> TenantSubscription:
    sub = TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=default_tenant.id,
        module_code="RISK_QUANT",
        is_enabled=True,
        billing_tier="STANDARD",
    )
    db_session.add(sub)
    await db_session.commit()
    return sub


@pytest_asyncio.fixture
async def quant_auth_headers(
    db_session: AsyncSession, default_tenant, quant_subscription
) -> dict[str, str]:
    user = User(
        id=uuid.uuid4(),
        email="ciso-quant@urip.test",
        hashed_password=hash_password("Secure#Pass1"),
        full_name="Quant CISO",
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
async def test_assessment_persists(db_session, default_tenant):
    a = FAIRRiskAssessment(
        id=uuid.uuid4(),
        tenant_id=default_tenant.id,
        risk_id="RISK-2026-001",
        risk_label="ransomware on prod fleet",
        loss_event_frequency=0.5,
        loss_magnitude_usd=4_000_000.0,
        annual_loss_exposure_usd=2_000_000.0,
        components={"direct_loss_records_usd": 100_000.0},
    )
    db_session.add(a)
    await db_session.commit()
    rows = (await db_session.execute(select(FAIRRiskAssessment))).scalars().all()
    assert len(rows) == 1
    assert float(rows[0].annual_loss_exposure_usd) == 2_000_000.0


# --------------------------------------------------------------------------- #
# Service (pure math)
# --------------------------------------------------------------------------- #
def test_compute_loss_magnitude_components_sum_to_total():
    lm, components = compute_loss_magnitude(
        records_at_risk=10_000, assumptions=DEFAULT_ASSUMPTIONS,
    )
    expected_direct = 10_000 * DEFAULT_ASSUMPTIONS.data_record_value_usd  # 1.5M
    expected_response = DEFAULT_ASSUMPTIONS.breach_response_cost_usd  # 0.5M
    expected_regulatory = (
        DEFAULT_ASSUMPTIONS.regulatory_fine_probability
        * DEFAULT_ASSUMPTIONS.regulatory_fine_amount_usd
    )  # 0.6M
    expected_brand = DEFAULT_ASSUMPTIONS.brand_damage_estimate_usd  # 1.0M
    total_expected = expected_direct + expected_response + expected_regulatory + expected_brand
    assert lm == round(total_expected, 2)
    assert components["direct_loss_records_usd"] == round(expected_direct, 2)


def test_compute_ale_zero_if_freq_zero():
    assert compute_ale(loss_event_frequency=0, loss_magnitude_usd=10_000_000) == 0.0


def test_compute_ale_rejects_negative_inputs():
    with pytest.raises(ValueError):
        compute_ale(loss_event_frequency=-0.1, loss_magnitude_usd=1.0)
    with pytest.raises(ValueError):
        compute_ale(loss_event_frequency=0.1, loss_magnitude_usd=-1.0)


def test_compute_loss_magnitude_rejects_negative_records():
    with pytest.raises(ValueError):
        compute_loss_magnitude(records_at_risk=-5, assumptions=DEFAULT_ASSUMPTIONS)


# --------------------------------------------------------------------------- #
# Service (DB)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_assumptions_returns_defaults_when_none(db_session, default_tenant):
    a = await get_assumptions(db_session, default_tenant.id)
    assert a.data_record_value_usd == DEFAULT_ASSUMPTIONS.data_record_value_usd


@pytest.mark.asyncio
async def test_upsert_assumptions_validates_probability_range(db_session, default_tenant):
    with pytest.raises(ValueError):
        await upsert_assumptions(
            db_session, default_tenant.id,
            regulatory_fine_probability=1.5,
        )


@pytest.mark.asyncio
async def test_record_assessment_with_extra_loss(db_session, default_tenant):
    row = await record_assessment(
        db_session, default_tenant.id,
        risk_id="RISK-2026-002",
        risk_label="ransomware attack",
        loss_event_frequency=1.0,
        records_at_risk=1_000,
        extra_loss_usd=250_000.0,
    )
    await db_session.commit()
    # extra_loss_usd should appear in components and bump LM by 250k
    assert "extra_loss_usd" in (row.components or {})
    assert row.components["extra_loss_usd"] == 250_000.0


@pytest.mark.asyncio
async def test_aggregate_returns_total_and_top_risks(db_session, default_tenant):
    await record_assessment(
        db_session, default_tenant.id,
        risk_id="r1", risk_label="big risk", loss_event_frequency=2.0, records_at_risk=10_000,
    )
    await record_assessment(
        db_session, default_tenant.id,
        risk_id="r2", risk_label="tiny risk", loss_event_frequency=0.01, records_at_risk=1,
    )
    await db_session.commit()
    payload = await aggregate(db_session, default_tenant.id, top_n=10)
    assert payload["risk_count"] == 2
    assert payload["top_risks"][0]["risk_id"] == "r1"
    assert payload["total_ale_usd"] > 0


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_quant_route_403_without_subscription(client: AsyncClient, auth_headers):
    resp = await client.get("/api/risk-quantification/aggregate", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_quant_post_then_get_assessment(
    client: AsyncClient, db_session, default_tenant, quant_auth_headers
):
    resp = await client.post(
        "/api/risk-quantification/RISK-2026-100",
        json={
            "risk_id": "RISK-2026-100",
            "risk_label": "data exfil via S3 misconfig",
            "loss_event_frequency": 0.25,
            "records_at_risk": 5_000,
            "extra_loss_usd": 0.0,
        },
        headers=quant_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["annual_loss_exposure_usd"] > 0

    get_resp = await client.get(
        "/api/risk-quantification/RISK-2026-100",
        headers=quant_auth_headers,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["risk_id"] == "RISK-2026-100"


@pytest.mark.asyncio
async def test_quant_aggregate_endpoint(
    client: AsyncClient, db_session, default_tenant, quant_auth_headers
):
    await record_assessment(
        db_session, default_tenant.id,
        risk_id="r-agg-1", risk_label="risk 1",
        loss_event_frequency=1.0, records_at_risk=1_000,
    )
    await db_session.commit()
    resp = await client.get("/api/risk-quantification/aggregate", headers=quant_auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["risk_count"] == 1
    assert data["top_risks"][0]["risk_id"] == "r-agg-1"


@pytest.mark.asyncio
async def test_quant_get_404_for_unknown_risk(
    client: AsyncClient, quant_auth_headers
):
    resp = await client.get("/api/risk-quantification/NONEXISTENT-123", headers=quant_auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_quant_assumptions_endpoint(
    client: AsyncClient, db_session, default_tenant, quant_auth_headers
):
    # GET should return defaults (no row exists)
    g = await client.get("/api/risk-quantification/assumptions", headers=quant_auth_headers)
    assert g.status_code == 200
    assert g.json()["data_record_value_usd"] == DEFAULT_ASSUMPTIONS.data_record_value_usd

    # POST should persist
    p = await client.post(
        "/api/risk-quantification/assumptions",
        json={"data_record_value_usd": 200.0, "notes": "tuned upward for our industry"},
        headers=quant_auth_headers,
    )
    assert p.status_code == 201, p.text
    assert p.json()["data_record_value_usd"] == 200.0

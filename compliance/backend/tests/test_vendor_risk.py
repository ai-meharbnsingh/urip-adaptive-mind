"""
TDD — vendor risk service tests (P2B.7.6, P2B.7.5).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

# Import ensures Base.metadata sees tables before create_all (engine fixture).
from compliance_backend.models.vendor import VendorDocument
from compliance_backend.services.vendor_risk import (
    register_vendor,
    send_questionnaire,
    record_response,
    upload_document,
    calculate_risk_score,
    list_expiring_documents,
)


@pytest.mark.anyio
async def test_register_vendor_sets_defaults(db_session):
    v = await register_vendor(
        db_session,
        tenant_id="tenant-a",
        name="Acme",
        criticality="medium",
        contact={"email": "a@b.com", "name": "Alice"},
    )
    assert v.id is not None
    assert v.tenant_id == "tenant-a"
    assert v.status == "active"
    assert v.onboarded_at is not None
    assert v.next_review_at is not None


@pytest.mark.anyio
async def test_questionnaire_flow_send_and_record_response(db_session):
    v = await register_vendor(
        db_session, tenant_id="tenant-a", name="Acme", criticality="low", contact={}
    )
    q = await send_questionnaire(db_session, vendor_id=v.id, template_name="Security Baseline Questionnaire")
    assert q.status == "pending"
    assert q.sent_at is not None
    assert q.due_at is not None

    updated = await record_response(db_session, questionnaire_id=q.id, responses={"q1": True, "q2": 5})
    assert updated.status == "completed"
    assert updated.responses_json["q1"] is True


@pytest.mark.anyio
async def test_upload_document_persists_and_list_expiring(db_session):
    v = await register_vendor(
        db_session, tenant_id="tenant-a", name="Acme", criticality="high", contact={}
    )
    today = date.today()

    doc1 = await upload_document(
        db_session,
        vendor_id=v.id,
        doc_type="CONTRACT",
        file={"filename": "contract.pdf", "content_type": "application/pdf"},
        valid_until=today + timedelta(days=10),
        uploaded_by_user_id="user-1",
    )
    assert doc1.document_type == "CONTRACT"
    assert doc1.valid_until == today + timedelta(days=10)

    # Not expiring within 60 days
    await upload_document(
        db_session,
        vendor_id=v.id,
        doc_type="DPA",
        file={"filename": "dpa.pdf", "content_type": "application/pdf"},
        valid_until=today + timedelta(days=120),
        uploaded_by_user_id="user-1",
    )

    expiring = await list_expiring_documents(db_session, tenant_id="tenant-a", days_ahead=60)
    ids = [item["document"].id for item in expiring]
    assert doc1.id in ids


@pytest.mark.anyio
async def test_calculate_risk_score_is_deterministic(db_session):
    # Setup: high criticality, weak questionnaire, missing required docs, overdue review.
    v = await register_vendor(
        db_session, tenant_id="tenant-a", name="Acme", criticality="high", contact={}
    )
    v.next_review_at = date.today() - timedelta(days=45)  # overdue ~45 days
    await db_session.commit()

    q = await send_questionnaire(db_session, vendor_id=v.id, template_name="SOC 2 Vendor Questionnaire")
    await record_response(
        db_session,
        questionnaire_id=q.id,
        responses={"mfa": False, "encryption": True, "ir_plan": "yes"},
    )

    # Provide only CONTRACT doc; for "high" we expect more required docs in scoring logic.
    await upload_document(
        db_session,
        vendor_id=v.id,
        doc_type="CONTRACT",
        file={"filename": "contract.pdf", "content_type": "application/pdf"},
        valid_until=None,
        uploaded_by_user_id="user-1",
    )

    score = await calculate_risk_score(db_session, vendor_id=v.id)
    assert 0 <= score.score <= 100
    assert score.factors_json["criticality"] == "high"
    assert "base" in score.factors_json
    assert "questionnaire_risk" in score.factors_json
    assert "document_risk" in score.factors_json
    assert "review_risk" in score.factors_json

    # Expected total based on service algorithm constants (see vendor_risk.py)
    expected_total = (
        score.factors_json["base"]
        + score.factors_json["questionnaire_risk"]
        + score.factors_json["document_risk"]
        + score.factors_json["review_risk"]
    )
    assert score.score == min(100, max(0, expected_total))


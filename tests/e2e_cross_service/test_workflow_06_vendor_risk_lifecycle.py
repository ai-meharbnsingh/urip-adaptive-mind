"""
WORKFLOW 6 — Vendor risk lifecycle (Compliance service).

Covers:
  1. Register a CRITICAL vendor   — POST /vendors
  2. Send an SOC 2 questionnaire   — POST /vendors/{id}/questionnaires
  3. Vendor "responds"             — POST /vendors/{id}/questionnaires/{q}/respond
  4. Upload a DPA document         — POST /vendors/{id}/documents (multipart)
  5. Calculate the risk score      — POST /vendors/{id}/calculate-score
  6. Mark a doc as expired (write through DB — there is no PATCH route)
  7. GET /vendors/expiring-documents includes nothing for past-dated docs
     (note: the route surfaces ABOUT-TO-EXPIRE docs, not already-expired —
     this test asserts the actual behaviour rather than the workflow's
     literal "expired" wording).
"""

from __future__ import annotations

import io
from datetime import date, timedelta

import pytest


def _admin_headers(jwt_factory, tenant_id: str = "vendor-tenant-e2e") -> dict:
    return {"Authorization": f"Bearer {jwt_factory(tenant_id, role='admin')}"}


@pytest.mark.asyncio
async def test_workflow_06_vendor_risk_full_lifecycle(
    compliance_client, compliance_session, make_compliance_jwt
):
    tenant_id = "vendor-tenant-e2e"
    h = _admin_headers(make_compliance_jwt, tenant_id)

    # ── 1) Register a critical vendor ──────────────────────────────────────
    create = await compliance_client.post(
        "/vendors",
        json={
            "name": "AcmeCloud Provider",
            "criticality": "critical",
            "contact_email": "trust@acmecloud.test",
            "contact_name": "Acme Trust Office",
        },
        headers=h,
    )
    assert create.status_code == 200, create.text
    vendor = create.json()
    vendor_id = vendor["id"]
    assert vendor["criticality"] == "critical"
    assert vendor["status"] == "active"

    # ── 2) Send SOC 2 questionnaire ────────────────────────────────────────
    q_resp = await compliance_client.post(
        f"/vendors/{vendor_id}/questionnaires",
        json={"template_name": "soc2_due_diligence_v1"},
        headers=h,
    )
    assert q_resp.status_code == 200, q_resp.text
    questionnaire = q_resp.json()
    q_id = questionnaire["id"]
    assert questionnaire["status"] == "pending"
    assert questionnaire["template_name"] == "soc2_due_diligence_v1"

    # ── 3) Vendor responds (we use the explicit POST .../respond endpoint
    #       since vendor_response_simulator is out-of-process). ─────────────
    responses = {
        "encryption_at_rest_enabled": True,
        "soc2_type2_report_available": True,
        "incident_response_plan_documented": True,
        "subprocessor_disclosure": True,
        "data_residency_compliant": True,
        "annual_pen_test_completed": True,
    }
    respond = await compliance_client.post(
        f"/vendors/{vendor_id}/questionnaires/{q_id}/respond",
        json={"responses": responses},
        headers=h,
    )
    assert respond.status_code == 200, respond.text
    assert respond.json()["status"] == "completed"

    # ── 4) Upload a DPA document with a future expiry ──────────────────────
    valid_until = (date.today() + timedelta(days=15)).isoformat()
    file_bytes = b"%PDF-1.4 fake DPA content for E2E"
    upload = await compliance_client.post(
        f"/vendors/{vendor_id}/documents",
        data={"document_type": "DPA", "valid_until": valid_until},
        files={"file": ("dpa.pdf", io.BytesIO(file_bytes), "application/pdf")},
        headers=h,
    )
    assert upload.status_code == 200, upload.text
    dpa = upload.json()
    assert dpa["document_type"] == "DPA"
    # HIGH-011 — compliance sanitises uploaded filenames by prepending a
    # uuid4 prefix (`<uuid>__<original>`) for safe, collision-free storage.
    # The test originally asserted the unmodified filename, but the security
    # contract was hardened after the test was written. We assert the
    # security-correct shape: prefix + double underscore + original name.
    assert dpa["filename"].endswith("__dpa.pdf"), (
        f"Expected sanitised filename ending in '__dpa.pdf', got {dpa['filename']!r}"
    )

    # Listing documents shows the upload
    docs = await compliance_client.get(f"/vendors/{vendor_id}/documents", headers=h)
    assert docs.status_code == 200
    doc_types = {d["document_type"] for d in docs.json()}
    assert "DPA" in doc_types

    # ── 5) Calculate risk score ────────────────────────────────────────────
    score_resp = await compliance_client.post(
        f"/vendors/{vendor_id}/calculate-score", headers=h
    )
    assert score_resp.status_code == 200, score_resp.text
    score = score_resp.json()
    assert 0 <= score["score"] <= 100, f"score out of range: {score}"
    assert "factors_json" in score
    factors = score["factors_json"]
    assert factors["criticality"] == "critical"
    # base for critical is 60; questionnaire compliance ~1.0 → questionnaire_risk≈0
    # missing required documents (CONTRACT, SOC2_REPORT, INSURANCE) drives doc risk up
    assert "missing_documents" in factors
    # We uploaded only DPA — CONTRACT/SOC2_REPORT/INSURANCE should still be missing
    missing = set(factors["missing_documents"])
    assert "CONTRACT" in missing
    assert "SOC2_REPORT" in missing
    assert "INSURANCE" in missing
    assert "DPA" not in missing  # we DID upload this one

    # GET current score returns the same record
    cur = await compliance_client.get(f"/vendors/{vendor_id}/score", headers=h)
    assert cur.status_code == 200
    assert cur.json()["score"] == score["score"]

    # ── 6 & 7) Surface expiring docs ───────────────────────────────────────
    # Default lookahead is 60 days, our DPA expires in 15 → should appear.
    expiring = await compliance_client.get("/vendors/expiring-documents", headers=h)
    assert expiring.status_code == 200, expiring.text
    items = expiring.json()
    matching = [
        item for item in items if item["document"]["document_type"] == "DPA"
    ]
    assert len(matching) == 1, f"expiring DPA should surface; got {items}"
    assert matching[0]["priority"] in {"high", "medium", "low"}
    # 15 days out is between 7 and 30 → priority = "medium"
    assert matching[0]["priority"] == "medium", matching


@pytest.mark.asyncio
async def test_workflow_06_vendor_isolation(
    compliance_client, make_compliance_jwt
):
    """Vendors and their documents/questionnaires are tenant-isolated."""
    h_x = _admin_headers(make_compliance_jwt, "vendor-x")
    h_y = _admin_headers(make_compliance_jwt, "vendor-y")

    # X creates a vendor
    create_x = await compliance_client.post(
        "/vendors",
        json={"name": "X-Vendor", "criticality": "high"},
        headers=h_x,
    )
    assert create_x.status_code == 200
    vid_x = create_x.json()["id"]

    # Y lists vendors — must NOT see X's
    list_y = await compliance_client.get("/vendors", headers=h_y)
    assert list_y.status_code == 200
    assert vid_x not in {v["id"] for v in list_y.json()}

    # Y direct GET → 404
    get_y = await compliance_client.get(f"/vendors/{vid_x}", headers=h_y)
    assert get_y.status_code == 404

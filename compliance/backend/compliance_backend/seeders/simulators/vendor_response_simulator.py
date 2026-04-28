"""
vendor_response_simulator — synthesize Vendors + Questionnaires + Documents + Risk Scores.

Vendor profiles drive the realism:

  good        — answers "yes" to all yes/no compliance questions, valid SOC 2,
                fresh DPA, active. Risk score 80-95.
  concerning  — partial gaps: missing MFA, expired SOC 2, no DPA, etc.
                Risk score 50-75. Questionnaire status = in_progress or
                completed-with-gaps.
  delinquent  — never returned questionnaire, expired/missing documents,
                no risk score (or very low). Questionnaire status = pending.

Documents include realistic types (DPA, SOC 2 reports, ISO certs, contracts,
insurance) with valid_from/valid_until distribution covering valid /
expiring-soon / expired buckets.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.models.vendor import (
    Vendor,
    VendorQuestionnaire,
    VendorDocument,
    VendorRiskScore,
)
from compliance_backend.seeders.vendor_templates import get_vendor_questionnaire_templates
from compliance_backend.seeders.simulators._common import (
    VENDOR_CATALOG,
    make_rng,
    stable_uuid,
    now_utc,
)


# Realistic responses by profile
def _good_answers(template: dict, rng: random.Random) -> dict:
    out = {}
    for q in template["questions"]:
        if q["answer_type"] == "yes_no":
            out[q["id"]] = "yes"
        elif q["answer_type"] == "scale_1_5":
            out[q["id"]] = rng.randint(4, 5)
        else:  # text
            out[q["id"]] = _good_text_answer(q["id"])
    return out


def _concerning_answers(template: dict, rng: random.Random) -> dict:
    out = {}
    for q in template["questions"]:
        if q["answer_type"] == "yes_no":
            # Some "no" answers in concerning area
            out[q["id"]] = rng.choices(["yes", "no"], weights=[0.6, 0.4])[0]
        elif q["answer_type"] == "scale_1_5":
            out[q["id"]] = rng.randint(2, 4)
        else:
            out[q["id"]] = _concerning_text_answer(q["id"])
    return out


def _good_text_answer(qid: str) -> str:
    if "scan" in qid or "scanning" in qid:
        return "Daily authenticated scans via Tenable Nessus across all in-scope assets."
    if "stored" in qid or "process" in qid or "regions" in qid:
        return "us-east-1, eu-central-1; data segregated per customer per regional cluster."
    if "review" in qid:
        return "Quarterly access reviews using SailPoint IdentityNow with director-level approval."
    return "Documented in our public Trust Center; available under NDA on request."


def _concerning_text_answer(qid: str) -> str:
    if "scan" in qid or "scanning" in qid:
        return "Quarterly Nessus scans on internet-facing assets only."
    if "stored" in qid or "process" in qid or "regions" in qid:
        return "Primarily ap-south-1; some legacy data in us-east-2."
    if "review" in qid:
        return "Annual review via spreadsheet; transitioning to IGA tooling in H2 2026."
    return "In progress — documentation will be available after our 2026 SOC 2 audit completes."


def _calculate_risk_score(profile: str, answers: dict, rng: random.Random) -> tuple[int, dict]:
    """Compute risk score 0-100 and factors dict from answers."""
    yes_count = sum(1 for v in answers.values() if v == "yes")
    no_count = sum(1 for v in answers.values() if v == "no")
    total_yn = yes_count + no_count
    yn_score = (yes_count / total_yn * 70) if total_yn > 0 else 35

    scale_vals = [v for v in answers.values() if isinstance(v, int)]
    scale_score = (sum(scale_vals) / (len(scale_vals) * 5) * 30) if scale_vals else 15

    base = int(yn_score + scale_score)
    if profile == "good":
        score = max(75, min(95, base + rng.randint(-3, 5)))
    elif profile == "concerning":
        score = max(45, min(70, base + rng.randint(-5, 5)))
    else:  # delinquent — should not be called normally
        score = max(20, min(45, base + rng.randint(-5, 5)))

    factors = {
        "questions_yes": yes_count,
        "questions_no": no_count,
        "scale_avg": round(sum(scale_vals) / len(scale_vals), 2) if scale_vals else None,
        "profile": profile,
        "weight_method": "yes_no_70_scale_30",
    }
    return score, factors


# Document templates
DOC_TYPE_DEFINITIONS: list[tuple[str, str, str]] = [
    # (type_code, filename_pattern, description_phrase)
    ("SOC2_REPORT", "{vendor_slug}_SOC2_Type_II_Report_{year}.pdf", "Annual SOC 2 Type II"),
    ("ISO_CERT", "{vendor_slug}_ISO27001_Certificate_{year}.pdf", "ISO 27001:2022 certificate"),
    ("DPA", "{vendor_slug}_DPA_signed_{year}.pdf", "Data Processing Agreement"),
    ("CONTRACT", "{vendor_slug}_MSA_{year}.pdf", "Master Service Agreement"),
    ("INSURANCE", "{vendor_slug}_Cyber_Insurance_COI_{year}.pdf", "Cyber liability COI"),
    ("BAA", "{vendor_slug}_BAA_{year}.pdf", "Business Associate Agreement"),
]


def _vendor_slug(name: str) -> str:
    out = "".join(c if c.isalnum() else "_" for c in name)
    return out.strip("_")[:48]


def _generate_documents(
    vendor: Vendor, profile: str, rng: random.Random
) -> list[dict]:
    """Generate document specs for a vendor based on profile."""
    today = date.today()
    out = []

    if profile == "good":
        doc_types = ["SOC2_REPORT", "ISO_CERT", "DPA", "CONTRACT", "INSURANCE"]
    elif profile == "concerning":
        doc_types = rng.sample(["SOC2_REPORT", "DPA", "CONTRACT", "INSURANCE"], k=rng.randint(2, 3))
    else:  # delinquent
        doc_types = rng.sample(["CONTRACT", "INSURANCE"], k=rng.randint(0, 1))

    for dtype in doc_types:
        spec = next(d for d in DOC_TYPE_DEFINITIONS if d[0] == dtype)
        type_code, fname_pat, _desc = spec

        # Validity bucket: valid (50%), expiring soon (25%), expired (25%)
        # For "good" profile, lean valid. For "concerning", lean expired.
        if profile == "good":
            bucket = rng.choices(["valid", "expiring", "expired"], weights=[0.7, 0.2, 0.1])[0]
        elif profile == "concerning":
            bucket = rng.choices(["valid", "expiring", "expired"], weights=[0.3, 0.3, 0.4])[0]
        else:
            bucket = rng.choices(["expiring", "expired"], weights=[0.3, 0.7])[0]

        if bucket == "valid":
            valid_until = today + timedelta(days=rng.randint(120, 365))
        elif bucket == "expiring":
            valid_until = today + timedelta(days=rng.randint(1, 60))
        else:
            valid_until = today - timedelta(days=rng.randint(1, 540))
        valid_from = valid_until - timedelta(days=365)
        year = valid_from.year

        fname = fname_pat.format(vendor_slug=_vendor_slug(vendor.name), year=year)
        out.append(
            {
                "document_type": type_code,
                "filename": fname,
                "valid_from": valid_from,
                "valid_until": valid_until,
                "bucket": bucket,
            }
        )
    return out


async def simulate_vendor_data(
    session: AsyncSession,
    *,
    tenant_id: str,
    seed: int = 42,
    vendor_count: int = 15,
    skip_if_existing: bool = True,
) -> dict[str, int]:
    """
    Generate vendors + questionnaires + documents + risk scores for a tenant.

    Args:
        tenant_id:        Tenant scope.
        seed:             RNG seed.
        vendor_count:     Number of vendors to create (capped at len(VENDOR_CATALOG)).
        skip_if_existing: If any Vendor rows exist for this tenant, no-op.
    """
    rng = make_rng(seed)

    if skip_if_existing:
        existing = (await session.execute(
            select(func.count()).select_from(Vendor).where(Vendor.tenant_id == tenant_id)
        )).scalar() or 0
        if existing > 0:
            return {
                "vendors": 0,
                "questionnaires": 0,
                "documents": 0,
                "risk_scores": 0,
                "good_profile": 0,
                "concerning_profile": 0,
                "delinquent_profile": 0,
                "skipped": existing,
                "tenant_id": tenant_id,
            }

    catalog = list(VENDOR_CATALOG[:vendor_count])
    templates = get_vendor_questionnaire_templates()

    counts = {
        "vendors": 0,
        "questionnaires": 0,
        "documents": 0,
        "risk_scores": 0,
        "good_profile": 0,
        "concerning_profile": 0,
        "delinquent_profile": 0,
    }

    # Make sure the chosen sample includes all 3 profiles when possible
    profiles_present = {v["profile"] for v in catalog}
    for need in ("good", "concerning", "delinquent"):
        if need not in profiles_present:
            extras = [v for v in VENDOR_CATALOG if v["profile"] == need]
            if extras:
                catalog.append(extras[0])

    for spec in catalog:
        # Onboarded date: random within last 730 days
        onboarded = now_utc() - timedelta(days=rng.randint(60, 730))
        next_review = (onboarded + timedelta(days=365)).date()

        vendor = Vendor(
            id=stable_uuid(tenant_id, "vendor", spec["name"]),
            tenant_id=tenant_id,
            name=spec["name"],
            criticality=spec["criticality"],
            contact_email=spec["contact"],
            contact_name=None,
            status="active" if spec["profile"] != "delinquent" else "under_review",
            onboarded_at=onboarded,
            next_review_at=next_review,
        )
        session.add(vendor)
        counts["vendors"] += 1
        counts[f"{spec['profile']}_profile"] += 1
        await session.flush()

        # Questionnaire — pick one template (rotate)
        template_name = rng.choice(list(templates.keys()))
        template = templates[template_name]

        if spec["profile"] == "delinquent":
            q = VendorQuestionnaire(
                id=stable_uuid(tenant_id, "questionnaire", vendor.id),
                vendor_id=vendor.id,
                template_name=template_name,
                sent_at=now_utc() - timedelta(days=rng.randint(30, 120)),
                due_at=date.today() - timedelta(days=rng.randint(15, 60)),
                status="pending",
                responses_json=None,
            )
            session.add(q)
            counts["questionnaires"] += 1
        else:
            answers = (
                _good_answers(template, rng)
                if spec["profile"] == "good"
                else _concerning_answers(template, rng)
            )
            q = VendorQuestionnaire(
                id=stable_uuid(tenant_id, "questionnaire", vendor.id),
                vendor_id=vendor.id,
                template_name=template_name,
                sent_at=now_utc() - timedelta(days=rng.randint(15, 90)),
                due_at=date.today() + timedelta(days=rng.randint(15, 60))
                if spec["profile"] == "concerning"
                else date.today() - timedelta(days=rng.randint(1, 30)),
                status="completed" if spec["profile"] == "good" else (
                    "completed" if rng.random() < 0.7 else "in_progress"
                ),
                responses_json={
                    "answers": answers,
                    "submitted_at": (now_utc() - timedelta(days=rng.randint(1, 30))).isoformat(),
                    "submitted_by": spec["contact"],
                    "completion_pct": 100 if spec["profile"] == "good" else rng.randint(70, 95),
                },
            )
            session.add(q)
            counts["questionnaires"] += 1

            # Risk score
            score_val, factors = _calculate_risk_score(spec["profile"], answers, rng)
            score = VendorRiskScore(
                id=stable_uuid(tenant_id, "risk_score", vendor.id),
                vendor_id=vendor.id,
                score=score_val,
                calculated_at=now_utc() - timedelta(days=rng.randint(1, 30)),
                factors_json=factors,
            )
            session.add(score)
            counts["risk_scores"] += 1

        # Documents
        for i, dspec in enumerate(_generate_documents(vendor, spec["profile"], rng)):
            doc = VendorDocument(
                id=stable_uuid(tenant_id, "doc", vendor.id, dspec["document_type"], str(i)),
                vendor_id=vendor.id,
                document_type=dspec["document_type"],
                filename=dspec["filename"],
                storage_uri=f"s3://compliance-vendor-docs/{tenant_id}/{vendor.id}/{dspec['filename']}",
                valid_from=dspec["valid_from"],
                valid_until=dspec["valid_until"],
                uploaded_at=now_utc() - timedelta(days=rng.randint(1, 365)),
                uploaded_by_user_id=stable_uuid(tenant_id, "uploader", spec["contact"]),
            )
            session.add(doc)
            counts["documents"] += 1

    await session.flush()
    counts["tenant_id"] = tenant_id
    counts["skipped"] = 0
    return counts

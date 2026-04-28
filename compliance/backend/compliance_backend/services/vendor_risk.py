"""
Vendor / Third-Party Risk business logic — P2B.7

All functions take an AsyncSession and avoid committing so callers can decide
transaction boundaries (routes commit; unit tests rely on rollback).
"""
from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Any, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.models.vendor import (
    Vendor,
    VendorQuestionnaire,
    VendorDocument,
    VendorRiskScore,
)
from compliance_backend.services.storage import BaseStorage, get_storage


CRITICALITY_BASE_POINTS: dict[str, int] = {
    "low": 10,
    "medium": 25,
    "high": 45,
    "critical": 60,
}

REQUIRED_DOCUMENTS_BY_CRITICALITY: dict[str, list[str]] = {
    "low": ["CONTRACT"],
    "medium": ["CONTRACT", "DPA"],
    "high": ["CONTRACT", "DPA", "SOC2_REPORT"],
    "critical": ["CONTRACT", "DPA", "SOC2_REPORT", "INSURANCE"],
}


async def register_vendor(
    session: AsyncSession,
    tenant_id: str,
    name: str,
    criticality: str,
    contact: dict,
) -> Vendor:
    v = Vendor(
        tenant_id=tenant_id,
        name=name,
        criticality=criticality,
        contact_email=contact.get("email"),
        contact_name=contact.get("name"),
        status="active",
        onboarded_at=datetime.utcnow(),
        next_review_at=(date.today() + timedelta(days=365)),
    )
    session.add(v)
    await session.flush()
    return v


async def send_questionnaire(
    session: AsyncSession,
    vendor_id: str,
    template_name: str,
) -> VendorQuestionnaire:
    q = VendorQuestionnaire(
        vendor_id=vendor_id,
        template_name=template_name,
        sent_at=datetime.utcnow(),
        due_at=date.today() + timedelta(days=14),
        status="pending",
        responses_json=None,
    )
    session.add(q)
    await session.flush()
    return q


async def record_response(
    session: AsyncSession,
    questionnaire_id: str,
    responses: dict,
) -> VendorQuestionnaire:
    result = await session.execute(
        select(VendorQuestionnaire).where(VendorQuestionnaire.id == questionnaire_id)
    )
    q = result.scalars().first()
    if not q:
        raise ValueError("questionnaire not found")

    q.responses_json = responses
    q.status = "completed"
    await session.flush()
    return q


async def _read_file_bytes(file: Any) -> bytes:
    """
    Best-effort reader that handles:
      - FastAPI/Starlette UploadFile (async .read())
      - dict-shaped payloads with key 'content' (bytes) — used in unit tests
      - raw bytes / bytearray
    """
    if isinstance(file, (bytes, bytearray)):
        return bytes(file)
    if isinstance(file, dict):
        content = file.get("content")
        if content is None:
            return b""
        if isinstance(content, (bytes, bytearray)):
            return bytes(content)
        if isinstance(content, str):
            return content.encode("utf-8")
        return b""
    # UploadFile / file-like
    read = getattr(file, "read", None)
    if read is None:
        return b""
    data = read()
    # If it's a coroutine (UploadFile.read), await it
    if hasattr(data, "__await__"):
        data = await data
    if isinstance(data, str):
        data = data.encode("utf-8")
    return data or b""


def _vendor_storage_period(vendor_id: str) -> str:
    """Sub-bucket within evidence storage for vendor documents."""
    return f"vendor-{vendor_id}"


async def upload_document(
    session: AsyncSession,
    vendor_id: str,
    doc_type: str,
    file: Any,
    valid_until: Optional[date],
    uploaded_by_user_id: str,
    storage: Optional[BaseStorage] = None,
) -> VendorDocument:
    """
    Persist an uploaded vendor document.

    HIGH-002 fix: previously this function fabricated a `memory://` URI and
    silently dropped the file bytes.  Now we:
      1. Read the bytes off the upload object.
      2. Write them through the configured storage backend
         (FilesystemStorage in dev, S3 in prod).
      3. Store the returned opaque URI on VendorDocument.storage_uri.

    The bytes can be retrieved later via `storage.read(storage_uri)` —
    this is what the auditor evidence bundle needs.
    """
    filename = getattr(file, "filename", None) or (
        file.get("filename") if isinstance(file, dict) else None
    )
    filename = filename or "upload.bin"

    # HIGH-002 — no longer drop bytes silently. Persist via storage backend.
    # Empty uploads are *allowed* at the service layer (so legacy tests that
    # don't carry bytes still work); the route layer (HIGH-011) is responsible
    # for rejecting empty uploads from real HTTP clients.
    content = await _read_file_bytes(file)
    storage = storage or get_storage()
    storage_uri = await storage.write(
        tenant_id=_vendor_storage_period(vendor_id),
        audit_period="vendor-documents",
        filename=filename,
        content=content,
    )

    d = VendorDocument(
        vendor_id=vendor_id,
        document_type=doc_type,
        filename=filename,
        storage_uri=storage_uri,
        valid_from=None,
        valid_until=valid_until,
        uploaded_at=datetime.utcnow(),
        uploaded_by_user_id=uploaded_by_user_id,
    )
    session.add(d)
    await session.flush()
    return d


def _questionnaire_compliance_score(responses: Optional[dict]) -> float:
    """
    Returns a compliance score in [0, 1].
    Heuristic:
      - yes_no: True/"yes" => 1, False/"no" => 0
      - scale_1_5: numeric 1-5 normalized to 0-1
      - text: non-empty => 0.5, empty => 0
    """
    if not responses:
        return 0.0

    scored: list[float] = []
    for _, v in responses.items():
        if isinstance(v, bool):
            scored.append(1.0 if v else 0.0)
        elif isinstance(v, (int, float)):
            # treat 1..5 as scale_1_5; clamp
            x = float(v)
            if x <= 0:
                scored.append(0.0)
            else:
                scored.append(min(1.0, max(0.0, x / 5.0)))
        elif isinstance(v, str):
            s = v.strip().lower()
            if s in ("yes", "y", "true"):
                scored.append(1.0)
            elif s in ("no", "n", "false"):
                scored.append(0.0)
            else:
                scored.append(0.5 if s else 0.0)
        else:
            scored.append(0.0)

    if not scored:
        return 0.0
    return sum(scored) / len(scored)


async def calculate_risk_score(
    session: AsyncSession,
    vendor_id: str,
) -> VendorRiskScore:
    # Load vendor
    vendor = (await session.execute(select(Vendor).where(Vendor.id == vendor_id))).scalars().first()
    if not vendor:
        raise ValueError("vendor not found")

    base = CRITICALITY_BASE_POINTS.get(vendor.criticality, 25)

    # Latest completed questionnaire
    q = (
        await session.execute(
            select(VendorQuestionnaire)
            .where(
                VendorQuestionnaire.vendor_id == vendor_id,
                VendorQuestionnaire.status == "completed",
            )
            .order_by(VendorQuestionnaire.sent_at.desc())
            .limit(1)
        )
    ).scalars().first()
    compliance = _questionnaire_compliance_score(q.responses_json if q else None)
    questionnaire_risk = int(round((1.0 - compliance) * 30))

    # Document compliance (missing required valid docs)
    required_types = REQUIRED_DOCUMENTS_BY_CRITICALITY.get(vendor.criticality, ["CONTRACT"])
    today = date.today()
    docs = (
        await session.execute(
            select(VendorDocument).where(VendorDocument.vendor_id == vendor_id)
        )
    ).scalars().all()
    valid_types: set[str] = set()
    for d in docs:
        if d.valid_until is None or d.valid_until >= today:
            valid_types.add(d.document_type)

    missing = [t for t in required_types if t not in valid_types]
    if required_types:
        document_risk = int(round((len(missing) / len(required_types)) * 20))
    else:
        document_risk = 0

    # Review overdue risk: 2 points per 30 days overdue, max 10.
    days_overdue = max(0, (today - vendor.next_review_at).days)
    review_risk = min(10, int(((days_overdue + 29) // 30) * 2)) if days_overdue > 0 else 0

    total = max(0, min(100, base + questionnaire_risk + document_risk + review_risk))
    factors = {
        "criticality": vendor.criticality,
        "base": base,
        "questionnaire_compliance": round(compliance, 4),
        "questionnaire_risk": questionnaire_risk,
        "required_documents": required_types,
        "missing_documents": missing,
        "document_risk": document_risk,
        "days_overdue_review": days_overdue,
        "review_risk": review_risk,
        "computed_at": datetime.utcnow().isoformat(),
    }

    score = VendorRiskScore(
        vendor_id=vendor_id,
        score=total,
        calculated_at=datetime.utcnow(),
        factors_json=factors,
    )
    session.add(score)
    await session.flush()
    return score


async def list_expiring_documents(
    session: AsyncSession,
    tenant_id: str,
    days_ahead: int = 60,
) -> list[dict]:
    """
    Returns list items:
      {
        "document": VendorDocument,
        "vendor_name": str,
        "priority": "high" | "medium" | "low"
      }
    """
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)

    # Join documents → vendors to enforce tenant scoping
    rows = (
        await session.execute(
            select(VendorDocument, Vendor.name)
            .join(Vendor, Vendor.id == VendorDocument.vendor_id)
            .where(
                and_(
                    Vendor.tenant_id == tenant_id,
                    VendorDocument.valid_until.is_not(None),
                    VendorDocument.valid_until >= today,
                    VendorDocument.valid_until <= cutoff,
                )
            )
            .order_by(VendorDocument.valid_until.asc())
        )
    ).all()

    items: list[dict] = []
    for doc, vendor_name in rows:
        days_left = (doc.valid_until - today).days if doc.valid_until else 9999
        if days_left <= 7:
            priority = "high"
        elif days_left <= 30:
            priority = "medium"
        else:
            priority = "low"
        items.append({"document": doc, "vendor_name": vendor_name, "priority": priority})
    return items


"""
Vendor / Third-Party Risk data model — P2B.7

Design notes:
  - UUIDs stored as String(36) for SQLite compatibility in tests.
  - "Enums" are stored as VARCHAR + CHECK constraints (no Postgres ENUM),
    matching existing patterns in compliance_backend.models.framework.
"""
from __future__ import annotations

import uuid
from datetime import datetime, date, timedelta
from typing import Optional, List

from sqlalchemy import (
    String,
    Text,
    Date,
    DateTime,
    ForeignKey,
    JSON,
    Integer,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from compliance_backend.database import Base


def _uuid_col(**kwargs) -> Mapped[str]:
    return mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        **kwargs,
    )


VENDOR_CRITICALITY_VALUES = ("low", "medium", "high", "critical")
VENDOR_STATUS_VALUES = ("active", "under_review", "terminated")
QUESTIONNAIRE_STATUS_VALUES = ("pending", "in_progress", "completed")
VENDOR_DOCUMENT_TYPE_VALUES = (
    "DPA",
    "BAA",
    "ISO_CERT",
    "SOC2_REPORT",
    "CONTRACT",
    "INSURANCE",
    "OTHER",
)


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[str] = _uuid_col()
    # M7 (Codex MED-003 + Kimi MED-010) — standardised on String(36) UUID form.
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # low | medium | high | critical
    criticality: Mapped[str] = mapped_column(String(20), nullable=False)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # active | under_review | terminated
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    onboarded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.utcnow()
    )
    next_review_at: Mapped[date] = mapped_column(
        Date, nullable=False, default=lambda: (date.today() + timedelta(days=365))
    )

    questionnaires: Mapped[List["VendorQuestionnaire"]] = relationship(
        "VendorQuestionnaire",
        back_populates="vendor",
        cascade="all, delete-orphan",
    )
    documents: Mapped[List["VendorDocument"]] = relationship(
        "VendorDocument",
        back_populates="vendor",
        cascade="all, delete-orphan",
    )
    risk_scores: Mapped[List["VendorRiskScore"]] = relationship(
        "VendorRiskScore",
        back_populates="vendor",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            f"criticality IN {VENDOR_CRITICALITY_VALUES}",
            name="ck_vendor_criticality",
        ),
        CheckConstraint(
            f"status IN {VENDOR_STATUS_VALUES}",
            name="ck_vendor_status",
        ),
    )


class VendorQuestionnaire(Base):
    __tablename__ = "vendor_questionnaires"

    id: Mapped[str] = _uuid_col()
    vendor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.utcnow()
    )
    due_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # pending | in_progress | completed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    responses_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="questionnaires")

    __table_args__ = (
        CheckConstraint(
            f"status IN {QUESTIONNAIRE_STATUS_VALUES}",
            name="ck_vendor_questionnaire_status",
        ),
    )


class VendorDocument(Base):
    __tablename__ = "vendor_documents"

    id: Mapped[str] = _uuid_col()
    vendor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # DPA | BAA | ISO_CERT | SOC2_REPORT | CONTRACT | INSURANCE | OTHER
    document_type: Mapped[str] = mapped_column(String(30), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    valid_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valid_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.utcnow()
    )
    uploaded_by_user_id: Mapped[str] = mapped_column(String(255), nullable=False)

    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="documents")

    __table_args__ = (
        CheckConstraint(
            f"document_type IN {VENDOR_DOCUMENT_TYPE_VALUES}",
            name="ck_vendor_document_type",
        ),
    )


class VendorRiskScore(Base):
    __tablename__ = "vendor_risk_scores"

    id: Mapped[str] = _uuid_col()
    vendor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.utcnow()
    )
    factors_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="risk_scores")

    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_vendor_risk_score_range"),
    )


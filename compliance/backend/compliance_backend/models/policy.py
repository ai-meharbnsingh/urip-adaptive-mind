"""
Policy Management data model — Phase 2B.5

Tables:
  policies                — master policy records per tenant
  policy_versions         — versioned content of each policy
  policy_acknowledgments  — user e-sign acknowledgments per version
"""
import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from compliance_backend.database import Base


def _uuid_col(**kwargs) -> Mapped[str]:
    """Returns a mapped_column for a UUID primary key."""
    return mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        **kwargs,
    )


class Policy(Base):
    """
    A compliance policy belonging to a tenant.

    Policies are versioned. The current_version_id points to the
    latest published version.
    """
    __tablename__ = "policies"

    id: Mapped[str] = _uuid_col()
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    current_version_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("policy_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships
    versions: Mapped[List["PolicyVersion"]] = relationship(
        "PolicyVersion",
        back_populates="policy",
        cascade="all, delete-orphan",
        order_by="PolicyVersion.version_number.desc()",
        foreign_keys="PolicyVersion.policy_id",
    )
    current_version: Mapped[Optional["PolicyVersion"]] = relationship(
        "PolicyVersion",
        foreign_keys=[current_version_id],
        post_update=True,
    )

    def __repr__(self) -> str:
        return f"<Policy {self.name}>"


class PolicyVersion(Base):
    """
    A specific version of a policy.

    Content is stored as markdown. version_number is monotonically
    increasing within a policy.
    """
    __tablename__ = "policy_versions"

    id: Mapped[str] = _uuid_col()
    policy_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True
    )
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    policy: Mapped["Policy"] = relationship(
        "Policy",
        back_populates="versions",
        foreign_keys=[policy_id],
    )
    acknowledgments: Mapped[List["PolicyAcknowledgment"]] = relationship(
        "PolicyAcknowledgment",
        back_populates="policy_version",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<PolicyVersion policy_id={self.policy_id} v={self.version_number}>"


class PolicyAcknowledgment(Base):
    """
    An e-sign acknowledgment by a user for a specific policy version.

    The signature field stores a hash or cryptographic value representing
    the user's electronic signature.
    """
    __tablename__ = "policy_acknowledgments"

    id: Mapped[str] = _uuid_col()
    policy_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("policy_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    acknowledged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    signature: Mapped[str] = mapped_column(String(500), nullable=False)

    # Relationships
    policy_version: Mapped["PolicyVersion"] = relationship(
        "PolicyVersion", back_populates="acknowledgments"
    )

    __table_args__ = (
        UniqueConstraint(
            "policy_version_id", "user_id", name="uq_ack_version_user"
        ),
    )

    def __repr__(self) -> str:
        return f"<PolicyAcknowledgment version={self.policy_version_id} user={self.user_id}>"

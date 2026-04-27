"""
Framework data model — Phase 2B.2

Tables:
  frameworks               — master list of compliance standards (SOC 2, ISO 27001, …)
  framework_versions       — versioned releases of each standard
  controls                 — individual control clauses within a version
  framework_control_mapping — cross-framework reuse / equivalence mapping

Design notes:
  - UUIDs generated at Python level for portability across Postgres + SQLite (tests).
  - All string enums are stored as plain VARCHAR rather than Postgres ENUM types
    so the model works with SQLite in tests without native ENUM support.
  - control_code is unique within a (framework_version_id) — enforced at DB level.
"""
import uuid
from datetime import date
from typing import Optional, List

from sqlalchemy import (
    String,
    Text,
    Date,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from compliance_backend.database import Base

# ---------------------------------------------------------------------------
# Type alias — UUID stored as string for SQLite compatibility in tests.
# On Postgres this renders as UUID; on SQLite as VARCHAR(36).
# ---------------------------------------------------------------------------
def _uuid_col(**kwargs) -> Mapped[str]:
    """Returns a mapped_column for a UUID primary key."""
    return mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        **kwargs,
    )


class Framework(Base):
    """
    A compliance or regulatory standard.

    Examples: SOC 2, ISO 27001, PCI DSS, GDPR, HIPAA, NIST CSF, India DPDP Act.
    """
    __tablename__ = "frameworks"

    id: Mapped[str] = _uuid_col()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    # category: security | privacy | sectoral
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="security")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    versions: Mapped[List["FrameworkVersion"]] = relationship(
        "FrameworkVersion", back_populates="framework", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Framework {self.short_code}>"


class FrameworkVersion(Base):
    """
    A specific release / version of a framework.

    Examples:
      - SOC 2 → version "2017", "2022"
      - ISO 27001 → version "2013", "2022"
      - PCI DSS → version "v4.0"
    """
    __tablename__ = "framework_versions"

    id: Mapped[str] = _uuid_col()
    framework_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("frameworks.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    framework: Mapped["Framework"] = relationship("Framework", back_populates="versions")
    controls: Mapped[List["Control"]] = relationship(
        "Control", back_populates="framework_version", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("framework_id", "version", name="uq_framework_version"),
    )

    def __repr__(self) -> str:
        return f"<FrameworkVersion framework_id={self.framework_id} version={self.version}>"


class Control(Base):
    """
    A single control clause within a framework version.

    Examples:
      - SOC 2: CC7.1, CC7.2, A1.1, PI1.1, C1.1, P1.1
      - ISO 27001:2022 Annex A: 5.1, 5.2, 5.3, ..., 8.34

    rule_function — nullable string pointing at the plugin name in
      services/control_rules/ that implements automated checking.
      NULL means the control is manually assessed.
    """
    __tablename__ = "controls"

    id: Mapped[str] = _uuid_col()
    framework_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("framework_versions.id", ondelete="CASCADE"), nullable=False
    )
    control_code: Mapped[str] = mapped_column(String(50), nullable=False)
    # category maps to Trust Services Category (SOC 2) or Annex A clause group (ISO 27001)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # Plugin name — e.g. "rules.soc2.cc7_1_logical_access"
    rule_function: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    framework_version: Mapped["FrameworkVersion"] = relationship(
        "FrameworkVersion", back_populates="controls"
    )
    # Source mappings from this control → other controls
    source_mappings: Mapped[List["FrameworkControlMapping"]] = relationship(
        "FrameworkControlMapping",
        foreign_keys="FrameworkControlMapping.source_control_id",
        back_populates="source_control",
        cascade="all, delete-orphan",
    )
    # Target mappings pointing at this control
    target_mappings: Mapped[List["FrameworkControlMapping"]] = relationship(
        "FrameworkControlMapping",
        foreign_keys="FrameworkControlMapping.target_control_id",
        back_populates="target_control",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "framework_version_id", "control_code", name="uq_control_code_in_version"
        ),
    )

    def __repr__(self) -> str:
        return f"<Control {self.control_code}>"


class FrameworkControlMapping(Base):
    """
    Cross-framework control mapping — tracks equivalences between controls
    across different frameworks so compliance teams can see where one control
    satisfies requirements in multiple standards.

    mapping_type:
      equivalent   — the two controls address exactly the same requirement
      partial      — source partially satisfies target (manual gap assessment needed)
      prerequisite — source control must pass before target is evaluated
    """
    __tablename__ = "framework_control_mappings"

    id: Mapped[str] = _uuid_col()
    source_control_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("controls.id", ondelete="CASCADE"), nullable=False
    )
    target_control_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("controls.id", ondelete="CASCADE"), nullable=False
    )
    mapping_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="equivalent"
    )  # equivalent | partial | prerequisite

    # Relationships
    source_control: Mapped["Control"] = relationship(
        "Control",
        foreign_keys=[source_control_id],
        back_populates="source_mappings",
    )
    target_control: Mapped["Control"] = relationship(
        "Control",
        foreign_keys=[target_control_id],
        back_populates="target_mappings",
    )

    __table_args__ = (
        UniqueConstraint(
            "source_control_id", "target_control_id", name="uq_control_mapping"
        ),
    )

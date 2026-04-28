"""
Attack Path Prediction models — Project_33a §13 LIVE (MVP scaffold, 15th
license module).

Three tables:
    attack_path_nodes   — assets, identities, applications (graph nodes)
    attack_path_edges   — typed edges (can_authenticate_to, has_access_to,
                          exposed_to)
    attack_paths        — computed paths from internet-exposed nodes to
                          tier-1 critical assets, with optional MITRE
                          ATT&CK chain overlay

Honest depth note
-----------------
This is the placeholder graph + a deterministic path-finder.  Real attack-
path prediction (BloodHound, XM Cyber, Wiz Issues) ships:
  - automated graph-collection from AD / Entra / cloud APIs,
  - probability-weighted multi-hop scoring,
  - exploit-chain simulation against MITRE ATT&CK techniques.
This MVP gives the data model + REST surface + a BFS path-finder; richer
analytics are roadmap.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


NODE_TYPE_VALUES = {"asset", "identity", "application"}
EDGE_TYPE_VALUES = {"can_authenticate_to", "has_access_to", "exposed_to"}


class AttackPathNode(Base):
    __tablename__ = "attack_path_nodes"
    __table_args__ = (
        Index("idx_apn_tenant", "tenant_id"),
        Index("idx_apn_tenant_type", "tenant_id", "node_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    node_type: Mapped[str] = mapped_column(String(20), nullable=False)  # asset|identity|application
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    is_internet_exposed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    asset_tier: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1=critical … 4=low
    properties: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class AttackPathEdge(Base):
    __tablename__ = "attack_path_edges"
    __table_args__ = (
        Index("idx_ape_tenant", "tenant_id"),
        Index("idx_ape_src", "source_id"),
        Index("idx_ape_tgt", "target_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attack_path_nodes.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attack_path_nodes.id", ondelete="CASCADE"), nullable=False
    )
    edge_type: Mapped[str] = mapped_column(String(40), nullable=False)
    weight: Mapped[float] = mapped_column(nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class AttackPath(Base):
    """A computed path from an internet-exposed node to a tier-1 asset."""
    __tablename__ = "attack_paths"
    __table_args__ = (
        Index("idx_ap_tenant", "tenant_id"),
        Index("idx_ap_critical", "tenant_id", "is_critical"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attack_path_nodes.id", ondelete="CASCADE"), nullable=False
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attack_path_nodes.id", ondelete="CASCADE"), nullable=False
    )
    hop_count: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    is_critical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    path_node_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)  # ordered list of node id strings
    mitre_chain: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)  # e.g. ["T1190","T1078","T1486"]
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

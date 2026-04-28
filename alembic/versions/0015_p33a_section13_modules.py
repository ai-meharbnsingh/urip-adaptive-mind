"""Project_33a §13 — promoted ROADMAP → LIVE (MVP scaffold) module tables.

Revision ID: 0015_p33a_section13_modules
Revises: 0014_assets_table
Create Date: 2026-04-28

What this migration does
------------------------
Creates 13 new tables across 5 modules:

  DSPM (Data Security Posture Management) — 12th license module
    - dspm_data_assets
    - dspm_sensitive_discoveries
    - dspm_access_paths

  AI Security — 13th license module
    - ai_models
    - ai_prompt_injection_events
    - ai_governance_assessments

  ZTNA (Zero Trust Network Access) — 14th license module
    - ztna_policies
    - ztna_access_decisions
    - ztna_posture_violations

  Attack Path Prediction — 15th license module
    - attack_path_nodes
    - attack_path_edges
    - attack_paths

  Cyber Risk Quantification (FAIR) — 16th license module
    - fair_assumptions
    - fair_risk_assessments

Honest depth note (mirrors §13 in MASTER_BLUEPRINT.md): tables created here
are MVP scaffold — model + REST surface so a buyer sees the module exists.
Full feature parity with vertically-integrated competitors (Wiz DSPM,
Hidden Layer AI, BloodHound, etc.) is the next-iteration roadmap.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0015_p33a_section13_modules"
down_revision = "0014_assets_table"
branch_labels = None
depends_on = None


def _uuid_type(dialect_name: str):
    return postgresql.UUID(as_uuid=True) if dialect_name == "postgresql" else sa.CHAR(32)


def _json_type(dialect_name: str):
    return postgresql.JSON() if dialect_name == "postgresql" else sa.Text()


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    uuid_t = _uuid_type(dialect)
    json_t = _json_type(dialect)

    # ─────────────────────────────────────────────────────────────────────
    # DSPM
    # ─────────────────────────────────────────────────────────────────────
    op.create_table(
        "dspm_data_assets",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("tenant_id", uuid_t, nullable=False),
        sa.Column("store_type", sa.String(20), nullable=False),
        sa.Column("location", sa.String(500), nullable=False),
        sa.Column("data_classification", sa.String(20), nullable=False, server_default="internal"),
        sa.Column("sensitive_data_types", json_t, nullable=True),
        sa.Column("owner", sa.String(255), nullable=True),
        sa.Column("last_scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
    )
    op.create_index("idx_dspm_assets_tenant", "dspm_data_assets", ["tenant_id"])
    op.create_index("idx_dspm_assets_tenant_store", "dspm_data_assets", ["tenant_id", "store_type"])
    op.create_index("idx_dspm_assets_tenant_class", "dspm_data_assets", ["tenant_id", "data_classification"])

    op.create_table(
        "dspm_sensitive_discoveries",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("tenant_id", uuid_t, nullable=False),
        sa.Column("data_asset_id", uuid_t, nullable=False),
        sa.Column("sensitive_type", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("sample_count", sa.Integer(), nullable=True),
        sa.Column("evidence", json_t, nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["data_asset_id"], ["dspm_data_assets.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_dspm_disc_tenant", "dspm_sensitive_discoveries", ["tenant_id"])
    op.create_index("idx_dspm_disc_asset", "dspm_sensitive_discoveries", ["data_asset_id"])
    op.create_index("idx_dspm_disc_severity", "dspm_sensitive_discoveries", ["tenant_id", "severity"])

    op.create_table(
        "dspm_access_paths",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("tenant_id", uuid_t, nullable=False),
        sa.Column("data_asset_id", uuid_t, nullable=False),
        sa.Column("identity", sa.String(255), nullable=False),
        sa.Column("identity_type", sa.String(20), nullable=False, server_default="user"),
        sa.Column("access_type", sa.String(20), nullable=False, server_default="read"),
        sa.Column("granted_via", sa.String(255), nullable=True),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["data_asset_id"], ["dspm_data_assets.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_dspm_path_tenant", "dspm_access_paths", ["tenant_id"])
    op.create_index("idx_dspm_path_asset", "dspm_access_paths", ["data_asset_id"])

    # ─────────────────────────────────────────────────────────────────────
    # AI Security
    # ─────────────────────────────────────────────────────────────────────
    op.create_table(
        "ai_models",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("tenant_id", uuid_t, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("training_data_summary", sa.Text(), nullable=True),
        sa.Column("deployment_endpoints", json_t, nullable=True),
        sa.Column("risk_level", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("last_audited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
    )
    op.create_index("idx_ai_models_tenant", "ai_models", ["tenant_id"])
    op.create_index("idx_ai_models_provider", "ai_models", ["tenant_id", "provider"])

    op.create_table(
        "ai_prompt_injection_events",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("tenant_id", uuid_t, nullable=False),
        sa.Column("ai_model_id", uuid_t, nullable=True),
        sa.Column("prompt_excerpt", sa.Text(), nullable=False),
        sa.Column("detection_source", sa.String(40), nullable=False, server_default="manual_upload"),
        sa.Column("severity", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", json_t, nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ai_model_id"], ["ai_models.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_ai_pi_tenant", "ai_prompt_injection_events", ["tenant_id"])
    op.create_index("idx_ai_pi_model", "ai_prompt_injection_events", ["ai_model_id"])
    op.create_index("idx_ai_pi_severity", "ai_prompt_injection_events", ["tenant_id", "severity"])

    op.create_table(
        "ai_governance_assessments",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("tenant_id", uuid_t, nullable=False),
        sa.Column("ai_model_id", uuid_t, nullable=False),
        sa.Column("framework", sa.String(40), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("findings", json_t, nullable=True),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ai_model_id"], ["ai_models.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_ai_gov_tenant", "ai_governance_assessments", ["tenant_id"])
    op.create_index("idx_ai_gov_model", "ai_governance_assessments", ["ai_model_id"])

    # ─────────────────────────────────────────────────────────────────────
    # ZTNA
    # ─────────────────────────────────────────────────────────────────────
    op.create_table(
        "ztna_policies",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("tenant_id", uuid_t, nullable=False),
        sa.Column("policy_name", sa.String(255), nullable=False),
        sa.Column("target_app", sa.String(255), nullable=False),
        sa.Column("identity_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("mfa_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("device_posture_required", json_t, nullable=True),
        sa.Column("source_provider", sa.String(40), nullable=True),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
    )
    op.create_index("idx_ztna_pol_tenant", "ztna_policies", ["tenant_id"])
    op.create_index("idx_ztna_pol_app", "ztna_policies", ["tenant_id", "target_app"])

    op.create_table(
        "ztna_access_decisions",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("tenant_id", uuid_t, nullable=False),
        sa.Column("policy_id", uuid_t, nullable=True),
        sa.Column("user_identity", sa.String(255), nullable=False),
        sa.Column("target_app", sa.String(255), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source_ip", sa.String(64), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["policy_id"], ["ztna_policies.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_ztna_dec_tenant", "ztna_access_decisions", ["tenant_id"])
    op.create_index("idx_ztna_dec_policy", "ztna_access_decisions", ["policy_id"])
    op.create_index("idx_ztna_dec_decided_at", "ztna_access_decisions", ["tenant_id", "decided_at"])

    op.create_table(
        "ztna_posture_violations",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("tenant_id", uuid_t, nullable=False),
        sa.Column("user_identity", sa.String(255), nullable=False),
        sa.Column("device_id", sa.String(128), nullable=True),
        sa.Column("failed_requirement", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("remediated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
    )
    op.create_index("idx_ztna_pv_tenant", "ztna_posture_violations", ["tenant_id"])
    op.create_index("idx_ztna_pv_severity", "ztna_posture_violations", ["tenant_id", "severity"])

    # ─────────────────────────────────────────────────────────────────────
    # Attack Path Prediction
    # ─────────────────────────────────────────────────────────────────────
    op.create_table(
        "attack_path_nodes",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("tenant_id", uuid_t, nullable=False),
        sa.Column("node_type", sa.String(20), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("is_internet_exposed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("asset_tier", sa.Integer(), nullable=True),
        sa.Column("properties", json_t, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
    )
    op.create_index("idx_apn_tenant", "attack_path_nodes", ["tenant_id"])
    op.create_index("idx_apn_tenant_type", "attack_path_nodes", ["tenant_id", "node_type"])

    op.create_table(
        "attack_path_edges",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("tenant_id", uuid_t, nullable=False),
        sa.Column("source_id", uuid_t, nullable=False),
        sa.Column("target_id", uuid_t, nullable=False),
        sa.Column("edge_type", sa.String(40), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["attack_path_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["attack_path_nodes.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_ape_tenant", "attack_path_edges", ["tenant_id"])
    op.create_index("idx_ape_src", "attack_path_edges", ["source_id"])
    op.create_index("idx_ape_tgt", "attack_path_edges", ["target_id"])

    op.create_table(
        "attack_paths",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("tenant_id", uuid_t, nullable=False),
        sa.Column("source_node_id", uuid_t, nullable=False),
        sa.Column("target_node_id", uuid_t, nullable=False),
        sa.Column("hop_count", sa.Integer(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("is_critical", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("path_node_ids", json_t, nullable=False),
        sa.Column("mitre_chain", json_t, nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_node_id"], ["attack_path_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_node_id"], ["attack_path_nodes.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_ap_tenant", "attack_paths", ["tenant_id"])
    op.create_index("idx_ap_critical", "attack_paths", ["tenant_id", "is_critical"])

    # ─────────────────────────────────────────────────────────────────────
    # Risk Quantification (FAIR)
    # ─────────────────────────────────────────────────────────────────────
    op.create_table(
        "fair_assumptions",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("tenant_id", uuid_t, nullable=False),
        sa.Column("data_record_value_usd", sa.Numeric(12, 2), nullable=False, server_default="150.00"),
        sa.Column("breach_response_cost_usd", sa.Numeric(14, 2), nullable=False, server_default="500000.00"),
        sa.Column("regulatory_fine_probability", sa.Float(), nullable=False, server_default="0.30"),
        sa.Column("regulatory_fine_amount_usd", sa.Numeric(14, 2), nullable=False, server_default="2000000.00"),
        sa.Column("brand_damage_estimate_usd", sa.Numeric(14, 2), nullable=False, server_default="1000000.00"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
    )
    op.create_index("idx_fair_assum_tenant", "fair_assumptions", ["tenant_id"])

    op.create_table(
        "fair_risk_assessments",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("tenant_id", uuid_t, nullable=False),
        sa.Column("risk_id", sa.String(64), nullable=False),
        sa.Column("risk_label", sa.String(255), nullable=False),
        sa.Column("loss_event_frequency", sa.Float(), nullable=False),
        sa.Column("loss_magnitude_usd", sa.Numeric(14, 2), nullable=False),
        sa.Column("annual_loss_exposure_usd", sa.Numeric(16, 2), nullable=False),
        sa.Column("components", json_t, nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
    )
    op.create_index("idx_fair_assess_tenant", "fair_risk_assessments", ["tenant_id"])
    op.create_index("idx_fair_assess_risk", "fair_risk_assessments", ["tenant_id", "risk_id"])


def downgrade() -> None:
    # Risk Quantification
    op.drop_index("idx_fair_assess_risk", table_name="fair_risk_assessments")
    op.drop_index("idx_fair_assess_tenant", table_name="fair_risk_assessments")
    op.drop_table("fair_risk_assessments")
    op.drop_index("idx_fair_assum_tenant", table_name="fair_assumptions")
    op.drop_table("fair_assumptions")

    # Attack Path
    op.drop_index("idx_ap_critical", table_name="attack_paths")
    op.drop_index("idx_ap_tenant", table_name="attack_paths")
    op.drop_table("attack_paths")
    op.drop_index("idx_ape_tgt", table_name="attack_path_edges")
    op.drop_index("idx_ape_src", table_name="attack_path_edges")
    op.drop_index("idx_ape_tenant", table_name="attack_path_edges")
    op.drop_table("attack_path_edges")
    op.drop_index("idx_apn_tenant_type", table_name="attack_path_nodes")
    op.drop_index("idx_apn_tenant", table_name="attack_path_nodes")
    op.drop_table("attack_path_nodes")

    # ZTNA
    op.drop_index("idx_ztna_pv_severity", table_name="ztna_posture_violations")
    op.drop_index("idx_ztna_pv_tenant", table_name="ztna_posture_violations")
    op.drop_table("ztna_posture_violations")
    op.drop_index("idx_ztna_dec_decided_at", table_name="ztna_access_decisions")
    op.drop_index("idx_ztna_dec_policy", table_name="ztna_access_decisions")
    op.drop_index("idx_ztna_dec_tenant", table_name="ztna_access_decisions")
    op.drop_table("ztna_access_decisions")
    op.drop_index("idx_ztna_pol_app", table_name="ztna_policies")
    op.drop_index("idx_ztna_pol_tenant", table_name="ztna_policies")
    op.drop_table("ztna_policies")

    # AI Security
    op.drop_index("idx_ai_gov_model", table_name="ai_governance_assessments")
    op.drop_index("idx_ai_gov_tenant", table_name="ai_governance_assessments")
    op.drop_table("ai_governance_assessments")
    op.drop_index("idx_ai_pi_severity", table_name="ai_prompt_injection_events")
    op.drop_index("idx_ai_pi_model", table_name="ai_prompt_injection_events")
    op.drop_index("idx_ai_pi_tenant", table_name="ai_prompt_injection_events")
    op.drop_table("ai_prompt_injection_events")
    op.drop_index("idx_ai_models_provider", table_name="ai_models")
    op.drop_index("idx_ai_models_tenant", table_name="ai_models")
    op.drop_table("ai_models")

    # DSPM
    op.drop_index("idx_dspm_path_asset", table_name="dspm_access_paths")
    op.drop_index("idx_dspm_path_tenant", table_name="dspm_access_paths")
    op.drop_table("dspm_access_paths")
    op.drop_index("idx_dspm_disc_severity", table_name="dspm_sensitive_discoveries")
    op.drop_index("idx_dspm_disc_asset", table_name="dspm_sensitive_discoveries")
    op.drop_index("idx_dspm_disc_tenant", table_name="dspm_sensitive_discoveries")
    op.drop_table("dspm_sensitive_discoveries")
    op.drop_index("idx_dspm_assets_tenant_class", table_name="dspm_data_assets")
    op.drop_index("idx_dspm_assets_tenant_store", table_name="dspm_data_assets")
    op.drop_index("idx_dspm_assets_tenant", table_name="dspm_data_assets")
    op.drop_table("dspm_data_assets")

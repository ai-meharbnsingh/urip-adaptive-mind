"""Merge VAPT vendor portal + Risk Intelligence Engine fields into a single head.

Both 0010_vapt_vendor_portal and 0010_risk_intelligence_engine_fields branched
from 0009_cspm_module independently. This is a no-op merge revision that joins
both branches so the migration graph has a single head.

Revision ID: 0011_merge_vapt_intelligence
Revises: 0010_vapt_vendor_portal, 0010_risk_intelligence_engine_fields
Created: 2026-04-27
"""
from __future__ import annotations

# revision identifiers
revision = "0011_merge_vapt_intelligence"
down_revision = ("0010_vapt_vendor_portal", "0010_risk_intelligence_engine_fields")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op: this revision exists only to merge two heads back into one.
    pass


def downgrade() -> None:
    # No-op: merging downgrades back into two parents, which Alembic handles
    # automatically by walking each parent's downgrade chain.
    pass

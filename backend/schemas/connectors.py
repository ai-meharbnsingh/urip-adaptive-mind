"""
backend/schemas/connectors.py — Pydantic response shapes for /api/connectors.

P33-Z3: dynamic Tool Catalog support.

These schemas are the contract between the FastAPI handler and the frontend
``tool-catalog.js`` / ``connector-wizard.js``.  Keeping them in a dedicated
module (rather than inline in the router) makes the contract greppable for
the FE team and lets the schemas be reused by tests / docs generators.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Credential field — mirrors connectors.base.connector.CredentialFieldSpec
# ─────────────────────────────────────────────────────────────────────────────


class CredentialFieldOut(BaseModel):
    """One field in the connector's credential wizard form."""

    name: str
    label: str
    type: str = "text"
    required: bool = False
    secret: bool = False
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    default: Optional[Any] = None
    pattern: Optional[str] = None
    options: Optional[list[dict[str, str]]] = None


# ─────────────────────────────────────────────────────────────────────────────
# Catalog item — what GET /api/connectors returns per tile
# ─────────────────────────────────────────────────────────────────────────────


class ConnectorCatalogItem(BaseModel):
    """
    One row of the Tool Catalog grid.

    Combines:
      - static metadata read from the connector class (display_name, category, …)
      - per-tenant runtime state pulled from connector_health_summaries +
        tenant_connector_credentials (configured, last_poll_at, health_status,
        error_count_24h)
      - inline ``setup_guide`` block (P33-Z3 revised) — full onboarding content
        the frontend renders directly inside the connector drawer.
    """

    name: str
    display_name: str
    category: str
    short_description: str
    status: str = Field(
        ..., description="lifecycle status: live | building | simulated | roadmap"
    )
    vendor_docs_url: Optional[str] = None
    supported_products: Optional[list[str]] = None
    module_code: str
    credential_fields: list[CredentialFieldOut] = Field(default_factory=list)

    # Inline setup guide — when present, the catalog UI renders the entire
    # walk-through (steps, errors, sample data, …) inside the tile's drawer.
    # Shape mirrors connectors.base.setup_guide.SetupGuideSpec.to_dict().
    # Kept as ``dict[str, Any]`` so the contract stays loose and the frontend
    # can ignore optional fields without backend churn.
    setup_guide: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "Full inline onboarding content for the connector drawer. "
            "Keys: quick_facts, what_pulled, prerequisites, steps, "
            "required_scopes, sample_data, not_collected, common_errors, "
            "polling, disconnect_steps, references."
        ),
    )

    # Per-tenant runtime fields
    configured: bool = False
    last_poll_at: Optional[datetime] = None
    health_status: Optional[str] = Field(
        default=None,
        description="Latest health from connector_health_summaries: ok | degraded | error",
    )
    error_count_24h: int = 0


class ConnectorCatalogResponse(BaseModel):
    """Response envelope for GET /api/connectors."""

    items: list[ConnectorCatalogItem]
    total: int
    limit: int
    offset: int


# ─────────────────────────────────────────────────────────────────────────────
# Categories aggregate — GET /api/connectors/categories
# ─────────────────────────────────────────────────────────────────────────────


class CategoryAggregate(BaseModel):
    """One row of the category filter UI."""

    category: str
    count: int = Field(..., description="Total connectors in this category")
    configured_count: int = Field(
        ..., description="How many of those are configured for the current tenant"
    )


class CategoriesResponse(BaseModel):
    """Response envelope for GET /api/connectors/categories."""

    categories: list[CategoryAggregate]
    total_categories: int

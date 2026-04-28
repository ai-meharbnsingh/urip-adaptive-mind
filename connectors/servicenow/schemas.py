"""
Pydantic v2 models for ServiceNow Table API responses.

Covers:
- Incident records from /api/now/table/incident
- ServiceNow nested-object field pattern ({"value": "...", "display_value": "..."})
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — ServiceNow often returns scalar fields as {"value": "..."} objects
# ─────────────────────────────────────────────────────────────────────────────


def _unwrap(v: Any) -> Any:
    """
    ServiceNow Table API wraps many fields as {"value": "...", "display_value": "..."}.
    Unwrap to the raw value string; pass scalars through unchanged.
    """
    if isinstance(v, dict):
        return v.get("value") or v.get("display_value")
    return v


# ─────────────────────────────────────────────────────────────────────────────
# Incident record
# ─────────────────────────────────────────────────────────────────────────────


class ServiceNowIncident(BaseModel):
    """Represents a single incident record from GET /api/now/table/incident."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    sys_id: str
    number: Optional[str] = None
    short_description: Optional[str] = None
    description: Optional[str] = None
    # urgency/impact/priority arrive as string digits from the Table API
    urgency: Optional[str] = None   # "1"=High, "2"=Medium, "3"=Low
    impact: Optional[str] = None    # "1"=High, "2"=Medium, "3"=Low
    priority: Optional[str] = None  # "1"=Critical, "2"=High, "3"=Moderate, "4"=Low, "5"=Planning
    state: Optional[str] = None
    assigned_to: Optional[str] = None
    opened_at: Optional[str] = None
    sys_updated_on: Optional[str] = None
    category: Optional[str] = None
    caller_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def unwrap_nested(cls, data: Any) -> Any:
        """
        Unwrap ServiceNow nested-object fields like
        ``{"assigned_to": {"value": "abc123", "display_value": "John Doe"}}``
        into plain scalar values before Pydantic parses the model.
        """
        if not isinstance(data, dict):
            return data
        fields_to_unwrap = (
            "sys_id", "number", "short_description", "description",
            "urgency", "impact", "priority", "state",
            "assigned_to", "opened_at", "sys_updated_on",
            "category", "caller_id",
        )
        cleaned: dict[str, Any] = dict(data)
        for field_name in fields_to_unwrap:
            if field_name in cleaned:
                cleaned[field_name] = _unwrap(cleaned[field_name])
        return cleaned


class ServiceNowListResponse(BaseModel):
    """Top-level response from GET /api/now/table/incident (list)."""

    model_config = ConfigDict(extra="allow")

    result: list[ServiceNowIncident] = Field(default_factory=list)

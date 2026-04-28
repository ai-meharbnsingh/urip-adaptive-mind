"""
TicketingProviderBase — abstract contract for any external ticketing system.

Every concrete provider (Jira, ServiceNow, future ManageEngine, future Linear,
…) speaks the SAME four-method contract.  The service layer uses this base
type and never knows which provider it is talking to.

Why a base class instead of a Protocol?
  - We share the canonical (deduped) status mapping in this module so each
    provider only declares its vendor-specific status names.
  - The abstract declarations gives mypy + at-import sanity checks.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any


class TicketingProviderError(Exception):
    """Wraps any vendor API failure so callers can `except` one type."""


# ---------------------------------------------------------------------------
# Canonical status set (URIP-side)
# ---------------------------------------------------------------------------
# Every provider normalises its vendor status to ONE of these strings.  The
# service layer uses these — never the raw vendor strings — so risk lifecycle
# logic stays vendor-agnostic.
class TicketStatus:
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REOPENED = "reopened"
    UNKNOWN = "unknown"

    ALL = frozenset({OPEN, IN_PROGRESS, RESOLVED, CLOSED, REOPENED, UNKNOWN})

    # Statuses that indicate work is finished.  When a webhook reports one of
    # these, the URIP risk can transition to `resolved` (subject to evidence
    # verification).
    TERMINAL = frozenset({RESOLVED, CLOSED})


@dataclass
class TicketCreateResult:
    """Typed result of create_ticket — provider-agnostic."""
    ticket_id: str          # vendor-specific; e.g. "URIP-42" or "INC0010234"
    ticket_url: str | None  # human-clickable URL (None if provider doesn't expose one)
    raw: dict[str, Any]     # full vendor response — for debugging / audit log


class TicketingProviderBase(abc.ABC):
    """Provider contract.  Every method MUST raise TicketingProviderError on
    upstream failure (the caller will translate to HTTP)."""

    provider_name: str = "base"

    # ------------------------------------------------------------------ #
    @abc.abstractmethod
    def create_ticket(self, risk: Any) -> TicketCreateResult:
        """
        Create a ticket from a Risk-like object.

        `risk` is duck-typed: must expose at least
            risk_id, finding, description, severity, owner_team, sla_deadline,
            cve_id (optional), composite_score (optional).
        """

    # ------------------------------------------------------------------ #
    @abc.abstractmethod
    def update_ticket(self, ticket_id: str, *, status: str | None = None,
                      comment: str | None = None) -> dict[str, Any]:
        """Update ticket status and/or add a comment."""

    # ------------------------------------------------------------------ #
    @abc.abstractmethod
    def get_ticket_status(self, ticket_id: str) -> str:
        """Return current vendor status, normalised to a TicketStatus value."""

    # ------------------------------------------------------------------ #
    @abc.abstractmethod
    def close_ticket(self, ticket_id: str, resolution: str = "Done") -> dict[str, Any]:
        """Force-close the ticket from the URIP side (e.g. risk auto-remediated)."""

    # ------------------------------------------------------------------ #
    # Helpers shared across concrete providers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_summary(risk: Any) -> str:
        """Default ticket summary line.  Providers may override if they need
        a different field layout."""
        rid = getattr(risk, "risk_id", "RISK-UNKNOWN")
        sev = (getattr(risk, "severity", "") or "").upper()
        finding = getattr(risk, "finding", "") or "Untitled finding"
        # Keep summaries short — both Jira and ServiceNow truncate at ~250 chars.
        if len(finding) > 200:
            finding = finding[:197] + "…"
        return f"[{rid}] [{sev}] {finding}"

    @staticmethod
    def _build_description(risk: Any) -> str:
        """Plaintext description.  Both providers accept plaintext on create."""
        lines = [
            f"URIP Risk ID: {getattr(risk, 'risk_id', '?')}",
            f"Severity: {getattr(risk, 'severity', '?')}",
            f"CVSS: {getattr(risk, 'cvss_score', '?')}",
            f"Owner team: {getattr(risk, 'owner_team', '?')}",
            f"Asset: {getattr(risk, 'asset', '?')}",
        ]
        cve = getattr(risk, "cve_id", None)
        if cve:
            lines.append(f"CVE: {cve}")
        composite = getattr(risk, "composite_score", None)
        if composite is not None:
            lines.append(f"URIP Composite Score: {composite}")
        sla = getattr(risk, "sla_deadline", None)
        if sla is not None:
            lines.append(f"SLA Deadline: {sla}")
        desc = getattr(risk, "description", None)
        if desc:
            lines.append("")
            lines.append(desc)
        return "\n".join(lines)

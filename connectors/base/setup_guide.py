"""
connectors/base/setup_guide.py — Structured onboarding content per connector.

P33-Z3 (revised): the Tool Catalog renders the full setup guide INLINE on the
connector tile / drawer.  No external markdown browsing — the customer clicks
a tile and sees everything they need to configure that tool, served by
``GET /api/connectors/{name}``.

Why a structured spec (and not a markdown blob)?
------------------------------------------------
- Frontend can render numbered steps, error tables, sample-JSON viewers, etc.
  with proper components.
- Backend can validate completeness (every connector has steps, errors, …).
- Translation / theming / partial reveal is trivial when the data is
  structured, not embedded inside markdown.
- Tests can assert "every connector has ≥ 3 common errors" without parsing.

Design decisions
----------------
- Plain stdlib ``@dataclass`` (not Pydantic) for two reasons:
    1. Keeps the connector module's import surface tiny — no Pydantic v1/v2
       version sniffing inside connector source.
    2. ``asdict()`` round-trips cleanly into the FastAPI response model
       (``ConnectorCatalogItem``) which IS Pydantic; no double validation.
- Every dataclass has a ``to_dict()`` helper that drops ``None`` values, so
  the JSON the frontend receives is compact.
- ``SetupGuideSpec.validate()`` returns a list of human-readable problems —
  the registry warns (not raises) for the same backward-compat reason as the
  metadata-completeness check (parallel workers should not crash imports).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Difficulty + helpers
# ─────────────────────────────────────────────────────────────────────────────


# Allowed difficulty values — drives a colored badge on the catalog tile.
SETUP_DIFFICULTY = ("easy", "medium", "hard")


def _drop_none(d: dict[str, Any]) -> dict[str, Any]:
    """Strip keys whose value is None — keeps API responses compact."""
    return {k: v for k, v in d.items() if v is not None}


# ─────────────────────────────────────────────────────────────────────────────
# Sub-section dataclasses
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class QuickFacts:
    """
    Top-of-card summary block.

    Mirrors the existing CATEGORY / MODULE_CODE / VENDOR_DOCS_URL / STATUS
    class attrs but adds the customer-facing fields:
      - difficulty / approx_setup_minutes : sets expectations before they start
      - polling_default_minutes / supports_webhooks : "how fresh is the data?"
    """

    category: str                      # e.g. "VM"
    module: str                        # e.g. "VM" — license module
    difficulty: str                    # one of SETUP_DIFFICULTY
    approx_setup_minutes: int          # rough wall-clock — sets expectation
    vendor_docs_url: Optional[str] = None
    polling_default_minutes: int = 15
    supports_webhooks: bool = False
    license_tier_required: Optional[str] = None  # e.g. "Tenable.io (paid)"

    def to_dict(self) -> dict[str, Any]:
        return _drop_none(asdict(self))


@dataclass
class PrereqItem:
    """
    One row in the "before you start" checklist.

    label    : short tag rendered as the row heading ("License tier")
    requirement : full sentence describing what the customer needs
    """

    label: str
    requirement: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SetupStep:
    """
    One numbered step in the installation walk-through.

    n         : 1-based ordinal — frontend renders the number badge.
    title     : short imperative ("Open API Keys page")
    body      : full instruction; may include menu paths, button names, URLs.
    screenshot: optional path/URL to a screenshot — the frontend can lazy-load.
    warning   : optional safety note rendered as a yellow inline banner.
    """

    n: int
    title: str
    body: str
    screenshot: Optional[str] = None
    warning: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return _drop_none(asdict(self))


@dataclass
class ScopeItem:
    """
    One required API scope / permission.

    For OAuth connectors this is a single Graph permission ("AuditLog.Read.All")
    or equivalent.  For role-based connectors this is the minimum role name.

    name        : machine identifier ("AuditLog.Read.All", "scanner-admin", …)
    description : human-readable purpose ("Read sign-in audit logs")
    required    : True for must-have, False for "recommended to enable extra
                  features".
    """

    name: str
    description: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ErrorFix:
    """
    One row of the troubleshooting table.

    error : the exact error message customers will see (or close paraphrase)
    cause : root cause in plain English
    fix   : actionable step-by-step resolution
    """

    error: str
    cause: str
    fix: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PollingSpec:
    """
    "Refresh & cadence" panel.

    default_minutes              : how often the scheduler polls.
    first_sync_estimate_minutes  : full-pull duration for an average tenant.
    webhook_supported            : True if the vendor pushes events to URIP.
    manual_refresh               : where to click for an on-demand poll.
    """

    default_minutes: int
    first_sync_estimate_minutes: int
    webhook_supported: bool
    manual_refresh: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─────────────────────────────────────────────────────────────────────────────
# Top-level spec
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SetupGuideSpec:
    """
    Full inline setup guide for one connector.

    Every concrete connector class sets ``SETUP_GUIDE = SetupGuideSpec(...)``
    so the Tool Catalog UI can render the entire onboarding flow without
    leaving the page.

    Fields
    ------
    quick_facts       : QuickFacts — top-of-card summary
    what_pulled       : list[str] — bullet list of data ingested
    prerequisites     : list[PrereqItem]
    steps             : list[SetupStep] — numbered walk-through
    required_scopes   : list[ScopeItem]
    sample_data       : dict — one realistic JSON finding
    not_collected     : list[str] — explicit privacy guarantees
    common_errors     : list[ErrorFix] — at least 3 entries enforced by tests
    polling           : PollingSpec
    disconnect_steps  : list[str]
    references        : list[str] — extra useful URLs (vendor support, etc.)
    """

    quick_facts: QuickFacts
    what_pulled: list[str]
    prerequisites: list[PrereqItem]
    steps: list[SetupStep]
    required_scopes: list[ScopeItem]
    sample_data: dict[str, Any]
    not_collected: list[str]
    common_errors: list[ErrorFix]
    polling: PollingSpec
    disconnect_steps: list[str]
    references: list[str] = field(default_factory=list)

    # ────────────────────────────────────────────────────────────────────
    # Serialization
    # ────────────────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Render to a JSON-friendly dict for the API response."""
        return {
            "quick_facts": self.quick_facts.to_dict(),
            "what_pulled": list(self.what_pulled),
            "prerequisites": [p.to_dict() for p in self.prerequisites],
            "steps": [s.to_dict() for s in self.steps],
            "required_scopes": [s.to_dict() for s in self.required_scopes],
            "sample_data": dict(self.sample_data),
            "not_collected": list(self.not_collected),
            "common_errors": [e.to_dict() for e in self.common_errors],
            "polling": self.polling.to_dict(),
            "disconnect_steps": list(self.disconnect_steps),
            "references": list(self.references),
        }

    # ────────────────────────────────────────────────────────────────────
    # Validation (used by registry + tests)
    # ────────────────────────────────────────────────────────────────────

    def validate(self) -> list[str]:
        """
        Return a list of problems (empty list = OK).

        Why list, not raises?  The registry should warn but not crash imports.
        Tests assert ``validate() == []`` for every connector — that's where
        we hard-fail incomplete guides.
        """
        problems: list[str] = []

        # quick_facts
        qf = self.quick_facts
        if qf.difficulty not in SETUP_DIFFICULTY:
            problems.append(
                f"quick_facts.difficulty={qf.difficulty!r} not in "
                f"{SETUP_DIFFICULTY!r}"
            )
        if qf.approx_setup_minutes <= 0:
            problems.append("quick_facts.approx_setup_minutes must be > 0")
        if qf.polling_default_minutes <= 0:
            problems.append("quick_facts.polling_default_minutes must be > 0")
        if qf.vendor_docs_url is not None and not qf.vendor_docs_url.startswith(
            ("http://", "https://")
        ):
            problems.append(
                f"quick_facts.vendor_docs_url={qf.vendor_docs_url!r} must be a URL"
            )

        # bullet lists
        if not self.what_pulled:
            problems.append("what_pulled is empty — list at least one data type")
        if not self.prerequisites:
            problems.append("prerequisites is empty — list at least one")

        # numbered steps
        if not self.steps:
            problems.append("steps is empty — list at least one")
        else:
            ordinals = [s.n for s in self.steps]
            if ordinals != sorted(ordinals):
                problems.append("steps are not ordered by .n ascending")
            for s in self.steps:
                if not s.title.strip() or not s.body.strip():
                    problems.append(f"step n={s.n} has empty title or body")

        if not self.required_scopes:
            problems.append("required_scopes is empty — list at least one")

        if not self.sample_data:
            problems.append("sample_data is empty — provide one realistic finding")

        if not self.not_collected:
            problems.append(
                "not_collected is empty — list at least one privacy guarantee"
            )

        # tests assert len(common_errors) >= 3 — surface that here too.
        if len(self.common_errors) < 3:
            problems.append(
                f"common_errors has {len(self.common_errors)} items; "
                "at least 3 required"
            )

        if self.polling.default_minutes <= 0:
            problems.append("polling.default_minutes must be > 0")
        if not self.polling.manual_refresh.strip():
            problems.append("polling.manual_refresh is empty")

        if not self.disconnect_steps:
            problems.append("disconnect_steps is empty — explain how to remove")

        return problems

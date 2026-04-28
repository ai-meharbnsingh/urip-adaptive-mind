"""
connectors/base/connector.py — Abstract Connector base class + data transfer objects.

P1.6: Connector Framework Abstraction
P33-Z3: Connector metadata contract (DISPLAY_NAME, CATEGORY, STATUS, …) for the
        dynamic Tool Catalog UI.

Design decisions
----------------
- BaseConnector is an ABC with four mandatory abstract methods mirroring the
  blueprint's connector contract: authenticate, fetch_findings, normalize, health_check.
- Pydantic dataclasses are used for ConnectorSession, RawFinding, URIPRiskRecord, and
  ConnectorHealth so callers get field validation and easy dict/JSON conversion for free.
- URIPRiskRecord fields align 1-to-1 with the Risk SQLAlchemy model's columns (excluding
  DB-managed fields: id, risk_id, status, sla_deadline, assigned_to, tenant_id, timestamps).
  The scheduler / API layer fills in those DB-side fields.
- fetch_findings() signature includes `since: datetime` (incremental fetch) but the
  `tenant_id` optional kwarg is added so simulator variants can scope output without
  requiring a ConnectorSession object to be passed around.

Metadata contract (Z3 / Tool Catalog)
-------------------------------------
Every concrete connector subclass declares CLASS attributes (not instance) that
the registry exposes through ``list_connectors_with_metadata()``.  The fields
power a 100% data-driven catalog UI (no hard-coded tile metadata client-side):

    DISPLAY_NAME        : str     — "Tenable Vulnerability Manager"
    CATEGORY            : str     — one of CONNECTOR_CATEGORIES below
    SHORT_DESCRIPTION   : str     — one-line catalog blurb
    STATUS              : str     — "live" | "building" | "simulated" | "roadmap"
    VENDOR_DOCS_URL     : str|None
    SUPPORTED_PRODUCTS  : list[str]|None  — for multi-product connectors
    MODULE_CODE         : str     — one of CORE/VM/EDR/NETWORK/IDENTITY/...
    CREDENTIAL_FIELDS   : list[CredentialFieldSpec]

Why class attributes?  The registry stores classes (factories) — we want the
catalog endpoint to read metadata WITHOUT calling the factory or hitting the
network.  Class attributes are the cheapest, most introspection-friendly way.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from connectors.base.setup_guide import SetupGuideSpec  # noqa: F401  (re-exported)


# ─────────────────────────────────────────────────────────────────────────────
# Data Transfer Objects (framework-level contracts)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ConnectorSession:
    """
    Returned by authenticate().  Holds auth material for a single
    (connector, tenant) pair.  Connectors may subclass this to carry
    additional fields (e.g., OAuth refresh token).
    """
    connector_name: str
    tenant_id: str
    token: str
    expires_at: datetime
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawFinding:
    """
    A single finding in its source-native shape, before normalization.
    Connectors return a list of these from fetch_findings().
    """
    id: str                  # source-native finding ID (string)
    source: str              # e.g. "tenable", "sentinelone", "simulator"
    raw_data: dict[str, Any] # full source payload — connector-specific structure
    fetched_at: datetime
    tenant_id: str           # tenant this finding belongs to


@dataclass
class URIPRiskRecord:
    """
    Normalized risk record.  Maps to backend.models.risk.Risk fields.
    DB-managed fields (id, risk_id, status, sla_deadline, timestamps) are
    populated by the API layer when persisting.
    """
    finding: str
    source: str
    domain: str              # endpoint | cloud | network | application | identity | ot
    cvss_score: float
    severity: str            # critical | high | medium | low
    asset: str
    owner_team: str
    description: Optional[str] = None
    cve_id: Optional[str] = None
    epss_score: Optional[float] = None
    in_kev_catalog: bool = False
    exploit_status: Optional[str] = None   # none | poc | active | weaponized
    asset_tier: Optional[int] = None       # 1=Critical … 4=Low
    composite_score: Optional[float] = None


@dataclass
class ConnectorHealth:
    """
    Returned by health_check().
    status: "ok" | "degraded" | "error"
    """
    connector_name: str
    status: str              # "ok" | "degraded" | "error"
    last_run: Optional[datetime]
    error_count: int = 0
    last_error: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Catalog metadata — categories, status values, credential field spec
# ─────────────────────────────────────────────────────────────────────────────


# Allowed CATEGORY values for the Tool Catalog filter.  Kept here as a constant
# so frontend, registry validation, and tests have one source of truth.
CONNECTOR_CATEGORIES: tuple[str, ...] = (
    "VM",
    "EDR",
    "NETWORK",
    "IDENTITY",
    "COLLABORATION",
    "ITSM",
    "DAST",
    "DLP",
    "EXTERNAL_THREAT",
    "CSPM",
    "OT",
    "NAC",
    "PAM",
    "FIREWALL",
    "EMAIL",
    "ADVISORY",
    "BUG_BOUNTY",
    "SOC",
    "EASM",
    "SIMULATOR",
    # Project_33a roadmap modules — added with module scaffolds
    "DSPM",          # Data Security Posture Management
    "AI_SECURITY",   # AI/ML model security + governance
    "ZTNA",          # Zero Trust Network Access (Zscaler ZPA, Cloudflare Access, Tailscale, Twingate)
    # P33 — Compliance training + background verification
    "LMS",           # Learning Management Systems (KnowBe4, Hoxhunt)
    "BGV",           # Background Verification (AuthBridge, OnGrid)
)


# Allowed STATUS values — drives the catalog status badge
# - "live"      : real connector hitting the vendor API
# - "building"  : connector class registered but not feature-complete
# - "simulated" : returns synthetic data only (simulator/extended_simulator)
# - "roadmap"   : placeholder so the tile is visible but disabled
ConnectorStatus = Literal["live", "building", "simulated", "roadmap"]


@dataclass
class CredentialFieldSpec:
    """
    One field in a connector's credential wizard form.

    Mirrors the FIELD_SHAPE used by ``frontend/js/connector-schemas.js`` so the
    backend can be the source of truth for the form.  The frontend's dynamic
    wizard reads these straight off the /api/connectors response.

    Attributes
    ----------
    name        : POST body key
    label       : displayed label
    type        : "text" | "url" | "password" | "number" | "select" | "uuid"
    required    : if True, field must be present in /configure body
    secret      : if True, render as password input with show/hide toggle
    placeholder : optional placeholder text
    help_text   : small hint text shown under the input
    default     : optional default pre-fill (number/text)
    pattern     : optional regex string for client-side validation
    options     : list of {value, label} for "select" type
    """

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

    def to_dict(self) -> dict[str, Any]:
        """Render to a JSON-friendly dict (drops None fields for compactness)."""
        out: dict[str, Any] = {
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "required": self.required,
            "secret": self.secret,
        }
        if self.placeholder is not None:
            out["placeholder"] = self.placeholder
        if self.help_text is not None:
            out["help_text"] = self.help_text
        if self.default is not None:
            out["default"] = self.default
        if self.pattern is not None:
            out["pattern"] = self.pattern
        if self.options is not None:
            out["options"] = self.options
        return out


# ─────────────────────────────────────────────────────────────────────────────
# Abstract base class
# ─────────────────────────────────────────────────────────────────────────────


class BaseConnector(abc.ABC):
    """
    Abstract interface every URIP connector must implement.

    Lifecycle
    ---------
    1. Instantiate the connector class (no args required — credentials come
       in via authenticate()).
    2. Call authenticate(tenant_credentials) → ConnectorSession.
    3. Call fetch_findings(since) → list[RawFinding].
    4. For each RawFinding, call normalize(raw) → URIPRiskRecord.
    5. Periodically call health_check() → ConnectorHealth.

    The ConnectorScheduler orchestrates this lifecycle; connectors themselves
    are stateless between calls (session is passed back by the caller if needed).

    Catalog metadata (Z3) — every concrete subclass MUST set:
        DISPLAY_NAME, CATEGORY, SHORT_DESCRIPTION, STATUS, MODULE_CODE,
        CREDENTIAL_FIELDS.   VENDOR_DOCS_URL and SUPPORTED_PRODUCTS are
        optional (default None).  ``ConnectorRegistry.register`` warns if any
        required field is left at its base-class placeholder so the catalog
        never silently shows an unconfigured tile.
    """

    NAME: str = "base"   # Override in subclasses; used by registry + logging

    # Catalog metadata — base-class placeholders, MUST be overridden.
    DISPLAY_NAME: str = ""
    CATEGORY: str = ""
    SHORT_DESCRIPTION: str = ""
    STATUS: ConnectorStatus = "live"
    VENDOR_DOCS_URL: Optional[str] = None
    SUPPORTED_PRODUCTS: Optional[list[str]] = None
    MODULE_CODE: str = "CORE"
    CREDENTIAL_FIELDS: list[CredentialFieldSpec] = []

    # Cyber Risk Index (TrendAI-style) — which sub-index this connector feeds.
    # One of "exposure" | "attack" | "security_config" | None.
    # - "exposure"        : things that EXPOSE you to attack (Tenable, EASM, …)
    # - "attack"          : things actively attacking you (EDR, identity risky-signins, DLP, …)
    # - "security_config" : misconfigurations (CSPM, MDM/UEM, firewall posture, …)
    # - None              : connector does not feed any of the three Cyber Risk
    #                       Index sub-indexes (e.g. ITSM, advisory, OT, email).
    RISK_INDEX_DOMAIN: Optional[Literal["exposure", "attack", "security_config"]] = None

    # Inline onboarding content (P33-Z3 revised) — populated per concrete
    # subclass with a SetupGuideSpec.  When set, the Tool Catalog UI renders
    # the entire installation walk-through inline on the connector tile so
    # customers never need to leave URIP to configure a tool.
    SETUP_GUIDE: Optional["SetupGuideSpec"] = None

    @abc.abstractmethod
    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate credentials and return a ConnectorSession.

        Parameters
        ----------
        tenant_credentials : dict
            Decrypted credentials blob from CredentialsVault.
            Shape is connector-specific (api_key, client_id/secret, etc.).

        Returns
        -------
        ConnectorSession
            Valid session object; token expires_at is set by the connector.

        Raises
        ------
        ConnectorAuthError
            If credentials are invalid or the upstream API rejects them.
        """
        ...

    @abc.abstractmethod
    def fetch_findings(self, since: datetime, **kwargs) -> list[RawFinding]:
        """
        Pull new/updated findings from the source since `since`.

        Parameters
        ----------
        since : datetime
            Fetch only findings created/updated after this timestamp.
            Connector must pass this as a filter to the upstream API where
            possible; otherwise filter locally.

        Returns
        -------
        list[RawFinding]
            Zero or more raw findings.  Empty list is valid (no new findings).
        """
        ...

    @abc.abstractmethod
    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map one RawFinding to a URIPRiskRecord.

        Must produce a complete URIPRiskRecord (all required fields populated).
        Optional fields (cve_id, epss_score, etc.) may be None if not available
        from this source.
        """
        ...

    @abc.abstractmethod
    def health_check(self) -> ConnectorHealth:
        """
        Return the connector's current operational status.
        Should NOT raise — return ConnectorHealth(status="error") instead.
        """
        ...


# ─────────────────────────────────────────────────────────────────────────────
# Connector-specific exceptions
# ─────────────────────────────────────────────────────────────────────────────


class ConnectorAuthError(Exception):
    """Raised when authenticate() fails."""


class ConnectorFetchError(Exception):
    """Raised when fetch_findings() encounters an unrecoverable API error."""


class ConnectorNormalizeError(Exception):
    """Raised when a raw finding cannot be normalized (malformed data)."""

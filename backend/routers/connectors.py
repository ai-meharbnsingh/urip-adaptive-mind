"""
backend/routers/connectors.py — Top-level /api/connectors router.

Z3-A: Wires the 7 production + 2 simulator connectors into the live API so
they stop being dead code (INV-1 fix).  This router is what the frontend
``connector-wizard.js`` (FV-1) actually calls.

Endpoints
---------
GET    /api/connectors                       — list connector types + per-tenant config status
GET    /api/connectors/{name}                — connector schema (field defs for the wizard)
POST   /api/connectors/{name}/configure      — store encrypted credentials for current tenant
POST   /api/connectors/{name}/test           — test connection (uses inline or stored creds)
DELETE /api/connectors/{name}                — remove credentials for current tenant
POST   /api/connectors/{name}/run-now        — trigger an immediate poll (admin only)
GET    /api/connectors/{name}/health         — connector health (status, error count)
GET    /api/connectors/{name}/findings       — recent findings for current tenant

Coordination
------------
- The legacy ``/api/settings/connectors`` endpoints in ``backend/routers/settings.py``
  remain in place — they back the older settings UI.  This new router is the
  canonical surface for the FV-1 wizard and is mounted at ``/api/connectors``.
- All endpoints require ``ciso`` role; the tenant scope comes from
  ``TenantContext`` populated by ``get_current_user``.
- Module gate is ``CORE`` because connectors are a platform-level feature.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user  # noqa: F401  (re-exported via rbac)
from backend.middleware.module_gate import require_module
from backend.middleware.rbac import role_required
from backend.middleware.tenant import TenantContext
from backend.models.agent_ingest import ConnectorHealthSummary
from backend.models.audit_log import AuditLog
from backend.models.risk import Risk
from backend.models.tenant_connector_credential import TenantConnectorCredential
from backend.models.user import User
from backend.schemas.connectors import (
    CategoriesResponse,
    CategoryAggregate,
    ConnectorCatalogItem,
    ConnectorCatalogResponse,
    CredentialFieldOut,
)
from backend.services.crypto_service import decrypt_credentials, encrypt_credentials
from backend.services.tenant_query import apply_tenant_filter
from connectors.base.connector import (
    BaseConnector,
    ConnectorAuthError,
    ConnectorFetchError,
    ConnectorHealth,
)
from connectors.base.registry import _global_registry

logger = logging.getLogger(__name__)


# CRIT-007 — connectors are a CORE platform feature.
router = APIRouter(dependencies=[Depends(require_module("CORE"))])


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────────────────────


class ConnectorListItem(BaseModel):
    name: str
    configured: bool


class ConnectorListResponse(BaseModel):
    items: list[ConnectorListItem]
    total: int
    limit: int
    offset: int


class ConnectorFieldSpec(BaseModel):
    name: str
    label: str
    required: bool
    secret: bool = False
    description: str | None = None


class ConnectorSchemaResponse(BaseModel):
    name: str
    fields: list[ConnectorFieldSpec]


class ConfigureRequest(BaseModel):
    credentials: dict = Field(..., description="Connector-specific credentials dict")


class ConfigureResponse(BaseModel):
    status: str
    connector: str


class TestRequest(BaseModel):
    credentials: dict | None = None


class TestResponse(BaseModel):
    success: bool
    message: str
    sample: list[dict[str, Any]] = Field(default_factory=list)


class DeleteResponse(BaseModel):
    status: str
    connector: str


class RunNowResponse(BaseModel):
    status: str
    connector: str
    records_ingested: int


class HealthResponse(BaseModel):
    connector_name: str
    status: str
    last_run: datetime | None
    error_count: int
    last_error: str | None


class FindingItem(BaseModel):
    risk_id: str
    finding: str
    severity: str
    cvss_score: float
    asset: str
    cve_id: str | None
    created_at: datetime


class FindingsResponse(BaseModel):
    items: list[FindingItem]
    total: int
    limit: int


# ─────────────────────────────────────────────────────────────────────────────
# Schema definitions per connector — drives the FV-1 wizard
# ─────────────────────────────────────────────────────────────────────────────

CONNECTOR_SCHEMAS: dict[str, list[ConnectorFieldSpec]] = {
    "tenable": [
        ConnectorFieldSpec(name="access_key", label="Access Key", required=True, secret=True),
        ConnectorFieldSpec(name="secret_key", label="Secret Key", required=True, secret=True),
        ConnectorFieldSpec(name="base_url", label="Base URL", required=False,
                           description="Default https://cloud.tenable.com"),
    ],
    "sentinelone": [
        ConnectorFieldSpec(name="api_token", label="API Token", required=True, secret=True),
        ConnectorFieldSpec(name="base_url", label="Base URL", required=True,
                           description="e.g. https://tenant.sentinelone.net"),
    ],
    "zscaler": [
        ConnectorFieldSpec(name="api_key", label="API Key", required=True, secret=True),
        ConnectorFieldSpec(name="username", label="Username", required=True),
        ConnectorFieldSpec(name="password", label="Password", required=True, secret=True),
        ConnectorFieldSpec(name="cloud", label="Cloud", required=True,
                           description="e.g. zscalerone, zscalertwo, zscaler"),
    ],
    "netskope": [
        ConnectorFieldSpec(name="client_id", label="Client ID", required=True),
        ConnectorFieldSpec(name="client_secret", label="Client Secret", required=True, secret=True),
        ConnectorFieldSpec(name="base_url", label="Base URL", required=True,
                           description="e.g. https://tenant.goskope.com"),
    ],
    "ms_entra": [
        ConnectorFieldSpec(name="tenant_id", label="Azure AD Tenant ID", required=True),
        ConnectorFieldSpec(name="client_id", label="Application (Client) ID", required=True),
        ConnectorFieldSpec(name="client_secret", label="Client Secret", required=True, secret=True),
    ],
    "manageengine_sdp": [
        ConnectorFieldSpec(name="auth_method", label="Auth Method", required=True,
                           description="oauth | token"),
        ConnectorFieldSpec(name="base_url", label="Base URL", required=True),
        ConnectorFieldSpec(name="client_id", label="Client ID (oauth)", required=False),
        ConnectorFieldSpec(name="client_secret", label="Client Secret (oauth)", required=False, secret=True),
        ConnectorFieldSpec(name="refresh_token", label="Refresh Token (oauth)", required=False, secret=True),
        ConnectorFieldSpec(name="auth_token", label="Auth Token (token)", required=False, secret=True),
    ],
    "cloudsek": [
        ConnectorFieldSpec(name="api_key", label="API Key", required=True, secret=True),
        ConnectorFieldSpec(name="org_id", label="Organization ID", required=True),
        ConnectorFieldSpec(name="api_base", label="API Base URL", required=False,
                           description="Default https://api.cloudsek.com"),
    ],
    "simulator": [
        ConnectorFieldSpec(name="tenant_id", label="Tenant Label", required=False,
                           description="Optional label for simulator runs"),
    ],
    "extended_simulator": [
        ConnectorFieldSpec(name="tenant_id", label="Tenant Label", required=False,
                           description="Optional label for extended-simulator runs"),
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _ensure_known_connector(name: str) -> None:
    """Raise 404 if `name` is not in the global registry."""
    if name not in _global_registry:
        raise HTTPException(
            status_code=404,
            detail=f"Connector '{name}' is not registered.",
        )


async def _load_credentials(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    connector_name: str,
) -> dict | None:
    """Return decrypted credentials for (tenant, connector) or None."""
    row = (
        await db.execute(
            select(TenantConnectorCredential).where(
                TenantConnectorCredential.tenant_id == tenant_id,
                TenantConnectorCredential.connector_name == connector_name,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return decrypt_credentials(row.encrypted_blob)


def _instantiate(name: str) -> BaseConnector:
    """Instantiate a connector via the registry."""
    factory = _global_registry.get(name)
    return factory()


def _next_risk_id(prefix: str = "RISK") -> str:
    """Compact risk_id — uses uuid4 short form to avoid collisions in tests."""
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


# ─────────────────────────────────────────────────────────────────────────────
# HIGH-3 — SSRF guard for user-supplied base_url
# ─────────────────────────────────────────────────────────────────────────────

# Fields in connector credentials dicts that are URLs the backend will hit.
# Every connector's `authenticate` ultimately uses one of these as the request
# host, so any user-supplied value must be vetted at the API boundary.
_URL_CREDENTIAL_FIELDS = ("base_url", "api_base", "url", "endpoint")


class SSRFValidationError(HTTPException):
    """HTTP 422 — the supplied URL fails SSRF / scheme validation."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=422, detail=detail)


def _is_disallowed_ip(addr: str) -> bool:
    """
    Return True if ``addr`` is in any range we never want the backend to call:
      - loopback (127.0.0.0/8, ::1)
      - private RFC 1918 (10/8, 172.16/12, 192.168/16, fc00::/7)
      - link-local (169.254/16, fe80::/10)  — includes cloud-metadata 169.254.169.254
      - multicast / unspecified / reserved
    """
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        # Not an IP literal — caller decides what to do with the hostname.
        return False
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    )


def _validate_outbound_url(raw_url: str, *, field_name: str = "base_url") -> None:
    """
    Validate a user-supplied URL for use as an outbound HTTP target.

    Rules:
      1. Scheme MUST be ``https``. http/file/gopher/ftp/etc. are rejected.
      2. Hostname must be present.
      3. If the hostname is an IP literal — it must NOT be private/loopback/link-local.
      4. If the hostname is a DNS name — every resolved A/AAAA record must
         clear rule 3. Resolution failures are OK to bubble up as 422 too,
         to avoid leaking timing info.

    Raises:
        SSRFValidationError: on any failure.
    """
    if not raw_url or not isinstance(raw_url, str):
        raise SSRFValidationError(f"{field_name!r} must be a non-empty string")

    parsed = urlparse(raw_url.strip())
    if parsed.scheme.lower() != "https":
        raise SSRFValidationError(
            f"{field_name!r} must use HTTPS scheme; got {parsed.scheme!r}"
        )
    host = parsed.hostname  # urlparse strips brackets from IPv6 hosts
    if not host:
        raise SSRFValidationError(f"{field_name!r} is missing a hostname")

    # Direct IP literal? Validate it.
    try:
        ipaddress.ip_address(host)
        is_literal = True
    except ValueError:
        is_literal = False

    if is_literal:
        if _is_disallowed_ip(host):
            raise SSRFValidationError(
                f"{field_name!r} resolves to a disallowed IP range "
                f"(loopback / private / link-local / metadata)"
            )
        return

    # Hostname — resolve all addresses and check each.
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise SSRFValidationError(
            f"{field_name!r} hostname could not be resolved: {exc}"
        ) from exc

    for info in infos:
        # info = (family, type, proto, canonname, sockaddr) — sockaddr[0] = ip
        ip_str = info[4][0]
        if _is_disallowed_ip(ip_str):
            raise SSRFValidationError(
                f"{field_name!r} resolves to a disallowed IP ({ip_str}); "
                "private / loopback / link-local / metadata addresses are blocked"
            )


def _validate_credentials_urls(creds: dict | None) -> None:
    """Run SSRF validation against every URL-shaped key in the creds dict."""
    if not creds:
        return
    for key in _URL_CREDENTIAL_FIELDS:
        if key in creds and creds[key]:
            _validate_outbound_url(creds[key], field_name=key)


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get("", response_model=ConnectorCatalogResponse)
async def list_connectors(
    category: str | None = Query(
        default=None,
        description="Filter to one category (e.g. VM, EDR, NETWORK). Case-insensitive.",
    ),
    status: str | None = Query(
        default=None,
        description="Filter by lifecycle status: live | building | simulated | roadmap.",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    """
    Return the Tool Catalog: every registered connector with full metadata
    plus per-tenant runtime state (configured flag, latest health, last poll).

    Z3: this is the SOLE feed for the dynamic Tool Catalog UI.  The frontend
    renders one tile per item — display_name, status badge, category, etc.
    are read straight off this response (no client-side hard-coding).
    """
    # Static metadata for every registered connector (sorted by name).
    all_meta = _global_registry.list_connectors_with_metadata()

    # Buyer-facing catalog: hide internal lifecycle tiers entirely.
    # Only "live" connectors are integrations a paying tenant can actually
    # configure today. Simulator / building / roadmap tiers are dev-only and
    # must never reach the customer UI (they remain available to tests via
    # the registry directly).
    all_meta = [m for m in all_meta if m["status"] == "live"]

    # Optional filters (applied BEFORE pagination so total reflects the filter)
    if category is not None:
        cat_upper = category.upper()
        all_meta = [m for m in all_meta if m["category"].upper() == cat_upper]
    if status is not None:
        all_meta = [m for m in all_meta if m["status"] == status.lower()]

    total = len(all_meta)
    page = all_meta[offset : offset + limit]

    # Per-tenant runtime state — fetched in two cheap queries.
    configured_rows = (
        await db.execute(
            apply_tenant_filter(
                select(TenantConnectorCredential.connector_name),
                TenantConnectorCredential,
            )
        )
    ).scalars().all()
    configured = set(configured_rows)

    # Health summaries (FV-3) — one row per (tenant, connector); may be empty.
    health_rows = (
        await db.execute(
            apply_tenant_filter(
                select(ConnectorHealthSummary), ConnectorHealthSummary,
            )
        )
    ).scalars().all()
    health_by_name: dict[str, ConnectorHealthSummary] = {
        row.connector_name: row for row in health_rows
    }

    items: list[ConnectorCatalogItem] = []
    for meta in page:
        h = health_by_name.get(meta["name"])
        items.append(
            ConnectorCatalogItem(
                name=meta["name"],
                display_name=meta["display_name"],
                category=meta["category"],
                short_description=meta["short_description"],
                status=meta["status"],
                vendor_docs_url=meta["vendor_docs_url"],
                supported_products=meta["supported_products"],
                module_code=meta["module_code"],
                credential_fields=[
                    CredentialFieldOut(**f) for f in meta["credential_fields"]
                ],
                # P33-Z3 (revised) — inline onboarding content for the drawer.
                setup_guide=meta.get("setup_guide"),
                configured=meta["name"] in configured,
                last_poll_at=h.last_poll_at if h else None,
                health_status=h.status if h else None,
                error_count_24h=h.error_count_24h if h else 0,
            )
        )

    return ConnectorCatalogResponse(
        items=items, total=total, limit=limit, offset=offset,
    )


@router.get("/categories", response_model=CategoriesResponse)
async def list_connector_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    """
    Aggregate connector counts by category for the filter UI.

    Returns: [{category, count, configured_count}, …] sorted by category name.

    The ``configured_count`` is per-tenant (uses TenantContext) so each tenant
    sees its own "X of Y configured" tally next to each filter chip.
    """
    all_meta = _global_registry.list_connectors_with_metadata()
    # Mirror the catalog filter — hide non-live tiers from the buyer UI so
    # dev-only categories (e.g. SIMULATOR) never appear in the filter dropdown.
    all_meta = [m for m in all_meta if m["status"] == "live"]

    configured_rows = (
        await db.execute(
            apply_tenant_filter(
                select(TenantConnectorCredential.connector_name),
                TenantConnectorCredential,
            )
        )
    ).scalars().all()
    configured: set[str] = set(configured_rows)

    # Count by category — collect both totals and per-tenant configured counts.
    counts: dict[str, dict[str, int]] = {}
    for meta in all_meta:
        cat = meta["category"]
        bucket = counts.setdefault(cat, {"count": 0, "configured_count": 0})
        bucket["count"] += 1
        if meta["name"] in configured:
            bucket["configured_count"] += 1

    aggregates = [
        CategoryAggregate(
            category=cat,
            count=bucket["count"],
            configured_count=bucket["configured_count"],
        )
        for cat, bucket in sorted(counts.items())
    ]

    return CategoriesResponse(
        categories=aggregates,
        total_categories=len(aggregates),
    )


@router.get("/{name}/setup-guide", response_model=ConnectorCatalogItem)
async def get_connector_setup_guide(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    """
    Return the full ConnectorCatalogItem for a single connector — including the
    inline ``setup_guide`` block the Tool Catalog drawer renders.

    This is the canonical endpoint behind the "click a tile" flow: the
    frontend fetches one item with all metadata + setup guide + per-tenant
    runtime state in a single round trip.

    Z3 (revised): setup content is served by the API, NOT external markdown.
    """
    _ensure_known_connector(name)
    meta = _global_registry.get_connector_metadata(name)

    tenant_id = TenantContext.get()

    # Per-tenant runtime state — same join the list endpoint does, scoped to
    # this connector only.
    configured_row = (
        await db.execute(
            select(TenantConnectorCredential.connector_name).where(
                TenantConnectorCredential.tenant_id == tenant_id,
                TenantConnectorCredential.connector_name == name,
            )
        )
    ).scalar_one_or_none()
    h = (
        await db.execute(
            select(ConnectorHealthSummary).where(
                ConnectorHealthSummary.tenant_id == tenant_id,
                ConnectorHealthSummary.connector_name == name,
            )
        )
    ).scalar_one_or_none()

    return ConnectorCatalogItem(
        name=meta["name"],
        display_name=meta["display_name"],
        category=meta["category"],
        short_description=meta["short_description"],
        status=meta["status"],
        vendor_docs_url=meta["vendor_docs_url"],
        supported_products=meta["supported_products"],
        module_code=meta["module_code"],
        credential_fields=[
            CredentialFieldOut(**f) for f in meta["credential_fields"]
        ],
        setup_guide=meta.get("setup_guide"),
        configured=configured_row is not None,
        last_poll_at=h.last_poll_at if h else None,
        health_status=h.status if h else None,
        error_count_24h=h.error_count_24h if h else 0,
    )


@router.get("/{name}", response_model=ConnectorSchemaResponse)
async def get_connector_schema(
    name: str,
    current_user: User = Depends(role_required("ciso")),
):
    """
    Return the credential field schema for a connector — the wizard uses this
    to render the right form (text inputs, secret fields, descriptions).
    """
    _ensure_known_connector(name)
    fields = CONNECTOR_SCHEMAS.get(name, [])
    return ConnectorSchemaResponse(name=name, fields=fields)


@router.post("/{name}/configure", response_model=ConfigureResponse)
async def configure_connector(
    name: str,
    payload: ConfigureRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    """
    Store encrypted credentials for the current tenant.  Upserts on
    (tenant_id, connector_name) — calling twice with new creds replaces the row.
    """
    _ensure_known_connector(name)
    tenant_id = TenantContext.get()

    # HIGH-3 SSRF — vet any URL-shaped creds before persisting them, so we
    # never store an attacker-controlled internal URL that the scheduler
    # would later hit.
    _validate_credentials_urls(payload.credentials)

    encrypted = encrypt_credentials(payload.credentials)

    existing = (
        await db.execute(
            select(TenantConnectorCredential).where(
                TenantConnectorCredential.tenant_id == tenant_id,
                TenantConnectorCredential.connector_name == name,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        row = TenantConnectorCredential(
            tenant_id=tenant_id,
            connector_name=name,
            encrypted_blob=encrypted,
        )
        db.add(row)
        action = "connector_credentials_created"
    else:
        existing.encrypted_blob = encrypted
        existing.updated_at = datetime.now(timezone.utc)
        action = "connector_credentials_updated"

    db.add(
        AuditLog(
            user_id=current_user.id,
            action=action,
            resource_type="connector",
            resource_id=None,
            details={"connector": name},
            tenant_id=tenant_id,
        )
    )
    await db.commit()

    return ConfigureResponse(status="configured", connector=name)


@router.post("/{name}/test", response_model=TestResponse)
async def test_connector_connection(
    name: str,
    payload: TestRequest | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    """
    Test connection using inline credentials (if provided in body) or stored
    credentials (otherwise).  Returns success/failure plus a small data sample
    for the simulator connectors.
    """
    _ensure_known_connector(name)
    tenant_id = TenantContext.get()

    creds: dict | None = None
    if payload is not None and payload.credentials is not None:
        creds = payload.credentials
        # HIGH-3 SSRF — only validate INLINE URLs. Stored creds were already
        # validated at /configure time; re-validating them would also mean
        # blocking a previously-OK base_url whose DNS now points at a private
        # IP, which is annoying without being more secure (we still wouldn't
        # have hit it because authenticate() resolves at request-time).
        _validate_credentials_urls(creds)
    if creds is None:
        creds = await _load_credentials(db, tenant_id, name)
    if creds is None:
        return TestResponse(
            success=False,
            message="No credentials provided and none stored for this connector.",
        )

    instance = _instantiate(name)
    try:
        instance.authenticate(creds)
    except ConnectorAuthError as exc:
        return TestResponse(success=False, message=f"Auth failed: {exc}")
    except Exception as exc:
        logger.exception("Connector %s test_connection auth raised", name)
        return TestResponse(success=False, message=f"Auth error: {exc}")

    # Try a tiny fetch to prove plumbing.  For most live connectors this hits
    # the network — for simulators it just synthesises a few findings.
    sample: list[dict[str, Any]] = []
    try:
        since = datetime.now(timezone.utc) - timedelta(minutes=15)
        # Cap simulator output so test responses stay small.
        try:
            findings = instance.fetch_findings(
                since, tenant_id=str(tenant_id), count=3
            )
        except TypeError:
            # Connector doesn't accept the optional kwargs — call basic form.
            findings = instance.fetch_findings(since)
        for raw in findings[:3]:
            try:
                normalized = instance.normalize(raw)
                sample.append(
                    {
                        "finding": normalized.finding,
                        "severity": normalized.severity,
                        "source": normalized.source,
                    }
                )
            except (KeyError, ValueError, TypeError, AttributeError):
                # L6 (Kimi LOW-002) — narrow catch.  Connector-shape mismatches
                # surface as KeyError / ValueError / AttributeError when the
                # foreign payload doesn't match the expected schema; bypass
                # this row but keep the test.
                continue
    except ConnectorFetchError as exc:
        return TestResponse(
            success=False, message=f"Auth ok but fetch failed: {exc}"
        )
    except Exception as exc:
        logger.exception("Connector %s test_connection fetch raised", name)
        return TestResponse(
            success=False, message=f"Auth ok but fetch error: {exc}"
        )

    return TestResponse(
        success=True,
        message=f"Connection to {name} OK ({len(sample)} sample finding(s)).",
        sample=sample,
    )


@router.delete("/{name}", response_model=DeleteResponse)
async def delete_connector(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    """Remove the current tenant's credentials for this connector."""
    _ensure_known_connector(name)
    tenant_id = TenantContext.get()

    row = (
        await db.execute(
            select(TenantConnectorCredential).where(
                TenantConnectorCredential.tenant_id == tenant_id,
                TenantConnectorCredential.connector_name == name,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No credentials stored for connector '{name}'.",
        )

    await db.delete(row)
    db.add(
        AuditLog(
            user_id=current_user.id,
            action="connector_credentials_deleted",
            resource_type="connector",
            resource_id=None,
            details={"connector": name},
            tenant_id=tenant_id,
        )
    )
    await db.commit()
    return DeleteResponse(status="removed", connector=name)


@router.post("/{name}/run-now", response_model=RunNowResponse)
async def run_connector_now(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    """
    Trigger an immediate poll for this connector.  Persists each normalised
    finding as a Risk row scoped to the current tenant.

    Admin-only (ciso role) — the scheduler is the normal path; this is for
    manual "kick the tires" use after configuring credentials.
    """
    _ensure_known_connector(name)
    tenant_id = TenantContext.get()

    creds = await _load_credentials(db, tenant_id, name)
    if creds is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Connector '{name}' is not configured for this tenant. "
                "POST credentials to /configure first."
            ),
        )

    instance = _instantiate(name)
    try:
        instance.authenticate(creds)
    except ConnectorAuthError as exc:
        raise HTTPException(status_code=400, detail=f"Auth failed: {exc}") from exc

    since = datetime.now(timezone.utc) - timedelta(minutes=15)
    try:
        try:
            raw_findings = instance.fetch_findings(
                since, tenant_id=str(tenant_id)
            )
        except TypeError:
            raw_findings = instance.fetch_findings(since)
    except ConnectorFetchError as exc:
        raise HTTPException(
            status_code=502, detail=f"Upstream fetch failed: {exc}"
        ) from exc

    ingested = 0
    now = datetime.now(timezone.utc)
    for raw in raw_findings:
        try:
            record = instance.normalize(raw)
        except (KeyError, ValueError, TypeError, AttributeError):
            # L6 — narrow catch on shape errors only; let unexpected
            # exceptions propagate so we see them in the logs as a
            # genuine bug, not silent data loss.
            logger.exception("Connector %s normalize failed for %s", name, raw.id)
            continue

        # Universal Intelligence Engine enrichment + de-dup (v3 §3.4–§4.1)
        from backend.services.connector_runner import preprocess_connector_record

        existing, enriched = await preprocess_connector_record(
            db,
            tenant_id=tenant_id,
            raw=raw,
            record=record,
        )
        if existing is not None:
            ingested += 1
            continue

        sla_days = {"critical": 3, "high": 7, "medium": 30, "low": 90}.get(
            (record.severity or "low").lower(), 30
        )
        risk = Risk(
            id=uuid.uuid4(),
            risk_id=_next_risk_id(),
            finding=record.finding,
            description=record.description,
            source=record.source,
            domain=record.domain,
            cvss_score=float(enriched["cvss_score"]),
            severity=record.severity,
            asset=record.asset,
            owner_team=record.owner_team,
            status="open",
            sla_deadline=now + timedelta(days=sla_days),
            cve_id=record.cve_id,
            fingerprint_key=enriched["fingerprint_key"],
            sources_attributed=enriched["sources_attributed"],
            advisory_status=enriched["advisory_status"],
            remediation_steps=enriched["remediation_steps"],
            asset_id=enriched.get("asset_id"),
            tenant_id=tenant_id,
        )
        db.add(risk)
        ingested += 1

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="connector_run_now",
            resource_type="connector",
            resource_id=None,
            details={"connector": name, "records_ingested": ingested},
            tenant_id=tenant_id,
        )
    )
    await db.commit()

    return RunNowResponse(
        status="ok", connector=name, records_ingested=ingested
    )


@router.get("/{name}/health", response_model=HealthResponse)
async def get_connector_health(
    name: str,
    current_user: User = Depends(role_required("ciso")),
):
    """
    Return the connector's self-reported operational health.

    Note: connectors are stateless between requests in the current architecture,
    so a fresh instance reports a baseline "ok / no errors / never run" state.
    Production scheduler will eventually persist health metrics — for now the
    endpoint at least proves the connector is reachable and instantiable.
    """
    _ensure_known_connector(name)
    instance = _instantiate(name)
    try:
        h: ConnectorHealth = instance.health_check()
    except Exception as exc:
        logger.exception("Connector %s health_check raised", name)
        return HealthResponse(
            connector_name=name,
            status="error",
            last_run=None,
            error_count=1,
            last_error=str(exc),
        )
    return HealthResponse(
        connector_name=h.connector_name,
        status=h.status,
        last_run=h.last_run,
        error_count=h.error_count,
        last_error=h.last_error,
    )


@router.get("/{name}/findings", response_model=FindingsResponse)
async def list_connector_findings(
    name: str,
    limit: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    """
    Return recent findings (Risk rows) attributed to this connector for the
    current tenant.  Tenant-scoped via apply_tenant_filter.
    """
    _ensure_known_connector(name)

    # Production connectors (tenable, sentinelone, …) emit findings whose
    # `source` matches the connector name. For the `simulator` and
    # `extended_simulator` connectors, however, the normalize() output preserves
    # the realistic upstream source label (crowdstrike, easm, cnapp, …) so
    # downstream code paths see lifelike data. Filtering by `source == "simulator"`
    # would therefore return zero rows even after a successful run-now.
    #
    # We special-case the two simulator connectors by filtering on the union
    # of source labels REAL_CVES exposes — every finding produced by the
    # simulator family carries one of these labels.
    if name in ("simulator", "extended_simulator"):
        from backend.simulator import REAL_CVES
        # Include the literal connector name too — directly-seeded test data
        # (e.g. `Risk(source="simulator", ...)`) should also surface here.
        allowed_sources = list(REAL_CVES.keys()) + [name]
        source_filter = Risk.source.in_(allowed_sources)
    else:
        source_filter = Risk.source == name

    query = (
        apply_tenant_filter(select(Risk), Risk)
        .where(source_filter)
        .order_by(desc(Risk.created_at))
        .limit(limit)
    )
    rows = (await db.execute(query)).scalars().all()

    items = [
        FindingItem(
            risk_id=r.risk_id,
            finding=r.finding,
            severity=r.severity,
            cvss_score=float(r.cvss_score),
            asset=r.asset,
            cve_id=r.cve_id,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return FindingsResponse(items=items, total=len(items), limit=limit)

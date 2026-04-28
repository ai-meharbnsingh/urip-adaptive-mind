"""
HashiCorp Vault connector for URIP.

Implements the BaseConnector contract:
  authenticate   → validates token via GET /v1/auth/token/lookup-self
  fetch_findings → posture findings (audit logging, root token, auth methods, mounts, health)
  normalize      → maps posture finding code → URIPRiskRecord
  health_check   → Vault health via /v1/sys/health

This connector produces POSTURE findings, not CVE-style vulnerabilities.
Cross-reference leaked-secret findings from GHAS with Vault audit data for
a complete secrets hygiene picture.

Vault HTTP API reference: https://developer.hashicorp.com/vault/api-docs
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional


def _run_async(coro: Any) -> Any:
    """
    Run a coroutine from synchronous code.

    Uses asyncio.run() which always creates a new event loop, ensuring
    compatibility with Python 3.10+ where get_event_loop() is deprecated
    in non-async contexts and raises in 3.12+ when there is no current loop.
    """
    return asyncio.run(coro)


from connectors.base.connector import (
    BaseConnector,
    ConnectorAuthError,
    ConnectorFetchError,
    ConnectorHealth,
    ConnectorSession,
    CredentialFieldSpec,
    RawFinding,
    URIPRiskRecord,
)
from connectors.base.registry import register_connector
from connectors.base.setup_guides_data import SETUP_GUIDES
from connectors.hashicorp_vault.api_client import VaultAPIClient
from connectors.hashicorp_vault.schemas import VaultHealth

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Posture finding codes + their default severity
# ─────────────────────────────────────────────────────────────────────────────

# Maps posture finding code → severity
_FINDING_SEVERITY: dict[str, str] = {
    "VAULT-AUDIT-DISABLED":       "critical",
    "VAULT-SEALED":               "critical",
    "VAULT-NOT-INITIALIZED":      "critical",
    "VAULT-ROOT-TOKEN":           "high",
    "VAULT-USERPASS-AUTH":        "medium",
    "VAULT-KV-V1-MOUNT":          "low",
    "VAULT-PERFORMANCE-STANDBY":  "info",
}

# Maps posture finding code → human-readable title
_FINDING_TITLE: dict[str, str] = {
    "VAULT-AUDIT-DISABLED":       "Vault audit logging is disabled",
    "VAULT-SEALED":               "Vault is sealed — secrets inaccessible",
    "VAULT-NOT-INITIALIZED":      "Vault is not initialized",
    "VAULT-ROOT-TOKEN":           "Service account token has root policy",
    "VAULT-USERPASS-AUTH":        "Userpass auth method enabled (no MFA enforced)",
    "VAULT-KV-V1-MOUNT":          "KV secrets engine v1 mount detected — migrate to v2",
    "VAULT-PERFORMANCE-STANDBY":  "Vault node is performance standby (informational)",
}


# ─────────────────────────────────────────────────────────────────────────────
# Connector class
# ─────────────────────────────────────────────────────────────────────────────


@register_connector("hashicorp_vault")
class HashicorpVaultConnector(BaseConnector):
    """
    Live connector for HashiCorp Vault (Community, Enterprise, HCP Vault).

    Data flow
    ---------
    1. Authenticate via GET /v1/auth/token/lookup-self (token validation).
    2. Probe /v1/sys/health, /v1/sys/audit, /v1/sys/auth, /v1/sys/mounts.
    3. Emit posture-based RawFindings for each misconfiguration detected.
    4. Normalize each RawFinding to a URIPRiskRecord.

    Supported products
    ------------------
    - Vault Community / Enterprise (self-hosted)
    - Vault on HCP (HashiCorp Cloud Platform — managed)
    - Vault Enterprise with Namespaces (multi-tenancy)

    Auth
    ----
    Vault token (X-Vault-Token).  Read-only ACL recommended.
    For Enterprise: also supply the namespace path.

    Cross-reference
    ---------------
    Combine with GHAS connector for a full secrets hygiene picture:
    GHAS detects leaked secrets in code; Vault shows whether audit logging
    would have caught misuse.
    """

    NAME = "hashicorp_vault"
    DISPLAY_NAME = "HashiCorp Vault"
    CATEGORY = "PAM"
    STATUS = "live"
    MODULE_CODE = "IDENTITY"
    RISK_INDEX_DOMAIN = "identity"

    SHORT_DESCRIPTION = (
        "Secrets management posture — verify audit logging is on, enumerate "
        "auth methods, list policies and mounted secret engines. "
        "Cross-reference with leaked-secret findings from GHAS."
    )

    VENDOR_DOCS_URL = "https://developer.hashicorp.com/vault/api-docs"

    SUPPORTED_PRODUCTS = [
        "Vault Community / Enterprise",
        "Vault on HCP (managed)",
        "Vault Enterprise with Namespaces",
    ]

    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="vault_addr",
            label="Vault Address",
            type="url",
            required=True,
            placeholder="https://vault.your-org.com:8200",
            help_text="Full URL to your Vault instance including port.",
            pattern=r"^https?://[^\s]+$",
        ),
        CredentialFieldSpec(
            name="token",
            label="Vault Token (read-only ACL recommended)",
            type="password",
            required=True,
            secret=True,
            placeholder="hvs.CAESI…",
            help_text=(
                "Generate via: vault token create -policy=urip-readonly -period=720h"
            ),
        ),
        CredentialFieldSpec(
            name="namespace",
            label="Namespace (Vault Enterprise only — leave blank for Community)",
            type="text",
            required=False,
            default="",
            placeholder="admin/teamA",
            help_text=(
                "Vault Enterprise namespace path. "
                "Leave blank for Vault Community or HCP Vault (root namespace)."
            ),
        ),
    ]

    SETUP_GUIDE = SETUP_GUIDES.get("hashicorp_vault")

    # ─────────────────────────────────────────────────────────────────────────
    # Constructor
    # ─────────────────────────────────────────────────────────────────────────

    def __init__(self) -> None:
        self._client: VaultAPIClient | None = None
        self._vault_addr: str = ""
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    # ─────────────────────────────────────────────────────────────────────────
    # BaseConnector contract
    # ─────────────────────────────────────────────────────────────────────────

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate Vault token by calling GET /v1/auth/token/lookup-self.

        Required credential keys:
            - vault_addr  : Vault instance URL
            - token       : Vault token

        Optional credential keys:
            - namespace   : Vault Enterprise namespace path

        Returns
        -------
        ConnectorSession
            Session with token field set to "vault-token-****".

        Raises
        ------
        ConnectorAuthError
            If credentials are missing or Vault rejects the token.
        """
        vault_addr = tenant_credentials.get("vault_addr", "").strip()
        token = tenant_credentials.get("token", "").strip()
        namespace = tenant_credentials.get("namespace", "").strip()

        if not vault_addr:
            raise ConnectorAuthError(
                "HashiCorp Vault credentials must include 'vault_addr'."
            )
        if not token:
            raise ConnectorAuthError(
                "HashiCorp Vault credentials must include 'token'."
            )

        self._vault_addr = vault_addr

        self._client = VaultAPIClient(
            vault_addr=vault_addr,
            token=token,
            namespace=namespace or None,
        )

        # Verify token by calling lookup-self.
        try:
            token_info = _run_async(self._client.get_token_info())
        except ConnectorAuthError:
            raise
        except Exception as exc:
            raise ConnectorAuthError(
                f"HashiCorp Vault authentication probe failed: {exc}"
            ) from exc

        token_data = token_info.get("data", {})
        display_name = token_data.get("display_name", "unknown")
        logger.info(
            "HashiCorp Vault authenticated: display_name=%s vault_addr=%s",
            display_name,
            vault_addr,
        )

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token="vault-token-****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
            extra={
                "display_name": display_name,
                "vault_addr": vault_addr,
                "namespace": namespace,
            },
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Probe Vault posture and return a finding for each misconfiguration.

        Posture checks performed:
          1. Health (sealed / not-initialized)
          2. Audit devices (audit logging enabled?)
          3. Token policies (root policy?)
          4. Auth methods (userpass without MFA?)
          5. Secret engine mounts (KV v1 still in use?)

        Parameters
        ----------
        since : datetime
            Ignored for posture connectors — full scan every run.
        tenant_id : str, optional
            Scoped into RawFinding.tenant_id.

        Returns
        -------
        list[RawFinding]
        """
        if self._client is None:
            raise ConnectorFetchError(
                "HashiCorp Vault connector not authenticated. "
                "Call authenticate() first."
            )

        tenant_id: str = kwargs.get("tenant_id", "unknown")
        findings: list[RawFinding] = []

        try:
            # ── 1. Health check ────────────────────────────────────────────
            health_raw = _run_async(self._client.healthcheck())
            health = VaultHealth.model_validate(health_raw)
            fetched_at = datetime.now(timezone.utc)

            if not health.initialized:
                findings.append(self._make_raw_finding(
                    code="VAULT-NOT-INITIALIZED",
                    extra=health_raw,
                    tenant_id=tenant_id,
                    fetched_at=fetched_at,
                ))
            elif health.sealed:
                findings.append(self._make_raw_finding(
                    code="VAULT-SEALED",
                    extra=health_raw,
                    tenant_id=tenant_id,
                    fetched_at=fetched_at,
                ))
            elif health.performance_standby:
                findings.append(self._make_raw_finding(
                    code="VAULT-PERFORMANCE-STANDBY",
                    extra=health_raw,
                    tenant_id=tenant_id,
                    fetched_at=fetched_at,
                ))

            # If Vault is sealed or not initialized, skip further probes.
            if not health.initialized or health.sealed:
                self._last_run = fetched_at
                return findings

            # ── 2. Audit devices ───────────────────────────────────────────
            audit_raw = _run_async(self._client.list_audit_devices())
            # Vault returns an empty dict when no audit devices are configured.
            # Filter out the "request_id" / "lease_id" Vault envelope keys —
            # audit device paths always end with "/".
            audit_devices = {
                k: v for k, v in audit_raw.items()
                if isinstance(v, dict) and k.endswith("/")
            }
            if not audit_devices:
                findings.append(self._make_raw_finding(
                    code="VAULT-AUDIT-DISABLED",
                    extra={"audit_raw": audit_raw},
                    tenant_id=tenant_id,
                    fetched_at=fetched_at,
                ))

            # ── 3. Token self-inspection (root policy?) ────────────────────
            token_raw = _run_async(self._client.get_token_info())
            token_data = token_raw.get("data", {})
            policies: list[str] = token_data.get("policies", [])
            if "root" in policies:
                findings.append(self._make_raw_finding(
                    code="VAULT-ROOT-TOKEN",
                    extra={"policies": policies},
                    tenant_id=tenant_id,
                    fetched_at=fetched_at,
                ))

            # ── 4. Auth methods (userpass without MFA) ─────────────────────
            auth_raw = _run_async(self._client.list_auth_methods())
            for path, method_info in auth_raw.items():
                if not isinstance(method_info, dict):
                    continue
                method_type = method_info.get("type", "")
                if method_type == "userpass":
                    findings.append(self._make_raw_finding(
                        code="VAULT-USERPASS-AUTH",
                        extra={
                            "auth_method_path": path,
                            "auth_method_type": method_type,
                            "auth_method_info": method_info,
                        },
                        tenant_id=tenant_id,
                        fetched_at=fetched_at,
                    ))
                    break  # one finding per connector run is sufficient

            # ── 5. Secret engines (KV v1 mounts) ──────────────────────────
            mounts_raw = _run_async(self._client.list_secret_engines())
            for path, mount_info in mounts_raw.items():
                if not isinstance(mount_info, dict):
                    continue
                mount_type = mount_info.get("type", "")
                options = mount_info.get("options") or {}
                kv_version = options.get("version", "")
                if mount_type == "kv" and kv_version == "1":
                    findings.append(self._make_raw_finding(
                        code="VAULT-KV-V1-MOUNT",
                        extra={
                            "mount_path": path,
                            "mount_type": mount_type,
                            "options": options,
                        },
                        tenant_id=tenant_id,
                        fetched_at=fetched_at,
                    ))

            self._last_run = fetched_at
            logger.info(
                "HashiCorp Vault: %d posture findings for tenant %s (vault=%s)",
                len(findings),
                tenant_id,
                self._vault_addr,
            )
            return findings

        except (ConnectorAuthError, ConnectorFetchError):
            raise
        except Exception as exc:
            self._error_count += 1
            msg = str(exc)
            self._last_error = msg
            logger.exception("HashiCorp Vault fetch_findings failed")
            raise ConnectorFetchError(
                f"HashiCorp Vault fetch_findings failed: {msg}"
            ) from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map a HashiCorp Vault posture RawFinding to a URIPRiskRecord.

        The external_id is the posture finding code (e.g. "VAULT-AUDIT-DISABLED").
        source_url points to the Vault admin UI.
        """
        raw_data = raw.raw_data
        code: str = raw_data.get("finding_code", "VAULT-UNKNOWN")
        title: str = _FINDING_TITLE.get(code, f"Vault posture issue: {code}")
        severity: str = _FINDING_SEVERITY.get(code, "medium")

        # Skip "info" severity — URIPRiskRecord only supports critical/high/medium/low.
        # Downgrade info → low for storage purposes.
        if severity == "info":
            severity = "low"

        source_url = f"{self._vault_addr}/ui/" if self._vault_addr else None

        description = (
            f"HashiCorp Vault posture finding [{code}]: {title}. "
            f"Vault address: {self._vault_addr or 'unknown'}. "
            f"Admin UI: {source_url or 'N/A'}."
        )

        # Enrich description with extra context from raw_data.
        extra = {k: v for k, v in raw_data.items() if k != "finding_code"}
        if extra:
            # Append first 300 chars of extra context.
            import json as _json
            extra_str = _json.dumps(extra, default=str)[:300]
            description += f" Context: {extra_str}"

        return URIPRiskRecord(
            finding=title,
            description=description,
            source=self.NAME,
            domain="identity",
            cvss_score=0.0,
            severity=severity,
            asset=self._vault_addr or "vault",
            owner_team="Security Engineering",
            cve_id=None,
            exploit_status=None,
        )

    def health_check(self) -> ConnectorHealth:
        """Return connector operational status via /v1/sys/health."""
        if self._client is None:
            return ConnectorHealth(
                connector_name=self.NAME,
                status="ok",
                last_run=None,
                error_count=0,
                last_error=None,
            )

        try:
            health_raw = _run_async(self._client.healthcheck())
            vault_status = health_raw.get("urip_health_status", "unknown")

            if vault_status == "healthy":
                status = "ok" if self._error_count == 0 else (
                    "degraded" if self._error_count < 5 else "error"
                )
            elif vault_status == "degraded":
                status = "degraded"
            else:
                # critical or unknown → error
                status = "error"

            return ConnectorHealth(
                connector_name=self.NAME,
                status=status,
                last_run=self._last_run,
                error_count=self._error_count,
                last_error=self._last_error,
            )
        except Exception as exc:
            return ConnectorHealth(
                connector_name=self.NAME,
                status="degraded",
                last_run=self._last_run,
                error_count=self._error_count + 1,
                last_error=str(exc),
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _make_raw_finding(
        code: str,
        extra: dict[str, Any],
        tenant_id: str,
        fetched_at: datetime,
    ) -> RawFinding:
        """Build a RawFinding for a posture finding code."""
        return RawFinding(
            id=f"hashicorp_vault:{code}",
            source="hashicorp_vault",
            raw_data={"finding_code": code, **extra},
            fetched_at=fetched_at,
            tenant_id=tenant_id,
        )

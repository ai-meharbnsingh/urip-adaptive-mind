"""
TDD tests for the HashiCorp Vault live connector.

Uses respx to mock all HTTP traffic — no real API calls.

Coverage (14 tests):
  1.  test_register
  2.  test_authenticate_valid               (X-Vault-Token header verified)
  3.  test_authenticate_with_namespace      (X-Vault-Namespace header)
  4.  test_authenticate_invalid_token       (403 → ConnectorAuthError)
  5.  test_health_sealed_returns_critical_finding
  6.  test_health_uninitialized_returns_critical_finding
  7.  test_health_standby_treated_as_healthy (HTTP 429 → ok)
  8.  test_health_performance_standby_treated_as_healthy (HTTP 473 → ok)
  9.  test_audit_disabled_produces_critical_finding
  10. test_root_policy_token_produces_high_finding
  11. test_userpass_auth_method_produces_medium_finding
  12. test_kv_v1_mount_produces_low_finding
  13. test_health_check_ok
  14. test_credential_secrets_marked
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
import respx

from connectors.base.connector import (
    ConnectorAuthError,
    ConnectorFetchError,
    ConnectorHealth,
    ConnectorSession,
    CredentialFieldSpec,
    RawFinding,
    URIPRiskRecord,
)
from connectors.base.registry import _global_registry
from connectors.hashicorp_vault.connector import HashicorpVaultConnector

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

VAULT_ADDR = "https://vault.test.example.com:8200"
VAULT_TOKEN = "hvs.TEST_TOKEN_ABCD1234"
VAULT_NS = "admin/teamA"


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def connector() -> HashicorpVaultConnector:
    return HashicorpVaultConnector()


@pytest.fixture
def valid_creds() -> dict[str, str]:
    return {
        "vault_addr": VAULT_ADDR,
        "token": VAULT_TOKEN,
        "namespace": "",
        "tenant_id": "tenant-vault-test",
    }


@pytest.fixture
def enterprise_creds() -> dict[str, str]:
    return {
        "vault_addr": VAULT_ADDR,
        "token": VAULT_TOKEN,
        "namespace": VAULT_NS,
        "tenant_id": "tenant-vault-enterprise",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Response helpers
# ─────────────────────────────────────────────────────────────────────────────


def _token_lookup_self(
    display_name: str = "urip-posture-scanner",
    policies: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "data": {
            "display_name": display_name,
            "policies": policies or ["default", "urip-readonly"],
            "accessor": "test-accessor-id",
            "ttl": 2591999,
            "renewable": True,
        }
    }


def _health_response(
    initialized: bool = True,
    sealed: bool = False,
    standby: bool = False,
    performance_standby: bool = False,
    version: str = "1.15.0",
) -> dict[str, Any]:
    return {
        "initialized": initialized,
        "sealed": sealed,
        "standby": standby,
        "performance_standby": performance_standby,
        "replication_performance_mode": "disabled",
        "replication_dr_mode": "disabled",
        "server_time_utc": 1714291200,
        "version": version,
        "cluster_name": "vault-cluster-test",
    }


def _audit_response_with_devices() -> dict[str, Any]:
    return {
        "file/": {
            "type": "file",
            "path": "file/",
            "description": "File audit device",
            "options": {"file_path": "/var/log/vault/audit.log"},
        }
    }


def _audit_response_empty() -> dict[str, Any]:
    # Vault returns an object with no audit-device keys (only envelope keys)
    return {"request_id": "abc-123", "lease_id": "", "renewable": False, "data": {}}


def _auth_methods_with_userpass() -> dict[str, Any]:
    return {
        "token/": {
            "type": "token",
            "accessor": "auth_token_xxx",
            "description": "token based credentials",
        },
        "userpass/": {
            "type": "userpass",
            "accessor": "auth_userpass_yyy",
            "description": "username and password credentials",
        },
    }


def _auth_methods_no_userpass() -> dict[str, Any]:
    return {
        "token/": {
            "type": "token",
            "accessor": "auth_token_xxx",
            "description": "token based credentials",
        },
        "approle/": {
            "type": "approle",
            "accessor": "auth_approle_zzz",
            "description": "approle credentials",
        },
    }


def _mounts_with_kv_v1() -> dict[str, Any]:
    return {
        "secret/": {
            "type": "kv",
            "description": "KV v1 legacy",
            "options": {"version": "1"},
        },
        "kv/": {
            "type": "kv",
            "description": "KV v2 secrets",
            "options": {"version": "2"},
        },
        "sys/": {
            "type": "system",
            "description": "system endpoint",
            "options": {},
        },
    }


def _mounts_no_kv_v1() -> dict[str, Any]:
    return {
        "kv/": {
            "type": "kv",
            "description": "KV v2 secrets",
            "options": {"version": "2"},
        },
        "pki/": {
            "type": "pki",
            "description": "PKI secrets",
            "options": {},
        },
    }


def _policies_response() -> dict[str, Any]:
    return {
        "keys": ["default", "urip-readonly"],
        "policies": ["default", "urip-readonly"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — mock all standard endpoints for a "clean" Vault
# ─────────────────────────────────────────────────────────────────────────────


def _mock_clean_vault(addr: str = VAULT_ADDR) -> None:
    """Mock all Vault endpoints so connector runs without findings."""
    respx.get(f"{addr}/v1/sys/health").mock(
        return_value=httpx.Response(200, json=_health_response())
    )
    respx.get(f"{addr}/v1/auth/token/lookup-self").mock(
        return_value=httpx.Response(200, json=_token_lookup_self())
    )
    respx.get(f"{addr}/v1/sys/audit").mock(
        return_value=httpx.Response(200, json=_audit_response_with_devices())
    )
    respx.get(f"{addr}/v1/sys/auth").mock(
        return_value=httpx.Response(200, json=_auth_methods_no_userpass())
    )
    respx.get(f"{addr}/v1/sys/mounts").mock(
        return_value=httpx.Response(200, json=_mounts_no_kv_v1())
    )
    respx.get(f"{addr}/v1/sys/policies/acl").mock(
        return_value=httpx.Response(200, json=_policies_response())
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Registration
# ─────────────────────────────────────────────────────────────────────────────


class TestHashicorpVaultRegistration:
    def test_register(self) -> None:
        """HashicorpVaultConnector must be registered under 'hashicorp_vault'."""
        assert "hashicorp_vault" in _global_registry
        factory = _global_registry.get("hashicorp_vault")
        instance = factory()
        assert isinstance(instance, HashicorpVaultConnector)

    def test_metadata(self) -> None:
        """Catalog metadata must be populated correctly."""
        assert HashicorpVaultConnector.NAME == "hashicorp_vault"
        assert HashicorpVaultConnector.DISPLAY_NAME == "HashiCorp Vault"
        assert HashicorpVaultConnector.CATEGORY == "PAM"
        assert HashicorpVaultConnector.STATUS == "live"
        assert HashicorpVaultConnector.MODULE_CODE == "IDENTITY"
        assert HashicorpVaultConnector.RISK_INDEX_DOMAIN == "identity"
        assert "Vault Community / Enterprise" in (
            HashicorpVaultConnector.SUPPORTED_PRODUCTS or []
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Authentication — valid token
# ─────────────────────────────────────────────────────────────────────────────


class TestHashicorpVaultAuthenticate:
    @respx.mock
    def test_authenticate_valid(
        self, connector: HashicorpVaultConnector, valid_creds: dict
    ) -> None:
        """Valid token — X-Vault-Token header must be set; ConnectorSession returned."""
        route = respx.get(f"{VAULT_ADDR}/v1/auth/token/lookup-self").mock(
            return_value=httpx.Response(200, json=_token_lookup_self())
        )

        session = connector.authenticate(valid_creds)

        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "hashicorp_vault"
        assert session.tenant_id == "tenant-vault-test"
        assert session.token == "vault-token-****"
        assert route.called

        # Verify X-Vault-Token header was sent.
        sent_request = route.calls[0].request
        assert sent_request.headers.get("x-vault-token") == VAULT_TOKEN, (
            f"Expected X-Vault-Token={VAULT_TOKEN!r}, "
            f"got {sent_request.headers.get('x-vault-token')!r}"
        )

    @respx.mock
    def test_authenticate_with_namespace(
        self, connector: HashicorpVaultConnector, enterprise_creds: dict
    ) -> None:
        """Enterprise namespace — X-Vault-Namespace header must be set."""
        route = respx.get(f"{VAULT_ADDR}/v1/auth/token/lookup-self").mock(
            return_value=httpx.Response(200, json=_token_lookup_self())
        )

        session = connector.authenticate(enterprise_creds)

        assert isinstance(session, ConnectorSession)
        assert route.called

        sent_request = route.calls[0].request
        assert sent_request.headers.get("x-vault-namespace") == VAULT_NS, (
            f"Expected X-Vault-Namespace={VAULT_NS!r}, "
            f"got {sent_request.headers.get('x-vault-namespace')!r}"
        )

    @respx.mock
    def test_authenticate_invalid_token(
        self, connector: HashicorpVaultConnector, valid_creds: dict
    ) -> None:
        """403 from Vault must raise ConnectorAuthError."""
        respx.get(f"{VAULT_ADDR}/v1/auth/token/lookup-self").mock(
            return_value=httpx.Response(
                403, json={"errors": ["permission denied"]}
            )
        )

        with pytest.raises(ConnectorAuthError):
            connector.authenticate(valid_creds)

    def test_authenticate_missing_vault_addr_raises(
        self, connector: HashicorpVaultConnector
    ) -> None:
        with pytest.raises(ConnectorAuthError, match="vault_addr"):
            connector.authenticate({"token": VAULT_TOKEN})

    def test_authenticate_missing_token_raises(
        self, connector: HashicorpVaultConnector
    ) -> None:
        with pytest.raises(ConnectorAuthError, match="token"):
            connector.authenticate({"vault_addr": VAULT_ADDR})


# ─────────────────────────────────────────────────────────────────────────────
# 3. fetch_findings — health-based critical findings
# ─────────────────────────────────────────────────────────────────────────────


class TestHashicorpVaultHealthFindings:
    @respx.mock
    def test_health_sealed_returns_critical_finding(
        self, connector: HashicorpVaultConnector, valid_creds: dict
    ) -> None:
        """Sealed Vault must produce a VAULT-SEALED critical finding."""
        # authenticate
        respx.get(f"{VAULT_ADDR}/v1/auth/token/lookup-self").mock(
            return_value=httpx.Response(200, json=_token_lookup_self())
        )
        # health endpoint returns 503 (sealed)
        respx.get(f"{VAULT_ADDR}/v1/sys/health").mock(
            return_value=httpx.Response(
                503, json=_health_response(initialized=True, sealed=True)
            )
        )

        connector.authenticate(valid_creds)
        findings = connector.fetch_findings(
            since=datetime.now(timezone.utc),
            tenant_id="tenant-vault-test",
        )

        assert len(findings) >= 1
        codes = [f.raw_data.get("finding_code") for f in findings]
        assert "VAULT-SEALED" in codes, f"Expected VAULT-SEALED in {codes}"

        # Normalize to check severity
        record = connector.normalize(findings[codes.index("VAULT-SEALED")])
        assert isinstance(record, URIPRiskRecord)
        assert record.severity == "critical"
        assert record.source == "hashicorp_vault"
        assert record.domain == "identity"

    @respx.mock
    def test_health_uninitialized_returns_critical_finding(
        self, connector: HashicorpVaultConnector, valid_creds: dict
    ) -> None:
        """Not-initialized Vault must produce a VAULT-NOT-INITIALIZED critical finding."""
        respx.get(f"{VAULT_ADDR}/v1/auth/token/lookup-self").mock(
            return_value=httpx.Response(200, json=_token_lookup_self())
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/health").mock(
            return_value=httpx.Response(
                501, json={"initialized": False, "sealed": True}
            )
        )

        connector.authenticate(valid_creds)
        findings = connector.fetch_findings(
            since=datetime.now(timezone.utc),
            tenant_id="tenant-vault-test",
        )

        codes = [f.raw_data.get("finding_code") for f in findings]
        assert "VAULT-NOT-INITIALIZED" in codes, f"Expected VAULT-NOT-INITIALIZED in {codes}"

        record = connector.normalize(findings[0])
        assert record.severity == "critical"

    @respx.mock
    def test_health_standby_treated_as_healthy(
        self, connector: HashicorpVaultConnector, valid_creds: dict
    ) -> None:
        """
        HTTP 429 from /sys/health = standby node = healthy.
        The connector should NOT produce a VAULT-SEALED or VAULT-NOT-INITIALIZED finding.
        """
        respx.get(f"{VAULT_ADDR}/v1/auth/token/lookup-self").mock(
            return_value=httpx.Response(200, json=_token_lookup_self())
        )
        # 429 = standby — VaultAPIClient.healthcheck() must treat this as healthy
        respx.get(f"{VAULT_ADDR}/v1/sys/health").mock(
            return_value=httpx.Response(
                429,
                json=_health_response(initialized=True, sealed=False, standby=True),
            )
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/audit").mock(
            return_value=httpx.Response(200, json=_audit_response_with_devices())
        )
        respx.get(f"{VAULT_ADDR}/v1/auth/token/lookup-self").mock(
            return_value=httpx.Response(200, json=_token_lookup_self())
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/auth").mock(
            return_value=httpx.Response(200, json=_auth_methods_no_userpass())
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/mounts").mock(
            return_value=httpx.Response(200, json=_mounts_no_kv_v1())
        )

        connector.authenticate(valid_creds)
        findings = connector.fetch_findings(
            since=datetime.now(timezone.utc),
            tenant_id="tenant-vault-test",
        )

        codes = [f.raw_data.get("finding_code") for f in findings]
        assert "VAULT-SEALED" not in codes
        assert "VAULT-NOT-INITIALIZED" not in codes

    @respx.mock
    def test_health_performance_standby_treated_as_healthy(
        self, connector: HashicorpVaultConnector, valid_creds: dict
    ) -> None:
        """
        HTTP 473 from /sys/health = performance standby = healthy.
        Connector may emit VAULT-PERFORMANCE-STANDBY (info/low) but not critical.
        """
        respx.get(f"{VAULT_ADDR}/v1/auth/token/lookup-self").mock(
            return_value=httpx.Response(200, json=_token_lookup_self())
        )
        # 473 = performance standby
        respx.get(f"{VAULT_ADDR}/v1/sys/health").mock(
            return_value=httpx.Response(
                473,
                json=_health_response(
                    initialized=True,
                    sealed=False,
                    standby=True,
                    performance_standby=True,
                ),
            )
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/audit").mock(
            return_value=httpx.Response(200, json=_audit_response_with_devices())
        )
        respx.get(f"{VAULT_ADDR}/v1/auth/token/lookup-self").mock(
            return_value=httpx.Response(200, json=_token_lookup_self())
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/auth").mock(
            return_value=httpx.Response(200, json=_auth_methods_no_userpass())
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/mounts").mock(
            return_value=httpx.Response(200, json=_mounts_no_kv_v1())
        )

        connector.authenticate(valid_creds)
        findings = connector.fetch_findings(
            since=datetime.now(timezone.utc),
            tenant_id="tenant-vault-test",
        )

        codes = [f.raw_data.get("finding_code") for f in findings]
        assert "VAULT-SEALED" not in codes
        assert "VAULT-NOT-INITIALIZED" not in codes
        # If performance standby finding is emitted, its severity should be low (not critical)
        if "VAULT-PERFORMANCE-STANDBY" in codes:
            idx = codes.index("VAULT-PERFORMANCE-STANDBY")
            record = connector.normalize(findings[idx])
            assert record.severity in ("low", "info"), (
                f"performance standby severity should be low/info, got {record.severity}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 4. fetch_findings — posture checks
# ─────────────────────────────────────────────────────────────────────────────


class TestHashicorpVaultPostureFindings:
    @respx.mock
    def test_audit_disabled_produces_critical_finding(
        self, connector: HashicorpVaultConnector, valid_creds: dict
    ) -> None:
        """Empty /sys/audit response must produce VAULT-AUDIT-DISABLED (critical)."""
        respx.get(f"{VAULT_ADDR}/v1/auth/token/lookup-self").mock(
            return_value=httpx.Response(200, json=_token_lookup_self())
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/health").mock(
            return_value=httpx.Response(200, json=_health_response())
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/audit").mock(
            return_value=httpx.Response(200, json=_audit_response_empty())
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/auth").mock(
            return_value=httpx.Response(200, json=_auth_methods_no_userpass())
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/mounts").mock(
            return_value=httpx.Response(200, json=_mounts_no_kv_v1())
        )

        connector.authenticate(valid_creds)
        findings = connector.fetch_findings(
            since=datetime.now(timezone.utc),
            tenant_id="tenant-vault-test",
        )

        codes = [f.raw_data.get("finding_code") for f in findings]
        assert "VAULT-AUDIT-DISABLED" in codes, f"Expected VAULT-AUDIT-DISABLED in {codes}"

        idx = codes.index("VAULT-AUDIT-DISABLED")
        record = connector.normalize(findings[idx])
        assert record.severity == "critical"
        assert record.source == "hashicorp_vault"

    @respx.mock
    def test_root_policy_token_produces_high_finding(
        self, connector: HashicorpVaultConnector, valid_creds: dict
    ) -> None:
        """Token with 'root' policy must produce VAULT-ROOT-TOKEN (high)."""
        # First lookup-self call (authenticate) — succeeds
        # Second lookup-self call (fetch_findings) — root policy
        respx.get(f"{VAULT_ADDR}/v1/auth/token/lookup-self").mock(
            side_effect=[
                httpx.Response(200, json=_token_lookup_self()),
                httpx.Response(200, json=_token_lookup_self(policies=["root"])),
            ]
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/health").mock(
            return_value=httpx.Response(200, json=_health_response())
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/audit").mock(
            return_value=httpx.Response(200, json=_audit_response_with_devices())
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/auth").mock(
            return_value=httpx.Response(200, json=_auth_methods_no_userpass())
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/mounts").mock(
            return_value=httpx.Response(200, json=_mounts_no_kv_v1())
        )

        connector.authenticate(valid_creds)
        findings = connector.fetch_findings(
            since=datetime.now(timezone.utc),
            tenant_id="tenant-vault-test",
        )

        codes = [f.raw_data.get("finding_code") for f in findings]
        assert "VAULT-ROOT-TOKEN" in codes, f"Expected VAULT-ROOT-TOKEN in {codes}"

        idx = codes.index("VAULT-ROOT-TOKEN")
        record = connector.normalize(findings[idx])
        assert record.severity == "high"

    @respx.mock
    def test_userpass_auth_method_produces_medium_finding(
        self, connector: HashicorpVaultConnector, valid_creds: dict
    ) -> None:
        """userpass auth method enabled must produce VAULT-USERPASS-AUTH (medium)."""
        respx.get(f"{VAULT_ADDR}/v1/auth/token/lookup-self").mock(
            return_value=httpx.Response(200, json=_token_lookup_self())
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/health").mock(
            return_value=httpx.Response(200, json=_health_response())
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/audit").mock(
            return_value=httpx.Response(200, json=_audit_response_with_devices())
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/auth").mock(
            return_value=httpx.Response(200, json=_auth_methods_with_userpass())
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/mounts").mock(
            return_value=httpx.Response(200, json=_mounts_no_kv_v1())
        )

        connector.authenticate(valid_creds)
        findings = connector.fetch_findings(
            since=datetime.now(timezone.utc),
            tenant_id="tenant-vault-test",
        )

        codes = [f.raw_data.get("finding_code") for f in findings]
        assert "VAULT-USERPASS-AUTH" in codes, f"Expected VAULT-USERPASS-AUTH in {codes}"

        idx = codes.index("VAULT-USERPASS-AUTH")
        record = connector.normalize(findings[idx])
        assert record.severity == "medium"

    @respx.mock
    def test_kv_v1_mount_produces_low_finding(
        self, connector: HashicorpVaultConnector, valid_creds: dict
    ) -> None:
        """KV v1 secret engine mount must produce VAULT-KV-V1-MOUNT (low)."""
        respx.get(f"{VAULT_ADDR}/v1/auth/token/lookup-self").mock(
            return_value=httpx.Response(200, json=_token_lookup_self())
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/health").mock(
            return_value=httpx.Response(200, json=_health_response())
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/audit").mock(
            return_value=httpx.Response(200, json=_audit_response_with_devices())
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/auth").mock(
            return_value=httpx.Response(200, json=_auth_methods_no_userpass())
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/mounts").mock(
            return_value=httpx.Response(200, json=_mounts_with_kv_v1())
        )

        connector.authenticate(valid_creds)
        findings = connector.fetch_findings(
            since=datetime.now(timezone.utc),
            tenant_id="tenant-vault-test",
        )

        codes = [f.raw_data.get("finding_code") for f in findings]
        assert "VAULT-KV-V1-MOUNT" in codes, f"Expected VAULT-KV-V1-MOUNT in {codes}"

        idx = codes.index("VAULT-KV-V1-MOUNT")
        record = connector.normalize(findings[idx])
        assert record.severity == "low"


# ─────────────────────────────────────────────────────────────────────────────
# 5. health_check
# ─────────────────────────────────────────────────────────────────────────────


class TestHashicorpVaultHealthCheck:
    def test_health_check_ok_before_authenticate(
        self, connector: HashicorpVaultConnector
    ) -> None:
        """Fresh connector (not authenticated) should return ok with error_count=0."""
        health = connector.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.connector_name == "hashicorp_vault"
        assert health.status == "ok"
        assert health.error_count == 0
        assert health.last_run is None

    @respx.mock
    def test_health_check_ok(
        self, connector: HashicorpVaultConnector, valid_creds: dict
    ) -> None:
        """Healthy Vault node should produce health_check status=ok."""
        respx.get(f"{VAULT_ADDR}/v1/auth/token/lookup-self").mock(
            return_value=httpx.Response(200, json=_token_lookup_self())
        )
        respx.get(f"{VAULT_ADDR}/v1/sys/health").mock(
            return_value=httpx.Response(200, json=_health_response())
        )

        connector.authenticate(valid_creds)
        health = connector.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.status == "ok"
        assert health.connector_name == "hashicorp_vault"


# ─────────────────────────────────────────────────────────────────────────────
# 6. Credential field contract
# ─────────────────────────────────────────────────────────────────────────────


class TestHashicorpVaultCredentialFields:
    def test_credential_secrets_marked(self) -> None:
        """The 'token' field must be marked secret=True."""
        field_map: dict[str, CredentialFieldSpec] = {
            f.name: f for f in HashicorpVaultConnector.CREDENTIAL_FIELDS
        }

        assert "vault_addr" in field_map, "vault_addr field missing"
        assert "token" in field_map, "token field missing"
        assert "namespace" in field_map, "namespace field missing"

        # token must be a secret (rendered as password input)
        assert field_map["token"].secret is True, (
            "token credential field must have secret=True"
        )
        assert field_map["token"].required is True

        # vault_addr must be required
        assert field_map["vault_addr"].required is True

        # namespace is optional (Community edition)
        assert field_map["namespace"].required is False

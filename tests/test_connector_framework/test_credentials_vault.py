"""
TDD tests for P1.6 — CredentialsVault (Fernet-encrypted credential storage).

Covers:
- Encrypt/decrypt round-trip: what goes in comes out exactly
- Tenant isolation: tenant A's credentials cannot be decrypted with tenant B's key slot
- Key required: no encryption without a valid Fernet key
- store() / retrieve() / delete() operations on the vault helper
- DB-layer: TenantConnectorCredential model has expected columns
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from connectors.base.credentials_vault import CredentialsVault


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def fernet_key() -> str:
    """Generate a fresh Fernet key for each test."""
    return Fernet.generate_key().decode()


@pytest.fixture
def vault(fernet_key: str) -> CredentialsVault:
    return CredentialsVault(fernet_key=fernet_key)


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Encrypt / Decrypt round-trip
# ─────────────────────────────────────────────────────────────────────────────

class TestEncryptDecryptRoundTrip:
    def test_roundtrip_simple_dict(self, vault: CredentialsVault):
        """Encrypt then decrypt returns identical dict."""
        creds = {"api_key": "secret-key-123", "region": "us-east-1"}
        cipher = vault.encrypt(creds)
        recovered = vault.decrypt(cipher)
        assert recovered == creds

    def test_roundtrip_complex_dict(self, vault: CredentialsVault):
        creds = {
            "client_id": str(uuid.uuid4()),
            "client_secret": "abc!@#XYZ",
            "tenant_id": str(uuid.uuid4()),
            "scopes": ["read", "write"],
            "nested": {"host": "api.example.com", "port": 443},
        }
        cipher = vault.encrypt(creds)
        recovered = vault.decrypt(cipher)
        assert recovered == creds

    def test_encrypt_produces_bytes(self, vault: CredentialsVault):
        cipher = vault.encrypt({"k": "v"})
        assert isinstance(cipher, bytes)

    def test_encrypt_is_nondeterministic(self, vault: CredentialsVault):
        """Fernet includes a timestamp + random IV — same input → different ciphertext."""
        creds = {"k": "v"}
        c1 = vault.encrypt(creds)
        c2 = vault.encrypt(creds)
        assert c1 != c2  # probabilistic but overwhelmingly true for Fernet

    def test_ciphertext_is_not_plaintext(self, vault: CredentialsVault):
        creds = {"secret": "do-not-expose"}
        cipher = vault.encrypt(creds)
        assert b"do-not-expose" not in cipher

    def test_decrypt_wrong_key_raises(self, fernet_key: str):
        vault_a = CredentialsVault(fernet_key=fernet_key)
        vault_b = CredentialsVault(fernet_key=Fernet.generate_key().decode())
        cipher = vault_a.encrypt({"data": "secret"})
        with pytest.raises(Exception):  # cryptography.fernet.InvalidToken or wrapped
            vault_b.decrypt(cipher)

    def test_decrypt_tampered_ciphertext_raises(self, vault: CredentialsVault):
        cipher = vault.encrypt({"data": "secret"})
        tampered = cipher[:-4] + b"XXXX"
        with pytest.raises(Exception):
            vault.decrypt(tampered)

    def test_missing_key_raises_on_construction(self):
        with pytest.raises((ValueError, TypeError)):
            CredentialsVault(fernet_key=None)  # type: ignore[arg-type]

    def test_empty_string_key_raises_on_construction(self):
        with pytest.raises((ValueError, Exception)):
            CredentialsVault(fernet_key="")

    def test_invalid_key_raises_on_construction(self):
        with pytest.raises(Exception):
            CredentialsVault(fernet_key="not-a-valid-fernet-key")


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Tenant isolation (store/retrieve with tenant_id + connector_name key)
# ─────────────────────────────────────────────────────────────────────────────

class TestTenantIsolation:
    def test_store_and_retrieve_returns_correct_credentials(self, vault: CredentialsVault):
        tenant_id = str(uuid.uuid4())
        creds = {"api_key": "MY-SECRET-KEY"}
        vault.store_in_memory(tenant_id=tenant_id, connector_name="tenable", credentials=creds)
        retrieved = vault.retrieve_from_memory(tenant_id=tenant_id, connector_name="tenable")
        assert retrieved == creds

    def test_different_tenants_get_different_credentials(self, vault: CredentialsVault):
        tenant_a = str(uuid.uuid4())
        tenant_b = str(uuid.uuid4())
        creds_a = {"api_key": "KEY-A"}
        creds_b = {"api_key": "KEY-B"}

        vault.store_in_memory(tenant_id=tenant_a, connector_name="sentinelone", credentials=creds_a)
        vault.store_in_memory(tenant_id=tenant_b, connector_name="sentinelone", credentials=creds_b)

        assert vault.retrieve_from_memory(tenant_id=tenant_a, connector_name="sentinelone") == creds_a
        assert vault.retrieve_from_memory(tenant_id=tenant_b, connector_name="sentinelone") == creds_b
        assert vault.retrieve_from_memory(tenant_id=tenant_a, connector_name="sentinelone") != creds_b

    def test_retrieve_nonexistent_returns_none(self, vault: CredentialsVault):
        result = vault.retrieve_from_memory(
            tenant_id=str(uuid.uuid4()),
            connector_name="nonexistent",
        )
        assert result is None

    def test_delete_removes_credentials(self, vault: CredentialsVault):
        tenant_id = str(uuid.uuid4())
        creds = {"api_key": "TO-DELETE"}
        vault.store_in_memory(tenant_id=tenant_id, connector_name="zscaler", credentials=creds)
        vault.delete_from_memory(tenant_id=tenant_id, connector_name="zscaler")
        assert vault.retrieve_from_memory(tenant_id=tenant_id, connector_name="zscaler") is None

    def test_different_connectors_same_tenant_are_isolated(self, vault: CredentialsVault):
        tenant_id = str(uuid.uuid4())
        creds_z = {"key": "zscaler-key"}
        creds_n = {"key": "netskope-key"}
        vault.store_in_memory(tenant_id=tenant_id, connector_name="zscaler", credentials=creds_z)
        vault.store_in_memory(tenant_id=tenant_id, connector_name="netskope", credentials=creds_n)

        assert vault.retrieve_from_memory(tenant_id=tenant_id, connector_name="zscaler") == creds_z
        assert vault.retrieve_from_memory(tenant_id=tenant_id, connector_name="netskope") == creds_n

    def test_overwrite_existing_credentials(self, vault: CredentialsVault):
        tenant_id = str(uuid.uuid4())
        vault.store_in_memory(tenant_id=tenant_id, connector_name="ms_entra", credentials={"v": "1"})
        vault.store_in_memory(tenant_id=tenant_id, connector_name="ms_entra", credentials={"v": "2"})
        assert vault.retrieve_from_memory(tenant_id=tenant_id, connector_name="ms_entra") == {"v": "2"}


# ─────────────────────────────────────────────────────────────────────────────
# Tests: DB model schema (TenantConnectorCredential)
# ─────────────────────────────────────────────────────────────────────────────

class TestTenantConnectorCredentialModel:
    def test_model_importable(self):
        from backend.models.tenant_connector_credential import TenantConnectorCredential
        assert TenantConnectorCredential is not None

    def test_model_has_required_columns(self):
        from backend.models.tenant_connector_credential import TenantConnectorCredential
        cols = {c.key for c in TenantConnectorCredential.__table__.columns}
        assert "tenant_id" in cols
        assert "connector_name" in cols
        assert "encrypted_blob" in cols
        assert "created_at" in cols
        assert "updated_at" in cols

    def test_model_tablename(self):
        from backend.models.tenant_connector_credential import TenantConnectorCredential
        assert TenantConnectorCredential.__tablename__ == "tenant_connector_credentials"

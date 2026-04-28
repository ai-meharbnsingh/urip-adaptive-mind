"""
connectors/base/credentials_vault.py — Fernet-encrypted credential storage helper.

P1.6: Connector Framework Abstraction

Design decisions
----------------
- Fernet (symmetric authenticated encryption) chosen over RSA because:
  1. Credentials are blobs stored server-side — no asymmetric key distribution needed.
  2. Fernet provides authentication (tamper detection) + encryption in one primitive.
  3. cryptography library already in requirements.txt (used by crypto_service.py).
  4. RSA would require key-pair management, larger ciphertext, and no timing advantage
     for this use case (blobs are < 1 KB).
  Key rotation: generate a new Fernet key, re-encrypt all blobs at rotation time.
  MultiFernet is the path forward for zero-downtime rotation (not in scope for P1.6).

- In-memory store (store_in_memory / retrieve_from_memory) is provided for:
  1. Tests — no DB dependency.
  2. Local dev — load all credentials at startup.
  The DB-backed path (store_to_db / retrieve_from_db) uses TenantConnectorCredential
  and is the production path.  Tests that need DB coverage go through the model tests.

- Tenant isolation: the store key is (tenant_id, connector_name).  Even if two tenants
  have credentials for the same connector, they are stored and retrieved independently.

- Missing key: ValueError is raised at construction time (not encrypt time) so callers
  discover misconfig on startup, not at first use.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


class CredentialsVault:
    """
    Fernet-backed credential encryption helper with in-memory isolation by tenant.

    Parameters
    ----------
    fernet_key : str
        URL-safe base64-encoded 32-byte Fernet key.
        Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

    Raises
    ------
    ValueError
        If fernet_key is None or empty.
    cryptography.fernet.InvalidToken (via cryptography)
        If fernet_key is not a valid Fernet key.
    """

    def __init__(self, fernet_key: Optional[str]) -> None:
        if not fernet_key:
            raise ValueError(
                "fernet_key must be a non-empty Fernet key string. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\""
            )
        # This raises ValueError/binascii.Error for invalid keys at construction time
        self._fernet = Fernet(
            fernet_key.encode() if isinstance(fernet_key, str) else fernet_key
        )
        # In-memory store: {(tenant_id, connector_name): encrypted_bytes}
        self._store: dict[tuple[str, str], bytes] = {}

    # ─────────────────────────────────────────────────────────────────────────
    # Encrypt / Decrypt
    # ─────────────────────────────────────────────────────────────────────────

    def encrypt(self, credentials: dict) -> bytes:
        """
        Serialize credentials dict to JSON and encrypt with Fernet.

        Parameters
        ----------
        credentials : dict
            Arbitrary JSON-serializable credential dict.

        Returns
        -------
        bytes
            Fernet token (encrypted, authenticated, timestamped).
        """
        plaintext = json.dumps(credentials).encode("utf-8")
        return self._fernet.encrypt(plaintext)

    def decrypt(self, cipher: bytes) -> dict:
        """
        Decrypt a Fernet token back to a credentials dict.

        Raises
        ------
        cryptography.fernet.InvalidToken
            If the ciphertext is tampered, expired, or encrypted with a different key.
        """
        plaintext = self._fernet.decrypt(cipher)
        return json.loads(plaintext.decode("utf-8"))

    # ─────────────────────────────────────────────────────────────────────────
    # In-memory store (tests + local dev)
    # ─────────────────────────────────────────────────────────────────────────

    def store_in_memory(
        self,
        tenant_id: str,
        connector_name: str,
        credentials: dict,
    ) -> None:
        """Encrypt credentials and store in memory under (tenant_id, connector_name)."""
        key = (tenant_id, connector_name)
        self._store[key] = self.encrypt(credentials)

    def retrieve_from_memory(
        self,
        tenant_id: str,
        connector_name: str,
    ) -> Optional[dict]:
        """
        Retrieve and decrypt credentials for (tenant_id, connector_name).

        Returns None if no credentials are stored for this key.
        """
        key = (tenant_id, connector_name)
        cipher = self._store.get(key)
        if cipher is None:
            return None
        return self.decrypt(cipher)

    def delete_from_memory(self, tenant_id: str, connector_name: str) -> None:
        """Remove credentials for (tenant_id, connector_name) from memory."""
        key = (tenant_id, connector_name)
        self._store.pop(key, None)

    # ─────────────────────────────────────────────────────────────────────────
    # Convenience: from settings (production bootstrap)
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def from_settings(cls) -> "CredentialsVault":
        """
        Construct a CredentialsVault using URIP_FERNET_KEY from settings.

        Raises ValueError if the key is not configured.
        """
        from backend.config import settings
        return cls(fernet_key=settings.URIP_FERNET_KEY)

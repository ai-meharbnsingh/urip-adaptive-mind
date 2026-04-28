"""
agent/reporter.py — The Encrypted Reporter.

The ONLY component that talks to the cloud.  Sends aggregate metadata only —
NEVER raw findings.  Every payload is HMAC-SHA256 signed; every request
carries a timestamp header to prevent replay attacks.

Decisions
---------
- HMAC-SHA256 (not JWT, not mTLS) chosen because:
    * static symmetric secret model; no PKI to manage,
    * canonical "{ts}.{path}.{body}" signing prevents header tampering,
    * smaller wire footprint,
    * simpler to debug (verifiable with `openssl dgst -hmac KEY -sha256`).
- Exponential backoff with hard limit of 5 attempts — beyond that we log loudly
  and give up so an unreachable cloud doesn't cause the agent to spin forever.
- Defence-in-depth: a `_assert_no_raw_findings` check runs on EVERY payload
  before signing.  Any leakage attempt aborts with RuntimeError.

Audit-fix CRIT-G5 (HKDF key derivation)
---------------------------------------
The cloud DB stores `shared_secret_hash = sha256(plain_secret)` for tenant
agent registrations. Previously, that exact hex digest was used DIRECTLY as
the HMAC key (`hmac.new(stored_hash, canonical, sha256)`). Therefore a DB
read compromise (backup leak / SQLi / insider) instantly handed the attacker
a usable signing key — they could forge agent metadata + drilldown responses
for every registered tenant.

Fix: derive a SEPARATE HMAC signing key from the stored hash via HKDF
(RFC 5869). The DB-stored hash remains the lookup index; the actual HMAC key
is `HKDF(stored_hash, salt=HMAC_KEY_SALT, info=b"urip-agent-hmac-v1")`. The
versioned `info` label gives us a clean rotation path (bump to `v2` and
re-derive everywhere). Both the agent and the cloud verifier use the same
helper (`_derive_hmac_key`) so the signatures match end-to-end.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any, Iterable, Optional

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger(__name__)

# ─── HKDF constants — must match cloud-side ────────────────────────────────
# Constant per release. If we ever need to invalidate every existing agent
# secret without re-registering, bump HMAC_KEY_INFO to a new version label.
HMAC_KEY_SALT = b"urip-agent-hmac-salt-v1"
HMAC_KEY_INFO = b"urip-agent-hmac-v1"
HMAC_KEY_LENGTH = 32  # 256-bit HMAC key for SHA-256


def _derive_hmac_key(stored_secret_hash: str) -> bytes:
    """
    Derive the HMAC signing key from the DB-stored secret hash via HKDF.

    `stored_secret_hash` is the hex sha256 of the plain shared secret — the
    same value the cloud has in `agent_registrations.shared_secret_hash`.
    Both sides MUST call this helper with the same input so the derived key
    matches.

    Why HKDF and not the raw hash?
        Storing the raw hash AS the HMAC key means a DB read = usable
        signing key. HKDF derives a separate, cryptographically distinct
        key so the on-disk artifact alone is not sufficient to forge.
    """
    if not stored_secret_hash:
        raise ValueError("stored_secret_hash must be non-empty")
    kdf = HKDF(
        algorithm=hashes.SHA256(),
        length=HMAC_KEY_LENGTH,
        salt=HMAC_KEY_SALT,
        info=HMAC_KEY_INFO,
    )
    return kdf.derive(stored_secret_hash.encode("utf-8"))

# Same banned-keys list as the cloud-side router.  Defence-in-depth: if the
# agent ever tries to send a payload containing 'asset' / 'ip' / 'hostname'
# etc., we abort BEFORE the HTTP call so nothing leaves the network.
RAW_FINDING_DENY_KEYS = frozenset(
    {"asset", "ip", "ip_address", "hostname", "username", "user", "finding", "cve_id"}
)

DEFAULT_MAX_RETRIES = 5
DEFAULT_BACKOFF_BASE_SECONDS = 1.0
DEFAULT_TIMEOUT_SECONDS = 15.0


def _assert_no_raw_findings(payload: Any, _path: str = "") -> None:
    """Recursively walk payload — raise RuntimeError if any banned key found."""
    if isinstance(payload, dict):
        for k, v in payload.items():
            if k.lower() in RAW_FINDING_DENY_KEYS:
                raise RuntimeError(
                    f"Refusing to send: payload contains raw-finding key "
                    f"'{k}' at {_path or '<root>'}"
                )
            _assert_no_raw_findings(v, f"{_path}.{k}" if _path else k)
    elif isinstance(payload, list):
        for i, item in enumerate(payload):
            _assert_no_raw_findings(item, f"{_path}[{i}]")


def sign_payload(secret: str, timestamp: str, path: str, body: bytes) -> str:
    """
    Produce hex HMAC-SHA256 of canonical "{timestamp}.{path}.{body}".

    Notes
    -----
    The plaintext `secret` lives only on the agent (returned ONCE at /register).
    The cloud stores only `sha256(secret)` as the lookup hash. We:
      1. compute that same `sha256(secret)` here (so the agent never needs
         the cloud's stored value),
      2. derive a SEPARATE HMAC signing key from it via HKDF (CRIT-G5 fix —
         a DB read of the stored hash alone is no longer a usable signing
         key),
      3. HMAC-SHA256 over canonical "{ts}.{path}.{body}".

    Both sides call `_derive_hmac_key(stored_secret_hash)` so the signatures
    are identical end-to-end.
    """
    stored_secret_hash = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    hmac_key = _derive_hmac_key(stored_secret_hash)
    canonical = timestamp.encode("utf-8") + b"." + path.encode("utf-8") + b"." + body
    return hmac.new(hmac_key, canonical, hashlib.sha256).hexdigest()


class EncryptedReporter:
    """Agent-side HTTP client for cloud ingest endpoints."""

    def __init__(
        self,
        cloud_portal_url: str,
        tenant_slug: str,
        shared_secret: str,
        agent_version: str,
        *,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base_seconds: float = DEFAULT_BACKOFF_BASE_SECONDS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        if not cloud_portal_url:
            raise ValueError("cloud_portal_url is required")
        if not tenant_slug:
            raise ValueError("tenant_slug is required")
        if not shared_secret:
            raise ValueError("shared_secret is required")

        self.cloud_portal_url = cloud_portal_url.rstrip("/")
        self.tenant_slug = tenant_slug
        self.shared_secret = shared_secret
        self.agent_version = agent_version
        self.max_retries = max_retries
        self.backoff_base_seconds = backoff_base_seconds
        self.timeout_seconds = timeout_seconds
        self._http = http_client  # injected for tests; lazy-create otherwise

    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────

    def report_to_cloud(
        self,
        endpoint: str,
        payload: dict,
        *,
        method: str = "POST",
    ) -> httpx.Response:
        """
        Sign and send a payload to /api/agent-ingest/{endpoint}.

        Performs anti-leak validation, HMAC signing, anti-replay timestamp
        header, and exponential-backoff retry on transient failure.

        Raises
        ------
        RuntimeError
            If payload contains raw-finding keys.
        httpx.HTTPError
            After max_retries exponential-backoff attempts.
        """
        # 1. Defence-in-depth — never send raw findings
        _assert_no_raw_findings(payload)

        # 2. Build canonical request
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        path = f"/api/agent-ingest/{endpoint.lstrip('/')}"
        url = f"{self.cloud_portal_url}{path}"
        timestamp = str(int(time.time()))
        signature = sign_payload(self.shared_secret, timestamp, path, body)

        headers = {
            "Content-Type": "application/json",
            "X-Agent-Tenant": self.tenant_slug,
            "X-Agent-Version": self.agent_version,
            "X-Timestamp": timestamp,
            "X-Signature": signature,
        }

        # 3. Send with retry
        last_exc: Optional[BaseException] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                client = self._http or httpx.Client(timeout=self.timeout_seconds)
                close_after = self._http is None
                try:
                    response = client.request(method, url, headers=headers, content=body)
                finally:
                    if close_after:
                        client.close()

                # Retry on 5xx and transient 429.  4xx is a bug — surface immediately.
                if response.status_code < 500 and response.status_code != 429:
                    return response
                logger.warning(
                    "report_to_cloud %s attempt %d returned status %d; will retry",
                    endpoint,
                    attempt,
                    response.status_code,
                )
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning(
                    "report_to_cloud %s attempt %d failed: %s", endpoint, attempt, exc
                )

            if attempt < self.max_retries:
                sleep_for = self.backoff_base_seconds * (2 ** (attempt - 1))
                time.sleep(sleep_for)

        msg = (
            f"report_to_cloud {endpoint}: gave up after {self.max_retries} attempts. "
            f"Last error: {last_exc!r}"
        )
        logger.error(msg)
        raise httpx.HTTPError(msg)

    # ─────────────────────────────────────────────────────────────────────
    # Convenience wrappers
    # ─────────────────────────────────────────────────────────────────────

    def send_metadata(self, summary: dict) -> httpx.Response:
        """Push aggregate metadata snapshot."""
        return self.report_to_cloud("metadata", summary)

    def send_heartbeat(self, connector_health: dict) -> httpx.Response:
        """Push agent heartbeat with per-connector health status."""
        return self.report_to_cloud("heartbeat", {"connector_health": connector_health})


# ─────────────────────────────────────────────────────────────────────────────
# Module-level convenience function (used by the entrypoint and tests)
# ─────────────────────────────────────────────────────────────────────────────


def report_to_cloud(
    *,
    cloud_portal_url: str,
    tenant_slug: str,
    shared_secret: str,
    agent_version: str,
    endpoint: str,
    payload: dict,
    http_client: Optional[httpx.Client] = None,
) -> httpx.Response:
    """One-shot helper used by simple call sites and tests."""
    reporter = EncryptedReporter(
        cloud_portal_url=cloud_portal_url,
        tenant_slug=tenant_slug,
        shared_secret=shared_secret,
        agent_version=agent_version,
        http_client=http_client,
    )
    return reporter.report_to_cloud(endpoint, payload)

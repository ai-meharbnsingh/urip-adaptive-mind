"""
Audit-fix critical findings — TDD tests for the 5 confirmed CRITICAL issues
from the 4-way audit (Gemini + Claude + Kimi + Codex).

Coverage:
  AF-CRIT-1  Production credentials file (.env.credentials.URIP-PRODUCTION-REFERENCE)
             must NOT be on disk in the repo working tree. .gitignore must
             carry both `.env.credentials*` and `*.credentials.*` patterns.
  AF-CRIT-3  .env file must NOT contain a literal JWT_SECRET_KEY assignment
             with the dev default value. (.env.example may keep it as a
             placeholder for the rotation story.)
  AF-CRIT-5  HMAC key derivation via HKDF — agent and cloud verifier must use
             HKDF-derived keys, not the raw stored hash.

The other two critical findings (AF-CRIT-2 compliance JWT enforcement and
AF-CRIT-4 policies.py admin gate) live in
compliance/backend/tests/test_audit_fix_critical.py because they require the
compliance app fixtures.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Project root resolution
# ---------------------------------------------------------------------------


def _project_root() -> Path:
    here = Path(__file__).resolve()
    for ancestor in [here] + list(here.parents):
        if (ancestor / ".gitignore").exists() and (ancestor / "backend").exists():
            return ancestor
    raise RuntimeError("Cannot find project root")


# ===========================================================================
# AF-CRIT-1 — Production credentials file must not be on disk
# ===========================================================================


def test_af_crit1_production_credentials_file_is_not_on_disk():
    """
    .env.credentials.URIP-PRODUCTION-REFERENCE contains live Neon DB password
    and demo CISO credentials. Must NOT exist in the working tree of the repo.
    Anyone with repo / dev-machine access could exfiltrate live production
    credentials. Per Gemini CRIT-G1 / Kimi CRIT-001 / Claude LOW-005, this
    file must be moved to _trash/ (per INV-0 — no rm).
    """
    root = _project_root()
    leaked = root / ".env.credentials.URIP-PRODUCTION-REFERENCE"
    assert not leaked.exists(), (
        f"AF-CRIT-1 — production credentials file still on disk at {leaked}. "
        f"Move it to {root / '_trash'} and rotate every credential it contains."
    )


def test_af_crit1_no_credentials_files_at_repo_root():
    """No file matching `*.credentials.*` should sit at the repo root."""
    root = _project_root()
    matches = [p for p in root.iterdir() if ".credentials." in p.name and p.is_file()]
    assert matches == [], (
        f"AF-CRIT-1 — credentials files still at repo root: {[str(p) for p in matches]}"
    )


def test_af_crit1_gitignore_blocks_credentials_files():
    """
    .gitignore must carry BOTH `.env.credentials*` (existing) and
    `*.credentials.*` (Gemini-recommended broader pattern) so that any future
    `.production.credentials.json` / `.staging.credentials.yaml` etc. is
    blocked by default.
    """
    gitignore = (_project_root() / ".gitignore").read_text()
    assert ".env.credentials*" in gitignore, (
        "AF-CRIT-1 — .gitignore is missing `.env.credentials*` pattern"
    )
    assert "*.credentials.*" in gitignore, (
        "AF-CRIT-1 — .gitignore is missing `*.credentials.*` pattern; new "
        "credential file shapes (`*.staging.credentials.json` etc.) would "
        "leak into git on accident."
    )


def test_af_crit1_rotation_procedure_documented():
    """
    Per the audit-fix instructions, .env.example must carry a visible
    secrets-rotation procedure so an operator knows how to react to a leak
    (this is the project's secrets-rotation 'README' for now).
    """
    text = (_project_root() / ".env.example").read_text().lower()
    assert "rotat" in text, ".env.example must document rotation procedure"
    # Specific procedural cues we expect the rotation block to include
    assert "secrets manager" in text or "vault" in text, (
        ".env.example must mention a secrets manager (Vault / AWS Secrets / "
        "Doppler / 1Password) so operators know secrets do not live on disk."
    )
    assert "secrets.token_urlsafe" in text or "token_urlsafe" in text, (
        ".env.example must show how to generate a strong JWT secret."
    )


# ===========================================================================
# AF-CRIT-3 — .env must not assign the default JWT secret
# ===========================================================================


def test_af_crit3_env_file_does_not_carry_default_jwt_secret():
    """
    Per Gemini CRIT-G5 / Codex CRIT-003: the literal line
    `JWT_SECRET_KEY=urip-dev-secret-change-in-production`
    must be removed from `.env`. The pydantic default in code already
    provides the dev fallback; keeping it in `.env` increases the risk of
    accidental production deployment with the well-known secret.

    Codex round-E: skip cleanly on a clean clone where `.env` has not been
    created yet — the assertion only needs to fire when an `.env` *exists*
    and is in danger of leaking the default secret.
    """
    env_path = _project_root() / ".env"
    if not env_path.exists():
        import pytest
        pytest.skip("no .env present in clean clone — nothing to leak")
    text = env_path.read_text()
    # Tolerate the secret string appearing inside comments, but reject any
    # actual KEY=VALUE assignment that ships the default secret.
    assignment_pattern = re.compile(
        r"^\s*JWT_SECRET_KEY\s*=\s*urip-dev-secret-change-in-production\s*$",
        re.MULTILINE,
    )
    assert assignment_pattern.search(text) is None, (
        "AF-CRIT-3 — .env still ships JWT_SECRET_KEY=<dev default>. "
        "Remove the assignment line; rely on the in-code pydantic default + "
        "warning so an operator who forgets to set the env var sees the "
        "loud dev-warning path, not a silent production secret."
    )


def test_af_crit3_env_file_still_marked_dev_only():
    """Removing the line must not erase the DEV-ONLY warnings."""
    env_path = _project_root() / ".env"
    if not env_path.exists():
        import pytest
        pytest.skip("no .env present in clean clone")
    text = env_path.read_text().lower()
    assert "dev" in text and ("only" in text or "rotate" in text), (
        ".env still must carry an explicit DEV-ONLY / rotate-required marker"
    )


# ===========================================================================
# AF-CRIT-5 — HMAC key derivation via HKDF
# ===========================================================================


def test_af_crit5_agent_uses_hkdf_for_hmac_key():
    """
    The agent-side HMAC key MUST be derived from the shared secret via HKDF,
    not used directly as `sha256(secret)`. Otherwise a DB compromise (which
    leaks `shared_secret_hash`) yields a usable signing key.
    """
    src = (_project_root() / "agent" / "reporter.py").read_text()
    assert "HKDF" in src, (
        "AF-CRIT-5 — agent/reporter.py must use HKDF to derive the HMAC "
        "signing key from the stored shared secret. The legacy "
        "`hmac.new(sha256(secret).hexdigest(), ...)` path is broken because "
        "the cloud DB stores exactly that sha256, so a DB read = signing "
        "key in the attacker's hand."
    )
    assert "urip-agent-hmac-v1" in src or "urip-agent-hmac" in src, (
        "AF-CRIT-5 — agent/reporter.py HKDF must use a versioned `info` "
        "label so the derivation is domain-separated and easy to rotate."
    )


def test_af_crit5_cloud_verifier_uses_hkdf_for_hmac_key():
    """The cloud-side verifier must derive its HMAC key the same way."""
    src = (_project_root() / "backend" / "routers" / "agent_ingest.py").read_text()
    assert "HKDF" in src, (
        "AF-CRIT-5 — backend/routers/agent_ingest.py must derive the HMAC "
        "verification key from the stored shared_secret_hash via HKDF."
    )
    assert "urip-agent-hmac-v1" in src or "urip-agent-hmac" in src, (
        "AF-CRIT-5 — cloud verifier must use the same versioned HKDF info "
        "label as the agent."
    )


def test_af_crit5_signature_with_legacy_key_is_rejected_by_signing_function():
    """
    Functional check: the agent's `sign_payload` must not produce the same
    signature for the legacy raw-sha256 key vs the HKDF-derived key.
    A legacy-style signature (raw sha256(secret) as HMAC key) must NOT match
    the new agent's signature for the same canonical message — proving the
    new derivation actually changes the signing key.
    """
    import hashlib
    import hmac as _hmac

    from agent.reporter import sign_payload

    secret = "demo-shared-secret-32-bytes-of-entropy-here-AAA"
    timestamp = "1714210000"
    path = "/api/agent-ingest/heartbeat"
    body = b'{"connector_health":{}}'

    new_sig = sign_payload(secret, timestamp, path, body)

    # Legacy key (DB-stored) — what an attacker gets from a DB leak
    legacy_key = hashlib.sha256(secret.encode("utf-8")).hexdigest().encode("utf-8")
    canonical = timestamp.encode("utf-8") + b"." + path.encode("utf-8") + b"." + body
    legacy_sig = _hmac.new(legacy_key, canonical, hashlib.sha256).hexdigest()

    assert new_sig != legacy_sig, (
        "AF-CRIT-5 — sign_payload still produces a signature identical to "
        "the legacy `hmac(sha256(secret), ...)` form. HKDF derivation has "
        "no effect; an attacker with the DB-stored hash can still forge."
    )


def test_af_crit5_agent_and_cloud_signatures_match_after_hkdf():
    """
    The agent's `sign_payload` and the cloud verifier's HMAC computation
    MUST produce the same hex digest for the same (secret, ts, path, body).
    This is the round-trip integrity guarantee — neither side can drift
    from the other or every agent breaks.
    """
    from agent.reporter import sign_payload, _derive_hmac_key  # type: ignore

    secret = "round-trip-secret-32-bytes-of-entropy-here-BBB"
    timestamp = "1714210000"
    path = "/api/agent-ingest/metadata"
    body = b'{"risk_summary":{"total_risks":1}}'

    # Agent signs with its public function
    agent_sig = sign_payload(secret, timestamp, path, body)

    # Cloud reproduces using the same derivation helper
    import hashlib as _hashlib
    import hmac as _hmac

    derived_key = _derive_hmac_key(_hashlib.sha256(secret.encode("utf-8")).hexdigest())
    canonical = timestamp.encode("utf-8") + b"." + path.encode("utf-8") + b"." + body
    cloud_sig = _hmac.new(derived_key, canonical, _hashlib.sha256).hexdigest()

    assert agent_sig == cloud_sig, (
        "AF-CRIT-5 — agent and cloud HKDF-derived HMAC keys disagree. "
        f"agent={agent_sig} cloud={cloud_sig}"
    )

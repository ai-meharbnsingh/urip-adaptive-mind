"""
Audit-fix critical findings — TDD tests for compliance-side CRITICALs from
the 4-way audit (Gemini + Claude + Kimi + Codex).

Coverage:
  AF-CRIT-2  Compliance JWT secret enforcement — refuse to start in
             production-like envs with default / empty COMPLIANCE_JWT_SECRET
             or URIP_JWT_SECRET. Mirror of `backend/config._enforce_jwt_secret_policy`.
             (Gemini CRIT-G2 / Codex CRIT-001 / Kimi CRIT-002 / Claude CRIT-B —
             4-way confirmed.)
  AF-CRIT-4  policies.py admin gate must route through `require_compliance_admin`,
             not the legacy `claims["role"] == "admin"` literal — otherwise
             ciso / super-admin / compliance-admin URIP-issued JWTs cannot
             create / publish / list-expiring policies.
             (Claude CRIT-A / Kimi HIGH-004.)
"""

from __future__ import annotations

import time
import warnings

import jwt
import pytest


STANDALONE_SECRET = "test-secret-standalone"


# ---------------------------------------------------------------------------
# Token helpers (mirror test_critfix_security so we exercise the same gate)
# ---------------------------------------------------------------------------


def _make_token(
    tenant_id: str,
    role: str = "admin",
    *,
    is_super_admin: bool = False,
    is_compliance_admin: bool = False,
) -> str:
    payload = {
        "sub": "user-audit-fix",
        "tenant_id": tenant_id,
        "role": role,
        "is_super_admin": is_super_admin,
        "is_compliance_admin": is_compliance_admin,
        "exp": int(time.time()) + 3600,
        "iss": "compliance",
    }
    return jwt.encode(payload, STANDALONE_SECRET, algorithm="HS256")


def _headers(
    tenant_id: str = "tenant-audit-fix",
    role: str = "admin",
    *,
    is_super_admin: bool = False,
    is_compliance_admin: bool = False,
) -> dict:
    return {
        "Authorization": "Bearer "
        + _make_token(
            tenant_id,
            role=role,
            is_super_admin=is_super_admin,
            is_compliance_admin=is_compliance_admin,
        )
    }


# ===========================================================================
# AF-CRIT-2 — Compliance JWT secret enforcement at import time
# ===========================================================================


# NOTE: We deliberately do NOT reload `compliance_backend.config` in these
# tests. Other modules (`middleware/auth.py`, `services/auditor_service.py`,
# `main.py`) hold a reference to the `settings` object via
# `from compliance_backend.config import settings`; reloading the config
# module replaces the module-level singleton but the OLD references in
# those modules keep pointing at the previous Settings instance, breaking
# JWT decode for the rest of the test session. Instead we exercise
# `_enforce_jwt_secret_policy` directly by constructing a Settings instance
# with the values we want to validate. This is a unit test of the policy
# function — the integration is exercised by importing the module at
# session start (conftest already does that with safe secrets).


def _build_settings(env: str, compliance_secret: str, urip_secret: str):
    """Construct a Settings instance bypassing the env-file load so we can
    exercise the policy gate independently of the test conftest's env vars.
    """
    from compliance_backend.config import Settings

    s = Settings(
        COMPLIANCE_ENV=env,
        COMPLIANCE_JWT_SECRET=compliance_secret,
        URIP_JWT_SECRET=urip_secret,
    )
    return s


def _run_policy(env: str, compliance_secret: str, urip_secret: str, monkeypatch):
    """Apply env vars + run the policy enforcement on a fresh Settings."""
    monkeypatch.setenv("COMPLIANCE_ENV", env)
    s = _build_settings(env, compliance_secret, urip_secret)
    from compliance_backend.config import _enforce_jwt_secret_policy

    _enforce_jwt_secret_policy(s)
    return s


def _config_error_class():
    from compliance_backend.config import ConfigError

    return ConfigError


@pytest.mark.parametrize("env", ["prod", "production", "staging"])
def test_af_crit2_production_with_default_compliance_secret_raises(monkeypatch, env):
    """Production-like env + default COMPLIANCE_JWT_SECRET → ConfigError."""
    ConfigError = _config_error_class()
    with pytest.raises(ConfigError) as exc_info:
        _run_policy(
            env,
            "change-me-in-production",
            "real-rotated-urip-secret-9f2b8c1d4a6e7f0c",
            monkeypatch,
        )
    msg = str(exc_info.value).lower()
    assert "compliance_jwt_secret" in msg
    assert "default" in msg or "rotate" in msg


@pytest.mark.parametrize("env", ["prod", "production", "staging"])
def test_af_crit2_production_with_default_urip_secret_raises(monkeypatch, env):
    """Production-like env + default URIP_JWT_SECRET → ConfigError."""
    ConfigError = _config_error_class()
    with pytest.raises(ConfigError) as exc_info:
        _run_policy(
            env,
            "real-rotated-compliance-secret-c2b8a1d4e7",
            "urip-shared-secret",  # default
            monkeypatch,
        )
    msg = str(exc_info.value).lower()
    assert "urip_jwt_secret" in msg


@pytest.mark.parametrize("env", ["prod", "production", "staging"])
def test_af_crit2_production_with_empty_compliance_secret_raises(monkeypatch, env):
    """Production-like env + empty COMPLIANCE_JWT_SECRET → ConfigError."""
    ConfigError = _config_error_class()
    with pytest.raises(ConfigError) as exc_info:
        _run_policy(
            env,
            "",
            "real-rotated-urip-secret-9f2b8c1d4a6e7f",
            monkeypatch,
        )
    msg = str(exc_info.value).lower()
    assert "compliance_jwt_secret" in msg
    assert "empty" in msg


@pytest.mark.parametrize("env", ["prod", "production", "staging"])
def test_af_crit2_production_with_identical_secrets_raises(monkeypatch, env):
    """Production-like env where compliance and urip secrets are identical →
    ConfigError. Defence-in-depth: a leak of one must not forge tokens for
    the other auth mode.
    """
    ConfigError = _config_error_class()
    same = "very-strong-but-shared-secret-9f2b8c1d4a6e7f0c2b9d8a1c3e5f7b8d"
    with pytest.raises(ConfigError) as exc_info:
        _run_policy(env, same, same, monkeypatch)
    assert (
        "different" in str(exc_info.value).lower()
        or "distinct" in str(exc_info.value).lower()
    )


@pytest.mark.parametrize("env", ["prod", "production", "staging"])
def test_af_crit2_production_with_rotated_secrets_passes(monkeypatch, env):
    """Real, distinct, non-default secrets in a production-like env → start cleanly."""
    s = _run_policy(
        env,
        "rotated-compliance-secret-9f2b8c1d4a6e7f0c2b9d8a1c3e5f7b8d",
        "rotated-urip-shared-secret-c2b9d8a1c3e5f7b8d9f2b8c1d4a6e7f0",
        monkeypatch,
    )
    assert "rotated-compliance-secret" in s.COMPLIANCE_JWT_SECRET
    assert "rotated-urip-shared-secret" in s.URIP_JWT_SECRET


@pytest.mark.parametrize("env", ["dev", "development", ""])
def test_af_crit2_dev_with_defaults_allowed_with_warning(monkeypatch, env, capsys):
    """In dev the defaults are allowed but produce a loud stderr warning."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        s = _run_policy(
            env,
            "change-me-in-production",
            "urip-shared-secret",
            monkeypatch,
        )
    assert s.COMPLIANCE_JWT_SECRET == "change-me-in-production"

    captured = capsys.readouterr()
    combined = (captured.err + captured.out).lower() + " ".join(
        str(w.message).lower() for w in caught
    )
    assert "compliance" in combined
    assert "default" in combined or "rotate" in combined or "dev" in combined


# ===========================================================================
# AF-CRIT-4 — policies.py routes through require_compliance_admin
# ===========================================================================


@pytest.mark.anyio
async def test_af_crit4_ciso_can_create_policy(client):
    """A user with role=ciso (URIP INTEGRATED-mode role) must pass the policy
    create gate. Previously the local `require_admin` only accepted
    role=="admin" — denying every legitimate URIP user.
    """
    tenant = "tenant-af4-ciso"
    resp = await client.post(
        "/policies",
        headers=_headers(tenant, role="ciso"),
        json={"name": "Acceptable Use", "content": "# AUP"},
    )
    assert resp.status_code != 403, (
        f"AF-CRIT-4 — ciso must pass policies admin gate; got 403: {resp.text}"
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.anyio
async def test_af_crit4_executive_cannot_create_policy(client):
    """role=executive is below the policy admin gate — must still 403."""
    tenant = "tenant-af4-exec"
    resp = await client.post(
        "/policies",
        headers=_headers(tenant, role="executive"),
        json={"name": "Should Fail", "content": "# X"},
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_af_crit4_super_admin_can_create_policy(client):
    """is_super_admin=True passes regardless of role (URIP super-admin bypass)."""
    tenant = "tenant-af4-sa"
    resp = await client.post(
        "/policies",
        headers=_headers(tenant, role="executive", is_super_admin=True),
        json={"name": "Super Admin Policy", "content": "# SA"},
    )
    assert resp.status_code != 403, resp.text
    assert resp.status_code == 201, resp.text


@pytest.mark.anyio
async def test_af_crit4_compliance_admin_capability_can_create_policy(client):
    """is_compliance_admin=True flag passes regardless of role."""
    tenant = "tenant-af4-ca"
    resp = await client.post(
        "/policies",
        headers=_headers(tenant, role="executive", is_compliance_admin=True),
        json={"name": "CA Policy", "content": "# CA"},
    )
    assert resp.status_code != 403, resp.text
    assert resp.status_code == 201, resp.text


@pytest.mark.anyio
async def test_af_crit4_legacy_admin_role_still_works(client):
    """Backward-compat: STANDALONE-mode role=admin must continue to pass."""
    tenant = "tenant-af4-legacy"
    resp = await client.post(
        "/policies",
        headers=_headers(tenant, role="admin"),
        json={"name": "Legacy Admin Policy", "content": "# legacy"},
    )
    assert resp.status_code != 403
    assert resp.status_code == 201


@pytest.mark.anyio
async def test_af_crit4_publish_version_uses_centralised_gate(client, db_session):
    """POST /policies/{id}/versions must accept ciso (not just admin)."""
    from compliance_backend.services import policy_manager

    tenant = "tenant-af4-publish"
    policy = await policy_manager.create_policy(
        session=db_session,
        tenant_id=tenant,
        name="Publishable",
        content="# v1",
        owner="admin-1",
    )
    await db_session.commit()

    resp = await client.post(
        f"/policies/{policy.id}/versions",
        headers=_headers(tenant, role="ciso"),
        json={"content": "# v2", "change_summary": "ciso-published"},
    )
    assert resp.status_code != 403, resp.text
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["version_number"] == 2


@pytest.mark.anyio
async def test_af_crit4_list_expiring_uses_centralised_gate(client):
    """GET /policies/expiring must accept ciso (not just admin)."""
    tenant = "tenant-af4-expiring"
    resp = await client.get(
        "/policies/expiring",
        headers=_headers(tenant, role="ciso"),
    )
    assert resp.status_code != 403, (
        f"AF-CRIT-4 — ciso must pass /policies/expiring gate; got 403"
    )
    # Empty list is OK; we only care about not-403.
    assert resp.status_code == 200, resp.text


@pytest.mark.anyio
async def test_af_crit4_local_require_admin_function_was_removed(client):
    """The legacy local `require_admin` function must be GONE — replaced by
    the centralised `require_compliance_admin` helper. Static check via
    importing the module and confirming there is no top-level `require_admin`
    that does the legacy literal compare.
    """
    from compliance_backend.routers import policies as policies_module

    # Acceptable: a private `_require_admin` shim that delegates.
    # Rejected:   a public `require_admin` doing claims["role"] != "admin".
    legacy = getattr(policies_module, "require_admin", None)
    assert legacy is None, (
        "AF-CRIT-4 — policies.py still exposes a top-level `require_admin` "
        "function. Replace with `_require_admin` shim that calls "
        "`require_compliance_admin(claims)`."
    )

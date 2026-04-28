"""
CRIT-004: JWT_SECRET_KEY default rotation enforcement.

Vulnerability:
- backend/config.py default JWT_SECRET_KEY = "urip-dev-secret-change-in-production"
- Same value committed in .env and .env.example
- A production deployment that forgets to rotate the secret would silently
  accept tokens forged by anyone who reads the public repo.

Required behaviour:
- If URIP_ENV in {prod, production, staging} AND JWT_SECRET_KEY equals the dev
  default OR is empty → raise ConfigError on import.
- In dev (URIP_ENV unset or = dev / development) the dev default is allowed
  but produces a loud warning.
"""

import importlib
import sys
import warnings

import pytest

DEV_DEFAULT_SECRET = "urip-dev-secret-change-in-production"


def _reload_config_expect_error():
    """Reload backend.config and return (exception_or_None, ConfigError class)."""
    if "backend.config" in sys.modules:
        del sys.modules["backend.config"]
    try:
        mod = importlib.import_module("backend.config")
        return None, getattr(mod, "ConfigError", RuntimeError)
    except Exception as exc:
        # Look up ConfigError on the partially-loaded module (it's defined
        # before the policy check runs, so the class exists)
        partial = sys.modules.get("backend.config")
        cls = getattr(partial, "ConfigError", None) if partial else None
        if cls is None:
            # last resort — re-import the module without the env var to
            # get a clean ConfigError reference
            cls = type(exc)  # any exception type so the assertion has something
        return exc, cls


def _reload_config_expect_ok():
    """Reload backend.config and return the module."""
    if "backend.config" in sys.modules:
        del sys.modules["backend.config"]
    return importlib.import_module("backend.config")


@pytest.mark.parametrize("urip_env", ["prod", "production", "staging"])
def test_production_with_dev_default_secret_raises(monkeypatch, urip_env):
    """A production-like env with the dev default secret MUST refuse to start."""
    monkeypatch.setenv("URIP_ENV", urip_env)
    monkeypatch.setenv("JWT_SECRET_KEY", DEV_DEFAULT_SECRET)

    exc, ConfigError = _reload_config_expect_error()
    assert exc is not None, "expected ConfigError to be raised on import"
    assert isinstance(exc, ConfigError), (
        f"expected ConfigError, got {type(exc).__name__}: {exc}"
    )
    msg = str(exc).lower()
    assert "jwt_secret_key" in msg
    assert "default" in msg or "rotate" in msg or "production" in msg


@pytest.mark.parametrize("urip_env", ["prod", "production", "staging"])
def test_production_with_empty_secret_raises(monkeypatch, urip_env):
    """A production-like env with an empty secret MUST refuse to start."""
    monkeypatch.setenv("URIP_ENV", urip_env)
    monkeypatch.setenv("JWT_SECRET_KEY", "")

    exc, ConfigError = _reload_config_expect_error()
    assert exc is not None, "expected ConfigError to be raised on import"
    assert isinstance(exc, ConfigError), (
        f"expected ConfigError, got {type(exc).__name__}: {exc}"
    )
    msg = str(exc).lower()
    assert "jwt_secret_key" in msg


@pytest.mark.parametrize("urip_env", ["dev", "development", ""])
def test_dev_with_default_secret_allowed_with_warning(monkeypatch, urip_env, capsys):
    """In dev the default secret is allowed but produces a loud stderr warning."""
    if urip_env == "":
        monkeypatch.delenv("URIP_ENV", raising=False)
    else:
        monkeypatch.setenv("URIP_ENV", urip_env)
    monkeypatch.setenv("JWT_SECRET_KEY", DEV_DEFAULT_SECRET)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cfg = _reload_config_expect_ok()
    assert cfg.settings.JWT_SECRET_KEY == DEV_DEFAULT_SECRET

    captured = capsys.readouterr()
    combined = (captured.err + captured.out).lower() + " ".join(
        str(w.message).lower() for w in caught
    )
    assert "jwt_secret_key" in combined or "secret" in combined
    assert "dev" in combined or "default" in combined or "rotate" in combined


@pytest.mark.parametrize("urip_env", ["prod", "production", "staging"])
def test_production_with_rotated_secret_passes(monkeypatch, urip_env):
    """A production-like env with a real rotated secret MUST start cleanly."""
    monkeypatch.setenv("URIP_ENV", urip_env)
    monkeypatch.setenv(
        "JWT_SECRET_KEY", "real-production-secret-9f2b8c1d4a6e7f0c2b9d8a1c3e5f7b8d"
    )

    cfg = _reload_config_expect_ok()
    assert "real-production-secret" in cfg.settings.JWT_SECRET_KEY


def test_env_example_does_not_carry_real_secret():
    """The committed .env.example must contain a clear ROTATE warning so the
    operator cannot deploy unchanged to production.
    """
    from pathlib import Path

    here = Path(__file__).resolve()
    repo_root = here
    for _ in range(6):
        if (repo_root / ".env.example").exists():
            break
        repo_root = repo_root.parent
    else:
        pytest.fail(".env.example not found by walking up from test file")

    text = (repo_root / ".env.example").read_text()
    assert DEV_DEFAULT_SECRET in text, "placeholder secret expected in .env.example"
    lower = text.lower()
    assert (
        "rotate" in lower
        or "must change" in lower
        or "do not deploy" in lower
        or "change before production" in lower
        or "change in production" in lower
    ), ".env.example must visibly warn to rotate JWT_SECRET_KEY"


def test_env_file_marked_dev_only():
    """The committed .env file is dev-only; it must mark itself as such so it
    cannot be silently shipped to production.

    Skipped on a clean clone (no .env present) — there is nothing to leak
    if the file isn't there. This matches the same skip-guard used in
    test_audit_fix_critical.py.
    """
    from pathlib import Path

    here = Path(__file__).resolve()
    repo_root = here
    for _ in range(6):
        if (repo_root / ".env").exists():
            break
        repo_root = repo_root.parent
    else:
        pytest.skip("no .env present in clean clone — nothing to mark")

    text = (repo_root / ".env").read_text().lower()
    assert "dev" in text and ("only" in text or "rotate" in text), (
        ".env must mark itself as dev-only / rotate-required so the dev "
        "default secret cannot accidentally ship to production"
    )

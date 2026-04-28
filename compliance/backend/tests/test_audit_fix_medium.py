"""
Tests for AUDIT-FIX MEDIUM worker — compliance side.
Covers M3 (CORS), M5 (auditor invitation single-use), M7 (tenant_id String(36)),
M8 (auditor get_control existence leak).
"""
from __future__ import annotations

import os
import importlib

import pytest


# ---------------------------------------------------------------------------
# M3 — Compliance CORS hardening
# ---------------------------------------------------------------------------


def test_m3_cors_origins_dev_default_localhost(monkeypatch):
    """Dev (or unset) env without explicit COMPLIANCE_CORS_ORIGINS still allows localhost."""
    monkeypatch.setenv("COMPLIANCE_ENV", "dev")
    monkeypatch.delenv("COMPLIANCE_CORS_ORIGINS", raising=False)
    # Re-import so Settings re-reads env.
    from compliance_backend import config as cfg
    importlib.reload(cfg)
    s = cfg.Settings()
    origins = s.CORS_ORIGINS
    assert "http://localhost:3000" in origins or "http://localhost:3001" in origins


def test_m3_cors_origins_production_deny_all_when_unset(monkeypatch):
    """Production-like env with no env var → deny-all (empty list)."""
    monkeypatch.setenv("COMPLIANCE_ENV", "production")
    monkeypatch.delenv("COMPLIANCE_CORS_ORIGINS", raising=False)
    from compliance_backend import config as cfg
    importlib.reload(cfg)
    s = cfg.Settings()
    assert s.CORS_ORIGINS == []


def test_m3_cors_origins_production_with_explicit_origins(monkeypatch):
    """Production env + explicit env var → exactly those origins, in order."""
    monkeypatch.setenv("COMPLIANCE_ENV", "production")
    monkeypatch.setenv(
        "COMPLIANCE_CORS_ORIGINS",
        "https://app.example.com, https://admin.example.com",
    )
    from compliance_backend import config as cfg
    importlib.reload(cfg)
    s = cfg.Settings()
    assert s.CORS_ORIGINS == [
        "https://app.example.com",
        "https://admin.example.com",
    ]


def test_m3_cors_wildcard_refused_in_production(monkeypatch):
    """Production env + COMPLIANCE_CORS_ORIGINS=* → ConfigError when origins
    are resolved (the policy check raises during module import / reload, so
    we catch the error from the reload itself)."""
    monkeypatch.setenv("COMPLIANCE_ENV", "production")
    monkeypatch.setenv("COMPLIANCE_CORS_ORIGINS", "*")
    # Also rotate JWT secrets so _enforce_jwt_secret_policy doesn't trip first.
    monkeypatch.setenv("COMPLIANCE_JWT_SECRET", "a-real-secret-32-bytes-or-more-A1234")
    monkeypatch.setenv("URIP_JWT_SECRET", "a-different-real-secret-32-bytes-XYZ7")
    from compliance_backend import config as cfg

    # The policy check runs during module-level `settings = get_settings()`,
    # so the reload itself raises ConfigError.  Either the reload error or
    # an explicit get_settings() call must raise.
    raised = None
    try:
        importlib.reload(cfg)
    except cfg.ConfigError as exc:
        raised = exc
    if raised is None:
        # Module imported cleanly — try calling get_settings() directly.
        with pytest.raises(cfg.ConfigError):
            cfg.get_settings()


# ---------------------------------------------------------------------------
# M5 — Auditor invitation single-use enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_m5_invitation_single_use_returns_already_accepted(db_session):
    """Second redemption returns the ALREADY_ACCEPTED sentinel."""
    from datetime import datetime, timedelta
    from compliance_backend.services.auditor_service import AuditorService

    svc = AuditorService(db=db_session)
    now = datetime.utcnow()
    created = await svc.create_invitation(
        tenant_id="tenant-m5",
        auditor_email="auditor@example.com",
        framework_id="fw-m5",
        audit_period_start=now,
        audit_period_end=now + timedelta(days=30),
        expires_at=now + timedelta(days=7),
        invited_by_user_id="admin-1",
    )
    await db_session.commit()
    raw_token = created.raw_token

    # First accept → tuple(access, jwt).
    first = await svc.accept_invitation(raw_token)
    await db_session.commit()
    assert first is not None
    assert first != AuditorService.ALREADY_ACCEPTED
    access, jwt_token = first
    assert access.accepted_at is not None
    assert isinstance(jwt_token, str) and len(jwt_token) > 20

    # Second accept → ALREADY_ACCEPTED sentinel.
    second = await svc.accept_invitation(raw_token)
    assert second == AuditorService.ALREADY_ACCEPTED


# ---------------------------------------------------------------------------
# M7 — Compliance tenant_id String(36) standardised
# ---------------------------------------------------------------------------


def test_m7_compliance_tenant_id_columns_are_string36():
    """Every tenant_id column on compliance models is String(36)."""
    # Import all the model modules so SQLAlchemy registers their tables.
    import compliance_backend.models.evidence  # noqa: F401
    import compliance_backend.models.control_run  # noqa: F401
    import compliance_backend.models.vendor  # noqa: F401
    import compliance_backend.models.tenant_state  # noqa: F401
    import compliance_backend.models.score_snapshot  # noqa: F401
    import compliance_backend.models.auditor  # noqa: F401

    from compliance_backend.database import Base

    bad: list[str] = []
    for table in Base.metadata.tables.values():
        col = table.columns.get("tenant_id")
        if col is None:
            continue
        # SQLAlchemy String type stores `length` directly.
        length = getattr(col.type, "length", None)
        if length is not None and length != 36:
            bad.append(f"{table.name}.tenant_id length={length}")
    assert not bad, f"non-String(36) tenant_id columns: {bad}"


# ---------------------------------------------------------------------------
# M8 — Auditor get_control existence leak: unified 404 message
# ---------------------------------------------------------------------------


def test_m8_get_control_uses_uniform_404_message():
    """Both the "control not found" and "control not in framework" paths return
    the same 404 detail string so an auditor cannot enumerate control IDs."""
    import inspect
    from compliance_backend.routers import auditor as auditor_router

    src = inspect.getsource(auditor_router.get_control)
    # Old code raised two different details:
    #   "Control not found." (control row missing)
    #   "Control not in audited framework." (cross-framework)
    # The fix replaces the second with the same generic detail.
    assert src.count("Control not in audited framework") == 0, (
        "M8: cross-framework control access must NOT have a distinct 404 detail"
    )
    # Verify there's at least one generic "Control not found" detail.
    assert "Control not found" in src, (
        "M8: the unified 404 detail must still be present"
    )

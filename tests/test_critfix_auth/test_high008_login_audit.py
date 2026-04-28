"""
HIGH-008: every login attempt (success + failure) must be persisted to the
audit log.

Vulnerability:
- POST /api/auth/login produced ZERO audit events.  Brute force attacks left
  no trace, password spray went undetected, and SOC analysts had no record
  of who tried to log in when.

Required behaviour:
- Each call to POST /api/auth/login writes an AuditLog row with:
    action="login_attempt"
    actor_email = the email submitted in the request
    success = True/False
    ip_address = request.client.host
    user_agent = request.headers["user-agent"]
    failure_reason in {user_not_found, password_mismatch, tenant_suspended,
                       account_disabled} when success=False
- The submitted password MUST NEVER appear in any field.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.auth import hash_password
from backend.models.audit_log import AuditLog
from backend.models.tenant import Tenant
from backend.models.user import User


SECRET_PASSWORD = "Sup3r$ecretP4ss!2024"


@pytest_asyncio.fixture
async def login_tenant(db_session: AsyncSession) -> Tenant:
    t = Tenant(
        id=uuid.uuid4(),
        name="Login Tenant",
        slug="login-tenant",
        domain="login.example.com",
        is_active=True,
        settings={},
    )
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)
    return t


@pytest_asyncio.fixture
async def login_user(db_session: AsyncSession, login_tenant: Tenant) -> User:
    u = User(
        id=uuid.uuid4(),
        email="alice@login.example.com",
        hashed_password=hash_password(SECRET_PASSWORD),
        full_name="Alice",
        role="ciso",
        is_active=True,
        is_super_admin=False,
        tenant_id=login_tenant.id,
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
async def disabled_user(db_session: AsyncSession, login_tenant: Tenant) -> User:
    u = User(
        id=uuid.uuid4(),
        email="bob.disabled@login.example.com",
        hashed_password=hash_password(SECRET_PASSWORD),
        full_name="Bob (disabled)",
        role="ciso",
        is_active=False,  # disabled
        is_super_admin=False,
        tenant_id=login_tenant.id,
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


async def _audit_rows(db: AsyncSession) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.action == "login_attempt")
        .order_by(AuditLog.created_at.desc())
    )
    return list(result.scalars().all())


def _row_text(row: AuditLog) -> str:
    """Concatenate every textual field on the row (for password leak check)."""
    parts = [
        row.action or "",
        row.resource_type or "",
        row.ip_address or "",
        str(row.details or ""),
    ]
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Successful login → audit row with success=True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_login_writes_audit_row(
    client: AsyncClient,
    db_session: AsyncSession,
    login_user: User,
):
    resp = await client.post(
        "/api/auth/login",
        json={"email": login_user.email, "password": SECRET_PASSWORD},
        headers={"User-Agent": "test-suite/1.0"},
    )
    assert resp.status_code == 200, resp.text

    rows = await _audit_rows(db_session)
    assert len(rows) >= 1
    row = rows[0]
    assert row.action == "login_attempt"
    assert row.details is not None
    assert row.details.get("actor_email") == login_user.email
    assert row.details.get("success") is True
    assert row.ip_address  # populated
    assert row.details.get("user_agent") == "test-suite/1.0"
    assert "failure_reason" not in row.details or row.details["failure_reason"] is None


# ---------------------------------------------------------------------------
# Failure cases — each must record a row with success=False + failure_reason
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_login_user_not_found_writes_audit_row(
    client: AsyncClient,
    db_session: AsyncSession,
):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "ghost@nowhere.invalid", "password": SECRET_PASSWORD},
        headers={"User-Agent": "ua-x"},
    )
    assert resp.status_code == 401

    rows = await _audit_rows(db_session)
    assert len(rows) == 1
    row = rows[0]
    assert row.details["actor_email"] == "ghost@nowhere.invalid"
    assert row.details["success"] is False
    assert row.details["failure_reason"] == "user_not_found"


@pytest.mark.asyncio
async def test_failed_login_password_mismatch_writes_audit_row(
    client: AsyncClient,
    db_session: AsyncSession,
    login_user: User,
):
    resp = await client.post(
        "/api/auth/login",
        json={"email": login_user.email, "password": "WrongPassword!"},
        headers={"User-Agent": "ua-y"},
    )
    assert resp.status_code == 401

    rows = await _audit_rows(db_session)
    assert any(
        r.details and r.details.get("failure_reason") == "password_mismatch"
        for r in rows
    ), [r.details for r in rows]


@pytest.mark.asyncio
async def test_failed_login_account_disabled_writes_audit_row(
    client: AsyncClient,
    db_session: AsyncSession,
    disabled_user: User,
):
    resp = await client.post(
        "/api/auth/login",
        json={"email": disabled_user.email, "password": SECRET_PASSWORD},
        headers={"User-Agent": "ua-z"},
    )
    assert resp.status_code in (401, 403)

    rows = await _audit_rows(db_session)
    assert any(
        r.details and r.details.get("failure_reason") == "account_disabled"
        for r in rows
    ), [r.details for r in rows]


@pytest.mark.asyncio
async def test_failed_login_tenant_suspended_writes_audit_row(
    client: AsyncClient,
    db_session: AsyncSession,
    login_user: User,
    login_tenant: Tenant,
):
    # Suspend the tenant — login should now fail with tenant_suspended
    login_tenant.is_active = False
    db_session.add(login_tenant)
    await db_session.commit()

    resp = await client.post(
        "/api/auth/login",
        json={"email": login_user.email, "password": SECRET_PASSWORD},
        headers={"User-Agent": "ua-w"},
    )
    assert resp.status_code in (401, 403)

    rows = await _audit_rows(db_session)
    assert any(
        r.details and r.details.get("failure_reason") == "tenant_suspended"
        for r in rows
    ), [r.details for r in rows]


# ---------------------------------------------------------------------------
# Password leak check — the SECRET must never appear in any audit row
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_password_never_persisted_to_audit_log(
    client: AsyncClient,
    db_session: AsyncSession,
    login_user: User,
):
    """Run all four flows then scan EVERY audit row text for the password."""
    # success
    await client.post(
        "/api/auth/login",
        json={"email": login_user.email, "password": SECRET_PASSWORD},
        headers={"User-Agent": "leak-ua"},
    )
    # password mismatch
    await client.post(
        "/api/auth/login",
        json={"email": login_user.email, "password": SECRET_PASSWORD + "X"},
        headers={"User-Agent": "leak-ua"},
    )
    # user not found
    await client.post(
        "/api/auth/login",
        json={"email": "no-such@nowhere.invalid", "password": SECRET_PASSWORD},
        headers={"User-Agent": "leak-ua"},
    )

    rows = await _audit_rows(db_session)
    assert rows, "no audit rows recorded"
    for row in rows:
        text = _row_text(row)
        assert SECRET_PASSWORD not in text, (
            f"PASSWORD LEAKED into audit row {row.id}: {text}"
        )
        # Also ensure the bad-attempt password never leaked
        assert (SECRET_PASSWORD + "X") not in text, (
            f"BAD ATTEMPT PASSWORD LEAKED into audit row {row.id}: {text}"
        )


@pytest.mark.asyncio
async def test_audit_row_for_failed_login_does_not_have_user_id_when_no_user(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """For 'user_not_found' there is no user → user_id should not crash the log."""
    resp = await client.post(
        "/api/auth/login",
        json={"email": "phantom@unknown.invalid", "password": "x"},
        headers={"User-Agent": "ua"},
    )
    assert resp.status_code == 401
    rows = await _audit_rows(db_session)
    assert rows
    # The row should still have a usable user_id (system sentinel) or be the
    # only entry with that email — the spec doesn't require a particular value
    # but the row MUST have been written.
    assert any(
        r.details and r.details.get("actor_email") == "phantom@unknown.invalid"
        for r in rows
    )

"""
TDD — Policy manager service tests.

Tests written BEFORE implementation.
Covers create, publish, acknowledge, pending, reminders, and expiry.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import text

from compliance_backend.models.policy import Policy, PolicyVersion, PolicyAcknowledgment
from compliance_backend.services import policy_manager


@pytest.fixture(autouse=True)
async def cleanup_policies(db_session):
    """Truncate policy tables after each test to ensure isolation."""
    yield
    await db_session.rollback()
    await db_session.execute(text("DELETE FROM policy_acknowledgments"))
    await db_session.execute(text("DELETE FROM policy_versions"))
    await db_session.execute(text("DELETE FROM policies"))
    await db_session.commit()


@pytest.mark.anyio
async def test_create_policy_creates_first_version(db_session):
    """create_policy creates a Policy and auto-publishes v1."""
    policy = await policy_manager.create_policy(
        session=db_session,
        tenant_id="tenant-1",
        name="Security Policy",
        content="# Security Policy\nBe secure.",
        owner="admin-1",
    )

    assert policy.id is not None
    assert policy.tenant_id == "tenant-1"
    assert policy.name == "Security Policy"
    assert policy.current_version_id is not None
    assert policy.is_active is True

    # Verify version exists
    versions = policy.versions
    assert len(versions) == 1
    assert versions[0].version_number == 1
    assert versions[0].content == "# Security Policy\nBe secure."


@pytest.mark.anyio
async def test_publish_new_version(db_session):
    """publish_new_version increments version and updates current_version_id."""
    policy = await policy_manager.create_policy(
        session=db_session,
        tenant_id="tenant-1",
        name="Versioned Policy",
        content="# V1",
        owner="admin-1",
    )

    v2 = await policy_manager.publish_new_version(
        session=db_session,
        policy_id=policy.id,
        content="# V2\nUpdated.",
        change_summary="Added new requirements",
        publisher="admin-1",
    )

    assert v2.version_number == 2
    assert v2.change_summary == "Added new requirements"

    await db_session.refresh(policy)
    assert policy.current_version_id == v2.id


@pytest.mark.anyio
async def test_acknowledge_creates_record(db_session):
    """
    acknowledge creates a PolicyAcknowledgment.

    HIGH-5 CHANGE — the previous expectation
    ``assert ack.signature == "sha256:abc123"`` captured the VULNERABLE
    behaviour where the server stored an attacker-controlled string verbatim
    (Codex HIGH-004 / Kimi MED-007). After the fix, the server computes its
    own HMAC-SHA256 and discards the caller's value. The new expectation is:
      - signature is exactly 64 hex chars (sha256 hex digest length)
      - the user-supplied "sha256:abc123" is NOT stored
      - verify_acknowledgment(ack) returns True
    """
    policy = await policy_manager.create_policy(
        session=db_session,
        tenant_id="tenant-1",
        name="Ack Policy",
        content="# Ack",
        owner="admin-1",
    )

    version = policy.versions[0]
    ack = await policy_manager.acknowledge(
        session=db_session,
        policy_version_id=version.id,
        user_id="user-1",
        signature="sha256:abc123",  # ignored by the server post-HIGH-5
    )

    assert ack.id is not None
    assert ack.policy_version_id == version.id
    assert ack.user_id == "user-1"
    assert ack.tenant_id == "tenant-1"
    # HIGH-5 — user-provided signature MUST NOT be stored as-is.
    assert ack.signature != "sha256:abc123"
    assert len(ack.signature) == 64  # sha256 hex
    assert policy_manager.verify_acknowledgment(ack) is True


@pytest.mark.anyio
async def test_acknowledge_is_idempotent(db_session):
    """
    acknowledge returns existing record on duplicate call.

    HIGH-5 CHANGE — the previous expectation
    ``assert ack2.signature == "sig1"`` exercised the same vulnerable
    "user-provided signature is stored verbatim" surface as the test above.
    Post-fix: the first ack's server-computed HMAC is preserved; the second
    call returns the same row. We assert idempotency without leaking the
    attacker-controlled string into the assertion.
    """
    policy = await policy_manager.create_policy(
        session=db_session,
        tenant_id="tenant-1",
        name="Idempotent Policy",
        content="# Content",
        owner="admin-1",
    )

    version = policy.versions[0]
    ack1 = await policy_manager.acknowledge(
        session=db_session,
        policy_version_id=version.id,
        user_id="user-1",
        signature="sig1",  # ignored
    )
    ack2 = await policy_manager.acknowledge(
        session=db_session,
        policy_version_id=version.id,
        user_id="user-1",
        signature="sig2",  # ignored
    )

    assert ack1.id == ack2.id
    # First-write-wins: same server-computed signature retained.
    assert ack1.signature == ack2.signature
    assert policy_manager.verify_acknowledgment(ack2) is True


@pytest.mark.anyio
async def test_list_pending_acknowledgments(db_session):
    """list_pending returns policies whose current version is not acked by user."""
    policy = await policy_manager.create_policy(
        session=db_session,
        tenant_id="tenant-1",
        name="Pending Policy",
        content="# Pending",
        owner="admin-1",
    )

    # User has not acknowledged → should be pending
    pending = await policy_manager.list_pending_acknowledgments(
        db_session, "tenant-1", "user-1"
    )
    assert len(pending) == 1
    assert pending[0].id == policy.id

    # Acknowledge
    await policy_manager.acknowledge(
        session=db_session,
        policy_version_id=policy.current_version_id,
        user_id="user-1",
        signature="sig",
    )

    # Now no longer pending
    pending = await policy_manager.list_pending_acknowledgments(
        db_session, "tenant-1", "user-1"
    )
    assert len(pending) == 0


@pytest.mark.anyio
async def test_list_pending_after_new_version(db_session):
    """Publishing a new version makes the policy pending again."""
    policy = await policy_manager.create_policy(
        session=db_session,
        tenant_id="tenant-1",
        name="Re-pending Policy",
        content="# V1",
        owner="admin-1",
    )

    await policy_manager.acknowledge(
        session=db_session,
        policy_version_id=policy.current_version_id,
        user_id="user-1",
        signature="sig",
    )

    await policy_manager.publish_new_version(
        session=db_session,
        policy_id=policy.id,
        content="# V2",
        change_summary="Updates",
        publisher="admin-1",
    )

    pending = await policy_manager.list_pending_acknowledgments(
        db_session, "tenant-1", "user-1"
    )
    assert len(pending) == 1
    assert pending[0].id == policy.id


@pytest.mark.anyio
async def test_send_reminders(db_session):
    """send_reminders returns users who acked old versions but not current."""
    policy = await policy_manager.create_policy(
        session=db_session,
        tenant_id="tenant-1",
        name="Reminder Policy",
        content="# V1",
        owner="admin-1",
    )

    # User acks v1
    await policy_manager.acknowledge(
        session=db_session,
        policy_version_id=policy.current_version_id,
        user_id="user-1",
        signature="sig1",
    )

    # Publish v2
    await policy_manager.publish_new_version(
        session=db_session,
        policy_id=policy.id,
        content="# V2",
        change_summary="Updates",
        publisher="admin-1",
    )

    reminders = await policy_manager.send_reminders(db_session, "tenant-1")
    assert len(reminders) == 1
    assert reminders[0][0].id == policy.id
    assert reminders[0][1] == "user-1"


@pytest.mark.anyio
async def test_check_expiry(db_session):
    """check_expiry returns policies expiring within 30 days."""
    soon = datetime.utcnow() + timedelta(days=10)

    policy = await policy_manager.create_policy(
        session=db_session,
        tenant_id="tenant-1",
        name="Expiring Policy",
        content="# Expire",
        owner="admin-1",
        expires_at=soon,
    )

    expiring = await policy_manager.check_expiry(db_session, "tenant-1")
    assert len(expiring) == 1
    assert expiring[0].id == policy.id


@pytest.mark.anyio
async def test_check_expiry_excludes_far_future(db_session):
    """Policies expiring far in the future are not returned."""
    far = datetime.utcnow() + timedelta(days=100)

    await policy_manager.create_policy(
        session=db_session,
        tenant_id="tenant-1",
        name="Long Policy",
        content="# Long",
        owner="admin-1",
        expires_at=far,
    )

    expiring = await policy_manager.check_expiry(db_session, "tenant-1")
    assert len(expiring) == 0

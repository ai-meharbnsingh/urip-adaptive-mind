"""
TDD — Policy model tests.

Tests written BEFORE implementation.
Covers model creation, FK constraints, tenant isolation, and relationships.
"""
import pytest
from sqlalchemy import select, text

from compliance_backend.models.policy import Policy, PolicyVersion, PolicyAcknowledgment


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
async def test_create_policy(db_session):
    """Policy can be created with required fields."""
    policy = Policy(
        tenant_id="tenant-1",
        name="Test Policy",
        owner_user_id="user-1",
        is_active=True,
    )
    db_session.add(policy)
    await db_session.commit()
    await db_session.refresh(policy)

    assert policy.id is not None
    assert len(policy.id) == 36
    assert policy.tenant_id == "tenant-1"
    assert policy.name == "Test Policy"
    assert policy.owner_user_id == "user-1"
    assert policy.current_version_id is None
    assert policy.is_active is True
    assert policy.created_at is not None


@pytest.mark.anyio
async def test_policy_version_fk_constraint(db_session):
    """PolicyVersion must have a valid policy_id FK."""
    policy = Policy(
        tenant_id="tenant-1",
        name="FK Test Policy",
        owner_user_id="user-1",
    )
    db_session.add(policy)
    await db_session.flush()

    version = PolicyVersion(
        policy_id=policy.id,
        version_number=1,
        content="# Version 1",
    )
    db_session.add(version)
    await db_session.commit()

    assert version.id is not None
    assert version.policy_id == policy.id


@pytest.mark.anyio
async def test_policy_version_orphan_deletion(db_session):
    """Deleting a policy cascades to its versions."""
    policy = Policy(
        tenant_id="tenant-1",
        name="Cascade Policy",
        owner_user_id="user-1",
    )
    db_session.add(policy)
    await db_session.flush()

    version = PolicyVersion(
        policy_id=policy.id,
        version_number=1,
        content="# Content",
    )
    db_session.add(version)
    await db_session.flush()

    await db_session.delete(policy)
    await db_session.commit()

    result = await db_session.execute(
        select(PolicyVersion).where(PolicyVersion.id == version.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.anyio
async def test_acknowledgment_unique_constraint(db_session):
    """A user can only acknowledge a version once."""
    policy = Policy(
        tenant_id="tenant-1",
        name="Ack Policy",
        owner_user_id="user-1",
    )
    db_session.add(policy)
    await db_session.flush()

    version = PolicyVersion(
        policy_id=policy.id,
        version_number=1,
        content="# Content",
    )
    db_session.add(version)
    await db_session.flush()

    ack1 = PolicyAcknowledgment(
        policy_version_id=version.id,
        user_id="user-a",
        tenant_id="tenant-1",
        signature="sig1",
    )
    db_session.add(ack1)
    await db_session.commit()

    ack2 = PolicyAcknowledgment(
        policy_version_id=version.id,
        user_id="user-a",
        tenant_id="tenant-1",
        signature="sig2",
    )
    db_session.add(ack2)
    with pytest.raises(Exception):
        await db_session.commit()


@pytest.mark.anyio
async def test_tenant_isolation(db_session):
    """Policies from different tenants are isolated."""
    p1 = Policy(tenant_id="tenant-a", name="Policy A", owner_user_id="u1")
    p2 = Policy(tenant_id="tenant-b", name="Policy B", owner_user_id="u2")
    db_session.add_all([p1, p2])
    await db_session.commit()

    result = await db_session.execute(
        select(Policy).where(Policy.tenant_id == "tenant-a")
    )
    policies = result.scalars().all()
    assert len(policies) == 1
    assert policies[0].name == "Policy A"


@pytest.mark.anyio
async def test_policy_current_version_relationship(db_session):
    """Policy.current_version resolves correctly."""
    policy = Policy(
        tenant_id="tenant-1",
        name="Rel Policy",
        owner_user_id="user-1",
    )
    db_session.add(policy)
    await db_session.flush()

    version = PolicyVersion(
        policy_id=policy.id,
        version_number=1,
        content="# V1",
    )
    db_session.add(version)
    await db_session.flush()

    policy.current_version_id = version.id
    await db_session.commit()
    await db_session.refresh(policy, attribute_names=["current_version"])

    assert policy.current_version is not None
    assert policy.current_version.id == version.id
    assert policy.current_version.content == "# V1"

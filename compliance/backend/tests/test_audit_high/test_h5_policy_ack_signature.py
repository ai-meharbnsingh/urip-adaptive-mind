"""
HIGH-5 — Policy acknowledgment non-repudiation.

Auditors:
  - Codex HIGH-004
  - Kimi MED-007

Vulnerability: ``PolicyAcknowledgment.signature`` was an attacker-controlled
string. Anyone with a valid JWT could record an "ack" with arbitrary content,
and there was no way for a third party (auditor) to confirm the ack actually
came from the user named.

Fix:
  - The server computes an HMAC-SHA256 over (policy_version_id, user_id,
    acknowledged_at_iso) using a server-side signing key, and stores that on
    the row.
  - A new ``verify_acknowledgment`` helper lets the auditor / regression tests
    re-derive the HMAC and compare. Tampering with the stored value flips the
    verifier to False.
"""
from __future__ import annotations

import os
import uuid

import pytest

from compliance_backend.models.policy import (
    Policy,
    PolicyVersion,
    PolicyAcknowledgment,
)
from compliance_backend.services import policy_manager


@pytest.fixture(autouse=True)
def _signing_key(monkeypatch):
    monkeypatch.setenv(
        "COMPLIANCE_POLICY_ACK_HMAC_KEY",
        "test-policy-ack-hmac-key-do-not-use-in-prod",
    )
    yield


@pytest.mark.anyio
async def test_acknowledge_stores_server_computed_signature(db_session):
    policy = await policy_manager.create_policy(
        session=db_session,
        tenant_id=str(uuid.uuid4()),
        name="Acceptable Use",
        content="content body",
        owner=str(uuid.uuid4()),
    )
    user_id = str(uuid.uuid4())

    ack = await policy_manager.acknowledge(
        session=db_session,
        policy_version_id=policy.current_version_id,
        user_id=user_id,
        signature="USER-PROVIDED-IGNORED",
    )

    # The stored signature must be the server-computed HMAC, NOT the
    # user-supplied string.
    assert ack.signature != "USER-PROVIDED-IGNORED"
    assert len(ack.signature) == 64  # hex sha256

    # And the verifier must agree.
    assert policy_manager.verify_acknowledgment(ack) is True


@pytest.mark.anyio
async def test_tampered_signature_fails_verification(db_session):
    policy = await policy_manager.create_policy(
        session=db_session,
        tenant_id=str(uuid.uuid4()),
        name="P-tamper",
        content="x",
        owner=str(uuid.uuid4()),
    )
    user_id = str(uuid.uuid4())

    ack = await policy_manager.acknowledge(
        session=db_session,
        policy_version_id=policy.current_version_id,
        user_id=user_id,
        signature="ignored",
    )

    # Tamper: flip the first character to a different hex digit
    original = ack.signature
    flipped = ("a" if original[0] != "a" else "b") + original[1:]
    ack.signature = flipped
    assert policy_manager.verify_acknowledgment(ack) is False

    # Restore: original verifies again
    ack.signature = original
    assert policy_manager.verify_acknowledgment(ack) is True


@pytest.mark.anyio
async def test_tampered_user_id_fails_verification(db_session):
    """Changing the user_id after the fact must invalidate the signature."""
    policy = await policy_manager.create_policy(
        session=db_session,
        tenant_id=str(uuid.uuid4()),
        name="P-user-tamper",
        content="x",
        owner=str(uuid.uuid4()),
    )
    real_user = str(uuid.uuid4())

    ack = await policy_manager.acknowledge(
        session=db_session,
        policy_version_id=policy.current_version_id,
        user_id=real_user,
        signature="ignored",
    )

    # Pretend an attacker rewrote user_id to claim someone else acked.
    other_user = str(uuid.uuid4())
    ack.user_id = other_user
    assert policy_manager.verify_acknowledgment(ack) is False


@pytest.mark.anyio
async def test_idempotent_returns_existing_ack_with_stored_signature(db_session):
    policy = await policy_manager.create_policy(
        session=db_session,
        tenant_id=str(uuid.uuid4()),
        name="P-idempotent",
        content="x",
        owner=str(uuid.uuid4()),
    )
    user_id = str(uuid.uuid4())

    first = await policy_manager.acknowledge(
        session=db_session,
        policy_version_id=policy.current_version_id,
        user_id=user_id,
        signature="anything-1",
    )
    second = await policy_manager.acknowledge(
        session=db_session,
        policy_version_id=policy.current_version_id,
        user_id=user_id,
        signature="anything-2",  # different — must be ignored
    )
    # Same row returned, same signature kept
    assert first.id == second.id
    assert first.signature == second.signature
    assert policy_manager.verify_acknowledgment(second) is True

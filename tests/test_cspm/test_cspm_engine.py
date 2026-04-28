"""
Tests for CSPM check engine.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.cspm import CspmCheckResult, CspmControl, CspmFramework, CspmScoreSnapshot
from backend.services.cspm_engine import CspmEngine
from backend.seeders.cspm.cis_aws_v2 import seed_cis_aws_v2
# Import rule modules so they register
import backend.services.cspm_rules.aws_rules  # noqa: F401
import backend.services.cspm_rules.azure_rules  # noqa: F401
import backend.services.cspm_rules.gcp_rules  # noqa: F401


@pytest_asyncio.fixture
async def seeded_aws_framework(db_session: AsyncSession) -> CspmFramework:
    await seed_cis_aws_v2(db_session)
    await db_session.commit()
    from sqlalchemy import select
    result = await db_session.execute(
        select(CspmFramework).where(CspmFramework.cloud_provider == "aws")
    )
    return result.scalars().first()


@pytest.mark.asyncio
async def test_engine_runs_all_controls(db_session: AsyncSession, seeded_aws_framework: CspmFramework):
    engine = CspmEngine(db_session)
    tenant_id = str(uuid.uuid4())
    results = await engine.run_cspm_checks(tenant_id, "aws", connector_data={})
    # All AWS controls have rule functions; with empty data many return inconclusive
    assert len(results) > 0
    assert all(isinstance(r, CspmCheckResult) for r in results)


@pytest.mark.asyncio
async def test_engine_score_computation(db_session: AsyncSession, seeded_aws_framework: CspmFramework):
    engine = CspmEngine(db_session)
    tenant_id = str(uuid.uuid4())
    connector_data = {
        "iam_users": [{"user_name": "root", "mfa_enabled": True}],
        "s3_buckets": [{"name": "bucket1", "public_read": False, "encryption": True}],
        "ec2_security_groups": [],
        "ec2_volumes": [{"volume_id": "vol-1", "encrypted": True}],
        "cloudtrail_trails": [{"name": "trail1", "is_multi_region_trail": True, "log_file_validation_enabled": True}],
        "vpcs": [{"vpc_id": "vpc-1"}],
        "vpc_flow_logs": [{"vpc_id": "vpc-1"}],
    }
    results = await engine.run_cspm_checks(tenant_id, "aws", connector_data)
    assert len(results) > 0

    # Check snapshot was created
    from sqlalchemy import select
    snap = await db_session.execute(
        select(CspmScoreSnapshot).where(
            CspmScoreSnapshot.tenant_id == uuid.UUID(tenant_id),
            CspmScoreSnapshot.cloud_provider == "aws",
        )
    )
    snapshot = snap.scalars().first()
    assert snapshot is not None
    assert 0 <= snapshot.score <= 100
    assert snapshot.pass_count + snapshot.fail_count + snapshot.inconclusive_count == len(results)


@pytest.mark.asyncio
async def test_engine_no_framework(db_session: AsyncSession):
    engine = CspmEngine(db_session)
    tenant_id = str(uuid.uuid4())
    results = await engine.run_cspm_checks(tenant_id, "oracle", connector_data={})
    assert results == []


@pytest.mark.asyncio
async def test_engine_connector_data_none(db_session: AsyncSession, seeded_aws_framework: CspmFramework):
    engine = CspmEngine(db_session)
    tenant_id = str(uuid.uuid4())
    results = await engine.run_cspm_checks(tenant_id, "aws")
    assert len(results) > 0

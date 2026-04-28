"""
Tests for CIS benchmark seeders.
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.cspm import CspmControl, CspmFramework
from backend.seeders.cspm.cis_aws_v2 import seed_cis_aws_v2, CIS_AWS_CONTROLS
from backend.seeders.cspm.cis_azure_v2 import seed_cis_azure_v2, CIS_AZURE_CONTROLS
from backend.seeders.cspm.cis_gcp_v3 import seed_cis_gcp_v3, CIS_GCP_CONTROLS


@pytest.mark.asyncio
async def test_seed_cis_aws_v2(db_session: AsyncSession):
    await seed_cis_aws_v2(db_session)
    await db_session.commit()

    fw = await db_session.execute(
        CspmFramework.__table__.select().where(CspmFramework.name == "CIS AWS Foundations v2.0")
    )
    framework = fw.fetchone()
    assert framework is not None
    assert framework.cloud_provider == "aws"

    ctrl_result = await db_session.execute(
        CspmControl.__table__.select().where(CspmControl.framework_id == framework.id)
    )
    controls = ctrl_result.fetchall()
    assert len(controls) == len(CIS_AWS_CONTROLS)
    assert len(controls) >= 58


@pytest.mark.asyncio
async def test_seed_cis_azure_v2(db_session: AsyncSession):
    await seed_cis_azure_v2(db_session)
    await db_session.commit()

    fw = await db_session.execute(
        CspmFramework.__table__.select().where(CspmFramework.name == "CIS Azure Foundations v2.0")
    )
    framework = fw.fetchone()
    assert framework is not None
    assert framework.cloud_provider == "azure"

    ctrl_result = await db_session.execute(
        CspmControl.__table__.select().where(CspmControl.framework_id == framework.id)
    )
    controls = ctrl_result.fetchall()
    assert len(controls) == len(CIS_AZURE_CONTROLS)
    assert len(controls) >= 120


@pytest.mark.asyncio
async def test_seed_cis_gcp_v3(db_session: AsyncSession):
    await seed_cis_gcp_v3(db_session)
    await db_session.commit()

    fw = await db_session.execute(
        CspmFramework.__table__.select().where(CspmFramework.name == "CIS GCP Foundations v3.0")
    )
    framework = fw.fetchone()
    assert framework is not None
    assert framework.cloud_provider == "gcp"

    ctrl_result = await db_session.execute(
        CspmControl.__table__.select().where(CspmControl.framework_id == framework.id)
    )
    controls = ctrl_result.fetchall()
    assert len(controls) == len(CIS_GCP_CONTROLS)
    assert len(controls) >= 110


@pytest.mark.asyncio
async def test_seed_all_idempotent(db_session: AsyncSession):
    """Running seeders twice should not duplicate controls."""
    await seed_cis_aws_v2(db_session)
    await seed_cis_aws_v2(db_session)
    await db_session.commit()

    fw = await db_session.execute(
        CspmFramework.__table__.select().where(CspmFramework.name == "CIS AWS Foundations v2.0")
    )
    framework = fw.fetchone()
    ctrl_result = await db_session.execute(
        CspmControl.__table__.select().where(CspmControl.framework_id == framework.id)
    )
    controls = ctrl_result.fetchall()
    assert len(controls) == len(CIS_AWS_CONTROLS)

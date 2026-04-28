"""
CLI runner for all CSPM CIS seeders.

Usage:
    python -m backend.seeders.cspm.run_all
"""
from __future__ import annotations

import asyncio
import logging

from backend.database import async_session
from backend.seeders.cspm.cis_aws_v2 import seed_cis_aws_v2
from backend.seeders.cspm.cis_azure_v2 import seed_cis_azure_v2
from backend.seeders.cspm.cis_gcp_v3 import seed_cis_gcp_v3

logger = logging.getLogger(__name__)


async def seed_all() -> None:
    async with async_session() as session:
        await seed_cis_aws_v2(session)
        await seed_cis_azure_v2(session)
        await seed_cis_gcp_v3(session)
        await session.commit()
        logger.info("All CSPM CIS seeders completed.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_all())

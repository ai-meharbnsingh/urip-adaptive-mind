"""
CLI runner for all framework seeders.

Usage:
    # From compliance/backend/ with installed package:
    python -m compliance_backend.seeders.run_all

    # Or via docker:
    docker-compose -f docker-compose.standalone.yml exec compliance_api \
        python -m compliance_backend.seeders.run_all

Idempotent — safe to run multiple times.
"""
import asyncio
import sys

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from compliance_backend.config import settings
from compliance_backend.database import Base
from compliance_backend.seeders.soc2 import seed_soc2
from compliance_backend.seeders.iso27001 import seed_iso27001


async def run() -> None:
    print(f"[seeder] Connecting to: {settings.COMPLIANCE_DB_URL}")

    engine = create_async_engine(settings.COMPLIANCE_DB_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with factory() as session:
        print("[seeder] Seeding SOC 2...")
        await seed_soc2(session)
        print("[seeder] Seeding ISO 27001:2022...")
        await seed_iso27001(session)
        await session.commit()
        print("[seeder] Done. All framework seeds committed.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())

"""
Dev server with in-memory SQLite — seeds frameworks on startup.
Used for local testing without Docker/Postgres.

Run:
    cd compliance/backend/
    python dev_server.py

Then:
    curl http://localhost:8001/health
    curl -H "Authorization: Bearer <token>" http://localhost:8001/frameworks
"""
import asyncio
import os

os.environ["COMPLIANCE_DB_URL"] = "sqlite+aiosqlite:///./dev.db"
os.environ["COMPLIANCE_JWT_SECRET"] = "dev-secret"
os.environ["COMPLIANCE_AUTH_MODE"] = "STANDALONE"

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from compliance_backend.database import Base
from compliance_backend.seeders.soc2 import seed_soc2
from compliance_backend.seeders.iso27001 import seed_iso27001


async def init_db():
    engine = create_async_engine(os.environ["COMPLIANCE_DB_URL"], echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        await seed_soc2(session)
        await seed_iso27001(session)
        await session.commit()
    await engine.dispose()
    print("[dev_server] DB initialized and seeded.")


if __name__ == "__main__":
    asyncio.run(init_db())

    import uvicorn
    from compliance_backend.main import app
    uvicorn.run(app, host="0.0.0.0", port=8001)

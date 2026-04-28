"""
Shared test fixtures for compliance backend tests.

Uses SQLite in-memory for all DB-touching tests so no running Postgres is required.
The async engine is configured via a module-scoped override of get_async_session.
"""
import os
import tempfile
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Point at in-memory SQLite before importing anything that touches DB
os.environ.setdefault("COMPLIANCE_DB_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("COMPLIANCE_JWT_SECRET", "test-secret-standalone")
os.environ.setdefault("COMPLIANCE_AUTH_MODE", "STANDALONE")
os.environ.setdefault("URIP_JWT_SECRET", "urip-shared-secret-for-test")

# Use a temp dir for filesystem storage in tests — avoids polluting the project dir
_EVIDENCE_TMPDIR = tempfile.mkdtemp(prefix="compliance_evidence_test_")
os.environ.setdefault("EVIDENCE_STORAGE_BASE_DIR", _EVIDENCE_TMPDIR)

from compliance_backend.main import app
from compliance_backend.database import Base, get_async_session

# Ensure new model tables are registered in Base.metadata by importing them explicitly
import compliance_backend.models.control_run  # noqa: F401
import compliance_backend.models.evidence  # noqa: F401
import compliance_backend.models.auditor  # noqa: F401
import compliance_backend.models.score_snapshot  # noqa: F401
import compliance_backend.models.tenant_state  # noqa: F401  # CRIT-006 server-side state
import compliance_backend.models.vendor  # noqa: F401
import compliance_backend.models.compliance_audit_log  # noqa: F401  # CritFix-B NEW-1
# Simulator-only TBD models (incidents, assets, access reviews) — promoted later
import compliance_backend.seeders.simulators.sim_models  # noqa: F401


# ---------------------------------------------------------------------------
# In-memory async engine (SQLite)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(scope="session")
async def session_factory(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return factory


@pytest_asyncio.fixture()
async def db_session(session_factory):
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture(autouse=True)
def _reset_compliance_rate_limit_state():
    """
    HIGH-2 audit fix added a process-wide slowapi limiter. Clear its in-
    memory storage before every test so test ordering can't cause spurious
    429s (writes from earlier tests would otherwise fill the per-IP bucket).
    """
    try:
        from compliance_backend.middleware import rate_limit as _rl
        try:
            _rl.limiter.limiter.storage.reset()
        except Exception:
            for attr in ("storage", "events", "expirations", "locks"):
                bucket = getattr(_rl.limiter.limiter.storage, attr, None)
                if bucket is not None and hasattr(bucket, "clear"):
                    try:
                        bucket.clear()
                    except Exception:
                        pass
    except Exception:
        pass
    yield


@pytest_asyncio.fixture()
async def client(session_factory):
    """HTTP client wired to the FastAPI app with DB override."""

    async def _override_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_async_session] = _override_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()

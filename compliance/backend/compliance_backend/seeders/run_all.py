"""
CLI runner for all framework seeders.

Usage:
    # From compliance/backend/ with installed package:
    python -m compliance_backend.seeders.run_all

    # Or via docker:
    docker-compose -f docker-compose.standalone.yml exec compliance_api \
        python -m compliance_backend.seeders.run_all

Idempotent — safe to run multiple times.

Currently registered: 15 frameworks
  Original 7 (Phase 2B): SOC 2, ISO 27001, GDPR, HIPAA, PCI DSS, India DPDP, NIST CSF
  New 8 (Phase 2C):      ISO 42001, EU AI Act, DORA, NIS2, ISO 27017,
                         ISO 27018, ISO 27701, CIS Controls v8
"""
import asyncio

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from compliance_backend.config import settings
from compliance_backend.database import Base  # noqa: F401  (kept for compatibility)
# Original 7
from compliance_backend.seeders.soc2 import seed_soc2
from compliance_backend.seeders.iso27001 import seed_iso27001
from compliance_backend.seeders.gdpr import seed_gdpr
from compliance_backend.seeders.hipaa import seed_hipaa
from compliance_backend.seeders.pci_dss import seed_pci_dss
from compliance_backend.seeders.india_dpdp import seed_india_dpdp
from compliance_backend.seeders.nist_csf import seed_nist_csf
# New 8 (Phase 2C)
from compliance_backend.seeders.iso42001 import seed_iso42001
from compliance_backend.seeders.eu_ai_act import seed_eu_ai_act
from compliance_backend.seeders.dora import seed_dora
from compliance_backend.seeders.nis2 import seed_nis2
from compliance_backend.seeders.iso27017 import seed_iso27017
from compliance_backend.seeders.iso27018 import seed_iso27018
from compliance_backend.seeders.iso27701 import seed_iso27701
from compliance_backend.seeders.cis_v8 import seed_cis_v8
# Cross-framework mappings (must run AFTER all framework seeders)
from compliance_backend.seeders.cross_mappings import seed_cross_mappings


# Ordered registry — original 7 first, then new 8, then mappings.
# Each entry: (display_name, seeder_callable)
SEEDER_REGISTRY: list[tuple[str, callable]] = [
    ("SOC 2", seed_soc2),
    ("ISO 27001:2022", seed_iso27001),
    ("GDPR", seed_gdpr),
    ("HIPAA", seed_hipaa),
    ("PCI DSS v4.0", seed_pci_dss),
    ("India DPDP Act 2023", seed_india_dpdp),
    ("NIST CSF 2.0", seed_nist_csf),
    # ----- new 8 -----
    ("ISO 42001:2023 (AI MS)", seed_iso42001),
    ("EU AI Act (Regulation 2024/1689)", seed_eu_ai_act),
    ("DORA (EU 2022/2554)", seed_dora),
    ("NIS2 Directive (EU 2022/2555)", seed_nis2),
    ("ISO 27017 (Cloud Security)", seed_iso27017),
    ("ISO 27018 (Cloud Privacy / PII)", seed_iso27018),
    ("ISO 27701 (PIMS)", seed_iso27701),
    ("CIS Controls v8", seed_cis_v8),
]


async def run() -> None:
    print(f"[seeder] Connecting to: {settings.COMPLIANCE_DB_URL}")

    engine = create_async_engine(settings.COMPLIANCE_DB_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with factory() as session:
        for name, seeder in SEEDER_REGISTRY:
            print(f"[seeder] Seeding {name}...")
            await seeder(session)

        print("[seeder] Seeding cross-framework mappings...")
        await seed_cross_mappings(session)

        await session.commit()
        print(
            f"[seeder] Done. {len(SEEDER_REGISTRY)} frameworks + cross-mappings committed."
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())

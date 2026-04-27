"""
Framework seeders for the Compliance Service.

Each seeder is idempotent — calling it twice must not create duplicate records.
The pattern used: check if framework short_code exists first; if yes, skip.

Usage (from a migration, CLI command, or startup hook):
    from compliance_backend.seeders.soc2 import seed_soc2
    from compliance_backend.seeders.iso27001 import seed_iso27001

    async with AsyncSession(engine) as session:
        await seed_soc2(session)
        await seed_iso27001(session)
        await session.commit()
"""

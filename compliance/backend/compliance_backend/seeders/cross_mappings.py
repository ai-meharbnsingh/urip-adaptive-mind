"""
Cross-framework control mappings seeder.

Maps equivalent and related controls across all 7 frameworks:
  SOC 2, ISO 27001, GDPR, HIPAA, PCI DSS v4.0, India DPDP Act 2023, NIST CSF 2.0

Each mapping resolves control codes to Control UUIDs at runtime using DB lookups.
This allows the seeder to work regardless of the UUID values assigned during seeding.

Mapping types:
  equivalent   — the two controls address exactly the same requirement
  partial      — source partially satisfies target (manual gap assessment needed)
  prerequisite — source control must pass before target is evaluated

Cross-mapping catalogue (25 mappings):
  1.  GDPR Art. 32   ↔ ISO 27001 5.32   (equivalent — security of processing / protection of records)
  2.  GDPR Art. 32   ↔ SOC 2 CC6.1      (equivalent — security measures)
  3.  GDPR Art. 32   ↔ HIPAA 164.312(a)(1) (equivalent — access control / security)
  4.  GDPR Art. 32   ↔ NIST PR.DS-01    (equivalent — data at rest security)
  5.  GDPR Art. 32   ↔ PCI DSS 3.5.1    (partial — PAN encryption vs PHI security)
  6.  ISO 27001 5.34 ↔ GDPR Art. 5(1)(f) (equivalent — privacy and PII protection)
  7.  ISO 27001 8.5  ↔ SOC 2 CC6.1      (equivalent — secure authentication / logical access)
  8.  ISO 27001 8.5  ↔ HIPAA 164.312(d) (equivalent — authentication)
  9.  ISO 27001 8.5  ↔ NIST PR.AA-03    (equivalent — authentication)
  10. ISO 27001 8.5  ↔ PCI DSS 8.3.1    (equivalent — authentication lifecycle)
  11. SOC 2 CC6.1    ↔ NIST PR.AA-05    (equivalent — access permissions / logical access)
  12. SOC 2 CC6.1    ↔ HIPAA 164.308(a)(4)(ii)(A) (equivalent — access authorization)
  13. SOC 2 CC7.2    ↔ NIST DE.CM-01    (equivalent — monitoring / anomaly detection)
  14. SOC 2 CC7.4    ↔ NIST RS.MA-01    (equivalent — incident response)
  15. SOC 2 CC7.4    ↔ HIPAA 164.308(a)(6)(ii) (equivalent — incident response)
  16. HIPAA 164.308(a)(1)(i) ↔ NIST ID.RA-01 (equivalent — risk analysis / vulnerability identification)
  17. HIPAA 164.312(e)(2)(ii) ↔ PCI DSS 4.2.1 (equivalent — transmission encryption)
  18. HIPAA 164.312(e)(2)(ii) ↔ ISO 27001 8.24 (equivalent — use of cryptography)
  19. PCI DSS 10.2.1 ↔ NIST DE.CM-01   (equivalent — audit logs / network monitoring)
  20. PCI DSS 12.10.1 ↔ NIST RS.MA-01  (equivalent — incident response plan)
  21. PCI DSS 11.3.1 ↔ NIST ID.RA-01   (partial — vulnerability scans vs vulnerability identification)
  22. GDPR Art. 33   ↔ HIPAA 164.308(a)(6)(ii) (equivalent — breach notification / incident reporting)
  23. GDPR Art. 12   ↔ India DPDP Sec. 5 (equivalent — notice and transparency)
  24. GDPR Art. 7    ↔ India DPDP Sec. 6(1) (equivalent — consent requirements)
  25. GDPR Art. 17   ↔ India DPDP Sec. 12 (equivalent — right to erasure / correction and erasure)

Idempotent: uses INSERT OR IGNORE semantics via DB unique constraint on (source, target).
"""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from compliance_backend.models.framework import (
    Framework, FrameworkVersion, Control, FrameworkControlMapping
)


# ---------------------------------------------------------------------------
# Mapping catalogue
# Format: (source_fw, source_code, target_fw, target_code, mapping_type)
# source_fw / target_fw = short_code of framework
# ---------------------------------------------------------------------------
MAPPING_CATALOGUE: list[tuple[str, str, str, str, str]] = [
    # ===========================================================
    # ORIGINAL 25 — across the original 7 frameworks (Phase 2B)
    # ===========================================================
    # 1
    ("GDPR", "Art. 32", "ISO27001", "5.32", "equivalent"),
    # 2
    ("GDPR", "Art. 32", "SOC2", "CC6.1", "equivalent"),
    # 3
    ("GDPR", "Art. 32", "HIPAA", "164.312(a)(1)", "equivalent"),
    # 4
    ("GDPR", "Art. 32", "NISTCSF", "PR.DS-01", "equivalent"),
    # 5
    ("GDPR", "Art. 32", "PCIDSS", "3.5.1", "partial"),
    # 6
    ("ISO27001", "5.34", "GDPR", "Art. 5(1)(f)", "equivalent"),
    # 7
    ("ISO27001", "8.5", "SOC2", "CC6.1", "equivalent"),
    # 8
    ("ISO27001", "8.5", "HIPAA", "164.312(d)", "equivalent"),
    # 9
    ("ISO27001", "8.5", "NISTCSF", "PR.AA-03", "equivalent"),
    # 10
    ("ISO27001", "8.5", "PCIDSS", "8.3.1", "equivalent"),
    # 11
    ("SOC2", "CC6.1", "NISTCSF", "PR.AA-05", "equivalent"),
    # 12
    ("SOC2", "CC6.1", "HIPAA", "164.308(a)(4)(ii)(A)", "equivalent"),
    # 13
    ("SOC2", "CC7.2", "NISTCSF", "DE.CM-01", "equivalent"),
    # 14
    ("SOC2", "CC7.4", "NISTCSF", "RS.MA-01", "equivalent"),
    # 15
    ("SOC2", "CC7.4", "HIPAA", "164.308(a)(6)(ii)", "equivalent"),
    # 16
    ("HIPAA", "164.308(a)(1)(i)", "NISTCSF", "ID.RA-01", "equivalent"),
    # 17
    ("HIPAA", "164.312(e)(2)(ii)", "PCIDSS", "4.2.1", "equivalent"),
    # 18
    ("HIPAA", "164.312(e)(2)(ii)", "ISO27001", "8.24", "equivalent"),
    # 19
    ("PCIDSS", "10.2.1", "NISTCSF", "DE.CM-01", "equivalent"),
    # 20
    ("PCIDSS", "12.10.1", "NISTCSF", "RS.MA-01", "equivalent"),
    # 21
    ("PCIDSS", "11.3.1", "NISTCSF", "ID.RA-01", "partial"),
    # 22
    ("GDPR", "Art. 33", "HIPAA", "164.308(a)(6)(ii)", "equivalent"),
    # 23
    ("GDPR", "Art. 12", "DPDP", "Sec. 5", "equivalent"),
    # 24
    ("GDPR", "Art. 7", "DPDP", "Sec. 6(1)", "equivalent"),
    # 25
    ("GDPR", "Art. 17", "DPDP", "Sec. 12", "equivalent"),

    # ===========================================================
    # NEW 35 — Phase 2C: cross-mappings touching the 8 new frameworks
    # ===========================================================
    # --- ISO 42001 (AI MS) ↔ EU AI Act ---
    # AI policy ↔ EU AI Act high-risk requirement to integrate AI in QMS
    ("ISO42001", "A.2.2", "EUAIACT", "Art. 17", "equivalent"),
    # AI risk management process ↔ EU AI Act Art. 9 risk management
    ("ISO42001", "Cl.6.1.2", "EUAIACT", "Art. 9", "equivalent"),
    # AI impact assessment ↔ EU AI Act FRIA (Art. 27)
    ("ISO42001", "A.5.2", "EUAIACT", "Art. 27", "partial"),
    # Data quality (A.7.4) ↔ EU AI Act Art. 10 data governance
    ("ISO42001", "A.7.4", "EUAIACT", "Art. 10", "equivalent"),
    # Logging events (A.6.2.8) ↔ EU AI Act Art. 12 record-keeping
    ("ISO42001", "A.6.2.8", "EUAIACT", "Art. 12", "equivalent"),
    # Technical documentation (A.6.2.7) ↔ EU AI Act Art. 11
    ("ISO42001", "A.6.2.7", "EUAIACT", "Art. 11", "equivalent"),

    # --- EU AI Act ↔ ISO 27001 / NIST CSF (security obligations on AI systems) ---
    # AI cybersecurity (Art. 15) ↔ ISO 27001 8.5 secure auth (partial — broader)
    ("EUAIACT", "Art. 15", "ISO27001", "8.24", "partial"),
    # AI risk management (Art. 9) ↔ NIST CSF risk identification
    ("EUAIACT", "Art. 9", "NISTCSF", "ID.RA-01", "equivalent"),

    # --- DORA ↔ NIS2 (both EU operational resilience but for different sectors) ---
    # DORA ICT risk management framework ↔ NIS2 Art. 21 risk management
    ("DORA", "Art. 6(1)", "NIS2", "Art. 21(1)", "equivalent"),
    # DORA incident classification ↔ NIS2 Art. 23(3) significance criteria
    ("DORA", "Art. 18", "NIS2", "Art. 23(3)", "equivalent"),
    # DORA major incident reporting (24h initial) ↔ NIS2 Art. 23(4)(a) early warning
    ("DORA", "Art. 19(1)", "NIS2", "Art. 23(4)(a)", "equivalent"),
    # DORA third-party register ↔ NIS2 Art. 21(2)(d) supply chain
    ("DORA", "Art. 28(3)", "NIS2", "Art. 21(2)(d)", "partial"),
    # DORA testing programme ↔ NIS2 Art. 21(2)(f) effectiveness assessment
    ("DORA", "Art. 24(1)", "NIS2", "Art. 21(2)(f)", "equivalent"),

    # --- DORA ↔ ISO 27001 ---
    # DORA Art. 9 protection ↔ ISO 27001 5.1 policies
    ("DORA", "Art. 9(2)", "ISO27001", "5.1", "equivalent"),
    # DORA Art. 11 ICT continuity ↔ ISO 27001 5.30 ICT readiness
    ("DORA", "Art. 11(1)", "ISO27001", "5.30", "equivalent"),
    # DORA Art. 12 backup ↔ ISO 27001 8.13 information backup
    ("DORA", "Art. 12(1)", "ISO27001", "8.13", "equivalent"),

    # --- NIS2 ↔ ISO 27001 / NIST CSF / SOC 2 ---
    # NIS2 Art. 21 risk analysis ↔ ISO 27001 5.1 policies
    ("NIS2", "Art. 21(2)(a)", "ISO27001", "5.1", "equivalent"),
    # NIS2 incident handling ↔ NIST CSF respond
    ("NIS2", "Art. 21(2)(b)", "NISTCSF", "RS.MA-01", "equivalent"),
    # NIS2 cryptography ↔ ISO 27001 8.24
    ("NIS2", "Art. 21(2)(h)", "ISO27001", "8.24", "equivalent"),
    # NIS2 MFA ↔ SOC 2 CC6.1 (logical access)
    ("NIS2", "Art. 21(2)(j)", "SOC2", "CC6.1", "partial"),
    # NIS2 incident reporting ↔ GDPR Art. 33 breach notification (overlap when PII involved)
    ("NIS2", "Art. 23(4)(a)", "GDPR", "Art. 33", "partial"),

    # --- ISO 27017 (Cloud) ↔ ISO 27001 / SOC 2 ---
    # 27017 segregation in virtual environments ↔ ISO 27001 8.22 network segregation
    ("ISO27017", "CLD.9.5.1", "ISO27001", "8.22", "equivalent"),
    # 27017 cloud admin ops ↔ ISO 27001 8.2 privileged access
    ("ISO27017", "CLD.12.1.5", "ISO27001", "8.2", "equivalent"),
    # 27017 cloud monitoring ↔ SOC 2 CC7.2 monitoring
    ("ISO27017", "CLD.12.4.5", "SOC2", "CC7.2", "equivalent"),

    # --- ISO 27018 (Cloud PII) ↔ GDPR / DPDP ---
    # 27018 A.2.1 (purpose) ↔ GDPR Art. 5(1)(b) purpose limitation
    ("ISO27018", "A.2.1", "GDPR", "Art. 5(1)(b)", "equivalent"),
    # 27018 A.10.6 (transit encryption) ↔ GDPR Art. 32
    ("ISO27018", "A.10.6", "GDPR", "Art. 32", "equivalent"),
    # 27018 A.6.1 (breach notification) ↔ GDPR Art. 33
    ("ISO27018", "A.6.1", "GDPR", "Art. 33", "equivalent"),
    # 27018 A.7.1 (geographic location of PII) ↔ DPDP cross-border (Sec. 16)
    ("ISO27018", "A.7.1", "DPDP", "Sec. 16", "partial"),

    # --- ISO 27701 (PIMS) ↔ GDPR / DPDP / SOC 2 ---
    # 27701 A.7.2.5 PIA ↔ GDPR Art. 35 DPIA
    ("ISO27701", "A.7.2.5", "GDPR", "Art. 35", "equivalent"),
    # 27701 A.7.3.6 access/correction/erasure ↔ GDPR Art. 15
    ("ISO27701", "A.7.3.6", "GDPR", "Art. 15", "equivalent"),
    # 27701 A.7.2.4 record consent ↔ GDPR Art. 7
    ("ISO27701", "A.7.2.4", "GDPR", "Art. 7", "equivalent"),
    # 27701 A.7.2.4 record consent ↔ DPDP Sec. 6(1)
    ("ISO27701", "A.7.2.4", "DPDP", "Sec. 6(1)", "equivalent"),
    # 27701 B.8.5.6 sub-processor disclosure ↔ GDPR Art. 28
    ("ISO27701", "B.8.5.6", "GDPR", "Art. 28", "equivalent"),

    # --- CIS v8 ↔ NIST CSF / ISO 27001 / PCI DSS / SOC 2 ---
    # CIS 1.1 asset inventory ↔ ISO 27001 5.9
    ("CISV8", "1.1", "ISO27001", "5.9", "equivalent"),
    # CIS 5.1 account inventory ↔ NIST CSF PR.AA-05
    ("CISV8", "5.1", "NISTCSF", "PR.AA-05", "equivalent"),
    # CIS 6.3 MFA ↔ PCI DSS 8.3.1
    ("CISV8", "6.3", "PCIDSS", "8.3.1", "equivalent"),
    # CIS 7.3 patch mgmt ↔ ISO 27001 8.8 vulnerabilities
    ("CISV8", "7.3", "ISO27001", "8.8", "equivalent"),
    # CIS 8.2 audit log ↔ SOC 2 CC7.2 monitoring
    ("CISV8", "8.2", "SOC2", "CC7.2", "equivalent"),
    # CIS 11.2 backups ↔ ISO 27001 8.13
    ("CISV8", "11.2", "ISO27001", "8.13", "equivalent"),
    # CIS 17.4 incident response ↔ NIST CSF RS.MA-01
    ("CISV8", "17.4", "NISTCSF", "RS.MA-01", "equivalent"),
    # CIS 18.2 external pentest ↔ PCI DSS 11.3.1
    ("CISV8", "18.2", "PCIDSS", "11.3.1", "equivalent"),
]


async def _get_control_id(
    session: AsyncSession, fw_short_code: str, control_code: str
) -> str | None:
    """Resolve a (framework short_code, control_code) pair to a Control.id."""
    fw_result = await session.execute(
        select(Framework).where(Framework.short_code == fw_short_code)
    )
    framework = fw_result.scalars().first()
    if not framework:
        return None

    ver_result = await session.execute(
        select(FrameworkVersion).where(
            and_(
                FrameworkVersion.framework_id == framework.id,
                FrameworkVersion.is_current == True,  # noqa: E712
            )
        )
    )
    version = ver_result.scalars().first()
    if not version:
        return None

    ctrl_result = await session.execute(
        select(Control).where(
            and_(
                Control.framework_version_id == version.id,
                Control.control_code == control_code,
            )
        )
    )
    control = ctrl_result.scalars().first()
    return control.id if control else None


async def seed_cross_mappings(session: AsyncSession) -> None:
    """
    Idempotent cross-framework mapping seeder.

    Resolves each mapping entry in MAPPING_CATALOGUE to Control UUIDs and
    creates FrameworkControlMapping records. Skips mappings where either
    control is not found (e.g., framework not yet seeded) or where the
    mapping already exists (idempotency via unique constraint).
    """
    for src_fw, src_code, tgt_fw, tgt_code, mtype in MAPPING_CATALOGUE:
        src_id = await _get_control_id(session, src_fw, src_code)
        tgt_id = await _get_control_id(session, tgt_fw, tgt_code)

        if not src_id or not tgt_id:
            # One of the frameworks/controls is not seeded — skip silently
            continue

        # Idempotency check — skip if mapping already exists
        existing = await session.execute(
            select(FrameworkControlMapping).where(
                and_(
                    FrameworkControlMapping.source_control_id == src_id,
                    FrameworkControlMapping.target_control_id == tgt_id,
                )
            )
        )
        if existing.scalars().first():
            continue

        mapping = FrameworkControlMapping(
            id=str(uuid.uuid4()),
            source_control_id=src_id,
            target_control_id=tgt_id,
            mapping_type=mtype,
        )
        session.add(mapping)

    await session.flush()

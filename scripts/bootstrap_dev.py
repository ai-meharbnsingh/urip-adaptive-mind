"""
Dev bootstrap — creates a default tenant + admin user + small risk dataset.
Idempotent: re-running just upserts.

Run with:
    PYTHONPATH=. DATABASE_URL_SYNC=postgresql://urip:urip_dev@localhost:5433/urip \
        .venv/bin/python scripts/bootstrap_dev.py
"""
from __future__ import annotations

import os
import secrets
import string
import uuid
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.database import Base
from backend.middleware.auth import hash_password
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.models.risk import Risk


DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
ADMIN_EMAIL = "admin@adaptive-mind.com"


def _generate_random_password(length: int = 16) -> str:
    """Produce a strong random password with mixed case, digits, and symbols."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        # Guarantee at least one of each required character class.
        has_upper = any(c in string.ascii_uppercase for c in pwd)
        has_lower = any(c in string.ascii_lowercase for c in pwd)
        has_digit = any(c in string.digits for c in pwd)
        has_symbol = any(c in "!@#$%^&*()-_=+" for c in pwd)
        if has_upper and has_lower and has_digit and has_symbol:
            return pwd


_ENV_PASSWORD = os.environ.get("URIP_DEV_ADMIN_PASSWORD")
ADMIN_PASSWORD = _ENV_PASSWORD or _generate_random_password()
_PASSWORD_IS_GENERATED = _ENV_PASSWORD is None


def main() -> None:
    db_url = os.environ.get(
        "DATABASE_URL_SYNC",
        "postgresql://urip:urip_dev@localhost:5433/urip",
    )
    engine = create_engine(db_url)

    with Session(engine) as s:
        # ── 1. Tenant ─────────────────────────────────────────────────
        tenant = s.get(Tenant, DEFAULT_TENANT_ID)
        if tenant is None:
            tenant = Tenant(
                id=DEFAULT_TENANT_ID,
                name="Adaptive Mind Demo",
                slug="adaptive-demo",
                domain="adaptive-mind.com",
                is_active=True,
                settings={},
            )
            s.add(tenant)
            s.commit()
            print(f"[+] Created tenant {tenant.slug}")
        else:
            print(f"[=] Tenant {tenant.slug} already exists")

        # ── 2. Admin user ────────────────────────────────────────────
        admin = s.execute(select(User).where(User.email == ADMIN_EMAIL)).scalar_one_or_none()
        if admin is None:
            admin = User(
                id=uuid.uuid4(),
                tenant_id=DEFAULT_TENANT_ID,
                email=ADMIN_EMAIL,
                hashed_password=hash_password(ADMIN_PASSWORD),
                full_name="URIP Administrator",
                role="ciso",
                is_active=True,
            )
            s.add(admin)
            s.commit()
            if _PASSWORD_IS_GENERATED:
                print(f"[+] Created admin {ADMIN_EMAIL} / password={ADMIN_PASSWORD!r}  ← auto-generated; set URIP_DEV_ADMIN_PASSWORD env var to pin it")
            else:
                print(f"[+] Created admin {ADMIN_EMAIL} (password unchanged from env)")
        else:
            # Reset password so we always know what it is
            admin.hashed_password = hash_password(ADMIN_PASSWORD)
            admin.is_active = True
            s.commit()
            if _PASSWORD_IS_GENERATED:
                print(f"[=] Admin {ADMIN_EMAIL} exists — password reset (auto-generated; set URIP_DEV_ADMIN_PASSWORD env var to pin it)")
            else:
                print(f"[=] Admin {ADMIN_EMAIL} exists — password reset (from env)")

        # ── 3. Demo risks ────────────────────────────────────────────
        risk_count = s.execute(select(Risk)).scalars().all()
        if risk_count:
            print(f"[=] {len(risk_count)} risks already present — skipping risk seed")
            return

        sources = ["tenable", "crowdstrike", "sentinelone", "ms_entra", "zscaler",
                   "cloudsek", "siem", "easm", "bug_bounty", "armis"]
        domains = ["network", "endpoint", "identity", "cloud", "application",
                   "ot", "external"]
        sevs    = [("critical", 9.5), ("high", 7.8), ("medium", 5.4), ("low", 3.0)]
        teams   = ["IT Security", "App Team", "Network Team", "Cloud Team",
                   "OT Team", "Identity Team"]
        statuses = ["open", "in_progress", "in_progress", "open", "open",
                    "accepted", "closed"]

        findings_template = [
            "Outdated TLS configuration",
            "Privilege escalation path detected",
            "Phishing exposure on public mailbox",
            "Unpatched OS package — CVE pending",
            "Misconfigured S3 bucket (public read)",
            "Open RDP port on internet-facing host",
            "Default credentials still active",
            "Suspicious outbound traffic to high-risk geo",
            "OT device using clear-text Modbus",
            "Expired SSL certificate on payment gateway",
        ]

        random.seed(42)
        risks = []
        now = datetime.now(timezone.utc)
        for i in range(1, 41):
            sev_label, base = random.choice(sevs)
            cvss = round(base + random.uniform(-1.0, 0.5), 1)
            cvss = max(0.1, min(10.0, cvss))
            created = now - timedelta(days=random.randint(0, 60), hours=random.randint(0, 23))
            sla     = created + timedelta(days={"critical": 3, "high": 7,
                                                 "medium": 30, "low": 90}[sev_label])
            risks.append(Risk(
                id=uuid.uuid4(),
                tenant_id=DEFAULT_TENANT_ID,
                risk_id=f"RISK-2026-{i:03d}",
                finding=random.choice(findings_template),
                description=f"Detected by {random.choice(sources)} scan during regular sweep.",
                source=random.choice(sources),
                domain=random.choice(domains),
                cvss_score=cvss,
                severity=sev_label,
                asset=f"{random.choice(['srv', 'ws', 'rtr', 'fw', 'app'])}-{random.randint(1, 99):02d}.adaptive-mind.com",
                owner_team=random.choice(teams),
                status=random.choice(statuses),
                sla_deadline=sla,
                in_kev_catalog=random.random() < 0.15,
                cve_id=f"CVE-2026-{random.randint(1000, 9999)}" if random.random() < 0.6 else None,
                epss_score=round(random.uniform(0.0, 1.0), 3) if random.random() < 0.7 else None,
                composite_score=round(cvss * 0.55 + random.uniform(0, 3), 2),
                created_at=created,
                updated_at=created + timedelta(hours=random.randint(0, 48)),
            ))
        s.add_all(risks)
        s.commit()
        print(f"[+] Created {len(risks)} demo risks")


if __name__ == "__main__":
    main()

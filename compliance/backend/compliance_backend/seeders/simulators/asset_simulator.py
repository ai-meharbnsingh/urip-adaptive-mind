"""
asset_simulator — generate realistic IT asset inventory.

Mix per 100 assets (target distribution):
  35 laptops, 8 servers, 12 cloud_workloads, 25 mobile devices,
  10 saas_apps, 6 network_devices, 4 desktops/containers.

Each asset includes:
  - asset_tag (ADV-LT-001 / ADV-SRV-001 / etc. — type-prefixed)
  - owner_user_id (FK to one of the simulated employees)
  - location (office / remote)
  - lifecycle_state (mostly "deployed", some "in_repair", "retired")
  - classification (internal / confidential / restricted with realistic spread)
  - discovered_by (matches Adverb's connector stack: tenable, manageengine_ec, etc.)
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.seeders.simulators.sim_models import Asset
from compliance_backend.seeders.simulators._common import (
    LAPTOP_MODELS,
    SERVER_MODELS,
    NETWORK_DEVICE_MODELS,
    MOBILE_MODELS,
    CLOUD_WORKLOAD_PATTERNS,
    SAAS_APPS,
    OFFICE_LOCATIONS,
    generate_employees,
    make_rng,
    stable_uuid,
    now_utc,
)


# Distribution weights — percentages of total
TYPE_DISTRIBUTION = [
    ("laptop", 0.35),
    ("server", 0.08),
    ("cloud_workload", 0.12),
    ("mobile", 0.25),
    ("saas_app", 0.10),
    ("network_device", 0.06),
    ("desktop", 0.02),
    ("container", 0.02),
]

CLASSIFICATION_DISTRIBUTION = [
    ("public", 0.05),
    ("internal", 0.55),
    ("confidential", 0.30),
    ("restricted", 0.10),
]

LIFECYCLE_DISTRIBUTION = [
    ("deployed", 0.85),
    ("in_repair", 0.04),
    ("in_stock", 0.05),
    ("retired", 0.05),
    ("destroyed", 0.01),
]

DISCOVERED_BY_TOOLS = [
    "manageengine_ec",
    "tenable",
    "sentinelone",
    "ms_entra",
    "aws_config",
    "manual",
]

OPERATING_SYSTEMS = {
    "laptop": ["Windows 11 Pro 23H2", "macOS Sonoma 14.5", "Ubuntu 22.04 LTS"],
    "desktop": ["Windows 11 Pro 23H2", "macOS Sonoma 14.5"],
    "server": [
        "Ubuntu Server 22.04 LTS", "RHEL 9.3", "Windows Server 2022 Standard",
        "Amazon Linux 2023", "Debian 12.5",
    ],
    "cloud_workload": ["Amazon Linux 2023", "Ubuntu 22.04 (EKS)", "Container (Alpine 3.19)"],
    "mobile": ["iOS 17.4.1", "iOS 17.5", "Android 14 (Samsung One UI 6.1)", "Android 14"],
    "container": ["Alpine 3.19", "Distroless"],
    "network_device": ["IOS XE 17.6", "PAN-OS 11.0", "FortiOS 7.4", "Junos 22.4R3"],
}


def _weighted_pick(rng: random.Random, distribution: list[tuple[str, float]]) -> str:
    items, weights = zip(*distribution)
    return rng.choices(items, weights=weights)[0]


def _ip_for_asset_type(rng: random.Random, atype: str) -> str:
    if atype == "cloud_workload":
        return f"10.{rng.randint(0,15)}.{rng.randint(0,255)}.{rng.randint(1,254)}"
    if atype == "saas_app":
        return None  # SaaS doesn't have an IP we own
    if atype == "network_device":
        return f"10.0.{rng.randint(0,3)}.{rng.choice([1,2,3])}"
    # Office assets
    return f"10.{rng.choice([10,11,12])}.{rng.randint(0,255)}.{rng.randint(1,254)}"


def _mac_address(rng: random.Random) -> str:
    return ":".join(f"{rng.randint(0, 255):02x}" for _ in range(6))


def _serial_number(rng: random.Random, model: str) -> str:
    base = "".join(c for c in model if c.isalnum())[:6].upper()
    return f"{base}-{rng.randint(100000, 999999)}"


def _name_for_asset(rng: random.Random, atype: str, idx: int, owner_email: str) -> tuple[str, str]:
    """Return (asset_tag, name)."""
    owner_handle = owner_email.split("@")[0]
    if atype == "laptop":
        model = rng.choice(LAPTOP_MODELS)
        return (f"ADV-LT-{idx:04d}", f"{model} ({owner_handle})")
    if atype == "desktop":
        model = rng.choice(LAPTOP_MODELS)
        return (f"ADV-WS-{idx:04d}", f"{model} desktop ({owner_handle})")
    if atype == "server":
        model = rng.choice(SERVER_MODELS)
        return (f"ADV-SRV-{idx:04d}", f"{model}")
    if atype == "cloud_workload":
        pattern = rng.choice(CLOUD_WORKLOAD_PATTERNS)
        return (f"ADV-CW-{idx:04d}", f"{pattern}-{rng.randint(1,9)}")
    if atype == "mobile":
        model = rng.choice(MOBILE_MODELS)
        return (f"ADV-MOB-{idx:04d}", f"{model} ({owner_handle})")
    if atype == "saas_app":
        app = rng.choice(SAAS_APPS)
        return (f"ADV-SAAS-{idx:04d}", app)
    if atype == "network_device":
        model = rng.choice(NETWORK_DEVICE_MODELS)
        return (f"ADV-NET-{idx:04d}", f"{model}")
    if atype == "container":
        return (f"ADV-CTR-{idx:04d}", f"container-{rng.choice(['api','worker','cron'])}-{rng.randint(1,99)}")
    return (f"ADV-X-{idx:04d}", f"unknown-{idx}")


async def simulate_assets(
    session: AsyncSession,
    *,
    tenant_id: str,
    count: int = 100,
    seed: int = 42,
    skip_if_existing: bool = True,
) -> dict[str, int]:
    """
    Generate `count` assets for the tenant.

    Args:
        tenant_id:        Tenant scope.
        count:            Total assets to create.
        seed:             RNG seed.
        skip_if_existing: No-op if any assets exist.
    """
    rng = make_rng(seed)

    if skip_if_existing:
        existing = (await session.execute(
            select(func.count()).select_from(Asset).where(Asset.tenant_id == tenant_id)
        )).scalar() or 0
        if existing > 0:
            return {"created": 0, "skipped": existing, "tenant_id": tenant_id}

    # Synthetic employees to own the assets
    employees = generate_employees(rng, tenant_id, count=max(50, count // 2))

    created = 0
    for i in range(count):
        atype = _weighted_pick(rng, TYPE_DISTRIBUTION)
        owner = rng.choice(employees)
        asset_tag, name = _name_for_asset(rng, atype, i + 1, owner["email"])
        classification = _weighted_pick(rng, CLASSIFICATION_DISTRIBUTION)
        lifecycle = _weighted_pick(rng, LIFECYCLE_DISTRIBUTION)
        os_pool = OPERATING_SYSTEMS.get(atype)
        os_choice = rng.choice(os_pool) if os_pool else None
        ip = _ip_for_asset_type(rng, atype) if atype not in ("saas_app",) else None
        mac = _mac_address(rng) if atype in ("laptop", "desktop", "mobile", "network_device") else None
        serial = _serial_number(rng, name) if atype in ("laptop", "desktop", "server", "mobile", "network_device") else None
        location = (
            rng.choice(OFFICE_LOCATIONS)
            if atype in ("laptop", "desktop", "mobile")
            else "Cloud (multi-AZ)" if atype in ("cloud_workload", "saas_app", "container")
            else rng.choice(OFFICE_LOCATIONS[:5])
        )

        asset = Asset(
            id=stable_uuid(tenant_id, "asset", asset_tag),
            tenant_id=tenant_id,
            asset_tag=asset_tag,
            name=name,
            asset_type=atype,
            classification=classification,
            lifecycle_state=lifecycle,
            owner_user_id=owner["user_id"],
            location=location,
            operating_system=os_choice,
            ip_address=ip,
            mac_address=mac,
            serial_number=serial,
            discovered_by=rng.choice(DISCOVERED_BY_TOOLS),
            last_seen_at=now_utc() - timedelta(days=rng.randint(0, 30), hours=rng.randint(0, 23)),
            metadata_json={
                "owner_email": owner["email"],
                "owner_department": owner["department"],
                "criticality": classification,
            },
        )
        session.add(asset)
        created += 1

    await session.flush()
    return {"created": created, "skipped": 0, "tenant_id": tenant_id}

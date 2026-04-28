from __future__ import annotations

import hashlib
import ipaddress
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import async_session
from backend.models.risk import Risk


def compute_asset_fingerprint(mac: str | None, hostname: str | None, ip: str | None) -> str:
    """
    v3 §3.5 — Asset Fingerprinting / De-duplication

    Composite identity input = lower(MAC) + lower(hostname) + canonical(IP)
    None values are rendered as empty strings.
    Returns: SHA-256 hex digest (64 chars).
    """
    mac_norm = (mac or "").strip().lower()
    host_norm = (hostname or "").strip().lower()
    ip_norm = _canonical_ip(ip)

    payload = f"{mac_norm}{host_norm}{ip_norm}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _canonical_ip(ip: str | None) -> str:
    if not ip:
        return ""
    raw = ip.strip()
    if not raw:
        return ""
    try:
        return ipaddress.ip_address(raw).compressed.lower()
    except ValueError:
        # Deterministic fallback; do not fail ingestion on malformed IP strings.
        return raw.lower()


async def find_existing_risk(
    tenant_id: Any,
    fingerprint: str,
    cve_id: str | None,
    *,
    db: AsyncSession | None = None,
) -> Risk | None:
    """
    De-dup target: existing OPEN Risk with same (tenant_id, fingerprint_key, cve_id).
    """
    if not tenant_id or not fingerprint or not cve_id:
        return None

    if db is not None:
        result = await db.execute(
            select(Risk).where(
                Risk.tenant_id == tenant_id,
                Risk.status == "open",
                Risk.fingerprint_key == fingerprint,
                Risk.cve_id == cve_id,
            )
        )
        return result.scalar_one_or_none()

    async with async_session() as session:
        result = await session.execute(
            select(Risk).where(
                Risk.tenant_id == tenant_id,
                Risk.status == "open",
                Risk.fingerprint_key == fingerprint,
                Risk.cve_id == cve_id,
            )
        )
        return result.scalar_one_or_none()


def merge_risk(existing_risk: Risk, new_finding: Any) -> Risk:
    """
    Merge a new normalized finding into an existing Risk row.

    - Keeps highest composite_score
    - Appends source into sources_attributed
    - Merges remediation_steps (unique)
    - Updates updated_at as a proxy for last_seen
    """
    _merge_composite_score(existing_risk, getattr(new_finding, "composite_score", None))
    _merge_sources(existing_risk, getattr(new_finding, "source", None))
    _merge_remediation_steps(existing_risk, getattr(new_finding, "remediation_steps", None))

    existing_risk.updated_at = datetime.now(timezone.utc)
    return existing_risk


def _merge_composite_score(existing_risk: Risk, incoming_score: Any) -> None:
    try:
        inc = None if incoming_score is None else float(incoming_score)
    except (TypeError, ValueError):
        inc = None

    try:
        cur = None if existing_risk.composite_score is None else float(existing_risk.composite_score)
    except (TypeError, ValueError):
        cur = None

    if inc is None:
        return
    if cur is None or inc > cur:
        existing_risk.composite_score = inc


def _merge_sources(existing_risk: Risk, incoming_source: Any) -> None:
    sources: list[str] = list(existing_risk.sources_attributed or [])

    def _add(src: str | None) -> None:
        if not src:
            return
        s = str(src).strip().lower()
        if not s:
            return
        if s not in sources:
            sources.append(s)

    _add(getattr(existing_risk, "source", None))
    _add(incoming_source)

    existing_risk.sources_attributed = sources


def _merge_remediation_steps(existing_risk: Risk, incoming_steps: Any) -> None:
    cur_steps = list(getattr(existing_risk, "remediation_steps", None) or [])

    merged: list[str] = []
    seen: set[str] = set()

    def _add(step: str) -> None:
        s = step.strip()
        if not s:
            return
        key = s.lower()
        if key in seen:
            return
        seen.add(key)
        merged.append(s)

    for s in cur_steps:
        if isinstance(s, str):
            _add(s)

    if incoming_steps:
        for s in incoming_steps:
            if isinstance(s, str):
                _add(s)

    existing_risk.remediation_steps = merged

from __future__ import annotations

import logging
import time
from typing import Literal

import httpx
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services import asset_fingerprint_service

logger = logging.getLogger(__name__)

_NVD_CVE_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
_PATCH_CACHE_TTL_SECONDS = 24 * 60 * 60
_patch_cache: dict[str, tuple["PatchInfo", float]] = {}


class PatchInfo(BaseModel):
    vendor_patch_released: bool
    references: list[str] = Field(default_factory=list)


class AdvisoryRecord(BaseModel):
    tenant_id: str
    cve_id: str
    fingerprint_key: str | None = None


class AssetState(BaseModel):
    installed_version: str | None = None
    patched_versions: list[str] = Field(default_factory=list)

    def is_patched(self) -> bool:
        if not self.installed_version:
            return False
        installed = self.installed_version.strip()
        if not installed:
            return False
        return installed in {v.strip() for v in self.patched_versions if v and v.strip()}


async def classify_advisory(
    advisory: AdvisoryRecord,
    asset_state: AssetState | None,
    *,
    db: AsyncSession | None = None,
) -> Literal["valid", "patch_available", "expired", "redundant"]:
    """
    v3 §3.7 — Advisory Applicability Check
    """
    if advisory.fingerprint_key:
        try:
            existing = await asset_fingerprint_service.find_existing_risk(
                tenant_id=advisory.tenant_id,
                fingerprint=advisory.fingerprint_key,
                cve_id=advisory.cve_id,
                db=db,
            )
            if existing is not None:
                return "redundant"
        except Exception:
            # De-dup is a best-effort classification signal; ingestion still proceeds.
            logger.exception("Advisory redundancy check failed for %s", advisory.cve_id)

    patch_info = fetch_patch_info_from_nvd(advisory.cve_id)
    if not patch_info.vendor_patch_released:
        return "valid"

    if asset_state is not None and asset_state.is_patched():
        return "expired"

    return "patch_available"


def fetch_patch_info_from_nvd(cve_id: str) -> PatchInfo:
    """
    Fetch vendor patch references from NVD and cache for 24h (in-memory TTL).

    Network failures return PatchInfo(vendor_patch_released=False) to avoid
    failing ingestion.
    """
    cve = (cve_id or "").strip().upper()
    if not cve:
        return PatchInfo(vendor_patch_released=False, references=[])

    now = time.monotonic()
    cached = _patch_cache.get(cve)
    if cached is not None:
        info, loaded_at = cached
        if (now - loaded_at) < _PATCH_CACHE_TTL_SECONDS:
            return info

    info = _fetch_patch_info_from_nvd_uncached(cve)
    _patch_cache[cve] = (info, now)
    return info


def _fetch_patch_info_from_nvd_uncached(cve_id: str) -> PatchInfo:
    try:
        resp = httpx.get(_NVD_CVE_API, params={"cveId": cve_id}, timeout=20.0)
        resp.raise_for_status()
        payload = resp.json()
    except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
        logger.warning("NVD patch lookup failed for %s (%s)", cve_id, type(exc).__name__)
        return PatchInfo(vendor_patch_released=False, references=[])

    refs: list[str] = []
    patch_like = False

    for vuln in payload.get("vulnerabilities", []) or []:
        cve = (vuln or {}).get("cve") or {}
        for ref in (cve.get("references") or []):
            url = (ref or {}).get("url")
            tags = [(t or "").lower() for t in ((ref or {}).get("tags") or [])]
            if url:
                refs.append(str(url))
            # Heuristic: treat "patch" or vendor advisory references as patch released.
            if any(t in {"patch", "vendor advisory", "release notes"} for t in tags):
                patch_like = True

    # Fallback heuristic: any references at all implies there's vendor material.
    if refs and not patch_like:
        patch_like = True

    # De-dup while preserving insertion order
    deduped: list[str] = []
    seen: set[str] = set()
    for r in refs:
        if r in seen:
            continue
        seen.add(r)
        deduped.append(r)

    return PatchInfo(vendor_patch_released=patch_like, references=deduped)

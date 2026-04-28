from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_classify_advisory_valid_when_no_vendor_patch(monkeypatch):
    from backend.services import advisory_applicability_service as svc

    async def _fake_find_existing_risk(*args, **kwargs):
        return None

    monkeypatch.setattr(svc.asset_fingerprint_service, "find_existing_risk", _fake_find_existing_risk)
    monkeypatch.setattr(svc, "fetch_patch_info_from_nvd", lambda cve_id: svc.PatchInfo(vendor_patch_released=False, references=[]))

    advisory = svc.AdvisoryRecord(tenant_id="t", cve_id="CVE-2024-0001", fingerprint_key="00" * 32)
    assert await svc.classify_advisory(advisory, asset_state=None) == "valid"


@pytest.mark.asyncio
async def test_classify_advisory_patch_available_when_unpatched(monkeypatch):
    from backend.services import advisory_applicability_service as svc

    async def _fake_find_existing_risk(*args, **kwargs):
        return None

    monkeypatch.setattr(svc.asset_fingerprint_service, "find_existing_risk", _fake_find_existing_risk)
    monkeypatch.setattr(svc, "fetch_patch_info_from_nvd", lambda cve_id: svc.PatchInfo(vendor_patch_released=True, references=["vendor_patch"]))

    advisory = svc.AdvisoryRecord(tenant_id="t", cve_id="CVE-2024-0002", fingerprint_key="11" * 32)
    asset_state = svc.AssetState(installed_version="1.0.0", patched_versions=["1.0.1"])
    assert await svc.classify_advisory(advisory, asset_state=asset_state) == "patch_available"


@pytest.mark.asyncio
async def test_classify_advisory_expired_when_patched(monkeypatch):
    from backend.services import advisory_applicability_service as svc

    async def _fake_find_existing_risk(*args, **kwargs):
        return None

    monkeypatch.setattr(svc.asset_fingerprint_service, "find_existing_risk", _fake_find_existing_risk)
    monkeypatch.setattr(svc, "fetch_patch_info_from_nvd", lambda cve_id: svc.PatchInfo(vendor_patch_released=True, references=["vendor_patch"]))

    advisory = svc.AdvisoryRecord(tenant_id="t", cve_id="CVE-2024-0003", fingerprint_key="22" * 32)
    asset_state = svc.AssetState(installed_version="1.0.1", patched_versions=["1.0.1"])
    assert await svc.classify_advisory(advisory, asset_state=asset_state) == "expired"


@pytest.mark.asyncio
async def test_classify_advisory_redundant_when_duplicate(monkeypatch):
    from backend.services import advisory_applicability_service as svc

    async def _fake_find_existing_risk(*args, **kwargs):
        return SimpleNamespace(id="r")

    monkeypatch.setattr(svc.asset_fingerprint_service, "find_existing_risk", _fake_find_existing_risk)
    monkeypatch.setattr(svc, "fetch_patch_info_from_nvd", lambda cve_id: svc.PatchInfo(vendor_patch_released=False, references=[]))

    advisory = svc.AdvisoryRecord(tenant_id="t", cve_id="CVE-2024-0004", fingerprint_key="33" * 32)
    assert await svc.classify_advisory(advisory, asset_state=None) == "redundant"


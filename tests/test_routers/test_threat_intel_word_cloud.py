"""
Threat-intel word-cloud endpoint tests.

GET /api/threat-intel/word-cloud → returns aggregated counts in three buckets:
    - apt_groups: list of {term, count}
    - ttps:       list of {term, count}
    - sectors:    list of {term, count}

The terms come from MITRE ATT&CK static map + OTX pulses already in the
service.  No external network calls happen in tests — the route just
aggregates what's already cached.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_word_cloud_returns_three_buckets(client, auth_headers):
    resp = await client.get("/api/threat-intel/word-cloud", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for k in ("apt_groups", "ttps", "sectors"):
        assert k in body, f"missing bucket {k}"
        assert isinstance(body[k], list)


@pytest.mark.asyncio
async def test_word_cloud_apt_groups_have_term_and_count(client, auth_headers):
    resp = await client.get("/api/threat-intel/word-cloud", headers=auth_headers)
    assert resp.status_code == 200
    apt = resp.json()["apt_groups"]
    if not apt:
        pytest.skip("APT bucket empty in this test fixture")
    for entry in apt:
        assert "term" in entry
        assert "count" in entry
        assert isinstance(entry["term"], str) and entry["term"]
        assert isinstance(entry["count"], int) and entry["count"] >= 1


@pytest.mark.asyncio
async def test_word_cloud_apt_includes_known_groups(client, auth_headers):
    resp = await client.get("/api/threat-intel/word-cloud", headers=auth_headers)
    apt = {e["term"] for e in resp.json()["apt_groups"]}
    # Static CVE-APT map lists APT28, APT29, APT41 etc.
    assert any(g in apt for g in ("APT28", "APT29", "APT41", "Lazarus", "Cl0p"))


@pytest.mark.asyncio
async def test_word_cloud_sectors_include_manufacturing(client, auth_headers):
    resp = await client.get("/api/threat-intel/word-cloud", headers=auth_headers)
    sectors = {e["term"] for e in resp.json()["sectors"]}
    assert "Manufacturing" in sectors


@pytest.mark.asyncio
async def test_word_cloud_results_sorted_descending(client, auth_headers):
    resp = await client.get("/api/threat-intel/word-cloud", headers=auth_headers)
    body = resp.json()
    for bucket in ("apt_groups", "ttps", "sectors"):
        counts = [e["count"] for e in body[bucket]]
        assert counts == sorted(counts, reverse=True), f"{bucket} not sorted desc"


@pytest.mark.asyncio
async def test_word_cloud_unauth_rejected(client):
    resp = await client.get("/api/threat-intel/word-cloud")
    assert resp.status_code in (401, 403)

"""
HIGH-004 — risks.py sort_by accepts any attribute name (getattr probe).

Vulnerability:
    `sort_col = getattr(Risk, sort_by, Risk.cvss_score)` allows a caller to
    point ORDER BY at any model attribute (including internal/private columns
    or relationships), which can leak ordering information about columns the
    UI never exposes.

Required behaviour:
    - sort_by is restricted to a fixed allowlist of public, sortable columns:
        {"created_at", "severity", "status", "cvss_score", "epss_score",
         "title", "tier"}
      ("title" maps to Risk.finding for legacy front-end compatibility,
       "tier" maps to Risk.asset_tier).
    - An invalid sort_by → 422 with a helpful message naming the allowed values.
    - A valid sort_by → 200.
    - The default sort_by ("composite_score") still works.
"""
import pytest
from httpx import AsyncClient


SORTABLE = {"created_at", "severity", "status", "cvss_score",
            "epss_score", "title", "tier"}


@pytest.mark.anyio
async def test_invalid_sort_by_returns_422(client: AsyncClient, auth_headers,
                                           seeded_risks):
    """Sending a non-allowlisted sort_by must return 422 with a clear msg."""
    resp = await client.get(
        "/api/risks?sort_by=__class__", headers=auth_headers
    )
    assert resp.status_code == 422, (
        f"Expected 422 for sort_by=__class__, got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    detail = str(body.get("detail", "")).lower()
    assert "sort_by" in detail or "sort" in detail, (
        f"Error message should mention sort_by, got: {detail}"
    )


@pytest.mark.anyio
async def test_attribute_probe_blocked(client: AsyncClient, auth_headers,
                                       seeded_risks):
    """Probing internal attributes (e.g., __tablename__, registry) → 422."""
    for probe in ["__tablename__", "metadata", "registry", "__init__"]:
        resp = await client.get(
            f"/api/risks?sort_by={probe}", headers=auth_headers
        )
        assert resp.status_code == 422, (
            f"sort_by={probe!r} should be rejected; got {resp.status_code}"
        )


@pytest.mark.anyio
async def test_valid_sort_by_returns_200(client: AsyncClient, auth_headers,
                                         seeded_risks):
    """Each allowlisted column is accepted."""
    for col in sorted(SORTABLE):
        resp = await client.get(
            f"/api/risks?sort_by={col}", headers=auth_headers
        )
        assert resp.status_code == 200, (
            f"sort_by={col!r} should be accepted; got {resp.status_code}: {resp.text}"
        )


@pytest.mark.anyio
async def test_default_sort_still_works(client: AsyncClient, auth_headers,
                                        seeded_risks):
    """Calling without sort_by uses the default and returns 200."""
    resp = await client.get("/api/risks", headers=auth_headers)
    assert resp.status_code == 200, resp.text


@pytest.mark.anyio
async def test_invalid_sort_by_lists_allowed_values(
    client: AsyncClient, auth_headers, seeded_risks
):
    """Error response should list at least one valid choice so callers can fix."""
    resp = await client.get(
        "/api/risks?sort_by=NOPE", headers=auth_headers
    )
    assert resp.status_code == 422
    body = resp.json()
    detail = str(body.get("detail", ""))
    # At minimum, mention one of the valid columns to guide the caller
    assert any(col in detail for col in SORTABLE), (
        f"422 detail should hint at valid columns, got: {detail}"
    )

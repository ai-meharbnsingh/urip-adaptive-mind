"""
HIGH-012 — ReDoS via tenant-supplied taxonomy regex.

Vulnerability:
    classify_asset() compiles each tenant-supplied taxonomy keyword as a regex
    via `re.compile(p, re.IGNORECASE)`. A malicious tenant admin can submit a
    catastrophic-backtracking pattern (e.g. `(a+)+$`) which DOSes every future
    classify call for that tenant.

Required behaviour:
    - The taxonomy admin endpoints (POST /api/asset-taxonomy and POST
      /api/asset-taxonomy/bulk) must reject any keyword that contains regex
      metacharacters: . * + ? ^ $ { } ( ) | [ ] \\
    - The error must be 422 with a message that says regex is not supported
      and that callers should use literal substrings.
    - PATCH /api/asset-taxonomy/{id} must apply the same validation.
"""
import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_post_taxonomy_rejects_regex_metacharacters(
    client: AsyncClient, auth_headers, default_tenant
):
    """
    Each metacharacter in isolation must be rejected by POST /asset-taxonomy.
    """
    bad_keywords = [
        "(a+)+$",       # classic catastrophic backtracking
        "foo.*bar",     # quantified wildcard
        "ev[il]+",      # character class + quantifier
        "h{1,5}i",      # bounded quantifier
        "x|y",          # alternation
        "back\\1",      # backreference / escape
        "^anchor",      # caret anchor
        "anchor$",      # dollar anchor
        "(group)",      # parens (group)
        "?optional",    # optional
    ]
    for kw in bad_keywords:
        resp = await client.post(
            "/api/asset-taxonomy",
            headers=auth_headers,
            json={"tier_code": "T1", "keyword": kw},
        )
        assert resp.status_code == 422, (
            f"keyword {kw!r} should be rejected (regex metachars), "
            f"got {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        msg = str(body.get("detail", "")).lower()
        assert "regex" in msg or "literal" in msg or "metachar" in msg, (
            f"422 response should mention regex / literal substrings; got: {msg}"
        )


@pytest.mark.anyio
async def test_post_taxonomy_accepts_literal_keyword(
    client: AsyncClient, auth_headers, default_tenant
):
    """Plain alphanumeric keywords are still accepted."""
    resp = await client.post(
        "/api/asset-taxonomy",
        headers=auth_headers,
        json={"tier_code": "T1", "keyword": "payment-gateway"},
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.anyio
async def test_bulk_taxonomy_rejects_regex_metacharacters(
    client: AsyncClient, auth_headers, default_tenant
):
    """Bulk import must reject the entire payload if any item contains a
    regex metacharacter (Pydantic-level validation = all-or-nothing)."""
    resp = await client.post(
        "/api/asset-taxonomy/bulk",
        headers=auth_headers,
        json=[
            {"tier_code": "T1", "keyword": "good-keyword"},
            {"tier_code": "T2", "keyword": "(bad+)+"},
        ],
    )
    assert resp.status_code == 422, (
        f"bulk import with one bad keyword should be 422, got {resp.status_code}: "
        f"{resp.text}"
    )


@pytest.mark.anyio
async def test_patch_taxonomy_rejects_regex_metacharacters(
    client: AsyncClient, auth_headers, default_tenant
):
    """PATCH must apply the same literal-only rule."""
    # First create a valid row
    resp = await client.post(
        "/api/asset-taxonomy",
        headers=auth_headers,
        json={"tier_code": "T1", "keyword": "ok-keyword"},
    )
    assert resp.status_code == 201, resp.text
    row_id = resp.json()["id"]

    # Now try to PATCH it with a malicious keyword
    resp = await client.patch(
        f"/api/asset-taxonomy/{row_id}",
        headers=auth_headers,
        json={"keyword": "(a+)+$"},
    )
    assert resp.status_code == 422, (
        f"PATCH with regex metachars should be 422, got {resp.status_code}: "
        f"{resp.text}"
    )

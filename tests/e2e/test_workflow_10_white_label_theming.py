"""
WORKFLOW 10 — White-label theming end-to-end (URIP).

Covers:
  1. Super-admin updates a tenant's branding via PATCH /api/admin/tenants/{slug}
     with logo_url, primary_color, secondary_color, and app_name.
  2. GET /api/admin/tenants/{slug} (super-admin) reflects the change.
  3. GET /api/tenants/{slug}/branding returned via the public-ish branding
     endpoint exposes the same payload.
  4. The tenant_slug embedded in the tenant admin's JWT (set by
     /api/auth/login + /api/admin/tenants/{slug}/users) is what the frontend
     uses to fetch the correct branding — we verify the slug round-trips.
  5. A user belonging to a DIFFERENT tenant cannot read this tenant's
     branding (404 — no info leak).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_workflow_10_branding_lifecycle(
    client: AsyncClient,
    tenant_factory,
    super_admin_headers: dict,
    make_user_in_tenant,
):
    onboarding_a = await tenant_factory(slug="brand-acme")
    slug_a = onboarding_a["slug"]

    # ── 1) Super-admin updates branding ─────────────────────────────────────
    new_branding = {
        "logo_url": "https://cdn.brand-acme.test/logo.svg",
        "primary_color": "#0D1B2A",
        "secondary_color": "#FF5733",
        "app_name": "Acme Risk Hub",
    }
    patch_resp = await client.patch(
        f"/api/admin/tenants/{slug_a}",
        json=new_branding,
        headers=super_admin_headers,
    )
    assert patch_resp.status_code == 200, patch_resp.text
    settings = patch_resp.json()["settings"]
    for k, v in new_branding.items():
        assert settings[k] == v, (
            f"Settings {k} did not persist: got {settings.get(k)!r}, expected {v!r}"
        )

    # ── 2) Super-admin GET reflects the change ─────────────────────────────
    detail_resp = await client.get(
        f"/api/admin/tenants/{slug_a}", headers=super_admin_headers
    )
    assert detail_resp.status_code == 200
    for k, v in new_branding.items():
        assert detail_resp.json()["settings"][k] == v

    # ── 3) GET /api/tenants/{slug}/branding from inside the tenant ─────────
    branding_resp = await client.get(
        f"/api/tenants/{slug_a}/branding",
        headers=onboarding_a["admin_headers"],
    )
    assert branding_resp.status_code == 200, branding_resp.text
    branding_body = branding_resp.json()
    assert branding_body["logo_url"] == new_branding["logo_url"]
    assert branding_body["primary_color"] == new_branding["primary_color"]
    assert branding_body["secondary_color"] == new_branding["secondary_color"]
    assert branding_body["app_name"] == new_branding["app_name"]

    # ── 4) tenant_slug round-trips via /api/auth/me ────────────────────────
    me_resp = await client.get(
        "/api/auth/me", headers=onboarding_a["admin_headers"]
    )
    assert me_resp.status_code == 200, me_resp.text
    assert me_resp.json()["tenant_slug"] == slug_a, (
        "Frontend uses tenant_slug from /me to choose which branding to fetch"
    )

    # ── 5) A user from a different tenant cannot read this branding ────────
    onboarding_b = await tenant_factory(slug="brand-beta")
    _, b_user_headers = await make_user_in_tenant(
        onboarding_b["tenant_id"], role="it_team"
    )
    cross_resp = await client.get(
        f"/api/tenants/{slug_a}/branding", headers=b_user_headers
    )
    assert cross_resp.status_code == 404, (
        f"Cross-tenant branding leak: user from B fetched {slug_a} branding: "
        f"{cross_resp.status_code} {cross_resp.text}"
    )


@pytest.mark.asyncio
async def test_workflow_10_invalid_color_rejected(
    client: AsyncClient,
    tenant_factory,
    super_admin_headers: dict,
):
    """primary_color and secondary_color must be 6-digit hex (#RRGGBB)."""
    onboarding = await tenant_factory(slug="brand-validation")
    bad = await client.patch(
        f"/api/admin/tenants/{onboarding['slug']}",
        json={"primary_color": "blue"},
        headers=super_admin_headers,
    )
    assert bad.status_code == 422, bad.text

    bad2 = await client.patch(
        f"/api/admin/tenants/{onboarding['slug']}",
        json={"secondary_color": "#XYZ123"},
        headers=super_admin_headers,
    )
    assert bad2.status_code == 422, bad2.text

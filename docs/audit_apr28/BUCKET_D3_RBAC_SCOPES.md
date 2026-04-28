# Bucket D3 — Per-Resource Scope Enforcement

**Date**: 2026-04-28
**Gemini finding**: RBAC is a simplistic linear hierarchy with no per-resource scopes.
**Scope of this fix**: additive scope layer on the 5 highest blast-radius admin routes.

---

## Files Changed

| File | Change |
|------|--------|
| `backend/middleware/scopes.py` | NEW — defines `ROLE_SCOPES` map + `_has()` + `require_scope()` dependency |
| `backend/routers/tenants.py` | Added `require_scope("tenants:read/write")` + `require_scope("modules:write")` to 8 admin routes |
| `backend/routers/settings.py` | Added `require_scope("settings:read/write")` + `require_scope("scoring:write")` to 7 routes |
| `backend/routers/vapt_admin.py` | Added `require_scope("vapt:read/write")` to 7 routes |
| `tests/test_rbac/test_scope_enforcement.py` | NEW — 18 tests (10 unit + 8 integration HTTP) |
| `tests/test_rbac/test_legacy_rbac.py` | Moved from `tests/test_rbac.py` (resolved Python module naming collision) |
| `docs/SCALING.md` | Appended partial-fix note |

---

## Scope Vocabulary (8 scopes)

| Scope | Granted to |
|-------|-----------|
| `tenants:read` | ciso, it_team, executive, board |
| `tenants:write` | ciso only (via `admin:*`) |
| `modules:read` | ciso, it_team, executive |
| `modules:write` | ciso only (via `admin:*`) |
| `scoring:write` | ciso, it_team (scoring read is also gated — weights are sensitive) |
| `vapt:read` | ciso, it_team, executive |
| `vapt:write` | ciso only (via `admin:*`) |
| `settings:read` | ciso, it_team, executive |
| `settings:write` | ciso only (via `admin:*`) |

`admin:*` wildcard (ciso only) satisfies any scope check via `_has()`.

---

## Test Output

```
======================== 22 passed, 1 warning in 4.82s =========================

tests/test_rbac/test_legacy_rbac.py::test_ciso_can_approve_acceptance PASSED
tests/test_rbac/test_legacy_rbac.py::test_it_team_cannot_approve PASSED
tests/test_rbac/test_legacy_rbac.py::test_executive_cannot_create_risk PASSED
tests/test_rbac/test_legacy_rbac.py::test_board_read_only PASSED
tests/test_rbac/test_scope_enforcement.py::TestScopeLogic::test_admin_wildcard_scope_grants_all PASSED
tests/test_rbac/test_scope_enforcement.py::TestScopeLogic::test_unknown_role_gets_no_scopes PASSED
tests/test_rbac/test_scope_enforcement.py::TestScopeLogic::test_ciso_has_all_defined_scopes PASSED
tests/test_rbac/test_scope_enforcement.py::TestScopeLogic::test_it_team_cannot_write_tenants PASSED
tests/test_rbac/test_scope_enforcement.py::TestScopeLogic::test_it_team_can_read_tenants PASSED
tests/test_rbac/test_scope_enforcement.py::TestScopeLogic::test_executive_cannot_write_modules PASSED
tests/test_rbac/test_scope_enforcement.py::TestScopeLogic::test_executive_can_read_modules PASSED
tests/test_rbac/test_scope_enforcement.py::TestScopeLogic::test_board_minimum_scope PASSED
tests/test_rbac/test_scope_enforcement.py::TestScopeLogic::test_it_team_has_scoring_write PASSED
tests/test_rbac/test_scope_enforcement.py::TestScopeLogic::test_executive_lacks_scoring_write PASSED
tests/test_rbac/test_scope_enforcement.py::test_ciso_can_read_scoring PASSED
tests/test_rbac/test_scope_enforcement.py::test_executive_blocked_from_scoring PASSED
tests/test_rbac/test_scope_enforcement.py::test_ciso_can_list_vapt_vendors PASSED
tests/test_rbac/test_scope_enforcement.py::test_board_blocked_from_vapt_read PASSED
tests/test_rbac/test_scope_enforcement.py::test_it_team_blocked_from_settings_write PASSED
tests/test_rbac/test_scope_enforcement.py::test_ciso_can_read_settings PASSED
tests/test_rbac/test_scope_enforcement.py::test_board_blocked_from_settings_read PASSED
tests/test_rbac/test_scope_enforcement.py::test_it_team_can_read_vapt_submissions PASSED
```

---

## What's Still TODO for Full RBAC (Honest)

This is a partial scope layer, not a full RBAC overhaul. The following remain unaddressed:

1. **Scope storage is hardcoded** — `ROLE_SCOPES` is a static dict in `scopes.py`. Per-tenant role customisation (e.g. a tenant's it_team gets extra scopes) requires a DB-backed permissions table.
2. **No admin UI for scope assignment** — there is no interface for a CISO to grant or revoke individual scopes from users or custom roles.
3. **Roles are still linear** — the underlying `role_required` hierarchy (board < executive < it_team < ciso) has not changed. The scope layer is additive, not a replacement. A true RBAC system would decouple roles from a linear rank entirely.
4. **No custom roles** — only 4 fixed roles exist. Enterprise customers typically need custom role definitions (e.g. "auditor", "readonly-executive").
5. **Super-admin is out-of-band** — `is_super_admin` flag bypasses both `role_required` and scope checks. Super-admin actions are not scope-limited.
6. **Other routers not covered** — only the 5 designated high-blast-radius routes received scope guards. The remaining ~30 routers use `role_required` alone.

Full RBAC overhaul is estimated as a 2-week sprint (DB schema, API, UI, migration).

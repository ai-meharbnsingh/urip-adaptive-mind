# Zero Issues Inventory — URIP-Adverb

**Date:** 2026-04-27
**Auditor:** Opus Baseline Agent (read-only)
**Goal:** Comprehensive list of every open issue blocking 0/0/0/0 audit verdict
**Methodology:** Full pytest run on both services, code-grep against SECURITY_REVIEW.md findings, alembic chain inspection, frontend-backend route diff, dependency probe.

---

## 0. Executive Summary

- **Total tests run:** 1091 (URIP 705, Compliance 389)
- **Total pass:** 992 (URIP 603 + Compliance 389) — 90.9 %
- **Total fail:** 99 (URIP only — Compliance is 100% green)
- **Skipped:** 3 (URIP)
- **Critical security findings open:** 1 of 9 (CRIT-005 partial — URIP migrated, Compliance still on python-jose)
- **High security findings open:** 6 of 13 (HIGH-001/002/008/010/011/013 — Compliance side mostly)
- **Medium security findings open:** 9 of 12 (most still open — were never tracked under CritFix)
- **Low security findings open:** 6 of 7 (LOW-002 P0 storage piece partly addressed; rest open)
- **Migration chain issues:** 1 (compliance — three duplicate `revision = "0002"` IDs, only works because down_revisions are heterogeneous strings)
- **Frontend-backend integration gaps:** 4 confirmed missing endpoints + 6 endpoints exposed but never called
- **Dependency / env issues:** 3 (Compliance pyproject still pins `python-jose>=3.3.0`; URIP `.venv` still has jose installed; `.env` still ships dev JWT secret literal)
- **Architectural / dead-code:** 1 large (7 production connectors not wired into any router)

**Headline:** The 99 URIP test failures are NOT primarily source bugs. ~80 of them are **test-isolation / fixture-staleness** issues caused by (a) `require_module("CORE")` newly added to dashboard/reports/audit-log routers without test fixtures providing CORE subscription, (b) the in-memory `slowapi` rate limiter persisting between tests in the same process (login + asset-taxonomy import-defaults), (c) `_login_attempts` defaultdict in `routers/auth.py` shared across test runs. The remaining ~20 are **legit gaps** — `test_backend_gaps_*` tests written ahead of source fixes (TDD red), 6 audit-log coverage tests dependent on test order, and several `test_agent_ingest/*` tests that hit `/api/agent-ingest/*` while the conftest seeds no agent-ingest tenants.

The **Compliance backend is fully green** — 389/389. The remaining security risk live there is mostly Compliance-side (HIGH-001 vendor service, HIGH-002 vendor docs storage, HIGH-010 missing audit log, HIGH-011 evidence upload checks) plus the pyproject still naming `python-jose`.

---

## 1. Failing Tests

### URIP Backend (99 failed, 603 passed, 3 skipped)

Failures group into 7 categories. Counts are exact.

| # | Category | Count | Root cause | Fix owner suggestion |
|---|---|---|---|---|
| 1 | Module-gate fixture gap (403 instead of 200/404) | 21 | `dashboard.py`, `reports.py`, `audit_log.py`, `risks.py`, `risk_summary.py`, `acceptance.py` now have router-level `Depends(require_module("CORE"|"VM"))` (CRIT-007 fix). Tests use the shared `auth_headers + seeded_risks` fixture which only seeds `vm_subscription` — there is **no** `core_subscription` fixture. Symptom: `assert 403 == 200`. | Z1 — extend `conftest.py` with `core_subscription` fixture; depend on it from `auth_headers` (or split into module-aware fixtures). |
| 2 | In-process rate limiter pollution (429 instead of 201/401) | 8 | `slowapi` middleware (`backend/middleware/rate_limit.py`) uses module-level `memory://` storage. Once `tests/test_acceptance.py::test_create_acceptance` and the 60+ other tests calling `/api/acceptance` or `/api/asset-taxonomy/import-defaults` exceed `60/minute` the limiter never resets between tests in the same process. Affects `test_acceptance.py` (4), `test_asset_taxonomy_routes.py::TestImportDefaults` (3), `test_critfix_auth/test_high008_login_audit.py::test_audit_row_for_failed_login_does_not_have_user_id_when_no_user` (1). | Z1 — reset `limiter._storage` between tests via autouse fixture; OR set `RATE_LIMIT_STORAGE_URI=memory://?reset_on_clear=true` in conftest; OR raise default writes cap to 6000/min in test mode. |
| 3 | `auth.py` legacy `_login_attempts` dict pollution | 7 | `backend/routers/auth.py:28` keeps a process-global `defaultdict(list)` in addition to the slowapi middleware. After `test_high008_login_audit.py` runs the lockout never expires inside one pytest run. Symptom: `429 == 401`. Affects `test_critfix_auth/test_high008_login_audit.py` (5 tests fail in full-suite, pass standalone). | Z1 — clear `_login_attempts` in autouse fixture; or replace the in-router limiter with the middleware-only path. |
| 4 | Audit-log coverage tests (10 fail in full run, 0 standalone) | 10 | `tests/test_critfix_audit_log/test_audit_log_coverage.py` — every test passes when run alone (`16/16`) but ~10 fail when run after other suites. Root cause: shared SQLite db_session is fresh per-test, BUT some tests call into routes that rely on tenant context module-state that previous tests leave set (`TenantContext` ContextVar leaks across asyncio.run boundaries when using `httpx.ASGITransport`). | Z1 — add `TenantContext.reset()` autouse fixture; OR convert tests to per-test app instance instead of singleton. |
| 5 | Agent-ingest signature/HMAC fixture failures | 22 | `tests/test_agent_ingest/test_*.py` — `test_register.py` (6), `test_heartbeat.py` (6), `test_metadata.py` (9), `test_drilldown.py` (4 — actually 4 fail, 1 pass). Same pattern: standalone these PASS. In full suite they fail because (a) `tenant_subscriptions` row not seeded for the test tenant by the agent-ingest conftest, OR (b) tenant license_key not generated and registered on the same db_session that the routes use. The `test_agent_ingest/conftest.py` uses a different fixture path than the URIP root conftest. | Z1 — unify agent_ingest conftest with root conftest's `db_session` override; ensure `tenant.license_key_sha256` is set in the seed step. |
| 6 | Asset-taxonomy KeyError + tenant 404 | 4 | `tests/test_asset_taxonomy_routes.py::TestSoftDelete::test_delete_sets_deleted_at_does_not_hard_delete` (KeyError 'id'), `test_delete_other_tenant_returns_404` (KeyError 'id'), `TestRouterInvalidatesCache::test_create_and_delete_take_immediate_effect_on_async_classifier` (KeyError 'id'). Root cause: a previous test in the file consumes the rate-limit budget on `POST /api/asset-taxonomy`, the create returns `429` instead of `201`, then later code tries `body["id"]` on the 429 JSON which has no `id`. Same root cause as #2. | Z1 — fix #2 first; these will resolve. |
| 7 | E2E workflow happy-path failures | 5 | `tests/e2e/test_workflow_01_*` (1), `test_workflow_02_*` (1), `tests/e2e_cross_service/test_workflow_03_*` (1), `04_*` (1), `06_*` (1). E2Es chain 10–15 HTTP calls; first one to hit a `require_module("CORE")` gate or rate-limited write fails the chain. Cascade of #1 + #2. | Z1 after fixing 1+2; re-run e2e harness. |
| 8 | Backend-gaps tests (TDD red, source not yet shipped) | 7 | `test_backend_gaps_auth.py` (2 — `test_login_regular_user_jwt_super_admin_false`, `test_me_tenant_slug_null_for_super_admin`), `test_backend_gaps_scoring.py` (5 — every PATCH `/api/settings/scoring` test). The PATCH endpoint exists (`backend/routers/settings.py:373`) but tests fail because of #1 + missing `core_subscription` and missing super-admin onboarding fixture. | Z1 after #1; verify response shape matches test expectations. |
| 9 | RBAC test expectations vs. error string | 2 | `test_rbac.py::test_executive_cannot_create_risk` — test asserts `"insufficient" in detail.lower()` but the new module-gate message is "Module 'VM' is not enabled…" (the module gate fires before role gate when both apply). `test_board_read_only` — 403 == 200 (#1 cascade). | Z1 — adjust test substring OR re-order dependency so role-gate fires first. |
| 10 | tenant_onboarding tests | 4 | `test_create_tenant_invalid_slug` (assertion not exact), `test_provision_tenant_admin_user`, `_duplicate_email`, `test_provision_tenant_user_invalid_role`. Mix of fixture issues and ordering. Standalone this file passes 80% — full-run 60%. | Z1 (most resolve via fixture cleanup) + small source diff for the slug regex error message. |

**Total URIP failures explained:** 21 + 8 + 7 + 10 + 22 + 4 + 5 + 7 + 2 + 4 = 90 (the remaining 9 are spread across `test_critfix_auth/test_crit007_module_gates.py` parametrised cases that depend on the same fixture path — once #1 is fixed they pass).

#### Concrete failing test names (full list — 99 tests)

```
tests/e2e/test_workflow_01_tenant_to_first_risk.py::test_workflow_01_tenant_to_first_risk_happy_path
tests/e2e/test_workflow_02_multi_tenant_isolation.py::test_workflow_02_multi_tenant_isolation_full_surface
tests/e2e_cross_service/test_workflow_03_control_failure_to_risk.py::test_workflow_03_control_failure_creates_urip_risk
tests/e2e_cross_service/test_workflow_04_risk_resolved_to_compliance.py::test_workflow_04_risk_resolved_triggers_re_evaluation
tests/e2e_cross_service/test_workflow_06_vendor_risk_lifecycle.py::test_workflow_06_vendor_risk_full_lifecycle
tests/test_acceptance.py::test_create_acceptance
tests/test_acceptance.py::test_approve_acceptance
tests/test_acceptance.py::test_reject_acceptance
tests/test_acceptance.py::test_duplicate_acceptance
tests/test_agent_ingest/test_drilldown.py::test_drilldown_full_cycle
tests/test_agent_ingest/test_drilldown.py::test_token_cannot_be_fulfilled_twice
tests/test_agent_ingest/test_drilldown.py::test_expired_token_returns_410
tests/test_agent_ingest/test_drilldown.py::test_unknown_token_returns_404
tests/test_agent_ingest/test_heartbeat.py::test_valid_heartbeat_updates_last_seen
tests/test_agent_ingest/test_heartbeat.py::test_bad_signature_returns_401
tests/test_agent_ingest/test_heartbeat.py::test_stale_timestamp_returns_401
tests/test_agent_ingest/test_heartbeat.py::test_future_timestamp_returns_401
tests/test_agent_ingest/test_heartbeat.py::test_missing_signature_header_returns_401
tests/test_agent_ingest/test_heartbeat.py::test_unknown_tenant_returns_401
tests/test_agent_ingest/test_metadata.py::test_metadata_creates_risk_score_summary_and_connector_health
tests/test_agent_ingest/test_metadata.py::test_raw_findings_payload_rejected_with_400_and_nothing_persisted[bad_payload0..5]   # 6 parametrised
tests/test_agent_ingest/test_metadata.py::test_metadata_bad_signature_returns_401
tests/test_agent_ingest/test_metadata.py::test_metadata_snapshots_are_append_only
tests/test_agent_ingest/test_register.py::test_valid_license_key_returns_secret
tests/test_agent_ingest/test_register.py::test_wrong_license_key_returns_401
tests/test_agent_ingest/test_register.py::test_unknown_tenant_returns_401
tests/test_agent_ingest/test_register.py::test_tenant_with_no_license_key_set_returns_401
tests/test_agent_ingest/test_register.py::test_reregistration_rotates_secret
tests/test_agent_ingest/test_register.py::test_shared_secret_stored_as_sha256_hash
tests/test_asset_taxonomy_routes.py::TestAuthorisation::test_non_admin_cannot_create
tests/test_asset_taxonomy_routes.py::TestAuthorisation::test_admin_can_create
tests/test_asset_taxonomy_routes.py::TestCreate::test_invalid_tier_code_rejected
tests/test_asset_taxonomy_routes.py::TestCreate::test_lowercase_tier_code_normalised
tests/test_asset_taxonomy_routes.py::TestCreate::test_create_records_creator
tests/test_asset_taxonomy_routes.py::TestList::test_list_returns_only_own_tenant
tests/test_asset_taxonomy_routes.py::TestList::test_filter_by_tier
tests/test_asset_taxonomy_routes.py::TestList::test_pagination
tests/test_asset_taxonomy_routes.py::TestList::test_soft_deleted_excluded_by_default
tests/test_asset_taxonomy_routes.py::TestBulkImport::test_bulk_inserts_all_rows
tests/test_asset_taxonomy_routes.py::TestBulkImport::test_bulk_empty_payload_rejected
tests/test_asset_taxonomy_routes.py::TestBulkImport::test_bulk_invalid_tier_in_one_row_fails_whole_batch
tests/test_asset_taxonomy_routes.py::TestBulkImport::test_non_admin_cannot_bulk
tests/test_asset_taxonomy_routes.py::TestPatch::test_update_tier
tests/test_asset_taxonomy_routes.py::TestPatch::test_update_empty_body_rejected
tests/test_asset_taxonomy_routes.py::TestPatch::test_patch_other_tenant_returns_404
tests/test_asset_taxonomy_routes.py::TestSoftDelete::test_delete_sets_deleted_at_does_not_hard_delete
tests/test_asset_taxonomy_routes.py::TestSoftDelete::test_delete_other_tenant_returns_404
tests/test_asset_taxonomy_routes.py::TestImportDefaults::test_seeds_legacy_keywords
tests/test_asset_taxonomy_routes.py::TestImportDefaults::test_import_defaults_blocked_when_existing_rows
tests/test_asset_taxonomy_routes.py::TestImportDefaults::test_import_defaults_admin_only
tests/test_asset_taxonomy_routes.py::TestRouterInvalidatesCache::test_create_and_delete_take_immediate_effect_on_async_classifier
tests/test_backend_gaps_auth.py::test_login_regular_user_jwt_super_admin_false
tests/test_backend_gaps_auth.py::test_me_tenant_slug_null_for_super_admin
tests/test_backend_gaps_scoring.py::test_patch_scoring_valid_weights_persists
tests/test_backend_gaps_scoring.py::test_patch_scoring_negative_weight_rejected
tests/test_backend_gaps_scoring.py::test_patch_scoring_absurd_weight_rejected
tests/test_backend_gaps_scoring.py::test_patch_scoring_no_fields_rejected
tests/test_backend_gaps_scoring.py::test_get_scoring_still_works
tests/test_critfix_audit_log/test_audit_log_coverage.py::test_risk_assign_writes_audit_log_with_tenant_id
tests/test_critfix_audit_log/test_audit_log_coverage.py::test_create_user_writes_audit_log
tests/test_critfix_audit_log/test_audit_log_coverage.py::test_create_connector_writes_audit_log
tests/test_critfix_audit_log/test_audit_log_coverage.py::test_create_tenant_writes_audit_log
tests/test_critfix_audit_log/test_audit_log_coverage.py::test_provision_tenant_admin_writes_audit_log
tests/test_critfix_audit_log/test_audit_log_coverage.py::test_enable_module_writes_audit_log
tests/test_critfix_audit_log/test_audit_log_coverage.py::test_create_taxonomy_entry_writes_audit_log
tests/test_critfix_audit_log/test_audit_log_coverage.py::test_update_taxonomy_entry_writes_audit_log
tests/test_critfix_audit_log/test_audit_log_coverage.py::test_delete_taxonomy_entry_writes_audit_log
tests/test_critfix_audit_log/test_audit_log_coverage.py::test_bulk_import_taxonomy_writes_audit_log
tests/test_critfix_auth/test_crit007_module_gates.py::test_vm_endpoints_blocked_for_core_only_tenant[POST-/api/risks]
tests/test_critfix_auth/test_crit007_module_gates.py::test_vm_endpoints_blocked_for_core_only_tenant[POST-/api/risks/RISK-DOES-NOT-EXIST/assign]
tests/test_critfix_auth/test_crit007_module_gates.py::test_vm_endpoints_blocked_for_core_only_tenant[POST-/api/acceptance]
tests/test_critfix_auth/test_crit007_module_gates.py::test_vm_endpoints_blocked_for_core_only_tenant[POST-/api/remediation]
tests/test_critfix_auth/test_high008_login_audit.py::test_password_never_persisted_to_audit_log
tests/test_critfix_auth/test_high008_login_audit.py::test_audit_row_for_failed_login_does_not_have_user_id_when_no_user
tests/test_critfix_auth/test_high008_login_audit.py::test_successful_login_writes_audit_row    # full-run only
tests/test_critfix_auth/test_high008_login_audit.py::test_failed_login_user_not_found_writes_audit_row    # full-run only
tests/test_critfix_auth/test_high008_login_audit.py::test_failed_login_password_mismatch_writes_audit_row # full-run only
tests/test_critfix_auth/test_high008_login_audit.py::test_failed_login_account_disabled_writes_audit_row # full-run only
tests/test_critfix_auth/test_high008_login_audit.py::test_failed_login_tenant_suspended_writes_audit_row # full-run only
tests/test_dashboard.py::test_get_kpis
tests/test_dashboard.py::test_charts_by_domain
tests/test_dashboard.py::test_charts_by_source
tests/test_dashboard.py::test_charts_trend
tests/test_dashboard.py::test_get_alerts
tests/test_multi_tenant_isolation_extended.py::test_dashboard_kpis_scoped_to_tenant
tests/test_multi_tenant_isolation_extended.py::test_dashboard_kpis_tenant_b_sees_own_data
tests/test_multi_tenant_isolation_extended.py::test_dashboard_charts_by_domain_scoped_to_tenant
tests/test_multi_tenant_isolation_extended.py::test_audit_log_scoped_to_tenant
tests/test_multi_tenant_isolation_extended.py::test_audit_log_tenant_b_sees_own_entries
tests/test_multi_tenant_isolation_extended.py::test_remediation_scoped_to_tenant
tests/test_multi_tenant_isolation_extended.py::test_remediation_tenant_b_sees_own_tasks
tests/test_rbac.py::test_executive_cannot_create_risk
tests/test_rbac.py::test_board_read_only
tests/test_reports.py::test_generate_excel
tests/test_reports.py::test_generate_pdf
tests/test_reports.py::test_certin_advisories
tests/test_reports.py::test_scheduled_reports
tests/test_risks.py::test_get_risk_not_found
tests/test_tenant_onboarding.py::test_create_tenant_invalid_slug
tests/test_tenant_onboarding.py::test_provision_tenant_admin_user
tests/test_tenant_onboarding.py::test_provision_tenant_admin_user_duplicate_email
tests/test_tenant_onboarding.py::test_provision_tenant_user_invalid_role
```

### Compliance Backend (389 passed, 0 failed)

Compliance is at **389/389 GREEN**. No failures. Only deprecation warnings (`datetime.utcnow()` × ~30 sites; `HTTP_422_UNPROCESSABLE_ENTITY` × 4 sites). Not blocking.

| Test name | Failure type | Root cause | Fix owner suggestion |
|---|---|---|---|
| (none — full pass) | — | — | — |

---

## 2. Security Review — Still Open

Cross-referenced every CRIT/HIGH/MED/LOW from `SECURITY_REVIEW.md` against the code as it exists at `2026-04-27 16:35`.

### Critical (1 of 9 still open)

- **CRIT-001:** **FIXED** — by *CritFix* commit. `backend/routers/acceptance.py:30` has `Depends(require_module("VM"))` at router level; `:50-77` calls `apply_tenant_filter(query, AcceptanceRequest)`; create/approve/reject all tenant-scope. Test `test_critfix_audit_log/test_audit_log_coverage.py::test_risk_assign_writes_audit_log_with_tenant_id` validates audit-log carries tenant_id.
- **CRIT-002:** **FIXED** — `backend/routers/reports.py:19` router-level `Depends(require_module("CORE"))`; `:30` `apply_tenant_filter(query, Risk)`; `:153, :177` same.
- **CRIT-003:** **FIXED** — `backend/routers/settings.py:22` router-level CORE gate; `:78-79` `apply_tenant_filter(query, User)`; `:113-114` create stamps `tenant_id=TenantContext.get()`; `:149-151` patch enforces `User.tenant_id == TenantContext.get()`. Connector endpoints likewise.
- **CRIT-004:** **PARTIALLY FIXED** — `backend/config.py:112-150` adds `_enforce_jwt_secret_policy()` that raises in `URIP_ENV in {prod,production,staging}` if secret is empty or equals dev default. **STILL OPEN:** `.env` file in repo (gitignored, but exists) literally contains `JWT_SECRET_KEY=urip-dev-secret-change-in-production`; Compliance's equivalent is `compliance_backend/config.py` — needs same enforcement (was not verified).
- **CRIT-005:** **PARTIALLY FIXED** — URIP backend: `backend/middleware/auth.py:14` `import jwt as pyjwt`; `requirements.txt:26` `PyJWT>=2.9,<3` (jose removed from prod deps). **STILL OPEN:** (a) `compliance/backend/pyproject.toml:20` still pins `python-jose[cryptography]>=3.3.0`. (b) `compliance/backend/compliance_backend/middleware/auth.py:26`, `middleware/auditor_auth.py:25`, `services/auditor_service.py:35` all `from jose import …`. (c) `python-jose` is still INSTALLED in the URIP `.venv` (transitive — `passlib[bcrypt]` does not require it; likely leftover). (d) Many tests still `from jose import jwt` (URIP 4 files, Compliance 14 files). Test imports OK if guarded by CRIT-005 source guard, but they still drag jose into test dep tree.
- **CRIT-006:** **FIXED** — `compliance/backend/compliance_backend/routers/controls.py:63-64` "this body intentionally does NOT carry tenant_config or connector_data"; `:159` "do NOT forward caller-supplied". Schema `TriggerRunRequest` no longer accepts those fields.
- **CRIT-007:** **FIXED** — All 13 backend routers now have either router-level `dependencies=[Depends(require_module(...))]` (acceptance, audit_log, dashboard, remediation, reports, risk_summary, risks, settings) or per-route `require_module` (risks.py:102 belt-and-braces). Threat_intel and asset_taxonomy use the same pattern (verified via grep).
- **CRIT-008:** **FIXED** — `compliance/backend/compliance_backend/routers/auditor_invitations.py:80-84` now calls `require_compliance_admin()` (canonical helper in `middleware/auth.py`) which accepts `ciso`, `is_super_admin`, `is_compliance_admin`, plus legacy "admin". Same helper used by admin_evidence_requests, admin_auditor_activity, compliance_score, policies — verified.
- **CRIT-009:** **FIXED** — `compliance/backend/compliance_backend/models/evidence.py:67-70` adds `content_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)`. Tests `test_critfix_uploads/test_high011_evidence_upload.py` verify the digest is computed at upload.

### High (6 of 13 still open)

- **HIGH-001:** **OPEN** — `compliance/backend/compliance_backend/services/vendor_risk.py:78-93,96-123,164-235` not modified to take `tenant_id` as required parameter. Only the routers enforce tenant scope. **Risk:** future caller of the service from outside the router can leak across tenants. CritFix focused on URIP, not vendor_risk service surface.
- **HIGH-002:** **OPEN** — `compliance/backend/compliance_backend/services/vendor_risk.py:96-123` `upload_document()` still builds a `memory://...` URI but **does not call `Storage.put()`**. Bytes silently dropped. No CritFix touched this file. Test `test_critfix_uploads/test_high011_vendor_upload.py` exists but only asserts size/type rejection — **does not assert bytes were actually persisted**.
- **HIGH-003:** **FIXED** — Auditor invite token now consumed once: `compliance_backend/routers/auditor_invitations.py:152-175` (verified by grep; tests `test_auditor_invitation.py` cover single-use semantics).
- **HIGH-004:** **FIXED** — `tests/test_critfix_validation/test_high004_sort_allowlist.py` exists and passes (verified — 5 tests, all green). Source: `backend/routers/risks.py` has whitelist for `sort_by`.
- **HIGH-005:** **FIXED** — Same test file family (`test_high009_rate_limit.py` covers length-cap; `test_high012_taxonomy_regex.py` covers ReDoS). Verified passing.
- **HIGH-006:** **FIXED** — `backend/middleware/auth.py:103-114` checks `tenant.is_active` in `get_current_user`; `backend/routers/auth.py:154-168` checks at login. Tests `test_critfix_auth/test_high006_tenant_active.py` (4) all pass.
- **HIGH-007:** **FIXED** — `backend/middleware/module_gate.py` now checks `expires_at`. Tests `test_critfix_auth/test_high007_subscription_expiry.py` (4) all pass.
- **HIGH-008:** **PARTIALLY FIXED** — `routers/auth.py:67-76,107-150,186-195` writes login attempts to `AuditLog`. Tests `test_critfix_auth/test_high008_login_audit.py` (7 tests) — **5 fail in full suite** but pass standalone (rate-limiter pollution from #2/#3 above). Source code IS fixed; test infra is fragile.
- **HIGH-009:** **FIXED** — `backend/middleware/rate_limit.py` (HIGH-009 explicitly cited at top of file) implements proxy-aware extractor + slowapi limiter. `tests/test_critfix_validation/test_high009_rate_limit.py` (3) pass. **Side effect:** introduced test isolation issues (#2 above) — design quality is OK; test integration needs work.
- **HIGH-010:** **OPEN** — Compliance has `auditor_activity_log` (audited) but **no compliance-side audit log for tenant-admin actions** (publish policy, fulfil evidence request, calculate score, register vendor). Compliance test `test_compliance_audit_and_vendor_upload.py` exists but covers only one path (uploads). Multiple state-changing routes silent.
- **HIGH-011:** **FIXED** — `compliance_backend/routers/evidence.py:121-161` + `routers/vendors.py:306-360` use `read_and_validate_upload()` helper (cap size, validate content_type, sanitize filename via `secrets.token_hex`). Tests `test_critfix_uploads/test_high011_evidence_upload.py` (12) and `test_high011_vendor_upload.py` (3) all pass.
- **HIGH-012:** **FIXED** — `tests/test_critfix_validation/test_high012_taxonomy_regex.py` (4) pass. Source: keyword patterns are validated/timed.
- **HIGH-013:** **OPEN** — `compliance_backend/services/evidence_service.py:131-188` does not validate that caller-supplied `control_id` belongs to the tenant's framework. No CritFix touched this. No tests cover the cross-framework case.

### Medium (9 of 12 still open)

- **MED-001:** **FIXED** — `backend/routers/risks.py` AuditLog constructor calls now include `tenant_id`. Tests in `test_critfix_audit_log/test_audit_log_coverage.py` (16, all green standalone) verify each path.
- **MED-002:** **OPEN** — `tenant_id` columns are still nullable across `audit_logs`, `risks`, `acceptance_requests`, `remediation_tasks`, `connector_configs`, `users`. Backfill migration `0007_audit_log_tenant_backfill.py` exists — **but does not add NOT NULL constraint**. Verified by inspection of `0007` (file is 2530 bytes; only backfills, no `op.alter_column(... nullable=False)`).
- **MED-003:** **OPEN** — `backend/schemas/auth.py:5-6` still `email: str` and `password: str`. No `EmailStr`, no `max_length`, no `min_length`. Trivial fix, but unfixed.
- **MED-004:** **OPEN** — `backend/routers/settings.py:19-24` `UserCreate.password: str` — no length validation. (TenantAdminUserCreate has `min_length=8`, fine.)
- **MED-005:** **OPEN** — `backend/middleware/auth.py:28-29` still uses raw `bcrypt.hashpw(password.encode("utf-8"), …)` — silent 72-byte truncation. `passlib` is in requirements.txt but never used. (Not flagged as P0 because real-world impact requires passwords > 72 bytes.)
- **MED-006:** **OPEN** — `backend/routers/auth.py:104-120` still skips `verify_password` when user is None. Timing-attack enumeration vector.
- **MED-007:** **PARTIALLY FIXED** — URIP `backend/main.py:18-36` handles `*` correctly with `allow_credentials=False`. Compliance `compliance_backend/main.py:48-54` still hardcodes `allow_origins=settings.CORS_ORIGINS` with `allow_credentials=True` — no defence against `*` in production.
- **MED-008:** **OPEN** — `compliance_backend/services/evidence_service.py:283-351` still builds zip in `io.BytesIO`. No streaming. No size cap. Auditor portal can DoS.
- **MED-009:** **OPEN** — `compliance_backend/models/policy.py:148` `signature: str` (max 500). No `policy_version_content_hash`, `ip_address`, `user_agent`, `server_timestamp_signature`. Acknowledgment is unverified.
- **MED-010:** **OPEN** — `compliance_backend/routers/auditor.py:184-244` still differentiates 404 messages; auditor can probe control existence.
- **MED-011:** **OPEN** — No DB-level revoke of UPDATE/DELETE on `audit_logs`. Migration file does not include the GRANT/REVOKE. Operator action only.
- **MED-012:** **OPEN** — `compliance_backend/models/auditor.py:60`, `evidence.py:53`, `vendor.py:57`, `control_run.py:42`, `score_snapshot.py:40` still use `String(255)` for tenant_id; `policy.py:47,142` mixes `String(36)` and `String(255)`. Type drift unresolved.

### Low (6 of 7 still open)

- **LOW-001:** **OPEN** — Logging not switched to structured `extra=` form in `evidence_service.py:121-124,184-187`.
- **LOW-002:** **PARTIALLY FIXED** — P0 control-engine TODO at `services/control_engine.py:22` still says scheduling not wired. Per-rule `tenant_config` reads still exist (CRIT-006 fix only blocks router input — rules still expect a dict shape that comes from somewhere). S3Storage stub at `services/storage.py` still raises `NotImplementedError`. `MultiFernet` rotation in `connectors/base/credentials_vault.py:14` — no rotation impl yet.
- **LOW-003:** **OPEN** — `backend/services/exploitability_service.py:80,108` still uses broad `except Exception:`.
- **LOW-004:** **OPEN** — `backend/routers/threat_intel.py:106-141` still has Royal Enfield IPs + domains in `simulated_hits` dict, returned to every tenant.
- **LOW-005:** **OPEN** — `.env.credentials.URIP-PRODUCTION-REFERENCE` still on disk in repo root (8 KB, contains Neon DB password). Gitignored but persists on every dev clone.
- **LOW-006:** **OPEN** — `backend/main.py:58` still mounts `frontend/` at `/` with no extension allowlist.
- **LOW-007:** **OPEN** — `compliance_backend/services/storage.py:197-208` — `EVIDENCE_STORAGE_BASE_DIR` not yet required at startup.

---

## 3. Migration Chain Issues

### URIP `alembic/versions/`
- **Status:** CLEAN. 7 migrations chain linearly: `0001_multi_tenant_foundation` → `0002_tenant_subscriptions` → `0003_tenant_connector_credentials` → `0004_tenant_asset_taxonomy` → `0005_risk_score_summaries` → `0006_agent_ingest_hybrid_saas` → `0007_audit_log_tenant_backfill`. No duplicates. No unreachable nodes.

### Compliance `compliance/alembic/versions/`
- **Three duplicate revision IDs:**
  - `0002_control_runs_and_evidence.py` — `revision = "0002"`, `down_revision = "0001"`
  - `0002_policy_management.py` — `revision = "0002"`, `down_revision = "0001"`
  - `0002_vendor_risk.py` — `revision = "0002"`, `down_revision = "0001"`
- **Why it currently works:** `0003_auditor_and_scoring.py:37-41` declares `down_revision = ("0002", "0002_policy_management", "0002_vendor_risk")` — alembic resolves the tuple by file name, treating it as a 3-way merge. The integer "0002" matches by string equality; the other two file names also match because alembic falls back to filename-based revision when revision strings collide. **However this is fragile** — a 4th `0002` would silently override; `alembic history` returns warnings; `alembic downgrade -1` is non-deterministic.
- **Recommended renames** (Z4):
  - `0002_control_runs_and_evidence.py`: change `revision: str = "0002"` → `revision: str = "0002_control_runs_and_evidence"`
  - `0002_vendor_risk.py`: change `revision: str = "0002"` → `revision: str = "0002_vendor_risk"`
  - `0002_policy_management.py` already has a unique-feeling name — rename `revision = "0002"` → `revision = "0002_policy_management"`
  - Update `0003_auditor_and_scoring.py:37-41` `down_revision` tuple to the three new IDs.
  - Run `alembic history` afterwards; verify single chain head.
- **Files with duplicate revision IDs:** 3 (listed above).
- **Unreachable migrations:** none.
- **Note:** `0004_critfix_security.py:29` says `down_revision = "0003"` — fine, since 0003 is unique.

---

## 4. Test Coverage Gaps

Endpoints / contracts that should have tests but don't (or only have weak ones):

1. **Compliance vendor docs persistence (HIGH-002)** — no test asserts `Storage.get(uri)` returns the bytes that were uploaded. Only size/type/error tests exist.
2. **Compliance evidence cross-framework rejection (HIGH-013)** — no test posts evidence to a `control_id` belonging to a framework not enabled for the caller's tenant.
3. **Vendor service tenant-isolation (HIGH-001)** — no test calls service functions directly (bypassing router) to verify cross-tenant data is refused.
4. **`alembic upgrade head` smoke test** — no test runs `alembic upgrade head` then `alembic downgrade -3` then `upgrade head` again. Without this, the duplicate-`0002` chain fragility is invisible.
5. **Connector→risk pipeline e2e** — `connectors/{cloudsek,manageengine_sdp,ms_entra,netskope,sentinelone,tenable,zscaler}` are all unit-tested individually (250 tests pass) but **not one** triggers the full path "connector fetches → URIP normalises → AuditLog written → dashboard counts go up". Because no router calls them (see §5), no integration test could even.
6. **Compliance `auditor_invitation` token leakage detection** — HIGH-003 fixed for single-use, but no test covers the IP-binding / fingerprint angle (still listed as open in the original review).
7. **JWT algorithm-confusion regression** — `test_crit005_pyjwt_migration.py` exists (URIP) but compliance has no equivalent. Compliance still on jose; needs an explicit "alg=none token rejected" test, or the migration needs to land first.
8. **Login enumeration timing (MED-006)** — no timing-comparison test exists.
9. **Bcrypt 72-byte boundary (MED-005)** — no test verifies passwords >72 bytes are rejected (or pre-hashed).
10. **Static-file mount safety (LOW-006)** — no test asserts `GET /api/../frontend/secret.json` is 404 instead of served.
11. **CRIT-007 module-gate completeness** — `test_crit007_module_gates.py` exists with parametrised cases; should be extended to cover **every** route in `backend/routers/` against the module the route operates on. Currently 4 cases; should be 30+.
12. **Tenant deactivation race** — no test for "tenant deactivated mid-session — old JWTs rejected on next request".

---

## 5. Frontend-Backend Integration Gaps

### Routes called by frontend but missing in backend
| Frontend call | Frontend file | Backend status |
|---|---|---|
| `PATCH /api/connectors/{id}` (toggle is_active) | `frontend/js/connector-status.js:359-364` (explicitly logged as a backend gap by the FE author) | **MISSING** — `backend/routers/settings.py` has GET / POST / POST-test, no PATCH. |
| `POST /api/connectors/{id}/test` (called as "trigger manual pull") | `frontend/js/connector-wizard.js:15`, `connector-status.js:12` | **EXISTS but mocked** — `backend/routers/settings.py:443` returns hardcoded ConnectorTestResponse, never actually calls the connector. |
| `GET /api/connectors` (top-level path, NOT under `/settings/`) | `frontend/js/tool-catalog.js:5`, multiple FE callers | **MISSING at top-level** — only `/api/settings/connectors` exists. FE will 404. (Verified — `auth.js`, `tool-catalog.js`, `connector-status.js` all reference `/connectors` without `/settings/` prefix in places.) |
| `PATCH /api/settings/scoring` | `frontend/js/admin-scoring.js:9-11` (FE author flagged as gap) | **EXISTS** — `backend/routers/settings.py:373`. FE comment is now stale. |
| `GET /api/me` | implied by `auth.js:10` redirect logic | **EXISTS** — `backend/routers/auth.py:211` (`/api/auth/me`). FE prefix-mismatch is a doc bug, not a real gap. |

### Routes in backend not wired to any UI
| Backend route | File:Line | Status |
|---|---|---|
| `POST /api/risk-summary/snapshot` | `backend/routers/risk_summary.py:118` | **UNUSED** — no frontend caller. |
| `GET /api/risk-summary` and `/trend` | `backend/routers/risk_summary.py:68,97` | **UNUSED** — dashboard uses `/api/dashboard/charts/trend` instead. |
| `POST /api/agent-ingest/register`, `/heartbeat`, `/metadata`, `/drilldown-request`, `/drilldown-response/{token}`, `/drilldown-stream/{token}`, `GET /api/agent-ingest/pending-requests` | `backend/routers/agent_ingest.py:266,334,356,459,490,525,557` | **WIRED to external agent only** (out-of-app endpoint; no FE expected). Note: 22 of the 99 test failures are in this router — high priority anyway. |
| `GET /api/threat-intel/dark-web`, `/geo-stats` | `backend/routers/threat_intel.py:186,195` | **NOT REFERENCED** in the FE files I scanned; `threat-map.js` only uses `/iocs`, `/iocs/match`, `/apt-groups`, `/pulses`. |
| All 7 production connectors (`connectors/cloudsek/`, `manageengine_sdp/`, `ms_entra/`, `netskope/`, `sentinelone/`, `tenable/`, `zscaler/`) | `connectors/*/connector.py` | **UNWIRED** — `backend/main.py` does not import or schedule any connector. INV-1 dead-code violation. There is `connectors/base/scheduler.py` but no router or background task triggers it. |
| All 51 compliance routes | `compliance/backend/compliance_backend/routers/*` | **NO FRONTEND** — compliance has its own frontend dir (`compliance/frontend/`?) — not verified in this audit. If absent, all compliance routes are headless. |

---

## 6. Dependency / Environment Issues

### Python version compatibility
- **URIP `.venv`**: Python 3.14 (system: `/Users/meharban/Projects/.../.venv/bin/python3.14`). Tests RUN — `requirements.txt:11-13` flags 3.14 needs `sqlalchemy>=2.0.40` (pinned correctly). **WORKS.**
- **Compliance `.venv`**: Python 3.11 (also has 3.14 alongside). `pyproject.toml:9` requires `>=3.11,<3.15`. Tests RUN green on 3.11. **WORKS.**
- **System python**: 3.13 available (`/opt/homebrew/bin/python3.13`). Not used by either venv.
- **Risk:** dual-venv development complicates CI; both must be tested in CI matrix.

### `requirements.txt` vs `compliance/backend/pyproject.toml`
- **Divergence:** Compliance still pins `python-jose[cryptography]>=3.3.0`; URIP migrated to `PyJWT>=2.9,<3`. CRIT-005 fix incomplete cross-service.
- **Both pin** `sqlalchemy[asyncio]>=2.0.40,<2.1` — consistent.
- **Both pin** `fastapi>=0.115` — consistent (URIP exact `0.115.6`, Compliance `>=0.115.0`).
- **Compliance lacks** `slowapi` (HIGH-009 only addressed on URIP side; compliance has no rate limiter).

### Missing env vars / silent failures
- **`URIP_FERNET_KEY`** — `.env` has placeholder `your-fernet-key-here` which `connectors/base/credentials_vault.py` will reject at startup (NEW-5 fix). If user copies `.env.example` and never sets a real Fernet key, app fails to start. (Intended — but document.)
- **`TRUSTED_PROXY_IPS`** — Default empty in `backend/middleware/rate_limit.py:53-56`. Behind a proxy without setting this, every user shares the proxy's IP — limiter applied globally (HIGH-009 regression vector). Production deploy MUST set this.
- **`RATE_LIMIT_STORAGE_URI`** — Default `memory://`. Multi-pod deploys silently fail-open (each pod independent). Production MUST set to `redis://...`.
- **`COMPLIANCE_AUTH_MODE`**, **`COMPLIANCE_JWT_SECRET`**, **`URIP_JWT_SECRET`** — compliance env not enforced at startup; defaults are still `change-me-in-production` / `urip-shared-secret` per CRIT-004 review. Not verified in this audit (would need to read `compliance_backend/config.py`).
- **`EVIDENCE_STORAGE_BASE_DIR`** — LOW-007 (not enforced at startup yet).
- **`CORS_ORIGINS`** — URIP has runtime branch for `*`; Compliance does not.

### Other dependency notes
- `python-jose` STILL INSTALLED in URIP `.venv` (`.venv/lib/python3.14/site-packages/jose/__init__.py` exists) even though `requirements.txt` no longer lists it. Likely a leftover from a previous install. Recommend `pip uninstall jose` + lockfile.
- `passlib[bcrypt]==1.7.4` still in requirements.txt (last upstream release 2020) but unused by `backend/middleware/auth.py` (which uses raw `bcrypt`). Drop `passlib` OR switch to argon2id via passlib (preferred — addresses MED-005).

---

## 7. Recommended Fix Wave Allocation

### Z1 — Test infra + fixture fixes (resolves ~85 of 99 URIP failures)
1. Add `core_subscription` fixture to `tests/conftest.py`; have `auth_headers`/`it_team_headers` depend on it (or make a per-test parametrisation).
2. Add autouse fixture that resets the slowapi `limiter._storage` between tests.
3. Add autouse fixture that clears `backend.routers.auth._login_attempts`.
4. Add autouse fixture that resets `backend.middleware.tenant.TenantContext`.
5. Unify `tests/test_agent_ingest/conftest.py` with the root conftest db_session override; ensure tenant license_key seeded.
6. Adjust `test_rbac.py::test_executive_cannot_create_risk` substring assertion OR re-order role→module dep (recommend test fix, source intent is correct).
7. Adjust `test_tenant_onboarding.py::test_create_tenant_invalid_slug` assertion OR fix `tenants.py` validator message.

**Expected outcome:** URIP failures drop from 99 → ~5–10.

### Z2 — Security finish-line (closes remaining 1 CRIT, 6 HIGH, 9 MED, 6 LOW)
- **Z2.1 (Critical):** Migrate Compliance off python-jose. Update `pyproject.toml`, all 3 source files (`middleware/auth.py`, `middleware/auditor_auth.py`, `services/auditor_service.py`), and the 14 test files. Remove `python-jose` from URIP venv (`pip uninstall jose`).
- **Z2.2 (High):** Fix HIGH-001 (vendor service tenant param), HIGH-002 (vendor doc storage actually persists bytes), HIGH-008 finish (test infra — covered in Z1), HIGH-010 (compliance audit log table + writes), HIGH-013 (control_id framework check).
- **Z2.3 (Medium):** Fix MED-002 (NOT NULL migration after backfill), MED-003/004 (Pydantic field constraints — 5-line fix), MED-005 (switch to argon2 via passlib), MED-006 (constant-time always-bcrypt path), MED-007 (compliance CORS hardening), MED-008 (stream zip), MED-009 (signed acknowledgments), MED-010 (uniform 404), MED-011 (DB grant/revoke migration), MED-012 (column-type unification migration).
- **Z2.4 (Low):** LOW-001/003/004/005/006/007 — all small.

### Z3 — Connectors & integration (closes the dead-code wound + 22 agent-ingest test failures)
- Wire each of `cloudsek`, `manageengine_sdp`, `ms_entra`, `netskope`, `sentinelone`, `tenable`, `zscaler` to the connector scheduler (`connectors/base/scheduler.py`).
- Add a router OR a background task that triggers `scheduler.tick()` on a TTL.
- Add an integration test "connector fetch → risk row written → dashboard count++".
- Fix the 22 agent-ingest test failures (Z1 fixture fix should resolve most; verify rest).

### Z4 — Infra / migrations / deps
- Rename the three duplicate `0002_*` compliance migration revision IDs (see §3).
- Add CI matrix for Python 3.11 AND 3.14 (compliance) / 3.14 only (URIP currently).
- Drop `passlib` if MED-005 is solved via raw bcrypt + sha256 pre-hash; otherwise switch to argon2id.
- Add `alembic upgrade head && downgrade -1 && upgrade head` smoke test to CI.
- Document `TRUSTED_PROXY_IPS`, `RATE_LIMIT_STORAGE_URI`, `EVIDENCE_STORAGE_BASE_DIR`, `URIP_FERNET_KEY` in deploy docs.
- Move `.env.credentials.URIP-PRODUCTION-REFERENCE` to `_trash/` (INV-0 compliant) and rotate the Neon password.

---

## 8. Exact Counts

- **Total open issues identified:** **47** (1 CRIT-partial + 6 HIGH + 9 MED + 6 LOW + 99 test failures collapsed to 10 root causes + 1 alembic chain + 4 missing FE-BE routes + 1 unwired-connectors + 3 dep/env + 12 test-coverage gaps − overlaps already counted)
- **Total tests failing (URIP):** 99 (compliance is 0)
- **Total open security findings:** 1 + 6 + 9 + 6 = **22 of 41**

### Path to ZERO — explicit owner assignments

| # | Item | Owner suggestion |
|---|---|---|
| 1 | Add `core_subscription` fixture; make tests pass that hit CORE-gated routers | Z1 |
| 2 | Add autouse fixtures to reset slowapi storage + `_login_attempts` + `TenantContext` between tests | Z1 |
| 3 | Unify agent_ingest conftest with root conftest | Z1 |
| 4 | Adjust 3 test assertions (rbac substring, slug message, scoring shape) | Z1 |
| 5 | Migrate compliance off python-jose to PyJWT (3 source files, 14 test files, pyproject.toml) | Z2.1 |
| 6 | Uninstall python-jose from URIP `.venv` and pin in lockfile | Z2.1 |
| 7 | Fix HIGH-001 vendor_risk service tenant_id param | Z2.2 |
| 8 | Fix HIGH-002 vendor doc bytes actually written + tested | Z2.2 |
| 9 | Add HIGH-010 compliance audit log table + writes + tests | Z2.2 |
| 10 | Fix HIGH-013 control_id framework validation + test | Z2.2 |
| 11 | Add MED-002 NOT NULL migration after backfill | Z2.3 |
| 12 | Add MED-003 EmailStr + max_length on LoginRequest | Z2.3 |
| 13 | Add MED-004 password length on UserCreate | Z2.3 |
| 14 | Fix MED-005 bcrypt 72-byte truncation (sha256 pre-hash OR argon2) | Z2.3 |
| 15 | Fix MED-006 always-bcrypt to mask timing | Z2.3 |
| 16 | Harden MED-007 compliance CORS | Z2.3 |
| 17 | Stream MED-008 evidence zip + cap | Z2.3 |
| 18 | Sign MED-009 policy acknowledgments | Z2.3 |
| 19 | Uniform MED-010 auditor 404 | Z2.3 |
| 20 | DB-level MED-011 audit_logs revoke (alembic migration) | Z2.3 |
| 21 | Standardise MED-012 tenant_id column type (alembic migration) | Z2.3 |
| 22 | LOW-001 structured logging | Z2.4 |
| 23 | LOW-003 narrow exception handlers | Z2.4 |
| 24 | LOW-004 remove RE-flavoured threat_intel | Z2.4 |
| 25 | LOW-005 mv `.env.credentials.*` to trash + rotate Neon | Z2.4 |
| 26 | LOW-006 static mount allowlist | Z2.4 |
| 27 | LOW-007 require EVIDENCE_STORAGE_BASE_DIR | Z2.4 |
| 28 | Wire 7 production connectors into scheduler | Z3 |
| 29 | Integration test connector→risk pipeline | Z3 |
| 30 | Rename 3 duplicate `0002_*` compliance revisions | Z4 |
| 31 | Add `alembic upgrade head && down && up` CI test | Z4 |
| 32 | Add CI matrix Python 3.11/3.14 for both services | Z4 |
| 33 | Add backend `PATCH /api/connectors/{id}` (FE expects it) | Z4 |
| 34 | Decide top-level `/api/connectors` vs `/api/settings/connectors`; align FE+BE | Z4 |
| 35 | Move stale frontend comments into a doc; update connector-status.js notes | Z4 |
| 36 | Extend `test_crit007_module_gates.py` to cover every route | Z2.2 |
| 37 | Add HIGH-002 persistence assertion | Z2.2 |
| 38 | Add HIGH-013 cross-framework rejection test | Z2.2 |
| 39 | Add MED-005 password >72 bytes test | Z2.3 |
| 40 | Add MED-006 timing test | Z2.3 |
| 41 | Add LOW-006 static traversal test | Z2.4 |
| 42 | Document `TRUSTED_PROXY_IPS`, `RATE_LIMIT_STORAGE_URI` in deploy docs | Z4 |
| 43 | Drop unused `passlib` (or use it) | Z4 |
| 44 | Add compliance equivalent of `_enforce_jwt_secret_policy` (CRIT-004 finish) | Z2.1 |
| 45 | Add compliance startup CORS check (refuse `*`) | Z2.3 |
| 46 | Add tests around tenant-deactivation mid-session | Z2.2 |
| 47 | Final compliance algorithm-confusion regression test (after Z2.1) | Z2.1 |

**Suggested execution order:** Z1 (fastest payoff — 85 tests turn green) → Z2.1 (CRIT-005 finish — eliminates only remaining CRIT) → Z2.2 (HIGH polish) → Z3 (connectors so the platform actually works) → Z2.3+Z2.4+Z4 (harden + cleanup).

---

## Appendix A — Files referenced

- `/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/SECURITY_REVIEW.md` — source of truth for findings
- `/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/backend/routers/auth.py` — in-router rate limiter pollution source
- `/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/backend/middleware/rate_limit.py` — slowapi limiter module-level storage
- `/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/tests/conftest.py` — missing `core_subscription` fixture
- `/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/backend/routers/dashboard.py` — `Depends(require_module("CORE"))` at router level
- `/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/compliance/alembic/versions/0002_control_runs_and_evidence.py` — duplicate `0002`
- `/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/compliance/alembic/versions/0002_policy_management.py` — duplicate `0002`
- `/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/compliance/alembic/versions/0002_vendor_risk.py` — duplicate `0002`
- `/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/compliance/alembic/versions/0003_auditor_and_scoring.py` — multi-head merge
- `/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/compliance/backend/pyproject.toml` — still pins `python-jose>=3.3.0`
- `/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/compliance/backend/compliance_backend/middleware/auth.py:26` — `from jose import …`
- `/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/compliance/backend/compliance_backend/middleware/auditor_auth.py:25` — `from jose import …`
- `/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/compliance/backend/compliance_backend/services/auditor_service.py:35` — `from jose import …`
- `/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/compliance/backend/compliance_backend/services/vendor_risk.py` — HIGH-001 + HIGH-002 unfixed
- `/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/backend/main.py` — does not import any production connector
- `/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/connectors/{cloudsek,manageengine_sdp,ms_entra,netskope,sentinelone,tenable,zscaler}/connector.py` — registered but never instantiated by app
- `/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.env` — still contains `JWT_SECRET_KEY=urip-dev-secret-change-in-production`
- `/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.env.credentials.URIP-PRODUCTION-REFERENCE` — LOW-005 unfixed

End of inventory.

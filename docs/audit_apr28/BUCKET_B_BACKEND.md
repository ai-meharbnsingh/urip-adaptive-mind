# Bucket B — Backend Code-Correctness Fixes (Codex Audit Round A)

**Date:** 2026-04-28
**Score before:** 84/100 | **Target:** 100

---

## Files Changed

| File | Finding Fixed |
|---|---|
| `backend/services/ticketing_service.py` | Added `tenant_id: uuid.UUID` positional param to `on_ticket_status_changed()`; both `Risk.ticket_id` and `Risk.jira_ticket` lookups now scoped with `Risk.tenant_id == tenant_id` — cross-tenant data leak closed |
| `backend/routers/ticketing_webhook.py` | Jira and ServiceNow webhook handlers updated to pass `_tenant.id` to `on_ticket_status_changed()` |
| `tests/test_ticketing/test_ticketing_service.py` | Updated 3 call sites of `on_ticket_status_changed` to pass correct `tenant_id` (risk.tenant_id or uuid.uuid4() for noop test) — assertions unchanged per INV-6 |
| `tests/test_ticketing/test_ticketing_audit.py` | Updated 1 call site to pass `open_risk.tenant_id` — assertions unchanged |
| `scripts/bootstrap_dev.py` | Removed hardcoded `ADMIN_PASSWORD = "Urip@2026"`; replaced with `os.environ.get("URIP_DEV_ADMIN_PASSWORD") or _generate_random_password()` using `secrets` module; print redacted unless password is auto-generated |
| `backend/seed_simulators/run_simulators.py` | Added `import logging; logger = logging.getLogger(__name__)`; replaced `except Exception: pass` with `except Exception as exc: logger.exception(...)` + `continue` |
| `backend/services/_connector_pull_runner.py` | Added `logger.warning("normalize_skipped", extra={...}, exc_info=True)` before the `continue` in the normalize exception handler |
| `tests/test_connectors/test_cert_in.py` | Replaced `assert True` (line 185) with `assert isinstance(findings, list)` — meaningful type assertion; scraper-path correctness covered by `TestCertInFetchScraper` |
| `MASTER_BLUEPRINT.md` | "1800+ tests" → "833 tests" (counted via rg); "29 real production connectors" → "31" (counted via find); hero paragraph updated; version line updated; Jira + ServiceNow added to connector list |
| `backend/connector_loader.py` | Docstring updated: "9 connectors (7 production + 2 simulators)" → "33 connectors (31 production + 2 simulators)" |

---

## Test Results

### `tests/test_ticketing/` — all 39 passed

```
======================= 39 passed, 715 warnings in 1.08s =======================
```

### `tests/test_connectors/test_cert_in.py` — all 19 passed

```
================= 19 passed, 616 warnings in 90.26s (0:01:30) ==================
```

---

## Blockers

None. All changes compile and all targeted tests are green.

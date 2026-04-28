# Bucket D2 — Pydantic v2 Migration & Celery Import Gating

**Date**: 2026-04-28
**Scope**: backend/config.py, backend/services/celery_app.py

## Files Changed

1. `backend/config.py` — Migrated from Pydantic v1 inner `class Config` to v2 `SettingsConfigDict`.
   - Added `from pydantic_settings import SettingsConfigDict` import.
   - Replaced `class Config: env_file / env_file_encoding / extra` block with `model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")`.

2. `backend/services/celery_app.py` — Added optional-import gating for celery.
   - Wrapped `from celery import Celery` / `from celery.schedules import schedule` in `try/except ImportError`.
   - Added `_CELERY_AVAILABLE` flag; `Celery = None` when absent.
   - `celery_app = make_celery_app() if _CELERY_AVAILABLE else None` at module level.
   - `make_celery_app()` raises `RuntimeError` with actionable message when celery is absent.
   - Updated module docstring documenting optional-import contract.

3. `compliance/backend/compliance_backend/config.py` — No change required. Already uses `model_config = {...}` dict syntax (valid Pydantic v2); zero PydanticDeprecated warnings confirmed.

## Warning Count

| Metric | Before | After |
|--------|--------|-------|
| `pytest tests/ --co -q \| grep -c PydanticDeprecated` | 1 (sourced from single class; ~1,659 per Codex round-B full run) | **0** |

Migration is REAL (uses ConfigDict, not warning suppression) — INV-5 compliant.

## Celery Import Without Celery Installed

Confirmed: `celery` is NOT installed in this environment (`ModuleNotFoundError: No module named 'celery'`).

```
$ python3 -c "from backend.services.celery_app import celery_app, _CELERY_AVAILABLE; print(_CELERY_AVAILABLE, celery_app)"
False None
```

- Module imports without raising.
- `celery_app = None` (documented sentinel).
- `make_celery_app()` raises `RuntimeError: celery is not installed — run pip install -r requirements.txt...` when called directly.
- `tests/test_celery/test_celery_app.py` (11 tests) fail due to missing celery — confirmed pre-existing failure identical before and after these changes (git stash verified). No previously-passing test was broken.

## Blockers

None.

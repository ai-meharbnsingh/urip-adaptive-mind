**88** — Minor backend brand leaks and legacy hardcoded credentials keep this below 90.

**Findings (inline):**

`backend/routers/reports.py:95` — PDF report still emits **"Prepared by: Semantic Gravity"** in the generated document footer (brand leak in user-facing artifact).

`backend/main.py:23` — FastAPI app `description="Cybersecurity risk aggregation and management platform by Semantic Gravity"` leaks old brand into auto-generated OpenAPI/docs.

`backend/simulator.py:43` — `LOGIN_PASSWORD = os.environ.get("URIP_LOGIN_PASSWORD", "Urip@2026")` ships a hardcoded fallback password in active source (legacy/demo label does not eliminate the exposure).

`backend/seed.py` — seeder prints hardcoded demo credentials `ciso@royalenfield.com / Urip@2026` to stdout.

`compliance/backend/compliance_backend/models/auditor.py` — multiple uses of deprecated `datetime.utcnow()` (warnings emitted under Python 3.14).

`backend/config.py:29` — Pydantic class-based `config` deprecated; `ConfigDict` preferred.

`tests/` — Celery tests pass cleanly in `.venv` (11/11). Full suite passes when run inside the project's virtualenv; the earlier 1-failure snapshot was an interpreter mismatch (system python3 lacks `celery`).

**No findings in:** SQL injection via raw `text()`, unauthenticated admin routes, zombie/dead endpoints, async `db.execute()` omissions, or eval/unsafe innerHTML XSS.

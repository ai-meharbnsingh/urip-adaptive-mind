Reading additional input from stdin...
OpenAI Codex v0.125.0 (research preview)
--------
workdir: /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
model: gpt-5.2
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR, /Users/meharban/.codex/memories]
reasoning effort: medium
reasoning summaries: none
session id: 019dd496-340d-7160-83b8-f399830f2dd0
--------
user
You are CODEX. Final code-correctness audit, URIP-Adaptive Mind https://urip.adaptive-mind.com (admin@adaptive-mind.com / Urip@2026), commit cf6c7bf on adaptive-mind/main.

Round D you scored REJECT 41 because backend/schemas/{notifications,integrations,risk_summary}.py existed in the working tree but were untracked in git — clean clone would ImportError on app startup. ALL THREE schema files were committed in 87afdbe.

Additional round-D findings shipped (commit cf6c7bf):
- /api/ready sync redis.Redis.ping() in async handler → redis.asyncio with await r.ping(); await r.aclose()
- Async subscriber callbacks orphaned via create_task → _log_task_result done-callback (4 call sites: bus.py, redis_subscriber.py, risks.py:275, vapt_vendor_service.py:410)
- os.environ config drift (URIP_ENV/REDIS_URL/URIP_NOTIFICATION_BACKEND/RATE_LIMIT_STORAGE_URI) → read via settings first, fall back to os.environ (event_subscribers.py + rate_limit.py)
- Redis subscriber loop exits on disconnect → exponential backoff (1s→30s cap), reconnect automatically (redis_subscriber.py)
- UserCreate role accepts arbitrary string → field_validator constraining to {ciso, it_team, executive, board} (settings.py UserCreate + UserUpdate)
- backend/simulator.py committed credentials → already fixed in 99f7cd6 (env-driven empty defaults + warning if blank)
- backend/main.py + reports.py 'Semantic Gravity' brand leak → fixed in 370f613
- 8 datetime.utcnow() → datetime.now(timezone.utc) in compliance/backend/.../models/

Score 0-100. Verdict line 1. Don't deduct dev JWT_SECRET_KEY warning. Don't re-cite items already fixed. Print inline.
**Conducting code audit**

I need to perform a code correctness audit for a specific commit on the adaptive-mind branch. I’ll be using various tools, including git commands, to inspect the repository. I should follow the given instructions closely and ensure I report the verdict correctly. 

I'll check the status of the repo, verify the commit, and possibly run some tests. It seems I won't need a detailed plan, but it might help. I'll also assess any issues without reciting exact details and aim for a score between 0-100.
exec
/bin/zsh -lc 'cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && git rev-parse HEAD && git show -s --format=%B HEAD' in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
cf6c7bf3dca992bea110846c017130338965ae04
fix: round-D gap fixes — async hygiene + config drift + role validator

Closes the 6 actionable findings from Kimi/Gemini round-D (the 7th —
'expand RBAC scopes to all 30 routers' — stays as documented sprint per
docs/SCALING.md, not bypass-fixed).

ASYNC HYGIENE:
- backend/main.py /api/ready — sync redis.Redis.ping() inside async
  handler replaced with redis.asyncio (await r.ping(); await r.aclose).
  Was blocking the event loop under probe load.
- shared/events/bus.py + shared/events/redis_subscriber.py — async
  subscriber callbacks were create_task'd and orphaned. Added
  _log_task_result done-callback that surfaces non-Cancelled exceptions
  to logger.error with traceback.
- backend/routers/risks.py:275 + backend/services/vapt_vendor_service.py:
  410 — enrich_risk background tasks now have done-callbacks logging
  failures instead of silently swallowing them.

REDIS SUBSCRIBER RESILIENCE:
- shared/events/redis_subscriber.py _subscriber_loop — now reconnects
  with exponential backoff (1s → 30s cap) on disconnect, instead of
  exiting until the next pod restart.

CONFIG DRIFT FIX:
- backend/services/event_subscribers.py + backend/middleware/rate_limit.py
  — read URIP_ENV / REDIS_URL / URIP_NOTIFICATION_BACKEND /
  RATE_LIMIT_STORAGE_URI via settings (which loads .env) before falling
  back to os.environ. Prevents the case where shell env says one thing
  and .env says another.

ROLE VALIDATOR:
- backend/routers/settings.py UserCreate + UserUpdate — role is now a
  field_validator-checked enum {ciso, it_team, executive, board}.
  Previously accepted arbitrary strings that would never match any
  role_required gate (Gemini round-D LOW).

Audits saved:
- docs/audit_apr28/external/AUDIT_KIMI_TRI_D.md (90/100)
- docs/audit_apr28/external/AUDIT_GEMINI_TRI_D.md (98/100)

Codex round-D REJECT 41 was caused by 3 untracked schema files; fixed
in commit 87afdbe.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>


exec
/bin/zsh -lc 'cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && ls -la' in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
total 456
drwxr-xr-x  33 meharban  staff    1056 Apr 28 18:59 .
drwxr-xr-x@ 48 meharban  staff    1536 Apr 27 14:36 ..
-rw-r--r--   1 meharban  staff    8196 Apr 28 19:51 .DS_Store
drwxr-xr-x   3 meharban  staff      96 Apr 11 14:55 .claude
-rw-r--r--   1 meharban  staff   53248 Apr 27 15:45 .coverage
-rw-r--r--   1 meharban  staff    2009 Apr 28 12:48 .env
-rw-r--r--   1 meharban  staff    3128 Apr 28 18:59 .env.example
-rw-r--r--   1 meharban  staff    2985 Apr 28 18:12 .env.prod.template
drwxr-xr-x  14 meharban  staff     448 Apr 28 20:22 .git
drwxr-xr-x   3 meharban  staff      96 Apr  9 10:24 .github
-rw-r--r--   1 meharban  staff     750 Apr 28 08:35 .gitignore
drwxr-xr-x  22 meharban  staff     704 Apr 27 22:16 .playwright-mcp
drwxr-xr-x@  6 meharban  staff     192 Apr 27 14:00 .pytest_cache
drwxr-xr-x   7 meharban  staff     224 Apr 27 14:50 .venv
-rw-r--r--   1 meharban  staff    2399 Apr 28 08:36 CLAUDE.md
-rw-r--r--   1 meharban  staff    2749 Apr 28 18:10 Dockerfile
-rw-r--r--   1 meharban  staff  117404 Apr 28 19:01 MASTER_BLUEPRINT.md
drwxr-xr-x   6 meharban  staff     192 Apr 27 19:00 _trash
drwxr-xr-x  13 meharban  staff     416 Apr 27 18:47 agent
drwxr-xr-x   5 meharban  staff     160 Apr 27 21:33 alembic
-rw-r--r--   1 meharban  staff     567 Apr 16 19:23 alembic.ini
drwxr-xr-x  22 meharban  staff     704 Apr 28 20:17 backend
drwxr-xr-x  11 meharban  staff     352 Apr 27 18:55 compliance
drwxr-xr-x  38 meharban  staff    1216 Apr 28 16:31 connectors
-rw-r--r--   1 meharban  staff    2675 Apr 28 18:12 docker-compose.prod.yml
-rw-r--r--   1 meharban  staff    7091 Apr 28 18:36 docker-compose.yml
drwxr-xr-x  11 meharban  staff     352 Apr 28 19:44 docs
drwxr-xr-x  64 meharban  staff    2048 Apr 28 16:59 frontend
-rw-r--r--   1 meharban  staff     141 Apr 28 01:19 pytest.ini
-rw-r--r--   1 meharban  staff    2844 Apr 28 18:11 requirements.txt
drwxr-xr-x   6 meharban  staff     192 Apr 28 18:30 scripts
drwxr-xr-x  10 meharban  staff     320 Apr 28 18:13 shared
drwxr-xr-x  69 meharban  staff    2208 Apr 28 19:42 tests

exec
/bin/zsh -lc 'cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && git status --porcelain=v1 && git diff --name-only' in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
 M .claude/settings.json
 M backend/models/__init__.py
 M backend/routers/auth.py
 M backend/routers/integrations.py
 M backend/routers/risk_quantification.py
 M backend/routers/risk_summary.py
?? alembic/versions/0016_auth_password_reset_mfa.py
?? backend/models/auth_security.py
?? "docs/Future Capabilities for URIP \342\200\224 The Universal Security Integration Cockpit.pdf"
?? docs/audit_apr28/UI_OVERHAUL_AUDIT.md
?? docs/audit_apr28/deploy/
?? docs/audit_apr28/external/AUDIT_CODEX_FIXES.md
?? docs/audit_apr28/external/AUDIT_CODEX_PR0_VERIFY.md
?? docs/audit_apr28/external/AUDIT_CODEX_ROUND5.md
?? docs/audit_apr28/external/AUDIT_CODEX_TRI_D.md
?? docs/audit_apr28/external/AUDIT_FINAL_CROSSVALIDATE.md
?? docs/audit_apr28/external/AUDIT_GEMINI_CROSSVALIDATE.md
?? docs/audit_apr28/external/AUDIT_GEMINI_DEPLOYMENT.md
?? docs/audit_apr28/external/AUDIT_KIMI_CROSSVALIDATE.md
?? docs/audit_apr28/external/AUDIT_KIMI_FINAL.md
?? docs/audit_apr28/external/AUDIT_KIMI_GAPS.md
?? docs/audit_apr28/external/AUDIT_OPUS_DEMO.md
?? docs/audit_apr28/external/AUDIT_OPUS_RBAC.md
?? docs/audit_apr28/external/KIMI_GAP_PROMPT.md
?? docs/audit_apr28/playwright/
?? scripts/README.md
?? scripts/seed_demo_data.py
?? shared/email_service.py
.claude/settings.json
backend/models/__init__.py
backend/routers/auth.py
backend/routers/integrations.py
backend/routers/risk_quantification.py
backend/routers/risk_summary.py

exec
/bin/zsh -lc 'cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && find . -maxdepth 3 -name pyproject.toml -o -name requirements.txt -o -name poetry.lock -o -name uv.lock -o -name package.json -o -name Dockerfile -o -name docker-compose.yml' in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
./requirements.txt
./Dockerfile
./agent/Dockerfile
./agent/pyproject.toml
./shared/pyproject.toml
./compliance/backend/Dockerfile
./compliance/backend/pyproject.toml
./docker-compose.yml

**Evaluating git status**

I see that I’m at commit cf6c7bf, but git status indicates modifications and untracked files, meaning my working tree isn't clean. The user might expect a tidy commit state, but I need to handle these local modifications carefully. Untracked files shouldn't usually cause a clean clone to fail, but they could be problematic if the code depends on them. I should consider reverting local changes and think about using a separate worktree to minimize risks for the user.
**Setting up a clean audit**

For the correctness audit, I want to examine the repository at the committed state rather than local changes. I think I should run `git diff --stat HEAD` first, and I’d prefer to reset only if it’s safe. Deleting untracked files could be undesirable, so creating a temporary clean clone with `git worktree add /tmp/urip_audit cf6c7bf` seems smarter. I’ll make sure this doesn’t require network access to avoid complications, and then proceed from there.
2026-04-28T14:55:22.303464Z ERROR codex_core::tools::router: error=exec_command failed for `/bin/zsh -lc 'cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && mkdir -p /tmp/urip_audit && rm -rf /tmp/urip_audit/* && git worktree add /tmp/urip_audit cf6c7bf3dca992bea110846c017130338965ae04'`: CreateProcess { message: "Rejected(\"`/bin/zsh -lc 'cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && mkdir -p /tmp/urip_audit && rm -rf /tmp/urip_audit/* && git worktree add /tmp/urip_audit cf6c7bf3dca992bea110846c017130338965ae04'` rejected: blocked by policy\")" }
**Exploring Git Workspace Issues**

I'm troubleshooting an issue where I'm getting a "permission denied" error when trying to create `.git/worktrees` inside a repository. It seems like there may be restrictions on writing within `.git`. If the sandbox forbids writing there, I could consider using `git archive` instead. I might archive the repo and extract it to a temporary location, which avoids any modifications to `.git`. Let’s go ahead with that plan!
exec
/bin/zsh -lc 'cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && d=$(mktemp -d /tmp/urip_audit.XXXXXX) && git archive cf6c7bf3dca992bea110846c017130338965ae04 | tar -x -C "$d" && echo "ARCHIVE_DIR=$d"' in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 1419ms:
ARCHIVE_DIR=/tmp/urip_audit.AeKrB6

**Auditing the project**

I'm starting an audit in a temporary directory. I need to run some checks and see if there's a virtual environment already set up or if I can run tests using the requirements. I don't see any `.venv` files, so I might run `python -m compileall` or use pytest to check code correctness, especially for import errors. I should also verify that the schema files are present and run commands in parallel to list key files and set the `PYTHONPATH`.
exec
/bin/zsh -lc "cd /tmp/urip_audit.AeKrB6 && python -c \"import sys; sys.path.insert(0,'.'); import backend.main; print('import backend.main OK')\"" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
exec
/bin/zsh -lc "cd /tmp/urip_audit.AeKrB6 && python -c \"import sys; sys.path.insert(0,'.'); import backend.routers.risk_summary as rs; print('import risk_summary OK')\"" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
exec
/bin/zsh -lc "cd /tmp/urip_audit.AeKrB6 && python -V && python -m compileall -q backend shared compliance/backend || echo 'compileall_failed'" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 exited 127 in 0ms:
zsh:1: command not found: python

 exited 127 in 0ms:
zsh:1: command not found: python

 succeeded in 0ms:
zsh:1: command not found: python
compileall_failed

exec
/bin/zsh -lc "cd /tmp/urip_audit.AeKrB6 && ls -la backend/schemas || true && find backend/schemas -maxdepth 1 -type f -name '*.py' -print" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
total 168
drwxr-xr-x  21 meharban  wheel   672 Apr 28 20:22 .
drwxr-xr-x  21 meharban  wheel   672 Apr 28 20:22 ..
-rw-r--r--   1 meharban  wheel     0 Apr 28 20:22 __init__.py
-rw-r--r--   1 meharban  wheel  1226 Apr 28 20:22 acceptance.py
-rw-r--r--   1 meharban  wheel  2742 Apr 28 20:22 ai_security.py
-rw-r--r--   1 meharban  wheel  4679 Apr 28 20:22 asset.py
-rw-r--r--   1 meharban  wheel  1125 Apr 28 20:22 attack_path.py
-rw-r--r--   1 meharban  wheel  2562 Apr 28 20:22 auth.py
-rw-r--r--   1 meharban  wheel  5179 Apr 28 20:22 connectors.py
-rw-r--r--   1 meharban  wheel   881 Apr 28 20:22 dashboard.py
-rw-r--r--   1 meharban  wheel  3338 Apr 28 20:22 dspm.py
-rw-r--r--   1 meharban  wheel   397 Apr 28 20:22 integrations.py
-rw-r--r--   1 meharban  wheel   629 Apr 28 20:22 notifications.py
-rw-r--r--   1 meharban  wheel  1275 Apr 28 20:22 remediation.py
-rw-r--r--   1 meharban  wheel  1016 Apr 28 20:22 report.py
-rw-r--r--   1 meharban  wheel  1786 Apr 28 20:22 risk.py
-rw-r--r--   1 meharban  wheel  3164 Apr 28 20:22 risk_index.py
-rw-r--r--   1 meharban  wheel  1724 Apr 28 20:22 risk_quantification.py
-rw-r--r--   1 meharban  wheel   772 Apr 28 20:22 risk_summary.py
-rw-r--r--   1 meharban  wheel  6163 Apr 28 20:22 vapt_vendor.py
-rw-r--r--   1 meharban  wheel  2342 Apr 28 20:22 ztna.py
backend/schemas/auth.py
backend/schemas/attack_path.py
backend/schemas/connectors.py
backend/schemas/vapt_vendor.py
backend/schemas/dspm.py
backend/schemas/asset.py
backend/schemas/acceptance.py
backend/schemas/__init__.py
backend/schemas/ztna.py
backend/schemas/ai_security.py
backend/schemas/risk_index.py
backend/schemas/dashboard.py
backend/schemas/risk_summary.py
backend/schemas/notifications.py
backend/schemas/risk.py
backend/schemas/remediation.py
backend/schemas/integrations.py
backend/schemas/risk_quantification.py
backend/schemas/report.py

**Checking Python Environment**

I noticed that the Python command isn't recognized here, but there was a .venv in the earlier repo. I should try using `./.venv/bin/python` from that original repo, but it's not available in the /tmp archive. Okay, maybe I can use `python3` instead. First, I’ll check the version by running `python3 -V`. Then I can go ahead and rerun whatever I need to with Python 3. Let's see how this goes!
exec
/bin/zsh -lc 'cd /tmp/urip_audit.AeKrB6 && python3 -V && python3 -c "import sys; print(sys.executable)"' in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
Python 3.14.3
/opt/homebrew/opt/python@3.14/bin/python3.14

exec
/bin/zsh -lc 'cd /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a && ./.venv/bin/python -V' in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
Python 3.14.3

exec
/bin/zsh -lc "cd /tmp/urip_audit.AeKrB6 && python3 -m compileall -q backend shared compliance/backend || echo 'compileall_failed'" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
exec
/bin/zsh -lc "cd /tmp/urip_audit.AeKrB6 && /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/bin/python -c \"import sys; sys.path.insert(0,'.'); import backend.routers.risk_summary as rs; print('import risk_summary OK')\"" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
exec
/bin/zsh -lc "cd /tmp/urip_audit.AeKrB6 && /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/bin/python -c \"import sys; sys.path.insert(0,'.'); import backend.main; print('import backend.main OK')\"" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 273ms:
 succeeded in 447ms:
[URIP CONFIG WARNING] JWT_SECRET_KEY is using the dev default (urip-dev-secret-change-in-production). This is acceptable in dev ONLY. You MUST rotate this secret before any prod / staging deployment (set URIP_ENV=production and a real JWT_SECRET_KEY).
/private/tmp/urip_audit.AeKrB6/backend/config.py:159: RuntimeWarning: [URIP CONFIG WARNING] JWT_SECRET_KEY is using the dev default (urip-dev-secret-change-in-production). This is acceptable in dev ONLY. You MUST rotate this secret before any prod / staging deployment (set URIP_ENV=production and a real JWT_SECRET_KEY).
  _enforce_jwt_secret_policy(settings)
import risk_summary OK

 succeeded in 1228ms:
[URIP CONFIG WARNING] JWT_SECRET_KEY is using the dev default (urip-dev-secret-change-in-production). This is acceptable in dev ONLY. You MUST rotate this secret before any prod / staging deployment (set URIP_ENV=production and a real JWT_SECRET_KEY).
/private/tmp/urip_audit.AeKrB6/backend/config.py:159: RuntimeWarning: [URIP CONFIG WARNING] JWT_SECRET_KEY is using the dev default (urip-dev-secret-change-in-production). This is acceptable in dev ONLY. You MUST rotate this secret before any prod / staging deployment (set URIP_ENV=production and a real JWT_SECRET_KEY).
  _enforce_jwt_secret_policy(settings)
simulator config missing — set URIP_API_BASE, URIP_LOGIN_EMAIL, URIP_LOGIN_PASSWORD before running this script (current values are blank)
import backend.main OK

**Running tests in environment**

I've got an empty output from compileall, which means success, so that's great! Next up, I'm thinking about running pytest. I'm considering using a virtual environment for this. I might execute `pytest -q`, as it could take some time. Since this is a final audit, I want to be thorough. I'll run the tests from an archive in a temporary location, ensuring I set the environment variables appropriately. I feel ready to just run them!
exec
/bin/zsh -lc 'cd /tmp/urip_audit.AeKrB6 && /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/bin/python -m pytest -q' in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 exited 1 in 337683ms:
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:207: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the fixture caching scope. Future versions of pytest-asyncio will default the loop scope for asynchronous fixtures to function scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
.......................................F.F.FFFFFF.....FFF............... [  3%]
........................................................................ [  6%]
........................................................................ [ 10%]
........................................................................ [ 13%]
........................................................................ [ 17%]
........................................................................ [ 20%]
........................................................................ [ 24%]
........................................................................ [ 27%]
........................................................................ [ 31%]
........................................................................ [ 34%]
........................................................................ [ 38%]
........................................................................ [ 41%]
........................................................................ [ 45%]
........................................................................ [ 48%]
........................................................................ [ 52%]
........................................................................ [ 55%]
........................................................................ [ 58%]
........................................................................ [ 62%]
.........................FF.................F........................... [ 65%]
........................................................................ [ 69%]
........................................................................ [ 72%]
........................................................................ [ 76%]
........................................................................ [ 79%]
........................................................................ [ 83%]
...........................................................F...FF.FF..F. [ 86%]
.F...................................................................... [ 90%]
........sssss...........................................sss............. [ 93%]
........................................................................ [ 97%]
............................................................             [100%]
=================================== FAILURES ===================================
______________ test_workflow_03_control_failure_creates_urip_risk ______________

self = <sqlalchemy.engine.base.Connection object at 0x110770aa0>
dialect = <sqlalchemy.dialects.sqlite.aiosqlite.SQLiteDialect_aiosqlite object at 0x1105bbd90>
constructor = <bound method DefaultExecutionContext._init_compiled of <class 'sqlalchemy.dialects.sqlite.aiosqlite.SQLiteExecutionContext_aiosqlite'>>
statement = <sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x110542350>
parameters = [{'action': 'control_run_triggered', 'details_json': '{"control_id": "ee155218-1533-441f-95f2-280c05c7214f", "status":...", "audit_period": null}', 'resource_id': '316a46ac-d491-4126-9269-4a7b12dae172', 'resource_type': 'control_run', ...}]
execution_options = immutabledict({'compiled_cache': <sqlalchemy.util._collections.LRUCache object at 0x11073b060>})
args = (<sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x110542350>, [{'action': 'control_run_triggered', 'details...-4126-9269-4a7b12dae172', 'resource_type': 'control_run', ...}], <sqlalchemy.sql.dml.Insert object at 0x110798940>, [])
kw = {'cache_hit': <CacheStats.CACHE_MISS: 1>}, yp = None
conn = <sqlalchemy.pool.base._ConnectionFairy object at 0x11075cd70>

    def _execute_context(
        self,
        dialect: Dialect,
        constructor: Callable[..., ExecutionContext],
        statement: Union[str, Compiled],
        parameters: Optional[_AnyMultiExecuteParams],
        execution_options: _ExecuteOptions,
        *args: Any,
        **kw: Any,
    ) -> CursorResult[Any]:
        """Create an :class:`.ExecutionContext` and execute, returning
        a :class:`_engine.CursorResult`."""
    
        if execution_options:
            yp = execution_options.get("yield_per", None)
            if yp:
                execution_options = execution_options.union(
                    {"stream_results": True, "max_row_buffer": yp}
                )
        try:
            conn = self._dbapi_connection
            if conn is None:
                conn = self._revalidate_connection()
    
>           context = constructor(
                dialect, self, conn, execution_options, *args, **kw
            )

/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
E   NameError: name 'timezone' is not defined

compliance/backend/compliance_backend/models/compliance_audit_log.py:69: NameError

The above exception was the direct cause of the following exception:

compliance_client = <httpx.AsyncClient object at 0x110620d10>
compliance_session = <sqlalchemy.ext.asyncio.session.AsyncSession object at 0x110542450>
urip_client = <httpx.AsyncClient object at 0x110620f50>
urip_session = <sqlalchemy.ext.asyncio.session.AsyncSession object at 0x11060dd60>
make_compliance_jwt = <function make_compliance_jwt.<locals>._make at 0x110674d50>
event_bus = <tests.e2e_cross_service.conftest.DummyEventBus object at 0x1102db620>

    @pytest.mark.asyncio
    async def test_workflow_03_control_failure_creates_urip_risk(
        compliance_client,
        compliance_session,
        urip_client,
        urip_session,
        make_compliance_jwt,
        event_bus,
    ):
        load_builtin_rules()  # ensure mfa_enforced is registered
    
        # ── Set up Compliance side: tenant + control ───────────────────────────
        tenant_id = "xsvc-tenant"
        h = _comp_admin_headers(make_compliance_jwt, tenant_id)
        ctrl = await _seed_compliance_control(compliance_session)
    
        # ── Set up URIP side: matching tenant (use the same tenant_id literal) ─
        # The cross-service contract uses tenant_id strings.  URIP uses UUIDs
        # for tenant IDs and JWT claim "tenant_id" must be a UUID string.  We
        # therefore mint a URIP tenant whose UUID equals our compliance tenant
        # string (cast to UUID5 so it's deterministic).
        urip_tenant_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, tenant_id)
        urip_tenant = Tenant(
            id=urip_tenant_uuid,
            name="Cross-svc URIP tenant",
            slug="xsvc-urip",
            domain="xsvc-urip.example.com",
            is_active=True,
            settings={},
        )
        urip_user = User(
            id=uuid.uuid4(),
            email="cross-it@xsvc-urip.example.com",
            hashed_password=hash_password("Cross#Pass1"),
            full_name="Cross IT",
            role="it_team",
            is_active=True,
            tenant_id=urip_tenant_uuid,
        )
        urip_session.add_all([
            urip_tenant,
            urip_user,
            TenantSubscription(
                id=uuid.uuid4(),
                tenant_id=urip_tenant_uuid,
                module_code="VM",
                is_enabled=True,
                billing_tier="STANDARD",
            ),
        ])
        await urip_session.commit()
    
        urip_token = create_access_token(
            str(urip_user.id), urip_user.role, tenant_id=str(urip_tenant_uuid)
        )
        urip_h = {"Authorization": f"Bearer {urip_token}"}
    
        # ── 1) Trigger a deliberately-failing control on Compliance ────────────
        # CRIT-006 — control engine no longer accepts caller-supplied tenant_config.
        # The tenant admin must populate the server-side tenant_config table; the
        # rule engine reads ONLY from there. Seed mfa_enabled=False so the
        # mfa_enforced rule fails deterministically.
        compliance_session.add(
            TenantConfig(tenant_id=tenant_id, settings={"mfa_enabled": False})
        )
        await compliance_session.commit()
    
>       fail_resp = await compliance_client.post(
            f"/controls/{ctrl.id}/run",
            json={},
            headers=h,
        )

tests/e2e_cross_service/test_workflow_03_control_failure_to_risk.py:189: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1859: in post
    return await self.request(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1540: in request
    return await self.send(request, auth=auth, follow_redirects=follow_redirects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1629: in send
    response = await self._send_handling_auth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1657: in _send_handling_auth
    response = await self._send_handling_redirects(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1694: in _send_handling_redirects
    response = await self._send_single_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1730: in _send_single_request
    response = await transport.handle_async_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_transports/asgi.py:170: in handle_async_request
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/applications.py:1054: in __call__
    await super().__call__(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/applications.py:113: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:187: in __call__
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:165: in __call__
    await self.app(scope, receive, _send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:185: in __call__
    with collapse_excgroups():
/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/contextlib.py:162: in __exit__
    self.gen.throw(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_utils.py:82: in collapse_excgroups
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:187: in __call__
    response = await self.dispatch_func(request, call_next)
compliance/backend/compliance_backend/middleware/rate_limit.py:188: in dispatch
    return await call_next(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:163: in call_next
    raise app_exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:149: in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/cors.py:85: in __call__
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/exceptions.py:62: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:715: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:735: in app
    await route.handle(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:288: in handle
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:76: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:73: in app
    response = await f(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:301: in app
    raw_response = await run_endpoint_function(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:212: in run_endpoint_function
    return await dependant.call(**values)
compliance/backend/compliance_backend/routers/controls.py:167: in trigger_run
    await write_audit(
compliance/backend/compliance_backend/services/audit_writer.py:65: in write_audit
    await session.flush()  # assign id; flush within current transaction
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/ext/asyncio/session.py:787: in flush
    await greenlet_spawn(self.sync_session.flush, objects=objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/_concurrency_py3k.py:203: in greenlet_spawn
    result = context.switch(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4331: in flush
    self._flush(objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4466: in _flush
    with util.safe_reraise():
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4427: in _flush
    flush_context.execute()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:466: in execute
    rec.execute(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:642: in execute
    util.preloaded.orm_persistence.save_obj(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:93: in save_obj
    _emit_insert_statements(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:1233: in _emit_insert_statements
    result = connection.execute(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1419: in execute
    return meth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/elements.py:527: in _execute_on_connection
    return connection._execute_clauseelement(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1641: in _execute_clauseelement
    ret = self._execute_context(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1821: in _execute_context
    self._handle_dbapi_exception(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:2363: in _handle_dbapi_exception
    raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: in _execute_context
    context = constructor(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
E   sqlalchemy.exc.StatementError: (builtins.NameError) name 'timezone' is not defined
E   [SQL: INSERT INTO compliance_audit_logs (id, tenant_id, user_id, action, resource_type, resource_id, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)]
E   [parameters: [{'resource_type': 'control_run', 'tenant_id': 'xsvc-tenant', 'action': 'control_run_triggered', 'details_json': '{"control_id": "ee155218-1533-441f-95f2-280c05c7214f", "status": "fail", "audit_period": null}', 'resource_id': '316a46ac-d491-4126-9269-4a7b12dae172', 'user_id': 'test-user'}]]

compliance/backend/compliance_backend/models/compliance_audit_log.py:69: StatementError
----------------------------- Captured stderr call -----------------------------
2026-04-28 20:26:00,656 INFO compliance_backend.services.evidence_service — EvidenceService.capture_evidence: id=8033f092-31f7-4f5c-8651-34b04d160ab6 control=ee155218-1533-441f-95f2-280c05c7214f tenant=xsvc-tenant type=config sha256=2aff7b8771f360d03c475549cb5d5495220522eb8b2b80a92f185e03e3eabdbb
2026-04-28 20:26:00,657 INFO compliance_backend.services.control_engine — ControlEngine.run_control: id=316a46ac-d491-4126-9269-4a7b12dae172 control=ee155218-1533-441f-95f2-280c05c7214f tenant=xsvc-tenant status=fail
------------------------------ Captured log call -------------------------------
INFO     compliance_backend.services.evidence_service:evidence_service.py:206 EvidenceService.capture_evidence: id=8033f092-31f7-4f5c-8651-34b04d160ab6 control=ee155218-1533-441f-95f2-280c05c7214f tenant=xsvc-tenant type=config sha256=2aff7b8771f360d03c475549cb5d5495220522eb8b2b80a92f185e03e3eabdbb
INFO     compliance_backend.services.control_engine:control_engine.py:185 ControlEngine.run_control: id=316a46ac-d491-4126-9269-4a7b12dae172 control=ee155218-1533-441f-95f2-280c05c7214f tenant=xsvc-tenant status=fail
____________ test_workflow_04_risk_resolved_triggers_re_evaluation _____________

self = <sqlalchemy.engine.base.Connection object at 0x1121889b0>
dialect = <sqlalchemy.dialects.sqlite.aiosqlite.SQLiteDialect_aiosqlite object at 0x110635a90>
constructor = <bound method DefaultExecutionContext._init_compiled of <class 'sqlalchemy.dialects.sqlite.aiosqlite.SQLiteExecutionContext_aiosqlite'>>
statement = <sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x1121cd750>
parameters = [{'action': 'control_run_triggered', 'details_json': '{"control_id": "4d71d790-e8c5-49fa-a3d6-4ac5095d6b68", "status":...", "audit_period": null}', 'resource_id': '3bfbe03a-58e4-49dc-a78a-2723a4e33bb1', 'resource_type': 'control_run', ...}]
execution_options = immutabledict({'compiled_cache': <sqlalchemy.util._collections.LRUCache object at 0x11073b060>})
args = (<sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x1121cd750>, [{'action': 'control_run_triggered', 'details...-49dc-a78a-2723a4e33bb1', 'resource_type': 'control_run', ...}], <sqlalchemy.sql.dml.Insert object at 0x110798940>, [])
kw = {'cache_hit': <CacheStats.CACHE_MISS: 1>}, yp = None
conn = <sqlalchemy.pool.base._ConnectionFairy object at 0x111d2cf50>

    def _execute_context(
        self,
        dialect: Dialect,
        constructor: Callable[..., ExecutionContext],
        statement: Union[str, Compiled],
        parameters: Optional[_AnyMultiExecuteParams],
        execution_options: _ExecuteOptions,
        *args: Any,
        **kw: Any,
    ) -> CursorResult[Any]:
        """Create an :class:`.ExecutionContext` and execute, returning
        a :class:`_engine.CursorResult`."""
    
        if execution_options:
            yp = execution_options.get("yield_per", None)
            if yp:
                execution_options = execution_options.union(
                    {"stream_results": True, "max_row_buffer": yp}
                )
        try:
            conn = self._dbapi_connection
            if conn is None:
                conn = self._revalidate_connection()
    
>           context = constructor(
                dialect, self, conn, execution_options, *args, **kw
            )

/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
E   NameError: name 'timezone' is not defined

compliance/backend/compliance_backend/models/compliance_audit_log.py:69: NameError

The above exception was the direct cause of the following exception:

compliance_client = <httpx.AsyncClient object at 0x110b47c50>
compliance_session = <sqlalchemy.ext.asyncio.session.AsyncSession object at 0x11060de50>
urip_client = <httpx.AsyncClient object at 0x110b47950>
urip_session = <sqlalchemy.ext.asyncio.session.AsyncSession object at 0x110b16cf0>
make_compliance_jwt = <function make_compliance_jwt.<locals>._make at 0x110ad38a0>
event_bus = <tests.e2e_cross_service.conftest.DummyEventBus object at 0x110636490>

    @pytest.mark.asyncio
    async def test_workflow_04_risk_resolved_triggers_re_evaluation(
        compliance_client,
        compliance_session,
        urip_client,
        urip_session,
        make_compliance_jwt,
        event_bus,
    ):
        load_builtin_rules()
        tenant_id = "wf4-tenant"
        h_comp = _comp_admin_headers(make_compliance_jwt, tenant_id)
    
        # ── Compliance: framework + ONE control wired to mfa_enforced ──────────
        fw = Framework(
            id=str(uuid.uuid4()),
            name="WF4 FW",
            short_code=f"WF4{uuid.uuid4().hex[:4].upper()}",
            category="security",
        )
        fv = FrameworkVersion(
            id=str(uuid.uuid4()),
            framework_id=fw.id,
            version="2024",
            is_current=True,
        )
        ctrl = Control(
            id=str(uuid.uuid4()),
            framework_version_id=fv.id,
            control_code="WF4-CC",
            category="Access",
            description="MFA control under WF4",
            rule_function="mfa_enforced",
        )
        compliance_session.add_all([fw, fv, ctrl])
        await compliance_session.flush()
    
        # CRIT-006 — control engine no longer accepts caller-supplied tenant_config.
        # Seed mfa_enabled=False in the server-side tenant_config so the first
        # run deterministically fails. Later we'll update this row to flip to True.
        tenant_cfg = TenantConfig(tenant_id=tenant_id, settings={"mfa_enabled": False})
        compliance_session.add(tenant_cfg)
        await compliance_session.commit()
    
        # Make the control fail first → score = 0% so we can observe it climb.
>       bad_run = await compliance_client.post(
            f"/controls/{ctrl.id}/run",
            json={},
            headers=h_comp,
        )

tests/e2e_cross_service/test_workflow_04_risk_resolved_to_compliance.py:97: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1859: in post
    return await self.request(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1540: in request
    return await self.send(request, auth=auth, follow_redirects=follow_redirects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1629: in send
    response = await self._send_handling_auth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1657: in _send_handling_auth
    response = await self._send_handling_redirects(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1694: in _send_handling_redirects
    response = await self._send_single_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1730: in _send_single_request
    response = await transport.handle_async_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_transports/asgi.py:170: in handle_async_request
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/applications.py:1054: in __call__
    await super().__call__(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/applications.py:113: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:187: in __call__
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:165: in __call__
    await self.app(scope, receive, _send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:185: in __call__
    with collapse_excgroups():
/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/contextlib.py:162: in __exit__
    self.gen.throw(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_utils.py:82: in collapse_excgroups
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:187: in __call__
    response = await self.dispatch_func(request, call_next)
compliance/backend/compliance_backend/middleware/rate_limit.py:188: in dispatch
    return await call_next(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:163: in call_next
    raise app_exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:149: in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/cors.py:85: in __call__
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/exceptions.py:62: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:715: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:735: in app
    await route.handle(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:288: in handle
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:76: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:73: in app
    response = await f(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:301: in app
    raw_response = await run_endpoint_function(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:212: in run_endpoint_function
    return await dependant.call(**values)
compliance/backend/compliance_backend/routers/controls.py:167: in trigger_run
    await write_audit(
compliance/backend/compliance_backend/services/audit_writer.py:65: in write_audit
    await session.flush()  # assign id; flush within current transaction
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/ext/asyncio/session.py:787: in flush
    await greenlet_spawn(self.sync_session.flush, objects=objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/_concurrency_py3k.py:203: in greenlet_spawn
    result = context.switch(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4331: in flush
    self._flush(objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4466: in _flush
    with util.safe_reraise():
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4427: in _flush
    flush_context.execute()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:466: in execute
    rec.execute(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:642: in execute
    util.preloaded.orm_persistence.save_obj(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:93: in save_obj
    _emit_insert_statements(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:1233: in _emit_insert_statements
    result = connection.execute(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1419: in execute
    return meth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/elements.py:527: in _execute_on_connection
    return connection._execute_clauseelement(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1641: in _execute_clauseelement
    ret = self._execute_context(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1821: in _execute_context
    self._handle_dbapi_exception(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:2363: in _handle_dbapi_exception
    raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: in _execute_context
    context = constructor(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
E   sqlalchemy.exc.StatementError: (builtins.NameError) name 'timezone' is not defined
E   [SQL: INSERT INTO compliance_audit_logs (id, tenant_id, user_id, action, resource_type, resource_id, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)]
E   [parameters: [{'resource_type': 'control_run', 'tenant_id': 'wf4-tenant', 'action': 'control_run_triggered', 'details_json': '{"control_id": "4d71d790-e8c5-49fa-a3d6-4ac5095d6b68", "status": "fail", "audit_period": null}', 'resource_id': '3bfbe03a-58e4-49dc-a78a-2723a4e33bb1', 'user_id': 'test-user'}]]

compliance/backend/compliance_backend/models/compliance_audit_log.py:69: StatementError
----------------------------- Captured stderr call -----------------------------
2026-04-28 20:26:01,072 INFO compliance_backend.services.evidence_service — EvidenceService.capture_evidence: id=41aadf52-2dba-4a32-a527-992580e63e43 control=4d71d790-e8c5-49fa-a3d6-4ac5095d6b68 tenant=wf4-tenant type=config sha256=2aff7b8771f360d03c475549cb5d5495220522eb8b2b80a92f185e03e3eabdbb
2026-04-28 20:26:01,073 INFO compliance_backend.services.control_engine — ControlEngine.run_control: id=3bfbe03a-58e4-49dc-a78a-2723a4e33bb1 control=4d71d790-e8c5-49fa-a3d6-4ac5095d6b68 tenant=wf4-tenant status=fail
------------------------------ Captured log call -------------------------------
INFO     compliance_backend.services.evidence_service:evidence_service.py:206 EvidenceService.capture_evidence: id=41aadf52-2dba-4a32-a527-992580e63e43 control=4d71d790-e8c5-49fa-a3d6-4ac5095d6b68 tenant=wf4-tenant type=config sha256=2aff7b8771f360d03c475549cb5d5495220522eb8b2b80a92f185e03e3eabdbb
INFO     compliance_backend.services.control_engine:control_engine.py:185 ControlEngine.run_control: id=3bfbe03a-58e4-49dc-a78a-2723a4e33bb1 control=4d71d790-e8c5-49fa-a3d6-4ac5095d6b68 tenant=wf4-tenant status=fail
____________ test_workflow_05_policy_versioning_and_acknowledgments ____________

self = <sqlalchemy.engine.base.Connection object at 0x11060c320>
dialect = <sqlalchemy.dialects.sqlite.aiosqlite.SQLiteDialect_aiosqlite object at 0x110637750>
constructor = <bound method DefaultExecutionContext._init_compiled of <class 'sqlalchemy.dialects.sqlite.aiosqlite.SQLiteExecutionContext_aiosqlite'>>
statement = <sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x110542d50>
parameters = [{'current_version_id': None, 'expires_at': None, 'is_active': True, 'name': 'Acceptable Use Policy', ...}]
execution_options = immutabledict({'compiled_cache': <sqlalchemy.util._collections.LRUCache object at 0x11063b380>})
args = (<sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x110542d50>, [{'current_version_id': None, 'expires_at': None, 'is_active': True, 'name': 'Acceptable Use Policy', ...}], <sqlalchemy.sql.dml.Insert object at 0x11063d0d0>, [])
kw = {'cache_hit': <CacheStats.CACHE_MISS: 1>}, yp = None
conn = <sqlalchemy.pool.base._ConnectionFairy object at 0x11058d6d0>

    def _execute_context(
        self,
        dialect: Dialect,
        constructor: Callable[..., ExecutionContext],
        statement: Union[str, Compiled],
        parameters: Optional[_AnyMultiExecuteParams],
        execution_options: _ExecuteOptions,
        *args: Any,
        **kw: Any,
    ) -> CursorResult[Any]:
        """Create an :class:`.ExecutionContext` and execute, returning
        a :class:`_engine.CursorResult`."""
    
        if execution_options:
            yp = execution_options.get("yield_per", None)
            if yp:
                execution_options = execution_options.union(
                    {"stream_results": True, "max_row_buffer": yp}
                )
        try:
            conn = self._dbapi_connection
            if conn is None:
                conn = self._revalidate_connection()
    
>           context = constructor(
                dialect, self, conn, execution_options, *args, **kw
            )

/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
    )
E   NameError: name 'timezone' is not defined

compliance/backend/compliance_backend/models/policy.py:64: NameError

The above exception was the direct cause of the following exception:

compliance_client = <httpx.AsyncClient object at 0x110620950>
make_compliance_jwt = <function make_compliance_jwt.<locals>._make at 0x110777ab0>

    @pytest.mark.asyncio
    async def test_workflow_05_policy_versioning_and_acknowledgments(
        compliance_client, make_compliance_jwt
    ):
        tenant_id = "policy-tenant-e2e"
        admin_h = _admin_headers(make_compliance_jwt, tenant_id)
    
        # ── 1) Admin creates a policy with an initial v1 ───────────────────────
>       create_resp = await compliance_client.post(
            "/policies",
            json={
                "name": "Acceptable Use Policy",
                "content": "v1 — be reasonable.",
            },
            headers=admin_h,
        )

tests/e2e_cross_service/test_workflow_05_policy_lifecycle.py:45: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1859: in post
    return await self.request(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1540: in request
    return await self.send(request, auth=auth, follow_redirects=follow_redirects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1629: in send
    response = await self._send_handling_auth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1657: in _send_handling_auth
    response = await self._send_handling_redirects(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1694: in _send_handling_redirects
    response = await self._send_single_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1730: in _send_single_request
    response = await transport.handle_async_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_transports/asgi.py:170: in handle_async_request
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/applications.py:1054: in __call__
    await super().__call__(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/applications.py:113: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:187: in __call__
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:165: in __call__
    await self.app(scope, receive, _send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:185: in __call__
    with collapse_excgroups():
/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/contextlib.py:162: in __exit__
    self.gen.throw(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_utils.py:82: in collapse_excgroups
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:187: in __call__
    response = await self.dispatch_func(request, call_next)
compliance/backend/compliance_backend/middleware/rate_limit.py:188: in dispatch
    return await call_next(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:163: in call_next
    raise app_exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:149: in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/cors.py:85: in __call__
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/exceptions.py:62: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:715: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:735: in app
    await route.handle(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:288: in handle
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:76: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:73: in app
    response = await f(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:301: in app
    raw_response = await run_endpoint_function(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:212: in run_endpoint_function
    return await dependant.call(**values)
compliance/backend/compliance_backend/routers/policies.py:140: in create_policy
    policy = await policy_manager.create_policy(
compliance/backend/compliance_backend/services/policy_manager.py:114: in create_policy
    await session.flush()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/ext/asyncio/session.py:787: in flush
    await greenlet_spawn(self.sync_session.flush, objects=objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/_concurrency_py3k.py:203: in greenlet_spawn
    result = context.switch(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4331: in flush
    self._flush(objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4466: in _flush
    with util.safe_reraise():
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4427: in _flush
    flush_context.execute()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:466: in execute
    rec.execute(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:642: in execute
    util.preloaded.orm_persistence.save_obj(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:93: in save_obj
    _emit_insert_statements(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:1233: in _emit_insert_statements
    result = connection.execute(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1419: in execute
    return meth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/elements.py:527: in _execute_on_connection
    return connection._execute_clauseelement(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1641: in _execute_clauseelement
    ret = self._execute_context(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1821: in _execute_context
    self._handle_dbapi_exception(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:2363: in _handle_dbapi_exception
    raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: in _execute_context
    context = constructor(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
    )
E   sqlalchemy.exc.StatementError: (builtins.NameError) name 'timezone' is not defined
E   [SQL: INSERT INTO policies (id, tenant_id, name, owner_user_id, current_version_id, expires_at, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)]
E   [parameters: [{'tenant_id': 'policy-tenant-e2e', 'owner_user_id': 'test-user', 'name': 'Acceptable Use Policy', 'is_active': True, 'current_version_id': None, 'expires_at': None}]]

compliance/backend/compliance_backend/models/policy.py:64: StatementError
__________________ test_workflow_05_expiring_policy_surfaced ___________________

self = <sqlalchemy.engine.base.Connection object at 0x10ec4b2f0>
dialect = <sqlalchemy.dialects.sqlite.aiosqlite.SQLiteDialect_aiosqlite object at 0x110634550>
constructor = <bound method DefaultExecutionContext._init_compiled of <class 'sqlalchemy.dialects.sqlite.aiosqlite.SQLiteExecutionContext_aiosqlite'>>
statement = <sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x10fe7b950>
parameters = [{'current_version_id': None, 'expires_at': datetime.datetime(2026, 5, 12, 14, 56, 1, 746610, tzinfo=datetime.timezone.utc), 'is_active': True, 'name': 'Soon-to-Expire Policy', ...}]
execution_options = immutabledict({'compiled_cache': <sqlalchemy.util._collections.LRUCache object at 0x11063b380>})
args = (<sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x10fe7b950>, [{'current_version_id': None, 'expires_at': d...utc), 'is_active': True, 'name': 'Soon-to-Expire Policy', ...}], <sqlalchemy.sql.dml.Insert object at 0x11063d0d0>, [])
kw = {'cache_hit': <CacheStats.CACHE_MISS: 1>}, yp = None
conn = <sqlalchemy.pool.base._ConnectionFairy object at 0x11058ee90>

    def _execute_context(
        self,
        dialect: Dialect,
        constructor: Callable[..., ExecutionContext],
        statement: Union[str, Compiled],
        parameters: Optional[_AnyMultiExecuteParams],
        execution_options: _ExecuteOptions,
        *args: Any,
        **kw: Any,
    ) -> CursorResult[Any]:
        """Create an :class:`.ExecutionContext` and execute, returning
        a :class:`_engine.CursorResult`."""
    
        if execution_options:
            yp = execution_options.get("yield_per", None)
            if yp:
                execution_options = execution_options.union(
                    {"stream_results": True, "max_row_buffer": yp}
                )
        try:
            conn = self._dbapi_connection
            if conn is None:
                conn = self._revalidate_connection()
    
>           context = constructor(
                dialect, self, conn, execution_options, *args, **kw
            )

/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
    )
E   NameError: name 'timezone' is not defined

compliance/backend/compliance_backend/models/policy.py:64: NameError

The above exception was the direct cause of the following exception:

compliance_client = <httpx.AsyncClient object at 0x1105cf710>
make_compliance_jwt = <function make_compliance_jwt.<locals>._make at 0x11073fe20>

    @pytest.mark.asyncio
    async def test_workflow_05_expiring_policy_surfaced(
        compliance_client, make_compliance_jwt
    ):
        tenant_id = "policy-expiry-tenant"
        admin_h = _admin_headers(make_compliance_jwt, tenant_id)
    
        # Policy that expires in 14 days (< 30-day window)
        soon = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
>       create = await compliance_client.post(
            "/policies",
            json={
                "name": "Soon-to-Expire Policy",
                "content": "Will expire shortly",
                "expires_at": soon,
            },
            headers=admin_h,
        )

tests/e2e_cross_service/test_workflow_05_policy_lifecycle.py:147: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1859: in post
    return await self.request(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1540: in request
    return await self.send(request, auth=auth, follow_redirects=follow_redirects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1629: in send
    response = await self._send_handling_auth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1657: in _send_handling_auth
    response = await self._send_handling_redirects(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1694: in _send_handling_redirects
    response = await self._send_single_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1730: in _send_single_request
    response = await transport.handle_async_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_transports/asgi.py:170: in handle_async_request
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/applications.py:1054: in __call__
    await super().__call__(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/applications.py:113: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:187: in __call__
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:165: in __call__
    await self.app(scope, receive, _send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:185: in __call__
    with collapse_excgroups():
/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/contextlib.py:162: in __exit__
    self.gen.throw(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_utils.py:82: in collapse_excgroups
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:187: in __call__
    response = await self.dispatch_func(request, call_next)
compliance/backend/compliance_backend/middleware/rate_limit.py:188: in dispatch
    return await call_next(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:163: in call_next
    raise app_exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:149: in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/cors.py:85: in __call__
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/exceptions.py:62: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:715: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:735: in app
    await route.handle(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:288: in handle
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:76: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:73: in app
    response = await f(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:301: in app
    raw_response = await run_endpoint_function(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:212: in run_endpoint_function
    return await dependant.call(**values)
compliance/backend/compliance_backend/routers/policies.py:140: in create_policy
    policy = await policy_manager.create_policy(
compliance/backend/compliance_backend/services/policy_manager.py:114: in create_policy
    await session.flush()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/ext/asyncio/session.py:787: in flush
    await greenlet_spawn(self.sync_session.flush, objects=objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/_concurrency_py3k.py:203: in greenlet_spawn
    result = context.switch(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4331: in flush
    self._flush(objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4466: in _flush
    with util.safe_reraise():
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4427: in _flush
    flush_context.execute()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:466: in execute
    rec.execute(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:642: in execute
    util.preloaded.orm_persistence.save_obj(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:93: in save_obj
    _emit_insert_statements(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:1233: in _emit_insert_statements
    result = connection.execute(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1419: in execute
    return meth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/elements.py:527: in _execute_on_connection
    return connection._execute_clauseelement(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1641: in _execute_clauseelement
    ret = self._execute_context(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1821: in _execute_context
    self._handle_dbapi_exception(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:2363: in _handle_dbapi_exception
    raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: in _execute_context
    context = constructor(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
    )
E   sqlalchemy.exc.StatementError: (builtins.NameError) name 'timezone' is not defined
E   [SQL: INSERT INTO policies (id, tenant_id, name, owner_user_id, current_version_id, expires_at, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)]
E   [parameters: [{'tenant_id': 'policy-expiry-tenant', 'owner_user_id': 'test-user', 'expires_at': datetime.datetime(2026, 5, 12, 14, 56, 1, 746610, tzinfo=datetime.timezone.utc), 'name': 'Soon-to-Expire Policy', 'is_active': True, 'current_version_id': None}]]

compliance/backend/compliance_backend/models/policy.py:64: StatementError
______________ test_workflow_05_policy_isolation_between_tenants _______________

self = <sqlalchemy.engine.base.Connection object at 0x10e9c7f20>
dialect = <sqlalchemy.dialects.sqlite.aiosqlite.SQLiteDialect_aiosqlite object at 0x110634050>
constructor = <bound method DefaultExecutionContext._init_compiled of <class 'sqlalchemy.dialects.sqlite.aiosqlite.SQLiteExecutionContext_aiosqlite'>>
statement = <sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x1102d2f50>
parameters = [{'current_version_id': None, 'expires_at': None, 'is_active': True, 'name': 'X policy', ...}]
execution_options = immutabledict({'compiled_cache': <sqlalchemy.util._collections.LRUCache object at 0x11063b380>})
args = (<sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x1102d2f50>, [{'current_version_id': None, 'expires_at': None, 'is_active': True, 'name': 'X policy', ...}], <sqlalchemy.sql.dml.Insert object at 0x11063d0d0>, [])
kw = {'cache_hit': <CacheStats.CACHE_MISS: 1>}, yp = None
conn = <sqlalchemy.pool.base._ConnectionFairy object at 0x11058d590>

    def _execute_context(
        self,
        dialect: Dialect,
        constructor: Callable[..., ExecutionContext],
        statement: Union[str, Compiled],
        parameters: Optional[_AnyMultiExecuteParams],
        execution_options: _ExecuteOptions,
        *args: Any,
        **kw: Any,
    ) -> CursorResult[Any]:
        """Create an :class:`.ExecutionContext` and execute, returning
        a :class:`_engine.CursorResult`."""
    
        if execution_options:
            yp = execution_options.get("yield_per", None)
            if yp:
                execution_options = execution_options.union(
                    {"stream_results": True, "max_row_buffer": yp}
                )
        try:
            conn = self._dbapi_connection
            if conn is None:
                conn = self._revalidate_connection()
    
>           context = constructor(
                dialect, self, conn, execution_options, *args, **kw
            )

/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
    )
E   NameError: name 'timezone' is not defined

compliance/backend/compliance_backend/models/policy.py:64: NameError

The above exception was the direct cause of the following exception:

compliance_client = <httpx.AsyncClient object at 0x1105ccf50>
make_compliance_jwt = <function make_compliance_jwt.<locals>._make at 0x11061b480>

    @pytest.mark.asyncio
    async def test_workflow_05_policy_isolation_between_tenants(
        compliance_client, make_compliance_jwt
    ):
        """A policy created by tenant X must not appear in tenant Y's lists."""
        admin_x = _admin_headers(make_compliance_jwt, "policy-iso-x")
        admin_y = _admin_headers(make_compliance_jwt, "policy-iso-y")
    
>       create_x = await compliance_client.post(
            "/policies",
            json={"name": "X policy", "content": "x"},
            headers=admin_x,
        )

tests/e2e_cross_service/test_workflow_05_policy_lifecycle.py:193: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1859: in post
    return await self.request(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1540: in request
    return await self.send(request, auth=auth, follow_redirects=follow_redirects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1629: in send
    response = await self._send_handling_auth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1657: in _send_handling_auth
    response = await self._send_handling_redirects(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1694: in _send_handling_redirects
    response = await self._send_single_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1730: in _send_single_request
    response = await transport.handle_async_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_transports/asgi.py:170: in handle_async_request
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/applications.py:1054: in __call__
    await super().__call__(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/applications.py:113: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:187: in __call__
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:165: in __call__
    await self.app(scope, receive, _send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:185: in __call__
    with collapse_excgroups():
/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/contextlib.py:162: in __exit__
    self.gen.throw(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_utils.py:82: in collapse_excgroups
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:187: in __call__
    response = await self.dispatch_func(request, call_next)
compliance/backend/compliance_backend/middleware/rate_limit.py:188: in dispatch
    return await call_next(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:163: in call_next
    raise app_exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:149: in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/cors.py:85: in __call__
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/exceptions.py:62: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:715: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:735: in app
    await route.handle(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:288: in handle
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:76: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:73: in app
    response = await f(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:301: in app
    raw_response = await run_endpoint_function(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:212: in run_endpoint_function
    return await dependant.call(**values)
compliance/backend/compliance_backend/routers/policies.py:140: in create_policy
    policy = await policy_manager.create_policy(
compliance/backend/compliance_backend/services/policy_manager.py:114: in create_policy
    await session.flush()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/ext/asyncio/session.py:787: in flush
    await greenlet_spawn(self.sync_session.flush, objects=objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/_concurrency_py3k.py:203: in greenlet_spawn
    result = context.switch(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4331: in flush
    self._flush(objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4466: in _flush
    with util.safe_reraise():
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4427: in _flush
    flush_context.execute()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:466: in execute
    rec.execute(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:642: in execute
    util.preloaded.orm_persistence.save_obj(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:93: in save_obj
    _emit_insert_statements(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:1233: in _emit_insert_statements
    result = connection.execute(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1419: in execute
    return meth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/elements.py:527: in _execute_on_connection
    return connection._execute_clauseelement(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1641: in _execute_clauseelement
    ret = self._execute_context(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1821: in _execute_context
    self._handle_dbapi_exception(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:2363: in _handle_dbapi_exception
    raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: in _execute_context
    context = constructor(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
    )
E   sqlalchemy.exc.StatementError: (builtins.NameError) name 'timezone' is not defined
E   [SQL: INSERT INTO policies (id, tenant_id, name, owner_user_id, current_version_id, expires_at, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)]
E   [parameters: [{'tenant_id': 'policy-iso-x', 'owner_user_id': 'test-user', 'name': 'X policy', 'is_active': True, 'current_version_id': None, 'expires_at': None}]]

compliance/backend/compliance_backend/models/policy.py:64: StatementError
_________________ test_workflow_06_vendor_risk_full_lifecycle __________________

self = <sqlalchemy.engine.base.Connection object at 0x10efe14f0>
dialect = <sqlalchemy.dialects.sqlite.aiosqlite.SQLiteDialect_aiosqlite object at 0x1105b9090>
constructor = <bound method DefaultExecutionContext._init_compiled of <class 'sqlalchemy.dialects.sqlite.aiosqlite.SQLiteExecutionContext_aiosqlite'>>
statement = <sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x10fb9ad50>
parameters = [{'action': 'vendor_created', 'details_json': '{"name": "AcmeCloud Provider", "criticality": "critical"}', 'resource_id': 'fc250eda-ed34-4967-a217-84879c3068d8', 'resource_type': 'vendor', ...}]
execution_options = immutabledict({'compiled_cache': <sqlalchemy.util._collections.LRUCache object at 0x11073b060>})
args = (<sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x10fb9ad50>, [{'action': 'vendor_created', 'details_json':...-ed34-4967-a217-84879c3068d8', 'resource_type': 'vendor', ...}], <sqlalchemy.sql.dml.Insert object at 0x110798940>, [])
kw = {'cache_hit': <CacheStats.CACHE_MISS: 1>}, yp = None
conn = <sqlalchemy.pool.base._ConnectionFairy object at 0x1105051d0>

    def _execute_context(
        self,
        dialect: Dialect,
        constructor: Callable[..., ExecutionContext],
        statement: Union[str, Compiled],
        parameters: Optional[_AnyMultiExecuteParams],
        execution_options: _ExecuteOptions,
        *args: Any,
        **kw: Any,
    ) -> CursorResult[Any]:
        """Create an :class:`.ExecutionContext` and execute, returning
        a :class:`_engine.CursorResult`."""
    
        if execution_options:
            yp = execution_options.get("yield_per", None)
            if yp:
                execution_options = execution_options.union(
                    {"stream_results": True, "max_row_buffer": yp}
                )
        try:
            conn = self._dbapi_connection
            if conn is None:
                conn = self._revalidate_connection()
    
>           context = constructor(
                dialect, self, conn, execution_options, *args, **kw
            )

/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
E   NameError: name 'timezone' is not defined

compliance/backend/compliance_backend/models/compliance_audit_log.py:69: NameError

The above exception was the direct cause of the following exception:

compliance_client = <httpx.AsyncClient object at 0x1104dcc50>
compliance_session = <sqlalchemy.ext.asyncio.session.AsyncSession object at 0x1104df350>
make_compliance_jwt = <function make_compliance_jwt.<locals>._make at 0x1105b52d0>

    @pytest.mark.asyncio
    async def test_workflow_06_vendor_risk_full_lifecycle(
        compliance_client, compliance_session, make_compliance_jwt
    ):
        tenant_id = "vendor-tenant-e2e"
        h = _admin_headers(make_compliance_jwt, tenant_id)
    
        # ── 1) Register a critical vendor ──────────────────────────────────────
>       create = await compliance_client.post(
            "/vendors",
            json={
                "name": "AcmeCloud Provider",
                "criticality": "critical",
                "contact_email": "trust@acmecloud.test",
                "contact_name": "Acme Trust Office",
            },
            headers=h,
        )

tests/e2e_cross_service/test_workflow_06_vendor_risk_lifecycle.py:37: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1859: in post
    return await self.request(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1540: in request
    return await self.send(request, auth=auth, follow_redirects=follow_redirects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1629: in send
    response = await self._send_handling_auth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1657: in _send_handling_auth
    response = await self._send_handling_redirects(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1694: in _send_handling_redirects
    response = await self._send_single_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1730: in _send_single_request
    response = await transport.handle_async_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_transports/asgi.py:170: in handle_async_request
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/applications.py:1054: in __call__
    await super().__call__(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/applications.py:113: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:187: in __call__
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:165: in __call__
    await self.app(scope, receive, _send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:185: in __call__
    with collapse_excgroups():
/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/contextlib.py:162: in __exit__
    self.gen.throw(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_utils.py:82: in collapse_excgroups
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:187: in __call__
    response = await self.dispatch_func(request, call_next)
compliance/backend/compliance_backend/middleware/rate_limit.py:188: in dispatch
    return await call_next(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:163: in call_next
    raise app_exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:149: in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/cors.py:85: in __call__
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/exceptions.py:62: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:715: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:735: in app
    await route.handle(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:288: in handle
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:76: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:73: in app
    response = await f(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:301: in app
    raw_response = await run_endpoint_function(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:212: in run_endpoint_function
    return await dependant.call(**values)
compliance/backend/compliance_backend/routers/vendors.py:168: in create_vendor
    await write_audit(
compliance/backend/compliance_backend/services/audit_writer.py:65: in write_audit
    await session.flush()  # assign id; flush within current transaction
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/ext/asyncio/session.py:787: in flush
    await greenlet_spawn(self.sync_session.flush, objects=objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/_concurrency_py3k.py:203: in greenlet_spawn
    result = context.switch(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4331: in flush
    self._flush(objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4466: in _flush
    with util.safe_reraise():
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4427: in _flush
    flush_context.execute()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:466: in execute
    rec.execute(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:642: in execute
    util.preloaded.orm_persistence.save_obj(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:93: in save_obj
    _emit_insert_statements(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:1233: in _emit_insert_statements
    result = connection.execute(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1419: in execute
    return meth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/elements.py:527: in _execute_on_connection
    return connection._execute_clauseelement(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1641: in _execute_clauseelement
    ret = self._execute_context(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1821: in _execute_context
    self._handle_dbapi_exception(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:2363: in _handle_dbapi_exception
    raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: in _execute_context
    context = constructor(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
E   sqlalchemy.exc.StatementError: (builtins.NameError) name 'timezone' is not defined
E   [SQL: INSERT INTO compliance_audit_logs (id, tenant_id, user_id, action, resource_type, resource_id, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)]
E   [parameters: [{'resource_type': 'vendor', 'tenant_id': 'vendor-tenant-e2e', 'action': 'vendor_created', 'details_json': '{"name": "AcmeCloud Provider", "criticality": "critical"}', 'resource_id': 'fc250eda-ed34-4967-a217-84879c3068d8', 'user_id': 'test-user'}]]

compliance/backend/compliance_backend/models/compliance_audit_log.py:69: StatementError
______________________ test_workflow_06_vendor_isolation _______________________

self = <sqlalchemy.engine.base.Connection object at 0x10eaa5c70>
dialect = <sqlalchemy.dialects.sqlite.aiosqlite.SQLiteDialect_aiosqlite object at 0x110636490>
constructor = <bound method DefaultExecutionContext._init_compiled of <class 'sqlalchemy.dialects.sqlite.aiosqlite.SQLiteExecutionContext_aiosqlite'>>
statement = <sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x11074da50>
parameters = [{'action': 'vendor_created', 'details_json': '{"name": "X-Vendor", "criticality": "high"}', 'resource_id': '68ec7f5d-7e3e-4d7f-b531-ae56598b5af1', 'resource_type': 'vendor', ...}]
execution_options = immutabledict({'compiled_cache': <sqlalchemy.util._collections.LRUCache object at 0x11073b060>})
args = (<sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x11074da50>, [{'action': 'vendor_created', 'details_json':...-7e3e-4d7f-b531-ae56598b5af1', 'resource_type': 'vendor', ...}], <sqlalchemy.sql.dml.Insert object at 0x110798940>, [])
kw = {'cache_hit': <CacheStats.CACHE_MISS: 1>}, yp = None
conn = <sqlalchemy.pool.base._ConnectionFairy object at 0x11058e3f0>

    def _execute_context(
        self,
        dialect: Dialect,
        constructor: Callable[..., ExecutionContext],
        statement: Union[str, Compiled],
        parameters: Optional[_AnyMultiExecuteParams],
        execution_options: _ExecuteOptions,
        *args: Any,
        **kw: Any,
    ) -> CursorResult[Any]:
        """Create an :class:`.ExecutionContext` and execute, returning
        a :class:`_engine.CursorResult`."""
    
        if execution_options:
            yp = execution_options.get("yield_per", None)
            if yp:
                execution_options = execution_options.union(
                    {"stream_results": True, "max_row_buffer": yp}
                )
        try:
            conn = self._dbapi_connection
            if conn is None:
                conn = self._revalidate_connection()
    
>           context = constructor(
                dialect, self, conn, execution_options, *args, **kw
            )

/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
E   NameError: name 'timezone' is not defined

compliance/backend/compliance_backend/models/compliance_audit_log.py:69: NameError

The above exception was the direct cause of the following exception:

compliance_client = <httpx.AsyncClient object at 0x1105cea50>
make_compliance_jwt = <function make_compliance_jwt.<locals>._make at 0x110ad38a0>

    @pytest.mark.asyncio
    async def test_workflow_06_vendor_isolation(
        compliance_client, make_compliance_jwt
    ):
        """Vendors and their documents/questionnaires are tenant-isolated."""
        h_x = _admin_headers(make_compliance_jwt, "vendor-x")
        h_y = _admin_headers(make_compliance_jwt, "vendor-y")
    
        # X creates a vendor
>       create_x = await compliance_client.post(
            "/vendors",
            json={"name": "X-Vendor", "criticality": "high"},
            headers=h_x,
        )

tests/e2e_cross_service/test_workflow_06_vendor_risk_lifecycle.py:158: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1859: in post
    return await self.request(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1540: in request
    return await self.send(request, auth=auth, follow_redirects=follow_redirects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1629: in send
    response = await self._send_handling_auth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1657: in _send_handling_auth
    response = await self._send_handling_redirects(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1694: in _send_handling_redirects
    response = await self._send_single_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1730: in _send_single_request
    response = await transport.handle_async_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_transports/asgi.py:170: in handle_async_request
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/applications.py:1054: in __call__
    await super().__call__(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/applications.py:113: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:187: in __call__
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:165: in __call__
    await self.app(scope, receive, _send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:185: in __call__
    with collapse_excgroups():
/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/contextlib.py:162: in __exit__
    self.gen.throw(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_utils.py:82: in collapse_excgroups
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:187: in __call__
    response = await self.dispatch_func(request, call_next)
compliance/backend/compliance_backend/middleware/rate_limit.py:188: in dispatch
    return await call_next(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:163: in call_next
    raise app_exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:149: in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/cors.py:85: in __call__
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/exceptions.py:62: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:715: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:735: in app
    await route.handle(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:288: in handle
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:76: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:73: in app
    response = await f(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:301: in app
    raw_response = await run_endpoint_function(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:212: in run_endpoint_function
    return await dependant.call(**values)
compliance/backend/compliance_backend/routers/vendors.py:168: in create_vendor
    await write_audit(
compliance/backend/compliance_backend/services/audit_writer.py:65: in write_audit
    await session.flush()  # assign id; flush within current transaction
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/ext/asyncio/session.py:787: in flush
    await greenlet_spawn(self.sync_session.flush, objects=objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/_concurrency_py3k.py:203: in greenlet_spawn
    result = context.switch(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4331: in flush
    self._flush(objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4466: in _flush
    with util.safe_reraise():
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4427: in _flush
    flush_context.execute()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:466: in execute
    rec.execute(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:642: in execute
    util.preloaded.orm_persistence.save_obj(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:93: in save_obj
    _emit_insert_statements(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:1233: in _emit_insert_statements
    result = connection.execute(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1419: in execute
    return meth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/elements.py:527: in _execute_on_connection
    return connection._execute_clauseelement(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1641: in _execute_clauseelement
    ret = self._execute_context(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1821: in _execute_context
    self._handle_dbapi_exception(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:2363: in _handle_dbapi_exception
    raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: in _execute_context
    context = constructor(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
E   sqlalchemy.exc.StatementError: (builtins.NameError) name 'timezone' is not defined
E   [SQL: INSERT INTO compliance_audit_logs (id, tenant_id, user_id, action, resource_type, resource_id, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)]
E   [parameters: [{'resource_type': 'vendor', 'tenant_id': 'vendor-x', 'action': 'vendor_created', 'details_json': '{"name": "X-Vendor", "criticality": "high"}', 'resource_id': '68ec7f5d-7e3e-4d7f-b531-ae56598b5af1', 'user_id': 'test-user'}]]

compliance/backend/compliance_backend/models/compliance_audit_log.py:69: StatementError
__________________ test_workflow_07_auditor_portal_full_cycle __________________

self = <sqlalchemy.engine.base.Connection object at 0x11060d6d0>
dialect = <sqlalchemy.dialects.sqlite.aiosqlite.SQLiteDialect_aiosqlite object at 0x110634b90>
constructor = <bound method DefaultExecutionContext._init_compiled of <class 'sqlalchemy.dialects.sqlite.aiosqlite.SQLiteExecutionContext_aiosqlite'>>
statement = <sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x1102d2d50>
parameters = [{'action': 'auditor_invitation_created', 'details_json': '{"auditor_email": "external-auditor@audit.example.com", "fr...15:01:03.052112"}', 'resource_id': '336c2b8b-ab79-4adc-bea4-4d3471bce574', 'resource_type': 'auditor_invitation', ...}]
execution_options = immutabledict({'compiled_cache': <sqlalchemy.util._collections.LRUCache object at 0x11073b060>})
args = (<sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x1102d2d50>, [{'action': 'auditor_invitation_created', 'de...ea4-4d3471bce574', 'resource_type': 'auditor_invitation', ...}], <sqlalchemy.sql.dml.Insert object at 0x110798940>, [])
kw = {'cache_hit': <CacheStats.CACHE_MISS: 1>}, yp = None
conn = <sqlalchemy.pool.base._ConnectionFairy object at 0x11058fcf0>

    def _execute_context(
        self,
        dialect: Dialect,
        constructor: Callable[..., ExecutionContext],
        statement: Union[str, Compiled],
        parameters: Optional[_AnyMultiExecuteParams],
        execution_options: _ExecuteOptions,
        *args: Any,
        **kw: Any,
    ) -> CursorResult[Any]:
        """Create an :class:`.ExecutionContext` and execute, returning
        a :class:`_engine.CursorResult`."""
    
        if execution_options:
            yp = execution_options.get("yield_per", None)
            if yp:
                execution_options = execution_options.union(
                    {"stream_results": True, "max_row_buffer": yp}
                )
        try:
            conn = self._dbapi_connection
            if conn is None:
                conn = self._revalidate_connection()
    
>           context = constructor(
                dialect, self, conn, execution_options, *args, **kw
            )

/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
E   NameError: name 'timezone' is not defined

compliance/backend/compliance_backend/models/compliance_audit_log.py:69: NameError

The above exception was the direct cause of the following exception:

compliance_client = <httpx.AsyncClient object at 0x11046cd10>
compliance_session = <sqlalchemy.ext.asyncio.session.AsyncSession object at 0x110776a40>
make_compliance_jwt = <function make_compliance_jwt.<locals>._make at 0x1105f4880>

    @pytest.mark.asyncio
    async def test_workflow_07_auditor_portal_full_cycle(
        compliance_client, compliance_session, make_compliance_jwt
    ):
        tenant_id = "auditor-tenant-e2e"
        h_admin = _admin_headers(make_compliance_jwt, tenant_id)
    
        # ── 1) Seed a framework + control + one auto-collected evidence row ───
        fw = Framework(
            id=str(uuid.uuid4()),
            name="SOC 2 (E2E)",
            short_code=f"SOC2E2E{uuid.uuid4().hex[:4].upper()}",
            category="security",
        )
        fv = FrameworkVersion(
            id=str(uuid.uuid4()),
            framework_id=fw.id,
            version="2017",
            is_current=True,
        )
        ctrl = Control(
            id=str(uuid.uuid4()),
            framework_version_id=fv.id,
            control_code=f"CC-{uuid.uuid4().hex[:4].upper()}",
            category="Access",
            title="Logical Access Controls",
            description="MFA enforced for all users.",
            rule_function="mfa_enforced",
        )
        compliance_session.add_all([fw, fv, ctrl])
        await compliance_session.flush()
    
        # Audit period — bounded with a comfortable cushion to absorb the
        # naive-vs-aware datetime conversion bug in
        # compliance_backend/services/auditor_service.py:_mint_auditor_jwt
        # (it does `int(access.expires_at.timestamp())` on a naive utcnow-derived
        # datetime, which on a non-UTC host produces an exp value offset by the
        # local TZ).  Picking +2 days handles any reasonable TZ.
        period_start = datetime.utcnow() - timedelta(days=1)
        period_end = datetime.utcnow() + timedelta(days=2)
    
        # An auto-collected evidence row inside the audit period
        pre_evidence = Evidence(
            id=str(uuid.uuid4()),
            control_id=ctrl.id,
            framework_id=fw.id,
            tenant_id=tenant_id,
            type="config",
            storage_uri="memory://noop",
            audit_period="Q4-2025",
            captured_at=datetime.utcnow(),
            captured_by="auto-collector",
            metadata_json={"source": "seed"},
        )
        compliance_session.add(pre_evidence)
        await compliance_session.flush()
    
        # ── 2) Admin creates an auditor invitation ─────────────────────────────
        expires = period_end + timedelta(minutes=5)
>       invite = await compliance_client.post(
            "/auditor-invitations",
            json={
                "auditor_email": "external-auditor@audit.example.com",
                "framework_id": fw.id,
                "audit_period_start": period_start.isoformat(),
                "audit_period_end": period_end.isoformat(),
                "expires_at": expires.isoformat(),
            },
            headers=h_admin,
        )

tests/e2e_cross_service/test_workflow_07_auditor_portal.py:100: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1859: in post
    return await self.request(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1540: in request
    return await self.send(request, auth=auth, follow_redirects=follow_redirects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1629: in send
    response = await self._send_handling_auth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1657: in _send_handling_auth
    response = await self._send_handling_redirects(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1694: in _send_handling_redirects
    response = await self._send_single_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1730: in _send_single_request
    response = await transport.handle_async_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_transports/asgi.py:170: in handle_async_request
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/applications.py:1054: in __call__
    await super().__call__(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/applications.py:113: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:187: in __call__
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:165: in __call__
    await self.app(scope, receive, _send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:185: in __call__
    with collapse_excgroups():
/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/contextlib.py:162: in __exit__
    self.gen.throw(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_utils.py:82: in collapse_excgroups
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:187: in __call__
    response = await self.dispatch_func(request, call_next)
compliance/backend/compliance_backend/middleware/rate_limit.py:188: in dispatch
    return await call_next(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:163: in call_next
    raise app_exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:149: in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/cors.py:85: in __call__
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/exceptions.py:62: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:715: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:735: in app
    await route.handle(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:288: in handle
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:76: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:73: in app
    response = await f(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:301: in app
    raw_response = await run_endpoint_function(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:212: in run_endpoint_function
    return await dependant.call(**values)
compliance/backend/compliance_backend/routers/auditor_invitations.py:151: in create_invitation
    await write_audit(
compliance/backend/compliance_backend/services/audit_writer.py:65: in write_audit
    await session.flush()  # assign id; flush within current transaction
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/ext/asyncio/session.py:787: in flush
    await greenlet_spawn(self.sync_session.flush, objects=objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/_concurrency_py3k.py:203: in greenlet_spawn
    result = context.switch(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4331: in flush
    self._flush(objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4466: in _flush
    with util.safe_reraise():
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4427: in _flush
    flush_context.execute()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:466: in execute
    rec.execute(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:642: in execute
    util.preloaded.orm_persistence.save_obj(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:93: in save_obj
    _emit_insert_statements(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:1233: in _emit_insert_statements
    result = connection.execute(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1419: in execute
    return meth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/elements.py:527: in _execute_on_connection
    return connection._execute_clauseelement(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1641: in _execute_clauseelement
    ret = self._execute_context(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1821: in _execute_context
    self._handle_dbapi_exception(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:2363: in _handle_dbapi_exception
    raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: in _execute_context
    context = constructor(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
E   sqlalchemy.exc.StatementError: (builtins.NameError) name 'timezone' is not defined
E   [SQL: INSERT INTO compliance_audit_logs (id, tenant_id, user_id, action, resource_type, resource_id, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)]
E   [parameters: [{'resource_type': 'auditor_invitation', 'tenant_id': 'auditor-tenant-e2e', 'action': 'auditor_invitation_created', 'details_json': '{"auditor_email":  ... (68 characters truncated) ... -4592-a9f1-a9dcc0218b64", "expires_at": "2026-04-30T15:01:03.052112"}', 'resource_id': '336c2b8b-ab79-4adc-bea4-4d3471bce574', 'user_id': 'test-user'}]]

compliance/backend/compliance_backend/models/compliance_audit_log.py:69: StatementError
----------------------------- Captured stderr call -----------------------------
2026-04-28 20:26:03,057 INFO compliance_backend.services.auditor_service — AuditorService.create_invitation: id=336c2b8b-ab79-4adc-bea4-4d3471bce574 tenant=auditor-tenant-e2e email=external-auditor@audit.example.com fw=223e5733-253c-4592-a9f1-a9dcc0218b64
------------------------------ Captured log call -------------------------------
INFO     compliance_backend.services.auditor_service:auditor_service.py:157 AuditorService.create_invitation: id=336c2b8b-ab79-4adc-bea4-4d3471bce574 tenant=auditor-tenant-e2e email=external-auditor@audit.example.com fw=223e5733-253c-4592-a9f1-a9dcc0218b64
______________ test_workflow_12_evidence_bundle_zip_with_manifest ______________

self = <sqlalchemy.engine.base.Connection object at 0x110582990>
dialect = <sqlalchemy.dialects.sqlite.aiosqlite.SQLiteDialect_aiosqlite object at 0x1105b8cd0>
constructor = <bound method DefaultExecutionContext._init_compiled of <class 'sqlalchemy.dialects.sqlite.aiosqlite.SQLiteExecutionContext_aiosqlite'>>
statement = <sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x10f624b50>
parameters = [{'action': 'evidence_uploaded', 'details_json': '{"control_id": "8757f061-b03c-4a4b-a2cf-9da9d7c656bf", "evidence_typ...g-0.txt", "size_bytes": 34}', 'resource_id': '08be6917-18f4-48e5-b7d2-7d0816d3369a', 'resource_type': 'evidence', ...}]
execution_options = immutabledict({'compiled_cache': <sqlalchemy.util._collections.LRUCache object at 0x11073b060>})
args = (<sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x10f624b50>, [{'action': 'evidence_uploaded', 'details_jso...8f4-48e5-b7d2-7d0816d3369a', 'resource_type': 'evidence', ...}], <sqlalchemy.sql.dml.Insert object at 0x110798940>, [])
kw = {'cache_hit': <CacheStats.CACHE_MISS: 1>}, yp = None
conn = <sqlalchemy.pool.base._ConnectionFairy object at 0x110392170>

    def _execute_context(
        self,
        dialect: Dialect,
        constructor: Callable[..., ExecutionContext],
        statement: Union[str, Compiled],
        parameters: Optional[_AnyMultiExecuteParams],
        execution_options: _ExecuteOptions,
        *args: Any,
        **kw: Any,
    ) -> CursorResult[Any]:
        """Create an :class:`.ExecutionContext` and execute, returning
        a :class:`_engine.CursorResult`."""
    
        if execution_options:
            yp = execution_options.get("yield_per", None)
            if yp:
                execution_options = execution_options.union(
                    {"stream_results": True, "max_row_buffer": yp}
                )
        try:
            conn = self._dbapi_connection
            if conn is None:
                conn = self._revalidate_connection()
    
>           context = constructor(
                dialect, self, conn, execution_options, *args, **kw
            )

/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
E   NameError: name 'timezone' is not defined

compliance/backend/compliance_backend/models/compliance_audit_log.py:69: NameError

The above exception was the direct cause of the following exception:

compliance_client = <httpx.AsyncClient object at 0x110337f50>
compliance_session = <sqlalchemy.ext.asyncio.session.AsyncSession object at 0x10feb8130>
make_compliance_jwt = <function make_compliance_jwt.<locals>._make at 0x1105466c0>

    @pytest.mark.asyncio
    async def test_workflow_12_evidence_bundle_zip_with_manifest(
        compliance_client, compliance_session, make_compliance_jwt
    ):
        tenant_id = "bundle-tenant-e2e"
        h = _admin_headers(make_compliance_jwt, tenant_id)
    
        fw, controls = await _seed_framework_with_controls(compliance_session, n_controls=3)
    
        # ── 1) Upload one evidence per control via the public POST /evidence ──
        uploaded_ids = []
        for i, ctrl in enumerate(controls):
>           resp = await compliance_client.post(
                "/evidence",
                data={
                    "control_id": ctrl.id,
                    "evidence_type": "log",
                    "framework_id": fw.id,
                    "audit_period": "Q4-2025",
                },
                files={
                    "file": (
                        f"log-{i}.txt",
                        io.BytesIO(f"log content for control {ctrl.control_code}\n".encode()),
                        "text/plain",
                    ),
                },
                headers=h,
            )

tests/e2e_cross_service/test_workflow_12_evidence_bundle.py:85: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1859: in post
    return await self.request(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1540: in request
    return await self.send(request, auth=auth, follow_redirects=follow_redirects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1629: in send
    response = await self._send_handling_auth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1657: in _send_handling_auth
    response = await self._send_handling_redirects(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1694: in _send_handling_redirects
    response = await self._send_single_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1730: in _send_single_request
    response = await transport.handle_async_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_transports/asgi.py:170: in handle_async_request
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/applications.py:1054: in __call__
    await super().__call__(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/applications.py:113: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:187: in __call__
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:165: in __call__
    await self.app(scope, receive, _send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:185: in __call__
    with collapse_excgroups():
/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/contextlib.py:162: in __exit__
    self.gen.throw(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_utils.py:82: in collapse_excgroups
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:187: in __call__
    response = await self.dispatch_func(request, call_next)
compliance/backend/compliance_backend/middleware/rate_limit.py:188: in dispatch
    return await call_next(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:163: in call_next
    raise app_exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:149: in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/cors.py:85: in __call__
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/exceptions.py:62: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:715: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:735: in app
    await route.handle(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:288: in handle
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:76: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:73: in app
    response = await f(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:301: in app
    raw_response = await run_endpoint_function(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:212: in run_endpoint_function
    return await dependant.call(**values)
compliance/backend/compliance_backend/routers/evidence.py:169: in upload_evidence
    await write_audit(
compliance/backend/compliance_backend/services/audit_writer.py:65: in write_audit
    await session.flush()  # assign id; flush within current transaction
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/ext/asyncio/session.py:787: in flush
    await greenlet_spawn(self.sync_session.flush, objects=objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/_concurrency_py3k.py:203: in greenlet_spawn
    result = context.switch(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4331: in flush
    self._flush(objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4466: in _flush
    with util.safe_reraise():
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4427: in _flush
    flush_context.execute()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:466: in execute
    rec.execute(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:642: in execute
    util.preloaded.orm_persistence.save_obj(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:93: in save_obj
    _emit_insert_statements(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:1233: in _emit_insert_statements
    result = connection.execute(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1419: in execute
    return meth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/elements.py:527: in _execute_on_connection
    return connection._execute_clauseelement(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1641: in _execute_clauseelement
    ret = self._execute_context(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1821: in _execute_context
    self._handle_dbapi_exception(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:2363: in _handle_dbapi_exception
    raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: in _execute_context
    context = constructor(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
E   sqlalchemy.exc.StatementError: (builtins.NameError) name 'timezone' is not defined
E   [SQL: INSERT INTO compliance_audit_logs (id, tenant_id, user_id, action, resource_type, resource_id, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)]
E   [parameters: [{'resource_type': 'evidence', 'tenant_id': 'bundle-tenant-e2e', 'action': 'evidence_uploaded', 'details_json': '{"control_id": "8757f061-b03c-4a4b-a2c ... (104 characters truncated) ... me": "703dd0a5fc5843c4b0e31a0e8fafa302__log-0.txt", "size_bytes": 34}', 'resource_id': '08be6917-18f4-48e5-b7d2-7d0816d3369a', 'user_id': 'test-user'}]]

compliance/backend/compliance_backend/models/compliance_audit_log.py:69: StatementError
----------------------------- Captured stderr call -----------------------------
2026-04-28 20:26:03,523 WARNING python_multipart.multipart — Skipping data after last boundary
2026-04-28 20:26:03,525 INFO compliance_backend.services.evidence_service — EvidenceService.upload_manual_evidence: id=08be6917-18f4-48e5-b7d2-7d0816d3369a control=8757f061-b03c-4a4b-a2cf-9da9d7c656bf tenant=bundle-tenant-e2e sha256=88893e9b9246088d3cf14030cb86d212bf6cc8c619827488b0f0c6f54e8346b8
------------------------------ Captured log call -------------------------------
WARNING  python_multipart.multipart:multipart.py:1401 Skipping data after last boundary
INFO     compliance_backend.services.evidence_service:evidence_service.py:273 EvidenceService.upload_manual_evidence: id=08be6917-18f4-48e5-b7d2-7d0816d3369a control=8757f061-b03c-4a4b-a2cf-9da9d7c656bf tenant=bundle-tenant-e2e sha256=88893e9b9246088d3cf14030cb86d212bf6cc8c619827488b0f0c6f54e8346b8
____________ test_workflow_12_bundle_period_filter_isolates_periods ____________

self = <sqlalchemy.engine.base.Connection object at 0x11060c140>
dialect = <sqlalchemy.dialects.sqlite.aiosqlite.SQLiteDialect_aiosqlite object at 0x1105b9310>
constructor = <bound method DefaultExecutionContext._init_compiled of <class 'sqlalchemy.dialects.sqlite.aiosqlite.SQLiteExecutionContext_aiosqlite'>>
statement = <sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x1102d2450>
parameters = [{'action': 'evidence_uploaded', 'details_json': '{"control_id": "be84c0ed-57c5-41e3-a7be-6fe0387cb248", "evidence_typ...b__a.txt", "size_bytes": 2}', 'resource_id': '37652bd4-fb37-4b51-8a77-8bb10443dc86', 'resource_type': 'evidence', ...}]
execution_options = immutabledict({'compiled_cache': <sqlalchemy.util._collections.LRUCache object at 0x11073b060>})
args = (<sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x1102d2450>, [{'action': 'evidence_uploaded', 'details_jso...b37-4b51-8a77-8bb10443dc86', 'resource_type': 'evidence', ...}], <sqlalchemy.sql.dml.Insert object at 0x110798940>, [])
kw = {'cache_hit': <CacheStats.CACHE_MISS: 1>}, yp = None
conn = <sqlalchemy.pool.base._ConnectionFairy object at 0x110404370>

    def _execute_context(
        self,
        dialect: Dialect,
        constructor: Callable[..., ExecutionContext],
        statement: Union[str, Compiled],
        parameters: Optional[_AnyMultiExecuteParams],
        execution_options: _ExecuteOptions,
        *args: Any,
        **kw: Any,
    ) -> CursorResult[Any]:
        """Create an :class:`.ExecutionContext` and execute, returning
        a :class:`_engine.CursorResult`."""
    
        if execution_options:
            yp = execution_options.get("yield_per", None)
            if yp:
                execution_options = execution_options.union(
                    {"stream_results": True, "max_row_buffer": yp}
                )
        try:
            conn = self._dbapi_connection
            if conn is None:
                conn = self._revalidate_connection()
    
>           context = constructor(
                dialect, self, conn, execution_options, *args, **kw
            )

/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
E   NameError: name 'timezone' is not defined

compliance/backend/compliance_backend/models/compliance_audit_log.py:69: NameError

The above exception was the direct cause of the following exception:

compliance_client = <httpx.AsyncClient object at 0x10ff9dc10>
compliance_session = <sqlalchemy.ext.asyncio.session.AsyncSession object at 0x10f8c82f0>
make_compliance_jwt = <function make_compliance_jwt.<locals>._make at 0x1105217a0>

    @pytest.mark.asyncio
    async def test_workflow_12_bundle_period_filter_isolates_periods(
        compliance_client, compliance_session, make_compliance_jwt
    ):
        tenant_id = "bundle-period-tenant"
        h = _admin_headers(make_compliance_jwt, tenant_id)
    
        fw, [ctrl] = await _seed_framework_with_controls(compliance_session, n_controls=1)
    
        # Q4-2025 evidence
>       r1 = await compliance_client.post(
            "/evidence",
            data={
                "control_id": ctrl.id,
                "evidence_type": "log",
                "framework_id": fw.id,
                "audit_period": "Q4-2025",
            },
            files={"file": ("a.txt", io.BytesIO(b"q4"), "text/plain")},
            headers=h,
        )

tests/e2e_cross_service/test_workflow_12_evidence_bundle.py:153: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1859: in post
    return await self.request(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1540: in request
    return await self.send(request, auth=auth, follow_redirects=follow_redirects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1629: in send
    response = await self._send_handling_auth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1657: in _send_handling_auth
    response = await self._send_handling_redirects(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1694: in _send_handling_redirects
    response = await self._send_single_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1730: in _send_single_request
    response = await transport.handle_async_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_transports/asgi.py:170: in handle_async_request
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/applications.py:1054: in __call__
    await super().__call__(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/applications.py:113: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:187: in __call__
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:165: in __call__
    await self.app(scope, receive, _send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:185: in __call__
    with collapse_excgroups():
/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/contextlib.py:162: in __exit__
    self.gen.throw(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_utils.py:82: in collapse_excgroups
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:187: in __call__
    response = await self.dispatch_func(request, call_next)
compliance/backend/compliance_backend/middleware/rate_limit.py:188: in dispatch
    return await call_next(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:163: in call_next
    raise app_exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:149: in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/cors.py:85: in __call__
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/exceptions.py:62: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:715: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:735: in app
    await route.handle(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:288: in handle
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:76: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:73: in app
    response = await f(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:301: in app
    raw_response = await run_endpoint_function(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:212: in run_endpoint_function
    return await dependant.call(**values)
compliance/backend/compliance_backend/routers/evidence.py:169: in upload_evidence
    await write_audit(
compliance/backend/compliance_backend/services/audit_writer.py:65: in write_audit
    await session.flush()  # assign id; flush within current transaction
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/ext/asyncio/session.py:787: in flush
    await greenlet_spawn(self.sync_session.flush, objects=objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/_concurrency_py3k.py:203: in greenlet_spawn
    result = context.switch(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4331: in flush
    self._flush(objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4466: in _flush
    with util.safe_reraise():
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4427: in _flush
    flush_context.execute()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:466: in execute
    rec.execute(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:642: in execute
    util.preloaded.orm_persistence.save_obj(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:93: in save_obj
    _emit_insert_statements(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:1233: in _emit_insert_statements
    result = connection.execute(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1419: in execute
    return meth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/elements.py:527: in _execute_on_connection
    return connection._execute_clauseelement(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1641: in _execute_clauseelement
    ret = self._execute_context(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1821: in _execute_context
    self._handle_dbapi_exception(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:2363: in _handle_dbapi_exception
    raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: in _execute_context
    context = constructor(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
E   sqlalchemy.exc.StatementError: (builtins.NameError) name 'timezone' is not defined
E   [SQL: INSERT INTO compliance_audit_logs (id, tenant_id, user_id, action, resource_type, resource_id, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)]
E   [parameters: [{'resource_type': 'evidence', 'tenant_id': 'bundle-period-tenant', 'action': 'evidence_uploaded', 'details_json': '{"control_id": "be84c0ed-57c5-41e3- ... (102 characters truncated) ... ilename": "e56f7a7ca7ef46bc934cce4c72f6adeb__a.txt", "size_bytes": 2}', 'resource_id': '37652bd4-fb37-4b51-8a77-8bb10443dc86', 'user_id': 'test-user'}]]

compliance/backend/compliance_backend/models/compliance_audit_log.py:69: StatementError
----------------------------- Captured stderr call -----------------------------
2026-04-28 20:26:03,853 WARNING python_multipart.multipart — Skipping data after last boundary
2026-04-28 20:26:03,855 INFO compliance_backend.services.evidence_service — EvidenceService.upload_manual_evidence: id=37652bd4-fb37-4b51-8a77-8bb10443dc86 control=be84c0ed-57c5-41e3-a7be-6fe0387cb248 tenant=bundle-period-tenant sha256=112f2dfa31205df3f5f9db109460c8b85067d7dc27f70781c2e4ef903ee9f26a
------------------------------ Captured log call -------------------------------
WARNING  python_multipart.multipart:multipart.py:1401 Skipping data after last boundary
INFO     compliance_backend.services.evidence_service:evidence_service.py:273 EvidenceService.upload_manual_evidence: id=37652bd4-fb37-4b51-8a77-8bb10443dc86 control=be84c0ed-57c5-41e3-a7be-6fe0387cb248 tenant=bundle-period-tenant sha256=112f2dfa31205df3f5f9db109460c8b85067d7dc27f70781c2e4ef903ee9f26a
___________________ test_workflow_12_bundle_is_tenant_scoped ___________________

self = <sqlalchemy.engine.base.Connection object at 0x10e9c6f30>
dialect = <sqlalchemy.dialects.sqlite.aiosqlite.SQLiteDialect_aiosqlite object at 0x1105b8f50>
constructor = <bound method DefaultExecutionContext._init_compiled of <class 'sqlalchemy.dialects.sqlite.aiosqlite.SQLiteExecutionContext_aiosqlite'>>
statement = <sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x110541f50>
parameters = [{'action': 'evidence_uploaded', 'details_json': '{"control_id": "b925ce5d-af77-4567-b4f5-03fcfe966682", "evidence_typ...7__a.txt", "size_bytes": 6}', 'resource_id': 'a0c6b23c-0433-4e39-8ad9-c987a8c9dc3b', 'resource_type': 'evidence', ...}]
execution_options = immutabledict({'compiled_cache': <sqlalchemy.util._collections.LRUCache object at 0x11073b060>})
args = (<sqlalchemy.dialects.sqlite.base.SQLiteCompiler object at 0x110541f50>, [{'action': 'evidence_uploaded', 'details_jso...433-4e39-8ad9-c987a8c9dc3b', 'resource_type': 'evidence', ...}], <sqlalchemy.sql.dml.Insert object at 0x110798940>, [])
kw = {'cache_hit': <CacheStats.CACHE_MISS: 1>}, yp = None
conn = <sqlalchemy.pool.base._ConnectionFairy object at 0x110406490>

    def _execute_context(
        self,
        dialect: Dialect,
        constructor: Callable[..., ExecutionContext],
        statement: Union[str, Compiled],
        parameters: Optional[_AnyMultiExecuteParams],
        execution_options: _ExecuteOptions,
        *args: Any,
        **kw: Any,
    ) -> CursorResult[Any]:
        """Create an :class:`.ExecutionContext` and execute, returning
        a :class:`_engine.CursorResult`."""
    
        if execution_options:
            yp = execution_options.get("yield_per", None)
            if yp:
                execution_options = execution_options.union(
                    {"stream_results": True, "max_row_buffer": yp}
                )
        try:
            conn = self._dbapi_connection
            if conn is None:
                conn = self._revalidate_connection()
    
>           context = constructor(
                dialect, self, conn, execution_options, *args, **kw
            )

/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
E   NameError: name 'timezone' is not defined

compliance/backend/compliance_backend/models/compliance_audit_log.py:69: NameError

The above exception was the direct cause of the following exception:

compliance_client = <httpx.AsyncClient object at 0x110620890>
compliance_session = <sqlalchemy.ext.asyncio.session.AsyncSession object at 0x10f81da90>
make_compliance_jwt = <function make_compliance_jwt.<locals>._make at 0x1107759b0>

    @pytest.mark.asyncio
    async def test_workflow_12_bundle_is_tenant_scoped(
        compliance_client, compliance_session, make_compliance_jwt
    ):
        tenant_a = "bundle-iso-a"
        tenant_b = "bundle-iso-b"
        h_a = _admin_headers(make_compliance_jwt, tenant_a)
        h_b = _admin_headers(make_compliance_jwt, tenant_b)
    
        fw, [ctrl] = await _seed_framework_with_controls(compliance_session, n_controls=1)
    
        # A uploads evidence
>       r = await compliance_client.post(
            "/evidence",
            data={
                "control_id": ctrl.id,
                "evidence_type": "log",
                "framework_id": fw.id,
                "audit_period": "Q4-2025",
            },
            files={"file": ("a.txt", io.BytesIO(b"data-A"), "text/plain")},
            headers=h_a,
        )

tests/e2e_cross_service/test_workflow_12_evidence_bundle.py:191: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1859: in post
    return await self.request(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1540: in request
    return await self.send(request, auth=auth, follow_redirects=follow_redirects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1629: in send
    response = await self._send_handling_auth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1657: in _send_handling_auth
    response = await self._send_handling_redirects(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1694: in _send_handling_redirects
    response = await self._send_single_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_client.py:1730: in _send_single_request
    response = await transport.handle_async_request(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/httpx/_transports/asgi.py:170: in handle_async_request
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/applications.py:1054: in __call__
    await super().__call__(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/applications.py:113: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:187: in __call__
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py:165: in __call__
    await self.app(scope, receive, _send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:185: in __call__
    with collapse_excgroups():
/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/contextlib.py:162: in __exit__
    self.gen.throw(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_utils.py:82: in collapse_excgroups
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:187: in __call__
    response = await self.dispatch_func(request, call_next)
compliance/backend/compliance_backend/middleware/rate_limit.py:188: in dispatch
    return await call_next(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:163: in call_next
    raise app_exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/base.py:149: in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/cors.py:85: in __call__
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/middleware/exceptions.py:62: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:715: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:735: in app
    await route.handle(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:288: in handle
    await self.app(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:76: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/routing.py:73: in app
    response = await f(request)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:301: in app
    raw_response = await run_endpoint_function(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:212: in run_endpoint_function
    return await dependant.call(**values)
compliance/backend/compliance_backend/routers/evidence.py:169: in upload_evidence
    await write_audit(
compliance/backend/compliance_backend/services/audit_writer.py:65: in write_audit
    await session.flush()  # assign id; flush within current transaction
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/ext/asyncio/session.py:787: in flush
    await greenlet_spawn(self.sync_session.flush, objects=objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/_concurrency_py3k.py:203: in greenlet_spawn
    result = context.switch(value)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4331: in flush
    self._flush(objects)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4466: in _flush
    with util.safe_reraise():
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/session.py:4427: in _flush
    flush_context.execute()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:466: in execute
    rec.execute(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/unitofwork.py:642: in execute
    util.preloaded.orm_persistence.save_obj(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:93: in save_obj
    _emit_insert_statements(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/orm/persistence.py:1233: in _emit_insert_statements
    result = connection.execute(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1419: in execute
    return meth(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/elements.py:527: in _execute_on_connection
    return connection._execute_clauseelement(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1641: in _execute_clauseelement
    ret = self._execute_context(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1821: in _execute_context
    self._handle_dbapi_exception(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:2363: in _handle_dbapi_exception
    raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py:1815: in _execute_context
    context = constructor(
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:1441: in _init_compiled
    self._process_execute_defaults()
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/engine/default.py:2385: in _process_execute_defaults
    param[param_key] = arg(self)
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/sqlalchemy/sql/schema.py:3630: in <lambda>
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

>       default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
E   sqlalchemy.exc.StatementError: (builtins.NameError) name 'timezone' is not defined
E   [SQL: INSERT INTO compliance_audit_logs (id, tenant_id, user_id, action, resource_type, resource_id, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)]
E   [parameters: [{'resource_type': 'evidence', 'tenant_id': 'bundle-iso-a', 'action': 'evidence_uploaded', 'details_json': '{"control_id": "b925ce5d-af77-4567-b4f5-03f ... (94 characters truncated) ... ilename": "ded11585002d4f989979c9f03b6314a7__a.txt", "size_bytes": 6}', 'resource_id': 'a0c6b23c-0433-4e39-8ad9-c987a8c9dc3b', 'user_id': 'test-user'}]]

compliance/backend/compliance_backend/models/compliance_audit_log.py:69: StatementError
----------------------------- Captured stderr call -----------------------------
2026-04-28 20:26:04,182 WARNING python_multipart.multipart — Skipping data after last boundary
2026-04-28 20:26:04,184 INFO compliance_backend.services.evidence_service — EvidenceService.upload_manual_evidence: id=a0c6b23c-0433-4e39-8ad9-c987a8c9dc3b control=b925ce5d-af77-4567-b4f5-03fcfe966682 tenant=bundle-iso-a sha256=33699b84f6f7bbeab3104840bb59e03f505203639e72635e4c6da77e360660ac
------------------------------ Captured log call -------------------------------
WARNING  python_multipart.multipart:multipart.py:1401 Skipping data after last boundary
INFO     compliance_backend.services.evidence_service:evidence_service.py:273 EvidenceService.upload_manual_evidence: id=a0c6b23c-0433-4e39-8ad9-c987a8c9dc3b control=b925ce5d-af77-4567-b4f5-03fcfe966682 tenant=bundle-iso-a sha256=33699b84f6f7bbeab3104840bb59e03f505203639e72635e4c6da77e360660ac
___________ test_af_crit3_env_file_does_not_carry_default_jwt_secret ___________

    def test_af_crit3_env_file_does_not_carry_default_jwt_secret():
        """
        Per Gemini CRIT-G5 / Codex CRIT-003: the literal line
        `JWT_SECRET_KEY=urip-dev-secret-change-in-production`
        must be removed from `.env`. The pydantic default in code already
        provides the dev fallback; keeping it in `.env` increases the risk of
        accidental production deployment with the well-known secret.
        """
>       text = (_project_root() / ".env").read_text()

tests/test_critfix_auth/test_audit_fix_critical.py:122: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/pathlib/__init__.py:787: in read_text
    with self.open(mode='r', encoding=encoding, errors=errors, newline=newline) as f:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = PosixPath('/private/tmp/urip_audit.AeKrB6/.env'), mode = 'r'
buffering = -1, encoding = 'locale', errors = None, newline = None

    def open(self, mode='r', buffering=-1, encoding=None,
             errors=None, newline=None):
        """
        Open the file pointed to by this path and return a file object, as
        the built-in open() function does.
        """
        if "b" not in mode:
            encoding = io.text_encoding(encoding)
>       return io.open(self, mode, buffering, encoding, errors, newline)
E       FileNotFoundError: [Errno 2] No such file or directory: '/private/tmp/urip_audit.AeKrB6/.env'

/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/pathlib/__init__.py:771: FileNotFoundError
_________________ test_af_crit3_env_file_still_marked_dev_only _________________

    def test_af_crit3_env_file_still_marked_dev_only():
        """Removing the line must not erase the DEV-ONLY warnings."""
>       text = (_project_root() / ".env").read_text().lower()

tests/test_critfix_auth/test_audit_fix_critical.py:139: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/pathlib/__init__.py:787: in read_text
    with self.open(mode='r', encoding=encoding, errors=errors, newline=newline) as f:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = PosixPath('/private/tmp/urip_audit.AeKrB6/.env'), mode = 'r'
buffering = -1, encoding = 'locale', errors = None, newline = None

    def open(self, mode='r', buffering=-1, encoding=None,
             errors=None, newline=None):
        """
        Open the file pointed to by this path and return a file object, as
        the built-in open() function does.
        """
        if "b" not in mode:
            encoding = io.text_encoding(encoding)
>       return io.open(self, mode, buffering, encoding, errors, newline)
E       FileNotFoundError: [Errno 2] No such file or directory: '/private/tmp/urip_audit.AeKrB6/.env'

/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/pathlib/__init__.py:771: FileNotFoundError
________________________ test_env_file_marked_dev_only _________________________

    def test_env_file_marked_dev_only():
        """The committed .env file is dev-only; it must mark itself as such so it
        cannot be silently shipped to production.
        """
        from pathlib import Path
    
        here = Path(__file__).resolve()
        repo_root = here
        for _ in range(6):
            if (repo_root / ".env").exists():
                break
            repo_root = repo_root.parent
        else:
>           pytest.fail(".env not found by walking up from test file")
E           Failed: .env not found by walking up from test file

tests/test_critfix_auth/test_crit004_jwt_secret.py:157: Failed
_ TestListConnectorsMetadata.test_list_returns_metadata_for_every_connector[asyncio] _

self = <tests.test_routers.test_connectors_metadata.TestListConnectorsMetadata object at 0x10f372fd0>
client = <httpx.AsyncClient object at 0x11100c1d0>
auth_headers = {'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0ZGUyZjM3NS1mMDJlLTRmNGUtYWY1My03MmZmMjQ5MTh...nQiLCJ0ZW5hbnRfaWQiOiIxYzllYTE4MS01Nzg0LTQyZGMtYjkzNS00YmZiNTcwZjkyOWMifQ.372t9NTTsXeqDh_kyGEgNxWI_iTUr-OycxFxv8EOlok'}
core_subscription = <backend.models.subscription.TenantSubscription object at 0x112d817f0>

    @pytest.mark.anyio
    async def test_list_returns_metadata_for_every_connector(
        self, client, auth_headers, core_subscription,
    ):
        resp = await client.get("/api/connectors", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
    
        names = {item["name"] for item in body["items"]}
        for expected in REAL_CONNECTORS:
>           assert expected in names, f"Missing connector {expected!r}"
E           AssertionError: Missing connector 'simulator'
E           assert 'simulator' in {'cloudsek', 'manageengine_sdp', 'ms_entra', 'netskope', 'sentinelone', 'tenable', ...}

tests/test_routers/test_connectors_metadata.py:197: AssertionError
----------------------------- Captured stderr call -----------------------------
{"ts": "2026-04-28T15:00:27.409994+00:00", "level": "INFO", "logger": "httpx", "message": "HTTP Request: GET http://test/api/connectors \"HTTP/1.1 200 OK\""}
------------------------------ Captured log call -------------------------------
INFO     httpx:_client.py:1740 HTTP Request: GET http://test/api/connectors "HTTP/1.1 200 OK"
________ TestListConnectorsMetadata.test_list_filter_by_status[asyncio] ________

self = <tests.test_routers.test_connectors_metadata.TestListConnectorsMetadata object at 0x10f4ff2f0>
client = <httpx.AsyncClient object at 0x111a3b1d0>
auth_headers = {'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1OGJiNzNkZS04M2E4LTQwNTEtYjJiMC0zMzYzNDg2MTU...nQiLCJ0ZW5hbnRfaWQiOiJiOWFlM2Y2Yy1hNTc1LTRhZmEtYjM0MS02YWMyYjdlOTRjNDYifQ.i8VX7BESxj5UGztWmyCx4xGHQb9PIaGUi2EiKUTV-fc'}
core_subscription = <backend.models.subscription.TenantSubscription object at 0x112d83770>

    @pytest.mark.anyio
    async def test_list_filter_by_status(
        self, client, auth_headers, core_subscription,
    ):
        resp = await client.get(
            "/api/connectors?status=simulated", headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        names = sorted(i["name"] for i in body["items"])
>       assert names == ["extended_simulator", "simulator"]
E       AssertionError: assert [] == ['extended_si..., 'simulator']
E         
E         Right contains 2 more items, first extra item: 'extended_simulator'
E         Use -v to get more diff

tests/test_routers/test_connectors_metadata.py:269: AssertionError
----------------------------- Captured stderr call -----------------------------
{"ts": "2026-04-28T15:00:28.575761+00:00", "level": "INFO", "logger": "httpx", "message": "HTTP Request: GET http://test/api/connectors?status=simulated \"HTTP/1.1 200 OK\""}
------------------------------ Captured log call -------------------------------
INFO     httpx:_client.py:1740 HTTP Request: GET http://test/api/connectors?status=simulated "HTTP/1.1 200 OK"
_____ TestListConnectorsMetadata.test_list_pagination_still_works[asyncio] _____

self = <tests.test_routers.test_connectors_metadata.TestListConnectorsMetadata object at 0x10f6989e0>
client = <httpx.AsyncClient object at 0x111a3bad0>
auth_headers = {'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0YTZiMzhlYi1hMjk1LTQ1OWItOWM2Yi04MDY0NmQxZGI...nQiLCJ0ZW5hbnRfaWQiOiIyZGFjZjRlNy0xNWNhLTRhMjEtOTBmNS1hMjdlZjBkNTA0ZGQifQ.Pm17hpCVRIWTyM-XvUI8lexLbGioSvR6zsEuebW_mgk'}
core_subscription = <backend.models.subscription.TenantSubscription object at 0x1122105f0>

    @pytest.mark.anyio
    async def test_list_pagination_still_works(
        self, client, auth_headers, core_subscription,
    ):
        resp = await client.get(
            "/api/connectors?limit=3&offset=0", headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 3
>       assert body["total"] >= 9
E       assert 7 >= 9

tests/test_routers/test_connectors_metadata.py:282: AssertionError
----------------------------- Captured stderr call -----------------------------
{"ts": "2026-04-28T15:00:28.870243+00:00", "level": "INFO", "logger": "httpx", "message": "HTTP Request: GET http://test/api/connectors?limit=3&offset=0 \"HTTP/1.1 200 OK\""}
------------------------------ Captured log call -------------------------------
INFO     httpx:_client.py:1740 HTTP Request: GET http://test/api/connectors?limit=3&offset=0 "HTTP/1.1 200 OK"
____ TestListConnectorsMetadata.test_list_reflects_configured_flag[asyncio] ____

self = <tests.test_routers.test_connectors_metadata.TestListConnectorsMetadata object at 0x10f609b50>
client = <httpx.AsyncClient object at 0x111a39850>
db_session = <sqlalchemy.ext.asyncio.session.AsyncSession object at 0x1126944b0>
auth_headers = {'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiMzE2OGUzYi1kODgxLTQ1NzgtOWRmNS1jNWQyMjY0MjV...nQiLCJ0ZW5hbnRfaWQiOiJmMmE4MzRmNy04OGQzLTQyZmEtOTkxMi0wNzgxNmE4OGM0NWIifQ.DSAgF6Oo8-_GAeyMAUFzpjjkINVfTpJIzI42NrA8AtI'}
default_tenant = <backend.models.tenant.Tenant object at 0x1123e05f0>
core_subscription = <backend.models.subscription.TenantSubscription object at 0x1122112e0>

    @pytest.mark.anyio
    async def test_list_reflects_configured_flag(
        self,
        client,
        db_session,
        auth_headers,
        default_tenant,
        core_subscription,
    ):
        """A row in tenant_connector_credentials → configured=True."""
        cred = TenantConnectorCredential(
            id=uuid.uuid4(),
            tenant_id=default_tenant.id,
            connector_name="simulator",
            encrypted_blob=b"fake-encrypted-bytes",
        )
        db_session.add(cred)
        await db_session.commit()
    
        resp = await client.get("/api/connectors", headers=auth_headers)
        items = {i["name"]: i for i in resp.json()["items"]}
>       assert items["simulator"]["configured"] is True
E       KeyError: 'simulator'

tests/test_routers/test_connectors_metadata.py:337: KeyError
----------------------------- Captured stderr call -----------------------------
{"ts": "2026-04-28T15:00:29.431283+00:00", "level": "INFO", "logger": "httpx", "message": "HTTP Request: GET http://test/api/connectors \"HTTP/1.1 200 OK\""}
------------------------------ Captured log call -------------------------------
INFO     httpx:_client.py:1740 HTTP Request: GET http://test/api/connectors "HTTP/1.1 200 OK"
_____ TestListConnectorsMetadata.test_list_cross_tenant_isolation[asyncio] _____

self = <tests.test_routers.test_connectors_metadata.TestListConnectorsMetadata object at 0x10f609e50>
client = <httpx.AsyncClient object at 0x111a384d0>
db_session = <sqlalchemy.ext.asyncio.session.AsyncSession object at 0x111426eb0>
auth_headers = {'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI5NTg5ZTFjZC1lZTQ0LTQ1ZjEtYjIyOC00NDcxMjdhMTc...nQiLCJ0ZW5hbnRfaWQiOiI0NmEzNTZkMS00M2FhLTQ2ZDMtOTM1NS02Njk3Yjk2ZmRkYmMifQ.KOIfQGsP1Vr-7RxCef60jb0RrlDscjr3c_yQ0jLTUk8'}
second_tenant_headers = {'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyYWE0OTRhMy1jYmY5LTQ2NjYtOGZlMS04MzhiNmE4NWQ...nQiLCJ0ZW5hbnRfaWQiOiI2MTgxMGI1Mi0wZGQ4LTRmOTUtOGU1Mi0yN2E1ZjFmMmE5MjkifQ.Zf89GSpftpBcsrSmFNEOqkqehahmc-o0Jisq5wGMmvU'}
default_tenant = <backend.models.tenant.Tenant object at 0x110ce9b30>
second_tenant = <backend.models.tenant.Tenant object at 0x112df4cd0>
core_subscription = <backend.models.subscription.TenantSubscription object at 0x112212de0>

    @pytest.mark.anyio
    async def test_list_cross_tenant_isolation(
        self,
        client,
        db_session,
        auth_headers,
        second_tenant_headers,
        default_tenant,
        second_tenant,
        core_subscription,
    ):
        """Tenant A configures simulator → Tenant B must NOT see it configured."""
        db_session.add(
            TenantConnectorCredential(
                id=uuid.uuid4(),
                tenant_id=default_tenant.id,
                connector_name="simulator",
                encrypted_blob=b"tenant-a-blob",
            )
        )
        # Also seed a health row for tenant A only.
        db_session.add(
            ConnectorHealthSummary(
                id=uuid.uuid4(),
                tenant_id=default_tenant.id,
                connector_name="simulator",
                status="ok",
                last_poll_at=datetime.now(timezone.utc),
                error_count_24h=0,
                last_error=None,
            )
        )
        await db_session.commit()
    
        # Tenant A sees configured=True + health
        resp_a = await client.get("/api/connectors", headers=auth_headers)
>       sim_a = next(
            i for i in resp_a.json()["items"] if i["name"] == "simulator"
        )
E       StopIteration

tests/test_routers/test_connectors_metadata.py:377: StopIteration

The above exception was the direct cause of the following exception:

self = <Coroutine test_list_cross_tenant_isolation[asyncio]>

    def runtest(self) -> None:
        self.obj = wrap_in_sync(
            # https://github.com/pytest-dev/pytest-asyncio/issues/596
            self.obj,  # type: ignore[has-type]
        )
>       super().runtest()

/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:533: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:1026: in inner
    _loop.run_until_complete(task)
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
future = <Task finished name='Task-6870' coro=<TestListConnectorsMetadata.test_list_cross_tenant_isolation() done, defined at /...it.AeKrB6/tests/test_routers/test_connectors_metadata.py:341> exception=RuntimeError('coroutine raised StopIteration')>

    def run_until_complete(self, future):
        """Run until the Future is done.
    
        If the argument is a coroutine, it is wrapped in a Task.
    
        WARNING: It would be disastrous to call run_until_complete()
        with the same coroutine twice -- it would wrap it in two
        different Tasks and that can't be good.
    
        Return the Future's result, or raise its exception.
        """
        self._check_closed()
        self._check_running()
    
        new_task = not futures.isfuture(future)
        future = tasks.ensure_future(future, loop=self)
        if new_task:
            # An exception is raised if the future didn't complete, so there
            # is no need to log the "destroy pending task" message
            future._log_destroy_pending = False
    
        future.add_done_callback(_run_until_complete_cb)
        try:
            self.run_forever()
        except:
            if new_task and future.done() and not future.cancelled():
                # The coroutine raised a BaseException. Consume the exception
                # to not log a warning, the caller doesn't have access to the
                # local task.
                future.exception()
            raise
        finally:
            future.remove_done_callback(_run_until_complete_cb)
        if not future.done():
            raise RuntimeError('Event loop stopped before Future completed.')
    
>       return future.result()
E       RuntimeError: coroutine raised StopIteration

/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/asyncio/base_events.py:719: RuntimeError
----------------------------- Captured stderr call -----------------------------
{"ts": "2026-04-28T15:00:29.924614+00:00", "level": "INFO", "logger": "httpx", "message": "HTTP Request: GET http://test/api/connectors \"HTTP/1.1 200 OK\""}
------------------------------ Captured log call -------------------------------
INFO     httpx:_client.py:1740 HTTP Request: GET http://test/api/connectors "HTTP/1.1 200 OK"
_ TestCategoriesAggregate.test_categories_returns_distinct_with_counts[asyncio] _

self = <tests.test_routers.test_connectors_metadata.TestCategoriesAggregate object at 0x10f373610>
client = <httpx.AsyncClient object at 0x111a3a150>
auth_headers = {'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkNzIxMzg5Yy1jYTVkLTQwZmQtYjU4Yy1kOGQ2ZGVkMjM...nQiLCJ0ZW5hbnRfaWQiOiI1Mjk1NzcxYy01MjgyLTQzYzctOWZhNy1kZWM2NWZjNTQ0ODgifQ.C8dk7RqI7-JOF2XDvOwp9KUAQ4uziMkPdWsuIc4Otkk'}
core_subscription = <backend.models.subscription.TenantSubscription object at 0x112213d10>

    @pytest.mark.anyio
    async def test_categories_returns_distinct_with_counts(
        self, client, auth_headers, core_subscription,
    ):
        resp = await client.get(
            "/api/connectors/categories", headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "categories" in body
        assert body["total_categories"] == len(body["categories"])
    
        by_cat = {c["category"]: c for c in body["categories"]}
        # Spot-check expected categories from the 9 real connectors.
        assert by_cat["VM"]["count"] == 1
        assert by_cat["EDR"]["count"] == 1
        assert by_cat["NETWORK"]["count"] == 1
        assert by_cat["IDENTITY"]["count"] == 1
        assert by_cat["DLP"]["count"] == 1
        assert by_cat["ITSM"]["count"] == 1
        assert by_cat["EXTERNAL_THREAT"]["count"] == 1
>       assert by_cat["SIMULATOR"]["count"] == 2
E       KeyError: 'SIMULATOR'

tests/test_routers/test_connectors_metadata.py:469: KeyError
----------------------------- Captured stderr call -----------------------------
{"ts": "2026-04-28T15:00:30.592175+00:00", "level": "INFO", "logger": "httpx", "message": "HTTP Request: GET http://test/api/connectors/categories \"HTTP/1.1 200 OK\""}
------------------------------ Captured log call -------------------------------
INFO     httpx:_client.py:1740 HTTP Request: GET http://test/api/connectors/categories "HTTP/1.1 200 OK"
___ TestListConnectors.test_list_returns_all_registered_connectors[asyncio] ____

self = <tests.test_routers.test_connectors_router.TestListConnectors object at 0x10f373d90>
client = <httpx.AsyncClient object at 0x111a3b290>
auth_headers = {'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3MzIyZWZmYS0zNTU0LTQwYmEtYjJmNS04ZmUxZTQyY2U...nQiLCJ0ZW5hbnRfaWQiOiIwZWM2Mjc3NC0zMzBmLTQ2MTItOWFjNi00M2ViOWYxM2I1NDEifQ.bt6ik0EZeSpLFPiloQYRWg1M_H4oI9vaZNgxYCsERoE'}

    @pytest.mark.anyio
    async def test_list_returns_all_registered_connectors(
        self, client, auth_headers
    ):
        resp = await client.get("/api/connectors", headers=auth_headers)
        assert resp.status_code == 200, resp.text
    
        body = resp.json()
        assert "items" in body, f"Missing 'items' key: {body}"
        assert "total" in body, f"Missing 'total' key: {body}"
    
        names = {item["name"] for item in body["items"]}
        # All 9 production + simulator connectors must show up
        for expected in (
            "tenable", "sentinelone", "zscaler", "netskope",
            "ms_entra", "manageengine_sdp", "cloudsek",
            "simulator", "extended_simulator",
        ):
>           assert expected in names, f"Missing connector '{expected}' in list"
E           AssertionError: Missing connector 'simulator' in list
E           assert 'simulator' in {'armis_ot', 'authbridge', 'aws_cspm', 'azure_cspm', 'bug_bounty', 'burp_enterprise', ...}

tests/test_routers/test_connectors_router.py:71: AssertionError
----------------------------- Captured stderr call -----------------------------
{"ts": "2026-04-28T15:00:31.272003+00:00", "level": "INFO", "logger": "httpx", "message": "HTTP Request: GET http://test/api/connectors \"HTTP/1.1 200 OK\""}
------------------------------ Captured log call -------------------------------
INFO     httpx:_client.py:1740 HTTP Request: GET http://test/api/connectors "HTTP/1.1 200 OK"
=============================== warnings summary ===============================
backend/config.py:159
  /private/tmp/urip_audit.AeKrB6/backend/config.py:159: RuntimeWarning: [URIP CONFIG WARNING] JWT_SECRET_KEY is using the dev default (urip-dev-secret-change-in-production). This is acceptable in dev ONLY. You MUST rotate this secret before any prod / staging deployment (set URIP_ENV=production and a real JWT_SECRET_KEY).
    _enforce_jwt_secret_policy(settings)

../../../Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_utils.py:39: 417 warnings
tests/e2e/test_workflow_01_tenant_to_first_risk.py: 1 warning
tests/e2e/test_workflow_02_multi_tenant_isolation.py: 8 warnings
tests/e2e/test_workflow_09_module_subscription.py: 3 warnings
tests/e2e/test_workflow_10_white_label_theming.py: 3 warnings
tests/e2e_cross_service/test_workflow_07_auditor_portal.py: 1 warning
tests/e2e_cross_service/test_workflow_11_compliance_scoring_trend.py: 2 warnings
tests/test_acceptance.py: 1 warning
tests/test_agent_ingest/test_drilldown.py: 3 warnings
tests/test_agent_ingest/test_heartbeat.py: 5 warnings
tests/test_agent_ingest/test_metadata.py: 7 warnings
tests/test_agent_ingest/test_register.py: 3 warnings
tests/test_ai_security/test_ai_security_module.py: 1 warning
tests/test_asset_taxonomy_routes.py: 11 warnings
tests/test_assets/test_asset_routes.py: 7 warnings
tests/test_attack_path/test_attack_path_module.py: 2 warnings
tests/test_audit_fix_medium.py: 10 warnings
tests/test_audit_high/test_h3_connector_ssrf.py: 18 warnings
tests/test_audit_high/test_h4_login_timing.py: 14 warnings
tests/test_audit_high/test_h6_signature_replay.py: 1 warning
tests/test_auth.py: 3 warnings
tests/test_backend_gaps_branding.py: 4 warnings
tests/test_backend_gaps_scoring.py: 3 warnings
tests/test_critfix_audit_log/test_audit_log_coverage.py: 1 warning
tests/test_critfix_auth/test_crit007_module_gates.py: 20 warnings
tests/test_critfix_auth/test_high006_tenant_active.py: 6 warnings
tests/test_critfix_auth/test_high007_subscription_expiry.py: 2 warnings
tests/test_critfix_auth/test_high008_login_audit.py: 7 warnings
tests/test_critfix_validation/test_high004_sort_allowlist.py: 6 warnings
tests/test_critfix_validation/test_high009_rate_limit.py: 16 warnings
tests/test_critfix_validation/test_high012_taxonomy_regex.py: 12 warnings
tests/test_cspm/test_cspm_routes.py: 4 warnings
tests/test_dspm/test_dspm_module.py: 2 warnings
tests/test_module_gate.py: 3 warnings
tests/test_module_subscription.py: 8 warnings
tests/test_multi_tenant_isolation.py: 2 warnings
tests/test_rbac/test_legacy_rbac.py: 3 warnings
tests/test_rbac/test_scope_enforcement.py: 4 warnings
tests/test_risk_index/test_risk_index_routes.py: 5 warnings
tests/test_risk_quantification/test_risk_quantification_module.py: 2 warnings
tests/test_risk_summary_routes.py: 6 warnings
tests/test_risks.py: 1 warning
tests/test_routers/test_connectors_metadata.py: 3 warnings
tests/test_routers/test_connectors_router.py: 10 warnings
tests/test_routers/test_threat_intel_word_cloud.py: 1 warning
tests/test_tenant_onboarding.py: 7 warnings
tests/test_ticketing/test_ticketing_webhooks.py: 2 warnings
tests/test_trust_center/test_trust_center_routes.py: 3 warnings
tests/test_trust_center/test_trust_center_streaming.py: 2 warnings
tests/test_vapt/test_vapt_security.py: 10 warnings
tests/test_vapt/test_vapt_vendor_routes.py: 7 warnings
tests/test_ztna/test_ztna_module.py: 1 warning
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_utils.py:39: DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead
    return asyncio.iscoroutinefunction(obj) or (callable(obj) and asyncio.iscoroutinefunction(obj.__call__))

../../../Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:233: 409 warnings
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:233: DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead
    is_coroutine = asyncio.iscoroutinefunction(dependant.call)

tests/connectors/servicenow/test_connector.py::test_register
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:1153: DeprecationWarning: 'asyncio.get_event_loop_policy' is deprecated and slated for removal in Python 3.16
    return asyncio.get_event_loop_policy()

tests/e2e/test_workflow_01_tenant_to_first_risk.py: 1 warning
tests/e2e/test_workflow_02_multi_tenant_isolation.py: 2 warnings
tests/e2e/test_workflow_08_connector_lifecycle.py: 2 warnings
tests/e2e/test_workflow_09_module_subscription.py: 2 warnings
tests/e2e/test_workflow_10_white_label_theming.py: 2 warnings
tests/e2e_cross_service/test_workflow_03_control_failure_to_risk.py: 2 warnings
tests/e2e_cross_service/test_workflow_04_risk_resolved_to_compliance.py: 2 warnings
tests/e2e_cross_service/test_workflow_05_policy_lifecycle.py: 3 warnings
tests/e2e_cross_service/test_workflow_06_vendor_risk_lifecycle.py: 2 warnings
tests/e2e_cross_service/test_workflow_07_auditor_portal.py: 2 warnings
tests/e2e_cross_service/test_workflow_11_compliance_scoring_trend.py: 4 warnings
tests/e2e_cross_service/test_workflow_12_evidence_bundle.py: 3 warnings
tests/test_acceptance.py: 4 warnings
tests/test_agent/test_drilldown.py: 3 warnings
tests/test_agent_ingest/test_drilldown.py: 5 warnings
tests/test_agent_ingest/test_heartbeat.py: 6 warnings
tests/test_agent_ingest/test_metadata.py: 9 warnings
tests/test_agent_ingest/test_register.py: 6 warnings
tests/test_ai_security/test_ai_security_module.py: 10 warnings
tests/test_asset_taxonomy_model.py: 6 warnings
tests/test_asset_taxonomy_routes.py: 23 warnings
tests/test_asset_taxonomy_service.py: 10 warnings
tests/test_assets/test_asset_backfill.py: 3 warnings
tests/test_assets/test_asset_connector_integration.py: 4 warnings
tests/test_assets/test_asset_model.py: 6 warnings
tests/test_assets/test_asset_routes.py: 16 warnings
tests/test_assets/test_asset_service.py: 17 warnings
tests/test_assets/test_sample_response.py: 1 warning
tests/test_attack_path/test_attack_path_module.py: 9 warnings
tests/test_audit_fix_medium.py: 12 warnings
tests/test_audit_high/test_h3_connector_ssrf.py: 19 warnings
tests/test_audit_high/test_h4_login_timing.py: 1 warning
tests/test_audit_high/test_h6_signature_replay.py: 2 warnings
tests/test_audit_low/test_low_fixes.py: 3 warnings
tests/test_auth.py: 5 warnings
tests/test_auto_remediation/test_auto_remediation_service.py: 8 warnings
tests/test_auto_remediation/test_executor_audit.py: 1 warning
tests/test_backend_gaps_auth.py: 4 warnings
tests/test_backend_gaps_branding.py: 7 warnings
tests/test_backend_gaps_scoring.py: 6 warnings
tests/test_connector_framework/test_base.py: 4 warnings
tests/test_critfix_audit_log/test_audit_log_coverage.py: 16 warnings
tests/test_critfix_auth/test_crit007_module_gates.py: 40 warnings
tests/test_critfix_auth/test_high006_tenant_active.py: 4 warnings
tests/test_critfix_auth/test_high007_subscription_expiry.py: 4 warnings
tests/test_critfix_auth/test_high008_login_audit.py: 7 warnings
tests/test_critfix_validation/test_high004_sort_allowlist.py: 5 warnings
tests/test_critfix_validation/test_high009_rate_limit.py: 3 warnings
tests/test_critfix_validation/test_high012_taxonomy_regex.py: 4 warnings
tests/test_critfix_validation/test_new5_fernet_key_param.py: 2 warnings
tests/test_cspm/test_cis_seeders.py: 4 warnings
tests/test_cspm/test_cspm_engine.py: 4 warnings
tests/test_cspm/test_cspm_routes.py: 13 warnings
tests/test_dashboard.py: 5 warnings
tests/test_dspm/test_dspm_module.py: 11 warnings
tests/test_intelligence_engine/test_advisory_applicability.py: 4 warnings
tests/test_intelligence_engine/test_asset_fingerprint.py: 2 warnings
tests/test_module_gate.py: 5 warnings
tests/test_module_subscription.py: 16 warnings
tests/test_multi_tenant_isolation.py: 4 warnings
tests/test_multi_tenant_isolation_extended.py: 7 warnings
tests/test_multi_tenant_model.py: 8 warnings
tests/test_rbac/test_legacy_rbac.py: 4 warnings
tests/test_rbac/test_scope_enforcement.py: 8 warnings
tests/test_remediation.py: 3 warnings
tests/test_reports.py: 4 warnings
tests/test_risk_aggregate.py: 5 warnings
tests/test_risk_aggregate_service.py: 17 warnings
tests/test_risk_index/test_risk_index_routes.py: 11 warnings
tests/test_risk_index/test_risk_index_service.py: 15 warnings
tests/test_risk_quantification/test_risk_quantification_module.py: 10 warnings
tests/test_risk_summary_routes.py: 14 warnings
tests/test_risks.py: 8 warnings
tests/test_routers/test_connectors_metadata.py: 14 warnings
tests/test_routers/test_connectors_router.py: 25 warnings
tests/test_routers/test_threat_intel_word_cloud.py: 6 warnings
tests/test_seed_simulators_audit_log.py: 6 warnings
tests/test_seed_simulators_credentials.py: 4 warnings
tests/test_services/test_event_subscribers.py: 9 warnings
tests/test_shared/test_distributed_events.py: 8 warnings
tests/test_shared/test_event_wiring.py: 5 warnings
tests/test_shared/test_redis_client.py: 3 warnings
tests/test_tenant_onboarding.py: 13 warnings
tests/test_ticketing/test_ticketing_audit.py: 2 warnings
tests/test_ticketing/test_ticketing_service.py: 7 warnings
tests/test_ticketing/test_ticketing_webhooks.py: 5 warnings
tests/test_trust_center/test_trust_center_routes.py: 6 warnings
tests/test_trust_center/test_trust_center_service.py: 13 warnings
tests/test_trust_center/test_trust_center_streaming.py: 10 warnings
tests/test_vapt/test_vapt_retest_flow.py: 6 warnings
tests/test_vapt/test_vapt_security.py: 12 warnings
tests/test_vapt/test_vapt_submission_pipeline.py: 5 warnings
tests/test_vapt/test_vapt_vendor_invitation.py: 8 warnings
tests/test_vapt/test_vapt_vendor_models.py: 5 warnings
tests/test_vapt/test_vapt_vendor_routes.py: 16 warnings
tests/test_ztna/test_ztna_module.py: 10 warnings
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:844: DeprecationWarning: 'asyncio.get_event_loop_policy' is deprecated and slated for removal in Python 3.16
    _restore_event_loop_policy(asyncio.get_event_loop_policy()),

tests/e2e/test_workflow_01_tenant_to_first_risk.py: 1 warning
tests/e2e/test_workflow_02_multi_tenant_isolation.py: 2 warnings
tests/e2e/test_workflow_08_connector_lifecycle.py: 2 warnings
tests/e2e/test_workflow_09_module_subscription.py: 2 warnings
tests/e2e/test_workflow_10_white_label_theming.py: 2 warnings
tests/e2e_cross_service/test_workflow_03_control_failure_to_risk.py: 2 warnings
tests/e2e_cross_service/test_workflow_04_risk_resolved_to_compliance.py: 2 warnings
tests/e2e_cross_service/test_workflow_05_policy_lifecycle.py: 3 warnings
tests/e2e_cross_service/test_workflow_06_vendor_risk_lifecycle.py: 2 warnings
tests/e2e_cross_service/test_workflow_07_auditor_portal.py: 2 warnings
tests/e2e_cross_service/test_workflow_11_compliance_scoring_trend.py: 4 warnings
tests/e2e_cross_service/test_workflow_12_evidence_bundle.py: 3 warnings
tests/test_acceptance.py: 4 warnings
tests/test_agent/test_drilldown.py: 3 warnings
tests/test_agent_ingest/test_drilldown.py: 5 warnings
tests/test_agent_ingest/test_heartbeat.py: 6 warnings
tests/test_agent_ingest/test_metadata.py: 9 warnings
tests/test_agent_ingest/test_register.py: 6 warnings
tests/test_ai_security/test_ai_security_module.py: 10 warnings
tests/test_asset_taxonomy_model.py: 6 warnings
tests/test_asset_taxonomy_routes.py: 23 warnings
tests/test_asset_taxonomy_service.py: 10 warnings
tests/test_assets/test_asset_backfill.py: 3 warnings
tests/test_assets/test_asset_connector_integration.py: 4 warnings
tests/test_assets/test_asset_model.py: 6 warnings
tests/test_assets/test_asset_routes.py: 16 warnings
tests/test_assets/test_asset_service.py: 17 warnings
tests/test_assets/test_sample_response.py: 1 warning
tests/test_attack_path/test_attack_path_module.py: 9 warnings
tests/test_audit_fix_medium.py: 12 warnings
tests/test_audit_high/test_h3_connector_ssrf.py: 19 warnings
tests/test_audit_high/test_h4_login_timing.py: 1 warning
tests/test_audit_high/test_h6_signature_replay.py: 2 warnings
tests/test_audit_low/test_low_fixes.py: 3 warnings
tests/test_auth.py: 5 warnings
tests/test_auto_remediation/test_auto_remediation_service.py: 8 warnings
tests/test_auto_remediation/test_executor_audit.py: 1 warning
tests/test_backend_gaps_auth.py: 4 warnings
tests/test_backend_gaps_branding.py: 7 warnings
tests/test_backend_gaps_scoring.py: 6 warnings
tests/test_connector_framework/test_base.py: 4 warnings
tests/test_critfix_audit_log/test_audit_log_coverage.py: 16 warnings
tests/test_critfix_auth/test_crit007_module_gates.py: 40 warnings
tests/test_critfix_auth/test_high006_tenant_active.py: 4 warnings
tests/test_critfix_auth/test_high007_subscription_expiry.py: 4 warnings
tests/test_critfix_auth/test_high008_login_audit.py: 7 warnings
tests/test_critfix_validation/test_high004_sort_allowlist.py: 5 warnings
tests/test_critfix_validation/test_high009_rate_limit.py: 3 warnings
tests/test_critfix_validation/test_high012_taxonomy_regex.py: 4 warnings
tests/test_critfix_validation/test_new5_fernet_key_param.py: 2 warnings
tests/test_cspm/test_cis_seeders.py: 4 warnings
tests/test_cspm/test_cspm_engine.py: 4 warnings
tests/test_cspm/test_cspm_routes.py: 13 warnings
tests/test_dashboard.py: 5 warnings
tests/test_dspm/test_dspm_module.py: 11 warnings
tests/test_intelligence_engine/test_advisory_applicability.py: 4 warnings
tests/test_intelligence_engine/test_asset_fingerprint.py: 2 warnings
tests/test_module_gate.py: 5 warnings
tests/test_module_subscription.py: 16 warnings
tests/test_multi_tenant_isolation.py: 4 warnings
tests/test_multi_tenant_isolation_extended.py: 7 warnings
tests/test_multi_tenant_model.py: 8 warnings
tests/test_rbac/test_legacy_rbac.py: 4 warnings
tests/test_rbac/test_scope_enforcement.py: 8 warnings
tests/test_remediation.py: 3 warnings
tests/test_reports.py: 4 warnings
tests/test_risk_aggregate.py: 5 warnings
tests/test_risk_aggregate_service.py: 17 warnings
tests/test_risk_index/test_risk_index_routes.py: 11 warnings
tests/test_risk_index/test_risk_index_service.py: 15 warnings
tests/test_risk_quantification/test_risk_quantification_module.py: 10 warnings
tests/test_risk_summary_routes.py: 14 warnings
tests/test_risks.py: 8 warnings
tests/test_routers/test_connectors_metadata.py: 14 warnings
tests/test_routers/test_connectors_router.py: 25 warnings
tests/test_routers/test_threat_intel_word_cloud.py: 6 warnings
tests/test_seed_simulators_audit_log.py: 6 warnings
tests/test_seed_simulators_credentials.py: 4 warnings
tests/test_services/test_event_subscribers.py: 9 warnings
tests/test_shared/test_distributed_events.py: 8 warnings
tests/test_shared/test_event_wiring.py: 5 warnings
tests/test_shared/test_redis_client.py: 3 warnings
tests/test_tenant_onboarding.py: 13 warnings
tests/test_ticketing/test_ticketing_audit.py: 2 warnings
tests/test_ticketing/test_ticketing_service.py: 7 warnings
tests/test_ticketing/test_ticketing_webhooks.py: 5 warnings
tests/test_trust_center/test_trust_center_routes.py: 6 warnings
tests/test_trust_center/test_trust_center_service.py: 13 warnings
tests/test_trust_center/test_trust_center_streaming.py: 10 warnings
tests/test_vapt/test_vapt_retest_flow.py: 6 warnings
tests/test_vapt/test_vapt_security.py: 12 warnings
tests/test_vapt/test_vapt_submission_pipeline.py: 5 warnings
tests/test_vapt/test_vapt_vendor_invitation.py: 8 warnings
tests/test_vapt/test_vapt_vendor_models.py: 5 warnings
tests/test_vapt/test_vapt_vendor_routes.py: 16 warnings
tests/test_ztna/test_ztna_module.py: 10 warnings
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:1125: DeprecationWarning: 'asyncio.set_event_loop_policy' is deprecated and slated for removal in Python 3.16
    asyncio.set_event_loop_policy(new_loop_policy)

tests/e2e/test_workflow_01_tenant_to_first_risk.py: 1 warning
tests/e2e/test_workflow_02_multi_tenant_isolation.py: 2 warnings
tests/e2e/test_workflow_08_connector_lifecycle.py: 2 warnings
tests/e2e/test_workflow_09_module_subscription.py: 2 warnings
tests/e2e/test_workflow_10_white_label_theming.py: 2 warnings
tests/e2e_cross_service/test_workflow_03_control_failure_to_risk.py: 2 warnings
tests/e2e_cross_service/test_workflow_04_risk_resolved_to_compliance.py: 2 warnings
tests/e2e_cross_service/test_workflow_05_policy_lifecycle.py: 3 warnings
tests/e2e_cross_service/test_workflow_06_vendor_risk_lifecycle.py: 2 warnings
tests/e2e_cross_service/test_workflow_07_auditor_portal.py: 2 warnings
tests/e2e_cross_service/test_workflow_11_compliance_scoring_trend.py: 4 warnings
tests/e2e_cross_service/test_workflow_12_evidence_bundle.py: 3 warnings
tests/test_acceptance.py: 4 warnings
tests/test_agent/test_drilldown.py: 3 warnings
tests/test_agent_ingest/test_drilldown.py: 5 warnings
tests/test_agent_ingest/test_heartbeat.py: 6 warnings
tests/test_agent_ingest/test_metadata.py: 9 warnings
tests/test_agent_ingest/test_register.py: 6 warnings
tests/test_ai_security/test_ai_security_module.py: 10 warnings
tests/test_asset_taxonomy_model.py: 6 warnings
tests/test_asset_taxonomy_routes.py: 23 warnings
tests/test_asset_taxonomy_service.py: 10 warnings
tests/test_assets/test_asset_backfill.py: 3 warnings
tests/test_assets/test_asset_connector_integration.py: 4 warnings
tests/test_assets/test_asset_model.py: 6 warnings
tests/test_assets/test_asset_routes.py: 16 warnings
tests/test_assets/test_asset_service.py: 17 warnings
tests/test_assets/test_sample_response.py: 1 warning
tests/test_attack_path/test_attack_path_module.py: 9 warnings
tests/test_audit_fix_medium.py: 12 warnings
tests/test_audit_high/test_h3_connector_ssrf.py: 19 warnings
tests/test_audit_high/test_h4_login_timing.py: 1 warning
tests/test_audit_high/test_h6_signature_replay.py: 2 warnings
tests/test_audit_low/test_low_fixes.py: 3 warnings
tests/test_auth.py: 5 warnings
tests/test_auto_remediation/test_auto_remediation_service.py: 8 warnings
tests/test_auto_remediation/test_executor_audit.py: 1 warning
tests/test_backend_gaps_auth.py: 4 warnings
tests/test_backend_gaps_branding.py: 7 warnings
tests/test_backend_gaps_scoring.py: 6 warnings
tests/test_connector_framework/test_base.py: 4 warnings
tests/test_critfix_audit_log/test_audit_log_coverage.py: 16 warnings
tests/test_critfix_auth/test_crit007_module_gates.py: 40 warnings
tests/test_critfix_auth/test_high006_tenant_active.py: 4 warnings
tests/test_critfix_auth/test_high007_subscription_expiry.py: 4 warnings
tests/test_critfix_auth/test_high008_login_audit.py: 7 warnings
tests/test_critfix_validation/test_high004_sort_allowlist.py: 5 warnings
tests/test_critfix_validation/test_high009_rate_limit.py: 3 warnings
tests/test_critfix_validation/test_high012_taxonomy_regex.py: 4 warnings
tests/test_critfix_validation/test_new5_fernet_key_param.py: 2 warnings
tests/test_cspm/test_cis_seeders.py: 4 warnings
tests/test_cspm/test_cspm_engine.py: 4 warnings
tests/test_cspm/test_cspm_routes.py: 13 warnings
tests/test_dashboard.py: 5 warnings
tests/test_dspm/test_dspm_module.py: 11 warnings
tests/test_intelligence_engine/test_advisory_applicability.py: 4 warnings
tests/test_intelligence_engine/test_asset_fingerprint.py: 2 warnings
tests/test_module_gate.py: 5 warnings
tests/test_module_subscription.py: 16 warnings
tests/test_multi_tenant_isolation.py: 4 warnings
tests/test_multi_tenant_isolation_extended.py: 7 warnings
tests/test_multi_tenant_model.py: 8 warnings
tests/test_rbac/test_legacy_rbac.py: 4 warnings
tests/test_rbac/test_scope_enforcement.py: 8 warnings
tests/test_remediation.py: 3 warnings
tests/test_reports.py: 4 warnings
tests/test_risk_aggregate.py: 5 warnings
tests/test_risk_aggregate_service.py: 17 warnings
tests/test_risk_index/test_risk_index_routes.py: 11 warnings
tests/test_risk_index/test_risk_index_service.py: 15 warnings
tests/test_risk_quantification/test_risk_quantification_module.py: 10 warnings
tests/test_risk_summary_routes.py: 14 warnings
tests/test_risks.py: 8 warnings
tests/test_routers/test_connectors_metadata.py: 14 warnings
tests/test_routers/test_connectors_router.py: 25 warnings
tests/test_routers/test_threat_intel_word_cloud.py: 6 warnings
tests/test_seed_simulators_audit_log.py: 6 warnings
tests/test_seed_simulators_credentials.py: 4 warnings
tests/test_services/test_event_subscribers.py: 9 warnings
tests/test_shared/test_distributed_events.py: 8 warnings
tests/test_shared/test_event_wiring.py: 5 warnings
tests/test_shared/test_redis_client.py: 3 warnings
tests/test_tenant_onboarding.py: 13 warnings
tests/test_ticketing/test_ticketing_audit.py: 2 warnings
tests/test_ticketing/test_ticketing_service.py: 7 warnings
tests/test_ticketing/test_ticketing_webhooks.py: 5 warnings
tests/test_trust_center/test_trust_center_routes.py: 6 warnings
tests/test_trust_center/test_trust_center_service.py: 13 warnings
tests/test_trust_center/test_trust_center_streaming.py: 10 warnings
tests/test_vapt/test_vapt_retest_flow.py: 6 warnings
tests/test_vapt/test_vapt_security.py: 12 warnings
tests/test_vapt/test_vapt_submission_pipeline.py: 5 warnings
tests/test_vapt/test_vapt_vendor_invitation.py: 8 warnings
tests/test_vapt/test_vapt_vendor_models.py: 5 warnings
tests/test_vapt/test_vapt_vendor_routes.py: 16 warnings
tests/test_ztna/test_ztna_module.py: 10 warnings
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:1126: DeprecationWarning: 'asyncio.get_event_loop_policy' is deprecated and slated for removal in Python 3.16
    loop = asyncio.get_event_loop_policy().new_event_loop()

tests/e2e/test_workflow_01_tenant_to_first_risk.py: 1 warning
tests/e2e/test_workflow_02_multi_tenant_isolation.py: 2 warnings
tests/e2e/test_workflow_08_connector_lifecycle.py: 2 warnings
tests/e2e/test_workflow_09_module_subscription.py: 2 warnings
tests/e2e/test_workflow_10_white_label_theming.py: 2 warnings
tests/e2e_cross_service/test_workflow_03_control_failure_to_risk.py: 2 warnings
tests/e2e_cross_service/test_workflow_04_risk_resolved_to_compliance.py: 2 warnings
tests/e2e_cross_service/test_workflow_05_policy_lifecycle.py: 3 warnings
tests/e2e_cross_service/test_workflow_06_vendor_risk_lifecycle.py: 2 warnings
tests/e2e_cross_service/test_workflow_07_auditor_portal.py: 2 warnings
tests/e2e_cross_service/test_workflow_11_compliance_scoring_trend.py: 4 warnings
tests/e2e_cross_service/test_workflow_12_evidence_bundle.py: 3 warnings
tests/test_acceptance.py: 4 warnings
tests/test_agent/test_drilldown.py: 3 warnings
tests/test_agent_ingest/test_drilldown.py: 5 warnings
tests/test_agent_ingest/test_heartbeat.py: 6 warnings
tests/test_agent_ingest/test_metadata.py: 9 warnings
tests/test_agent_ingest/test_register.py: 6 warnings
tests/test_ai_security/test_ai_security_module.py: 10 warnings
tests/test_asset_taxonomy_model.py: 6 warnings
tests/test_asset_taxonomy_routes.py: 23 warnings
tests/test_asset_taxonomy_service.py: 10 warnings
tests/test_assets/test_asset_backfill.py: 3 warnings
tests/test_assets/test_asset_connector_integration.py: 4 warnings
tests/test_assets/test_asset_model.py: 6 warnings
tests/test_assets/test_asset_routes.py: 16 warnings
tests/test_assets/test_asset_service.py: 17 warnings
tests/test_assets/test_sample_response.py: 1 warning
tests/test_attack_path/test_attack_path_module.py: 9 warnings
tests/test_audit_fix_medium.py: 12 warnings
tests/test_audit_high/test_h3_connector_ssrf.py: 19 warnings
tests/test_audit_high/test_h4_login_timing.py: 1 warning
tests/test_audit_high/test_h6_signature_replay.py: 2 warnings
tests/test_audit_low/test_low_fixes.py: 3 warnings
tests/test_auth.py: 5 warnings
tests/test_auto_remediation/test_auto_remediation_service.py: 8 warnings
tests/test_auto_remediation/test_executor_audit.py: 1 warning
tests/test_backend_gaps_auth.py: 4 warnings
tests/test_backend_gaps_branding.py: 7 warnings
tests/test_backend_gaps_scoring.py: 6 warnings
tests/test_connector_framework/test_base.py: 4 warnings
tests/test_critfix_audit_log/test_audit_log_coverage.py: 16 warnings
tests/test_critfix_auth/test_crit007_module_gates.py: 40 warnings
tests/test_critfix_auth/test_high006_tenant_active.py: 4 warnings
tests/test_critfix_auth/test_high007_subscription_expiry.py: 4 warnings
tests/test_critfix_auth/test_high008_login_audit.py: 7 warnings
tests/test_critfix_validation/test_high004_sort_allowlist.py: 5 warnings
tests/test_critfix_validation/test_high009_rate_limit.py: 3 warnings
tests/test_critfix_validation/test_high012_taxonomy_regex.py: 4 warnings
tests/test_critfix_validation/test_new5_fernet_key_param.py: 2 warnings
tests/test_cspm/test_cis_seeders.py: 4 warnings
tests/test_cspm/test_cspm_engine.py: 4 warnings
tests/test_cspm/test_cspm_routes.py: 13 warnings
tests/test_dashboard.py: 5 warnings
tests/test_dspm/test_dspm_module.py: 11 warnings
tests/test_intelligence_engine/test_advisory_applicability.py: 4 warnings
tests/test_intelligence_engine/test_asset_fingerprint.py: 2 warnings
tests/test_module_gate.py: 5 warnings
tests/test_module_subscription.py: 16 warnings
tests/test_multi_tenant_isolation.py: 4 warnings
tests/test_multi_tenant_isolation_extended.py: 7 warnings
tests/test_multi_tenant_model.py: 8 warnings
tests/test_rbac/test_legacy_rbac.py: 4 warnings
tests/test_rbac/test_scope_enforcement.py: 8 warnings
tests/test_remediation.py: 3 warnings
tests/test_reports.py: 4 warnings
tests/test_risk_aggregate.py: 5 warnings
tests/test_risk_aggregate_service.py: 17 warnings
tests/test_risk_index/test_risk_index_routes.py: 11 warnings
tests/test_risk_index/test_risk_index_service.py: 15 warnings
tests/test_risk_quantification/test_risk_quantification_module.py: 10 warnings
tests/test_risk_summary_routes.py: 14 warnings
tests/test_risks.py: 8 warnings
tests/test_routers/test_connectors_metadata.py: 14 warnings
tests/test_routers/test_connectors_router.py: 25 warnings
tests/test_routers/test_threat_intel_word_cloud.py: 6 warnings
tests/test_seed_simulators_audit_log.py: 6 warnings
tests/test_seed_simulators_credentials.py: 4 warnings
tests/test_services/test_event_subscribers.py: 9 warnings
tests/test_shared/test_distributed_events.py: 8 warnings
tests/test_shared/test_event_wiring.py: 5 warnings
tests/test_shared/test_redis_client.py: 3 warnings
tests/test_tenant_onboarding.py: 13 warnings
tests/test_ticketing/test_ticketing_audit.py: 2 warnings
tests/test_ticketing/test_ticketing_service.py: 7 warnings
tests/test_ticketing/test_ticketing_webhooks.py: 5 warnings
tests/test_trust_center/test_trust_center_routes.py: 6 warnings
tests/test_trust_center/test_trust_center_service.py: 13 warnings
tests/test_trust_center/test_trust_center_streaming.py: 10 warnings
tests/test_vapt/test_vapt_retest_flow.py: 6 warnings
tests/test_vapt/test_vapt_security.py: 12 warnings
tests/test_vapt/test_vapt_submission_pipeline.py: 5 warnings
tests/test_vapt/test_vapt_vendor_invitation.py: 8 warnings
tests/test_vapt/test_vapt_vendor_models.py: 5 warnings
tests/test_vapt/test_vapt_vendor_routes.py: 16 warnings
tests/test_ztna/test_ztna_module.py: 10 warnings
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:859: DeprecationWarning: 'asyncio.get_event_loop_policy' is deprecated and slated for removal in Python 3.16
    policy = asyncio.get_event_loop_policy()

tests/e2e/test_workflow_01_tenant_to_first_risk.py: 1 warning
tests/e2e/test_workflow_02_multi_tenant_isolation.py: 2 warnings
tests/e2e/test_workflow_08_connector_lifecycle.py: 2 warnings
tests/e2e/test_workflow_09_module_subscription.py: 2 warnings
tests/e2e/test_workflow_10_white_label_theming.py: 2 warnings
tests/e2e_cross_service/test_workflow_03_control_failure_to_risk.py: 2 warnings
tests/e2e_cross_service/test_workflow_04_risk_resolved_to_compliance.py: 2 warnings
tests/e2e_cross_service/test_workflow_05_policy_lifecycle.py: 3 warnings
tests/e2e_cross_service/test_workflow_06_vendor_risk_lifecycle.py: 2 warnings
tests/e2e_cross_service/test_workflow_07_auditor_portal.py: 2 warnings
tests/e2e_cross_service/test_workflow_11_compliance_scoring_trend.py: 4 warnings
tests/e2e_cross_service/test_workflow_12_evidence_bundle.py: 3 warnings
tests/test_acceptance.py: 4 warnings
tests/test_agent/test_drilldown.py: 3 warnings
tests/test_agent_ingest/test_drilldown.py: 5 warnings
tests/test_agent_ingest/test_heartbeat.py: 6 warnings
tests/test_agent_ingest/test_metadata.py: 9 warnings
tests/test_agent_ingest/test_register.py: 6 warnings
tests/test_ai_security/test_ai_security_module.py: 10 warnings
tests/test_asset_taxonomy_model.py: 6 warnings
tests/test_asset_taxonomy_routes.py: 23 warnings
tests/test_asset_taxonomy_service.py: 10 warnings
tests/test_assets/test_asset_backfill.py: 3 warnings
tests/test_assets/test_asset_connector_integration.py: 4 warnings
tests/test_assets/test_asset_model.py: 6 warnings
tests/test_assets/test_asset_routes.py: 16 warnings
tests/test_assets/test_asset_service.py: 17 warnings
tests/test_assets/test_sample_response.py: 1 warning
tests/test_attack_path/test_attack_path_module.py: 9 warnings
tests/test_audit_fix_medium.py: 12 warnings
tests/test_audit_high/test_h3_connector_ssrf.py: 19 warnings
tests/test_audit_high/test_h4_login_timing.py: 1 warning
tests/test_audit_high/test_h6_signature_replay.py: 2 warnings
tests/test_audit_low/test_low_fixes.py: 3 warnings
tests/test_auth.py: 5 warnings
tests/test_auto_remediation/test_auto_remediation_service.py: 8 warnings
tests/test_auto_remediation/test_executor_audit.py: 1 warning
tests/test_backend_gaps_auth.py: 4 warnings
tests/test_backend_gaps_branding.py: 7 warnings
tests/test_backend_gaps_scoring.py: 6 warnings
tests/test_connector_framework/test_base.py: 4 warnings
tests/test_critfix_audit_log/test_audit_log_coverage.py: 16 warnings
tests/test_critfix_auth/test_crit007_module_gates.py: 40 warnings
tests/test_critfix_auth/test_high006_tenant_active.py: 4 warnings
tests/test_critfix_auth/test_high007_subscription_expiry.py: 4 warnings
tests/test_critfix_auth/test_high008_login_audit.py: 7 warnings
tests/test_critfix_validation/test_high004_sort_allowlist.py: 5 warnings
tests/test_critfix_validation/test_high009_rate_limit.py: 3 warnings
tests/test_critfix_validation/test_high012_taxonomy_regex.py: 4 warnings
tests/test_critfix_validation/test_new5_fernet_key_param.py: 2 warnings
tests/test_cspm/test_cis_seeders.py: 4 warnings
tests/test_cspm/test_cspm_engine.py: 4 warnings
tests/test_cspm/test_cspm_routes.py: 13 warnings
tests/test_dashboard.py: 5 warnings
tests/test_dspm/test_dspm_module.py: 11 warnings
tests/test_intelligence_engine/test_advisory_applicability.py: 4 warnings
tests/test_intelligence_engine/test_asset_fingerprint.py: 2 warnings
tests/test_module_gate.py: 5 warnings
tests/test_module_subscription.py: 16 warnings
tests/test_multi_tenant_isolation.py: 4 warnings
tests/test_multi_tenant_isolation_extended.py: 7 warnings
tests/test_multi_tenant_model.py: 8 warnings
tests/test_rbac/test_legacy_rbac.py: 4 warnings
tests/test_rbac/test_scope_enforcement.py: 8 warnings
tests/test_remediation.py: 3 warnings
tests/test_reports.py: 4 warnings
tests/test_risk_aggregate.py: 5 warnings
tests/test_risk_aggregate_service.py: 17 warnings
tests/test_risk_index/test_risk_index_routes.py: 11 warnings
tests/test_risk_index/test_risk_index_service.py: 15 warnings
tests/test_risk_quantification/test_risk_quantification_module.py: 10 warnings
tests/test_risk_summary_routes.py: 14 warnings
tests/test_risks.py: 8 warnings
tests/test_routers/test_connectors_metadata.py: 14 warnings
tests/test_routers/test_connectors_router.py: 25 warnings
tests/test_routers/test_threat_intel_word_cloud.py: 6 warnings
tests/test_seed_simulators_audit_log.py: 6 warnings
tests/test_seed_simulators_credentials.py: 4 warnings
tests/test_services/test_event_subscribers.py: 9 warnings
tests/test_shared/test_distributed_events.py: 8 warnings
tests/test_shared/test_event_wiring.py: 5 warnings
tests/test_shared/test_redis_client.py: 3 warnings
tests/test_tenant_onboarding.py: 13 warnings
tests/test_ticketing/test_ticketing_audit.py: 2 warnings
tests/test_ticketing/test_ticketing_service.py: 7 warnings
tests/test_ticketing/test_ticketing_webhooks.py: 5 warnings
tests/test_trust_center/test_trust_center_routes.py: 6 warnings
tests/test_trust_center/test_trust_center_service.py: 13 warnings
tests/test_trust_center/test_trust_center_streaming.py: 10 warnings
tests/test_vapt/test_vapt_retest_flow.py: 6 warnings
tests/test_vapt/test_vapt_security.py: 12 warnings
tests/test_vapt/test_vapt_submission_pipeline.py: 5 warnings
tests/test_vapt/test_vapt_vendor_invitation.py: 8 warnings
tests/test_vapt/test_vapt_vendor_models.py: 5 warnings
tests/test_vapt/test_vapt_vendor_routes.py: 16 warnings
tests/test_ztna/test_ztna_module.py: 10 warnings
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:904: DeprecationWarning: 'asyncio.get_event_loop_policy' is deprecated and slated for removal in Python 3.16
    policy = asyncio.get_event_loop_policy()

tests/e2e/test_workflow_01_tenant_to_first_risk.py: 1 warning
tests/e2e/test_workflow_02_multi_tenant_isolation.py: 2 warnings
tests/e2e/test_workflow_08_connector_lifecycle.py: 2 warnings
tests/e2e/test_workflow_09_module_subscription.py: 2 warnings
tests/e2e/test_workflow_10_white_label_theming.py: 2 warnings
tests/e2e_cross_service/test_workflow_03_control_failure_to_risk.py: 2 warnings
tests/e2e_cross_service/test_workflow_04_risk_resolved_to_compliance.py: 2 warnings
tests/e2e_cross_service/test_workflow_05_policy_lifecycle.py: 3 warnings
tests/e2e_cross_service/test_workflow_06_vendor_risk_lifecycle.py: 2 warnings
tests/e2e_cross_service/test_workflow_07_auditor_portal.py: 2 warnings
tests/e2e_cross_service/test_workflow_11_compliance_scoring_trend.py: 4 warnings
tests/e2e_cross_service/test_workflow_12_evidence_bundle.py: 3 warnings
tests/test_acceptance.py: 4 warnings
tests/test_agent/test_drilldown.py: 3 warnings
tests/test_agent_ingest/test_drilldown.py: 5 warnings
tests/test_agent_ingest/test_heartbeat.py: 6 warnings
tests/test_agent_ingest/test_metadata.py: 9 warnings
tests/test_agent_ingest/test_register.py: 6 warnings
tests/test_ai_security/test_ai_security_module.py: 10 warnings
tests/test_asset_taxonomy_model.py: 6 warnings
tests/test_asset_taxonomy_routes.py: 23 warnings
tests/test_asset_taxonomy_service.py: 10 warnings
tests/test_assets/test_asset_backfill.py: 3 warnings
tests/test_assets/test_asset_connector_integration.py: 4 warnings
tests/test_assets/test_asset_model.py: 6 warnings
tests/test_assets/test_asset_routes.py: 16 warnings
tests/test_assets/test_asset_service.py: 17 warnings
tests/test_assets/test_sample_response.py: 1 warning
tests/test_attack_path/test_attack_path_module.py: 9 warnings
tests/test_audit_fix_medium.py: 12 warnings
tests/test_audit_high/test_h3_connector_ssrf.py: 19 warnings
tests/test_audit_high/test_h4_login_timing.py: 1 warning
tests/test_audit_high/test_h6_signature_replay.py: 2 warnings
tests/test_audit_low/test_low_fixes.py: 3 warnings
tests/test_auth.py: 5 warnings
tests/test_auto_remediation/test_auto_remediation_service.py: 8 warnings
tests/test_auto_remediation/test_executor_audit.py: 1 warning
tests/test_backend_gaps_auth.py: 4 warnings
tests/test_backend_gaps_branding.py: 7 warnings
tests/test_backend_gaps_scoring.py: 6 warnings
tests/test_connector_framework/test_base.py: 4 warnings
tests/test_critfix_audit_log/test_audit_log_coverage.py: 16 warnings
tests/test_critfix_auth/test_crit007_module_gates.py: 40 warnings
tests/test_critfix_auth/test_high006_tenant_active.py: 4 warnings
tests/test_critfix_auth/test_high007_subscription_expiry.py: 4 warnings
tests/test_critfix_auth/test_high008_login_audit.py: 7 warnings
tests/test_critfix_validation/test_high004_sort_allowlist.py: 5 warnings
tests/test_critfix_validation/test_high009_rate_limit.py: 3 warnings
tests/test_critfix_validation/test_high012_taxonomy_regex.py: 4 warnings
tests/test_critfix_validation/test_new5_fernet_key_param.py: 2 warnings
tests/test_cspm/test_cis_seeders.py: 4 warnings
tests/test_cspm/test_cspm_engine.py: 4 warnings
tests/test_cspm/test_cspm_routes.py: 13 warnings
tests/test_dashboard.py: 5 warnings
tests/test_dspm/test_dspm_module.py: 11 warnings
tests/test_intelligence_engine/test_advisory_applicability.py: 4 warnings
tests/test_intelligence_engine/test_asset_fingerprint.py: 2 warnings
tests/test_module_gate.py: 5 warnings
tests/test_module_subscription.py: 16 warnings
tests/test_multi_tenant_isolation.py: 4 warnings
tests/test_multi_tenant_isolation_extended.py: 7 warnings
tests/test_multi_tenant_model.py: 8 warnings
tests/test_rbac/test_legacy_rbac.py: 4 warnings
tests/test_rbac/test_scope_enforcement.py: 8 warnings
tests/test_remediation.py: 3 warnings
tests/test_reports.py: 4 warnings
tests/test_risk_aggregate.py: 5 warnings
tests/test_risk_aggregate_service.py: 17 warnings
tests/test_risk_index/test_risk_index_routes.py: 11 warnings
tests/test_risk_index/test_risk_index_service.py: 15 warnings
tests/test_risk_quantification/test_risk_quantification_module.py: 10 warnings
tests/test_risk_summary_routes.py: 14 warnings
tests/test_risks.py: 8 warnings
tests/test_routers/test_connectors_metadata.py: 14 warnings
tests/test_routers/test_connectors_router.py: 25 warnings
tests/test_routers/test_threat_intel_word_cloud.py: 6 warnings
tests/test_seed_simulators_audit_log.py: 6 warnings
tests/test_seed_simulators_credentials.py: 4 warnings
tests/test_services/test_event_subscribers.py: 9 warnings
tests/test_shared/test_distributed_events.py: 8 warnings
tests/test_shared/test_event_wiring.py: 5 warnings
tests/test_shared/test_redis_client.py: 3 warnings
tests/test_tenant_onboarding.py: 13 warnings
tests/test_ticketing/test_ticketing_audit.py: 2 warnings
tests/test_ticketing/test_ticketing_service.py: 7 warnings
tests/test_ticketing/test_ticketing_webhooks.py: 5 warnings
tests/test_trust_center/test_trust_center_routes.py: 6 warnings
tests/test_trust_center/test_trust_center_service.py: 13 warnings
tests/test_trust_center/test_trust_center_streaming.py: 10 warnings
tests/test_vapt/test_vapt_retest_flow.py: 6 warnings
tests/test_vapt/test_vapt_security.py: 12 warnings
tests/test_vapt/test_vapt_submission_pipeline.py: 5 warnings
tests/test_vapt/test_vapt_vendor_invitation.py: 8 warnings
tests/test_vapt/test_vapt_vendor_models.py: 5 warnings
tests/test_vapt/test_vapt_vendor_routes.py: 16 warnings
tests/test_ztna/test_ztna_module.py: 10 warnings
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:928: DeprecationWarning: 'asyncio.set_event_loop_policy' is deprecated and slated for removal in Python 3.16
    asyncio.set_event_loop_policy(previous_policy)

tests/e2e/test_workflow_01_tenant_to_first_risk.py: 1 warning
tests/e2e/test_workflow_02_multi_tenant_isolation.py: 2 warnings
tests/e2e/test_workflow_08_connector_lifecycle.py: 2 warnings
tests/e2e/test_workflow_09_module_subscription.py: 2 warnings
tests/e2e/test_workflow_10_white_label_theming.py: 2 warnings
tests/e2e_cross_service/test_workflow_03_control_failure_to_risk.py: 2 warnings
tests/e2e_cross_service/test_workflow_04_risk_resolved_to_compliance.py: 2 warnings
tests/e2e_cross_service/test_workflow_05_policy_lifecycle.py: 3 warnings
tests/e2e_cross_service/test_workflow_06_vendor_risk_lifecycle.py: 2 warnings
tests/e2e_cross_service/test_workflow_07_auditor_portal.py: 2 warnings
tests/e2e_cross_service/test_workflow_11_compliance_scoring_trend.py: 4 warnings
tests/e2e_cross_service/test_workflow_12_evidence_bundle.py: 3 warnings
tests/test_acceptance.py: 4 warnings
tests/test_agent/test_drilldown.py: 3 warnings
tests/test_agent_ingest/test_drilldown.py: 5 warnings
tests/test_agent_ingest/test_heartbeat.py: 6 warnings
tests/test_agent_ingest/test_metadata.py: 9 warnings
tests/test_agent_ingest/test_register.py: 6 warnings
tests/test_ai_security/test_ai_security_module.py: 10 warnings
tests/test_asset_taxonomy_model.py: 6 warnings
tests/test_asset_taxonomy_routes.py: 23 warnings
tests/test_asset_taxonomy_service.py: 10 warnings
tests/test_assets/test_asset_backfill.py: 3 warnings
tests/test_assets/test_asset_connector_integration.py: 4 warnings
tests/test_assets/test_asset_model.py: 6 warnings
tests/test_assets/test_asset_routes.py: 16 warnings
tests/test_assets/test_asset_service.py: 17 warnings
tests/test_assets/test_sample_response.py: 1 warning
tests/test_attack_path/test_attack_path_module.py: 9 warnings
tests/test_audit_fix_medium.py: 12 warnings
tests/test_audit_high/test_h3_connector_ssrf.py: 19 warnings
tests/test_audit_high/test_h4_login_timing.py: 1 warning
tests/test_audit_high/test_h6_signature_replay.py: 2 warnings
tests/test_audit_low/test_low_fixes.py: 3 warnings
tests/test_auth.py: 5 warnings
tests/test_auto_remediation/test_auto_remediation_service.py: 8 warnings
tests/test_auto_remediation/test_executor_audit.py: 1 warning
tests/test_backend_gaps_auth.py: 4 warnings
tests/test_backend_gaps_branding.py: 7 warnings
tests/test_backend_gaps_scoring.py: 6 warnings
tests/test_connector_framework/test_base.py: 4 warnings
tests/test_critfix_audit_log/test_audit_log_coverage.py: 16 warnings
tests/test_critfix_auth/test_crit007_module_gates.py: 40 warnings
tests/test_critfix_auth/test_high006_tenant_active.py: 4 warnings
tests/test_critfix_auth/test_high007_subscription_expiry.py: 4 warnings
tests/test_critfix_auth/test_high008_login_audit.py: 7 warnings
tests/test_critfix_validation/test_high004_sort_allowlist.py: 5 warnings
tests/test_critfix_validation/test_high009_rate_limit.py: 3 warnings
tests/test_critfix_validation/test_high012_taxonomy_regex.py: 4 warnings
tests/test_critfix_validation/test_new5_fernet_key_param.py: 2 warnings
tests/test_cspm/test_cis_seeders.py: 4 warnings
tests/test_cspm/test_cspm_engine.py: 4 warnings
tests/test_cspm/test_cspm_routes.py: 13 warnings
tests/test_dashboard.py: 5 warnings
tests/test_dspm/test_dspm_module.py: 11 warnings
tests/test_intelligence_engine/test_advisory_applicability.py: 4 warnings
tests/test_intelligence_engine/test_asset_fingerprint.py: 2 warnings
tests/test_module_gate.py: 5 warnings
tests/test_module_subscription.py: 16 warnings
tests/test_multi_tenant_isolation.py: 4 warnings
tests/test_multi_tenant_isolation_extended.py: 7 warnings
tests/test_multi_tenant_model.py: 8 warnings
tests/test_rbac/test_legacy_rbac.py: 4 warnings
tests/test_rbac/test_scope_enforcement.py: 8 warnings
tests/test_remediation.py: 3 warnings
tests/test_reports.py: 4 warnings
tests/test_risk_aggregate.py: 5 warnings
tests/test_risk_aggregate_service.py: 17 warnings
tests/test_risk_index/test_risk_index_routes.py: 11 warnings
tests/test_risk_index/test_risk_index_service.py: 15 warnings
tests/test_risk_quantification/test_risk_quantification_module.py: 10 warnings
tests/test_risk_summary_routes.py: 14 warnings
tests/test_risks.py: 8 warnings
tests/test_routers/test_connectors_metadata.py: 14 warnings
tests/test_routers/test_connectors_router.py: 25 warnings
tests/test_routers/test_threat_intel_word_cloud.py: 6 warnings
tests/test_seed_simulators_audit_log.py: 6 warnings
tests/test_seed_simulators_credentials.py: 4 warnings
tests/test_services/test_event_subscribers.py: 9 warnings
tests/test_shared/test_distributed_events.py: 8 warnings
tests/test_shared/test_event_wiring.py: 5 warnings
tests/test_shared/test_redis_client.py: 3 warnings
tests/test_tenant_onboarding.py: 13 warnings
tests/test_ticketing/test_ticketing_audit.py: 2 warnings
tests/test_ticketing/test_ticketing_service.py: 7 warnings
tests/test_ticketing/test_ticketing_webhooks.py: 5 warnings
tests/test_trust_center/test_trust_center_routes.py: 6 warnings
tests/test_trust_center/test_trust_center_service.py: 13 warnings
tests/test_trust_center/test_trust_center_streaming.py: 10 warnings
tests/test_vapt/test_vapt_retest_flow.py: 6 warnings
tests/test_vapt/test_vapt_security.py: 12 warnings
tests/test_vapt/test_vapt_submission_pipeline.py: 5 warnings
tests/test_vapt/test_vapt_vendor_invitation.py: 8 warnings
tests/test_vapt/test_vapt_vendor_models.py: 5 warnings
tests/test_vapt/test_vapt_vendor_routes.py: 16 warnings
tests/test_ztna/test_ztna_module.py: 10 warnings
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:940: DeprecationWarning: 'asyncio.get_event_loop_policy' is deprecated and slated for removal in Python 3.16
    policy = asyncio.get_event_loop_policy()

tests/e2e_cross_service/test_workflow_06_vendor_risk_lifecycle.py::test_workflow_06_vendor_risk_full_lifecycle
tests/e2e_cross_service/test_workflow_06_vendor_risk_lifecycle.py::test_workflow_06_vendor_isolation
  /private/tmp/urip_audit.AeKrB6/compliance/backend/compliance_backend/services/vendor_risk.py:53: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    onboarded_at=datetime.utcnow(),

tests/e2e_cross_service/test_workflow_07_auditor_portal.py::test_workflow_07_auditor_portal_full_cycle
  /private/tmp/urip_audit.AeKrB6/tests/e2e_cross_service/test_workflow_07_auditor_portal.py:79: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    period_start = datetime.utcnow() - timedelta(days=1)

tests/e2e_cross_service/test_workflow_07_auditor_portal.py::test_workflow_07_auditor_portal_full_cycle
  /private/tmp/urip_audit.AeKrB6/tests/e2e_cross_service/test_workflow_07_auditor_portal.py:80: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    period_end = datetime.utcnow() + timedelta(days=2)

tests/e2e_cross_service/test_workflow_07_auditor_portal.py::test_workflow_07_auditor_portal_full_cycle
  /private/tmp/urip_audit.AeKrB6/tests/e2e_cross_service/test_workflow_07_auditor_portal.py:91: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    captured_at=datetime.utcnow(),

tests/e2e_cross_service/test_workflow_11_compliance_scoring_trend.py::test_workflow_11_score_endpoint_returns_per_framework
  /private/tmp/urip_audit.AeKrB6/tests/e2e_cross_service/test_workflow_11_compliance_scoring_trend.py:72: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    now = datetime.utcnow()

tests/e2e_cross_service/test_workflow_11_compliance_scoring_trend.py::test_workflow_11_score_endpoint_returns_per_framework
tests/e2e_cross_service/test_workflow_11_compliance_scoring_trend.py::test_workflow_11_score_drop_emits_warning
  /private/tmp/urip_audit.AeKrB6/compliance/backend/compliance_backend/services/scoring_engine.py:95: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    as_of = as_of_date or datetime.utcnow()

tests/e2e_cross_service/test_workflow_11_compliance_scoring_trend.py::test_workflow_11_trend_returns_chronological_points
  /private/tmp/urip_audit.AeKrB6/tests/e2e_cross_service/test_workflow_11_compliance_scoring_trend.py:123: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    now = datetime.utcnow()

tests/e2e_cross_service/test_workflow_11_compliance_scoring_trend.py::test_workflow_11_trend_returns_chronological_points
  /private/tmp/urip_audit.AeKrB6/compliance/backend/compliance_backend/services/scoring_engine.py:215: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    cutoff = datetime.utcnow() - timedelta(days=days_back)

tests/e2e_cross_service/test_workflow_11_compliance_scoring_trend.py::test_workflow_11_score_drop_emits_warning
  /private/tmp/urip_audit.AeKrB6/tests/e2e_cross_service/test_workflow_11_compliance_scoring_trend.py:202: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    now = datetime.utcnow()

tests/e2e_cross_service/test_workflow_11_compliance_scoring_trend.py::test_workflow_11_score_drop_emits_warning
  /private/tmp/urip_audit.AeKrB6/compliance/backend/compliance_backend/services/scoring_engine.py:175: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    as_of = as_of_date or datetime.utcnow()

tests/test_connectors/test_cert_in.py::TestCertInFetchRSS::test_fetch_rss_empty
  /private/tmp/urip_audit.AeKrB6/connectors/cert_in/api_client.py:153: XMLParsedAsHTMLWarning: It looks like you're using an HTML parser to parse an XML document.
  
  Assuming this really is an XML document, what you're doing might work, but you should know that using an XML parser will be more reliable. To parse this document as XML, make sure you have the Python package 'lxml' installed, and pass the keyword argument `features="xml"` into the BeautifulSoup constructor.
  
  If you want or need to use an HTML parser on this document, you can make this warning go away by filtering it. To do that, run this code before calling the BeautifulSoup constructor:
  
      from bs4 import XMLParsedAsHTMLWarning
      import warnings
  
      warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
  
    soup = BeautifulSoup(html_text, "html.parser")

tests/test_critfix_auth/test_crit005_pyjwt_migration.py::test_decode_token_rejects_wrong_algorithm_token
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/jwt/api_jwt.py:147: InsecureKeyLengthWarning: The HMAC key is 44 bytes long, which is below the minimum recommended length of 64 bytes for SHA512. See RFC 7518 Section 3.2.
    return self._jws.encode(

tests/test_critfix_auth/test_crit005_pyjwt_migration.py::test_shared_uripverifier_accepts_pyjwt_token
tests/test_critfix_auth/test_crit005_pyjwt_migration.py::test_shared_uripverifier_rejects_tampered_token
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/jwt/api_jwt.py:147: InsecureKeyLengthWarning: The HMAC key is 23 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    return self._jws.encode(

tests/test_critfix_auth/test_crit005_pyjwt_migration.py::test_shared_uripverifier_accepts_pyjwt_token
tests/test_critfix_auth/test_crit005_pyjwt_migration.py::test_shared_uripverifier_rejects_tampered_token
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/jwt/api_jwt.py:365: InsecureKeyLengthWarning: The HMAC key is 23 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    decoded = self.decode_complete(

tests/test_shared/test_jwt_verifier.py::TestURIPVerifier::test_reject_wrong_secret
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/jwt/api_jwt.py:147: InsecureKeyLengthWarning: The HMAC key is 20 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    return self._jws.encode(

tests/test_vapt/test_vapt_vendor_invitation.py::test_jwt_signature_uses_jwt_secret_key
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/jwt/api_jwt.py:365: InsecureKeyLengthWarning: The HMAC key is 12 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    decoded = self.decode_complete(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/e2e_cross_service/test_workflow_03_control_failure_to_risk.py::test_workflow_03_control_failure_creates_urip_risk
FAILED tests/e2e_cross_service/test_workflow_04_risk_resolved_to_compliance.py::test_workflow_04_risk_resolved_triggers_re_evaluation
FAILED tests/e2e_cross_service/test_workflow_05_policy_lifecycle.py::test_workflow_05_policy_versioning_and_acknowledgments
FAILED tests/e2e_cross_service/test_workflow_05_policy_lifecycle.py::test_workflow_05_expiring_policy_surfaced
FAILED tests/e2e_cross_service/test_workflow_05_policy_lifecycle.py::test_workflow_05_policy_isolation_between_tenants
FAILED tests/e2e_cross_service/test_workflow_06_vendor_risk_lifecycle.py::test_workflow_06_vendor_risk_full_lifecycle
FAILED tests/e2e_cross_service/test_workflow_06_vendor_risk_lifecycle.py::test_workflow_06_vendor_isolation
FAILED tests/e2e_cross_service/test_workflow_07_auditor_portal.py::test_workflow_07_auditor_portal_full_cycle
FAILED tests/e2e_cross_service/test_workflow_12_evidence_bundle.py::test_workflow_12_evidence_bundle_zip_with_manifest
FAILED tests/e2e_cross_service/test_workflow_12_evidence_bundle.py::test_workflow_12_bundle_period_filter_isolates_periods
FAILED tests/e2e_cross_service/test_workflow_12_evidence_bundle.py::test_workflow_12_bundle_is_tenant_scoped
FAILED tests/test_critfix_auth/test_audit_fix_critical.py::test_af_crit3_env_file_does_not_carry_default_jwt_secret
FAILED tests/test_critfix_auth/test_audit_fix_critical.py::test_af_crit3_env_file_still_marked_dev_only
FAILED tests/test_critfix_auth/test_crit004_jwt_secret.py::test_env_file_marked_dev_only
FAILED tests/test_routers/test_connectors_metadata.py::TestListConnectorsMetadata::test_list_returns_metadata_for_every_connector[asyncio]
FAILED tests/test_routers/test_connectors_metadata.py::TestListConnectorsMetadata::test_list_filter_by_status[asyncio]
FAILED tests/test_routers/test_connectors_metadata.py::TestListConnectorsMetadata::test_list_pagination_still_works[asyncio]
FAILED tests/test_routers/test_connectors_metadata.py::TestListConnectorsMetadata::test_list_reflects_configured_flag[asyncio]
FAILED tests/test_routers/test_connectors_metadata.py::TestListConnectorsMetadata::test_list_cross_tenant_isolation[asyncio]
FAILED tests/test_routers/test_connectors_metadata.py::TestCategoriesAggregate::test_categories_returns_distinct_with_counts[asyncio]
FAILED tests/test_routers/test_connectors_router.py::TestListConnectors::test_list_returns_all_registered_connectors[asyncio]
21 failed, 2047 passed, 8 skipped, 6029 warnings in 335.97s (0:05:35)

exec
/bin/zsh -lc "cd /tmp/urip_audit.AeKrB6 && nl -ba .env.example | sed -n '1,200p'" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
exec
/bin/zsh -lc "cd /tmp/urip_audit.AeKrB6 && nl -ba compliance/backend/compliance_backend/models/compliance_audit_log.py | sed -n '1,120p'" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
     1	# URIP Environment Configuration
     2	# Copy this file to `.env` and fill real values for local dev.
     3	# Before deploying to staging or production, you MUST rotate every secret
     4	# below (especially JWT_SECRET_KEY) and set URIP_ENV=production.
     5	#
     6	# ─── SECRETS ROTATION PROCEDURE ──────────────────────────────────────────
     7	# Production secrets MUST live in a secrets manager (AWS Secrets Manager,
     8	# HashiCorp Vault, Doppler, 1Password Secrets Automation), NEVER on disk.
     9	#
    10	# Before first run:
    11	#   1. Generate a strong JWT secret:
    12	#        python3 -c 'import secrets; print(secrets.token_urlsafe(64))'
    13	#   2. Generate a Fernet key for credential encryption:
    14	#        python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
    15	#   3. Inject both via your secrets manager / orchestrator env vars.
    16	#   4. Set URIP_ENV=production. Backend refuses to start with the dev
    17	#      default `urip-dev-secret-change-in-production` in production-like
    18	#      envs (URIP_ENV in {prod, production, staging}).
    19	#
    20	# If a credential is suspected leaked:
    21	#   1. Rotate immediately at the source (Neon console, IAM, etc.).
    22	#   2. Generate a new JWT_SECRET_KEY — this invalidates ALL existing tokens.
    23	#   3. Audit DB query logs / access logs for unauthorised access.
    24	#   4. Re-deploy with the new secrets.
    25	#
    26	# DO NOT commit `.env`, `.env.production`, or any `.credentials.*` file
    27	# to git. These patterns are blocked by `.gitignore` for this reason.
    28	# ──────────────────────────────────────────────────────────────────────────
    29	
    30	# Set to: dev | development | staging | production | prod
    31	# In staging / prod the backend REFUSES TO START if JWT_SECRET_KEY is empty
    32	# or equal to the well-known dev default.
    33	URIP_ENV=dev
    34	
    35	DATABASE_URL=postgresql+asyncpg://urip:urip_dev@localhost:5432/urip
    36	
    37	# !!! ROTATE BEFORE PRODUCTION !!!
    38	# This default value is the well-known dev secret. The backend will refuse to
    39	# start if URIP_ENV is staging/production and this value is left unchanged.
    40	# Generate a strong secret, e.g.:  python -c 'import secrets; print(secrets.token_urlsafe(64))'
    41	# The placeholder string `urip-dev-secret-change-in-production` is the well-known
    42	# dev default — DO NOT use it in any production-like deployment.
    43	# Leave empty here — the backend falls back to the well-known dev default
    44	# in URIP_ENV=development only. Generate a real secret with the command above
    45	# before copying this file to .env for any other environment.
    46	JWT_SECRET_KEY=
    47	
    48	JWT_ALGORITHM=HS256
    49	JWT_EXPIRE_HOURS=8
    50	
    51	# !!! ROTATE BEFORE PRODUCTION !!!
    52	URIP_FERNET_KEY=your-fernet-key-here
    53	
    54	CORS_ORIGINS=http://localhost:8000,http://localhost:3000
    55	
    56	# Connector API Keys (populated when Royal Enfield provides access)
    57	CROWDSTRIKE_CLIENT_ID=
    58	CROWDSTRIKE_CLIENT_SECRET=
    59	ARMIS_API_KEY=
    60	ZSCALER_API_KEY=
    61	CYBERARK_API_KEY=
    62	OTX_API_KEY=
    63	VIRUSTOTAL_API_KEY=
    64	JIRA_URL=
    65	JIRA_API_TOKEN=
    66	SERVICENOW_URL=
    67	SERVICENOW_API_TOKEN=

 succeeded in 0ms:
     1	"""
     2	ComplianceAuditLog — append-only audit trail for tenant-scoped compliance
     3	admin actions (CritFix-B NEW-1, compliance-side).
     4	
     5	Why a separate model from URIP's AuditLog?
     6	------------------------------------------
     7	- The Compliance Service has its own database (compliance_db on port 5434)
     8	  and own SQLAlchemy Base — there is no shared audit_log table.
     9	- The existing `auditor_activity_log` (models/auditor.py) is for *external
    10	  auditor* sessions only — it is NOT the right place for tenant admin
    11	  actions like vendor mutations or policy publishes.
    12	- Cross-service event-bus emit (shared/events) is intentionally out of
    13	  scope for this fix — keep the audit row co-located with the data it
    14	  audits so a single DB transaction can guarantee atomicity.
    15	
    16	Tenant-id is NOT NULL on purpose: every state-changing compliance action
    17	MUST be tied to a tenant.  Super-admin/cross-tenant administrative
    18	actions are not modelled here yet (compliance has no super-admin concept).
    19	"""
    20	from __future__ import annotations
    21	
    22	import uuid
    23	from datetime import datetime
    24	
    25	from sqlalchemy import String, DateTime, Index, Text
    26	from sqlalchemy.orm import Mapped, mapped_column
    27	
    28	from compliance_backend.database import Base
    29	
    30	
    31	class ComplianceAuditLog(Base):
    32	    """
    33	    Append-only audit row for compliance-side state changes.
    34	
    35	    Fields
    36	    ------
    37	    id              opaque uuid pk
    38	    tenant_id       NOT NULL — the tenant the mutation affects
    39	    user_id         the actor (sub claim from JWT) — string because
    40	                    compliance auth.py stores user ids as raw JWT subs
    41	    action          short verb e.g. "vendor_created" / "policy_published"
    42	    resource_type   "vendor" | "policy" | "control_run" | "evidence" | ...
    43	    resource_id     opaque resource id (str — may be uuid, framework code,
    44	                    or null for batch ops like score snapshots)
    45	    details_json    JSON blob (stored as TEXT for SQLite compatibility) —
    46	                    free-form payload (changes diff, count, etc.)
    47	    created_at      auto, UTC
    48	    """
    49	
    50	    __tablename__ = "compliance_audit_logs"
    51	    __table_args__ = (
    52	        Index("idx_compliance_audit_logs_tenant_id", "tenant_id"),
    53	        Index("idx_compliance_audit_logs_action", "action"),
    54	    )
    55	
    56	    id: Mapped[str] = mapped_column(
    57	        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    58	    )
    59	    # nullable=False — every audit row MUST be tenant-stamped (NEW-1).
    60	    # M7 (Codex MED-003 + Kimi MED-010) — standardised on String(36) UUID form.
    61	    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    62	    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    63	    action: Mapped[str] = mapped_column(String(64), nullable=False)
    64	    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    65	    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    66	    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    67	    created_at: Mapped[datetime] = mapped_column(
    68	        DateTime(timezone=True),
    69	        default=lambda: datetime.now(timezone.utc),
    70	        nullable=False,
    71	    )

exec
/bin/zsh -lc 'cd /tmp/urip_audit.AeKrB6 && rg -n "JWT_SECRET_KEY" -S .env.example backend/config.py tests/test_critfix_auth/test_audit_fix_critical.py tests/test_critfix_auth/test_crit004_jwt_secret.py tests/test_critfix_auth/test_audit_fix_critical.py' in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
backend/config.py:5:- The dev default JWT_SECRET_KEY is `urip-dev-secret-change-in-production`.
backend/config.py:37:    JWT_SECRET_KEY: str = DEV_DEFAULT_JWT_SECRET
backend/config.py:123:    secret = s.JWT_SECRET_KEY or ""
backend/config.py:131:                "JWT_SECRET_KEY is empty in production-like environment "
backend/config.py:133:                "Generate a long random secret and set JWT_SECRET_KEY before deploying."
backend/config.py:137:                "JWT_SECRET_KEY is set to the well-known dev default value "
backend/config.py:147:            "[URIP CONFIG WARNING] JWT_SECRET_KEY is using the dev default "
backend/config.py:150:            "deployment (set URIP_ENV=production and a real JWT_SECRET_KEY)."
tests/test_critfix_auth/test_crit004_jwt_secret.py:2:CRIT-004: JWT_SECRET_KEY default rotation enforcement.
tests/test_critfix_auth/test_crit004_jwt_secret.py:5:- backend/config.py default JWT_SECRET_KEY = "urip-dev-secret-change-in-production"
tests/test_critfix_auth/test_crit004_jwt_secret.py:11:- If URIP_ENV in {prod, production, staging} AND JWT_SECRET_KEY equals the dev
tests/test_critfix_auth/test_crit004_jwt_secret.py:56:    monkeypatch.setenv("JWT_SECRET_KEY", DEV_DEFAULT_SECRET)
tests/test_critfix_auth/test_crit004_jwt_secret.py:72:    monkeypatch.setenv("JWT_SECRET_KEY", "")
tests/test_critfix_auth/test_crit004_jwt_secret.py:90:    monkeypatch.setenv("JWT_SECRET_KEY", DEV_DEFAULT_SECRET)
tests/test_critfix_auth/test_crit004_jwt_secret.py:95:    assert cfg.settings.JWT_SECRET_KEY == DEV_DEFAULT_SECRET
tests/test_critfix_auth/test_crit004_jwt_secret.py:110:        "JWT_SECRET_KEY", "real-production-secret-9f2b8c1d4a6e7f0c2b9d8a1c3e5f7b8d"
tests/test_critfix_auth/test_crit004_jwt_secret.py:114:    assert "real-production-secret" in cfg.settings.JWT_SECRET_KEY
tests/test_critfix_auth/test_crit004_jwt_secret.py:141:    ), ".env.example must visibly warn to rotate JWT_SECRET_KEY"
tests/test_critfix_auth/test_audit_fix_critical.py:9:  AF-CRIT-3  .env file must NOT contain a literal JWT_SECRET_KEY assignment
tests/test_critfix_auth/test_audit_fix_critical.py:117:    `JWT_SECRET_KEY=urip-dev-secret-change-in-production`
tests/test_critfix_auth/test_audit_fix_critical.py:126:        r"^\s*JWT_SECRET_KEY\s*=\s*urip-dev-secret-change-in-production\s*$",
tests/test_critfix_auth/test_audit_fix_critical.py:130:        "AF-CRIT-3 — .env still ships JWT_SECRET_KEY=<dev default>. "
tests/test_critfix_auth/test_audit_fix_critical.py:9:  AF-CRIT-3  .env file must NOT contain a literal JWT_SECRET_KEY assignment
tests/test_critfix_auth/test_audit_fix_critical.py:117:    `JWT_SECRET_KEY=urip-dev-secret-change-in-production`
tests/test_critfix_auth/test_audit_fix_critical.py:126:        r"^\s*JWT_SECRET_KEY\s*=\s*urip-dev-secret-change-in-production\s*$",
tests/test_critfix_auth/test_audit_fix_critical.py:130:        "AF-CRIT-3 — .env still ships JWT_SECRET_KEY=<dev default>. "
.env.example:4:# below (especially JWT_SECRET_KEY) and set URIP_ENV=production.
.env.example:22:#   2. Generate a new JWT_SECRET_KEY — this invalidates ALL existing tokens.
.env.example:31:# In staging / prod the backend REFUSES TO START if JWT_SECRET_KEY is empty
.env.example:46:JWT_SECRET_KEY=

exec
/bin/zsh -lc 'cd /tmp/urip_audit.AeKrB6 && rg -n "connectors/metadata|list_connectors_metadata|CONNECTORS_METADATA" -S backend/routers tests/test_routers/test_connectors_metadata.py tests/test_routers/test_connectors_router.py backend/models/__init__.py backend/routers/connectors.py backend/routers/integrations.py || true' in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
**Inspecting test failures**

I’ve noticed that the connectors metadata command returned no output, which suggests there might be missing file paths due to mismatched names. I need to check the failing tests related to the connectors metadata. It seems like the router path could be `backend/routers/connectors.py`. I'll take a look at `tests/test_routers/test_connectors_metadata.py` to inspect the area around the failing expectations. Let's open it up and see what's going on!
exec
/bin/zsh -lc "cd /tmp/urip_audit.AeKrB6 && nl -ba tests/test_routers/test_connectors_metadata.py | sed -n '1,260p'" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
     1	"""
     2	TDD — backend/routers/connectors.py — Tool Catalog metadata endpoints.
     3	
     4	P33-Z3: Verifies that GET /api/connectors returns full metadata for every
     5	registered connector AND that GET /api/connectors/categories returns the
     6	filter aggregates.
     7	
     8	Endpoints under test
     9	--------------------
    10	  GET /api/connectors                         — rich Tool Catalog feed
    11	  GET /api/connectors?category=VM             — filter by category
    12	  GET /api/connectors?status=simulated        — filter by status
    13	  GET /api/connectors/categories              — aggregates per filter chip
    14	
    15	Per-tenant runtime fields (configured / last_poll_at / health_status /
    16	error_count_24h) are pulled from connector_health_summaries (FV-3) +
    17	tenant_connector_credentials, so the tests seed those tables directly.
    18	"""
    19	from __future__ import annotations
    20	
    21	import os
    22	import uuid
    23	
    24	# Set Fernet key BEFORE backend imports.
    25	os.environ.setdefault(
    26	    "URIP_FERNET_KEY",
    27	    "M3JKpUVOfx1nPLQYMRrxnVZsJq3cJ5vXq7bOe6jfXok=",
    28	)
    29	os.environ.setdefault("DISABLE_CONNECTOR_SCHEDULER", "true")
    30	
    31	from datetime import datetime, timedelta, timezone
    32	
    33	import pytest
    34	import pytest_asyncio
    35	from sqlalchemy import select
    36	from sqlalchemy.ext.asyncio import AsyncSession
    37	
    38	from backend.middleware.auth import create_access_token, hash_password
    39	from backend.models.agent_ingest import ConnectorHealthSummary
    40	from backend.models.subscription import TenantSubscription
    41	from backend.models.tenant import Tenant
    42	from backend.models.tenant_connector_credential import TenantConnectorCredential
    43	from backend.models.user import User
    44	
    45	
    46	REAL_CONNECTORS = {
    47	    "tenable",
    48	    "sentinelone",
    49	    "zscaler",
    50	    "netskope",
    51	    "ms_entra",
    52	    "manageengine_sdp",
    53	    "cloudsek",
    54	    "simulator",
    55	    "extended_simulator",
    56	}
    57	
    58	
    59	# ─────────────────────────────────────────────────────────────────────────────
    60	# Registry isolation — pin global registry to the 9 "real" connectors that the
    61	# Tool Catalog tests are written against.
    62	#
    63	# Why this fixture exists
    64	# -----------------------
    65	# The connector registry is a *global* state populated by class-decorator side
    66	# effects at import time (`@register_connector("name")`).  When this test file
    67	# is run in isolation, only the 9 connectors imported by ``backend.main`` are
    68	# present in the registry.  When the full pytest suite runs, importing other
    69	# test modules (e.g. tests/test_connectors/test_crowdstrike.py) loads *more*
    70	# connector classes — each of which registers itself globally — and the
    71	# registry grows beyond the 9 names this test was written against.
    72	#
    73	# That global-state pollution makes assertions like ``names == ["sentinelone"]``
    74	# or ``by_cat["EDR"]["count"] == 1`` fail in batch even though they pass alone.
    75	#
    76	# Per INV-6, we don't relax the assertions; we restore deterministic state at
    77	# the fixture layer.  The fixture snapshots the entire registry, removes any
    78	# names not in REAL_CONNECTORS for the test body, then restores the full
    79	# snapshot afterwards so other tests are unaffected.
    80	# ─────────────────────────────────────────────────────────────────────────────
    81	
    82	
    83	@pytest.fixture(autouse=True)
    84	def _isolate_connector_registry():
    85	    """Filter the global connector registry to REAL_CONNECTORS for each test."""
    86	    from connectors.base.registry import _global_registry
    87	
    88	    snapshot = dict(_global_registry._store)
    89	    # Keep only the 9 baseline connectors during the test.
    90	    pinned = {
    91	        name: factory
    92	        for name, factory in snapshot.items()
    93	        if name in REAL_CONNECTORS
    94	    }
    95	    _global_registry._store = pinned
    96	    try:
    97	        yield
    98	    finally:
    99	        # Restore EVERY entry that existed before the test, including any new
   100	        # registrations that may have happened during the test (defensive).
   101	        restored = dict(snapshot)
   102	        for k, v in _global_registry._store.items():
   103	            restored.setdefault(k, v)
   104	        _global_registry._store = restored
   105	
   106	
   107	# ─────────────────────────────────────────────────────────────────────────────
   108	# Fixtures — CORE module subscription is required by the router (require_module).
   109	# ─────────────────────────────────────────────────────────────────────────────
   110	
   111	
   112	@pytest_asyncio.fixture
   113	async def core_subscription(
   114	    db_session: AsyncSession, default_tenant: Tenant,
   115	) -> TenantSubscription:
   116	    """Enable CORE module so /api/connectors* isn't 403'd."""
   117	    sub = TenantSubscription(
   118	        id=uuid.uuid4(),
   119	        tenant_id=default_tenant.id,
   120	        module_code="CORE",
   121	        is_enabled=True,
   122	        billing_tier="STANDARD",
   123	    )
   124	    db_session.add(sub)
   125	    await db_session.commit()
   126	    await db_session.refresh(sub)
   127	    return sub
   128	
   129	
   130	@pytest_asyncio.fixture
   131	async def second_tenant(db_session: AsyncSession) -> Tenant:
   132	    """A second tenant for cross-tenant isolation tests."""
   133	    t = Tenant(
   134	        id=uuid.uuid4(),
   135	        name="Tenant B",
   136	        slug="tenant-b",
   137	        domain="tenant-b.test",
   138	        is_active=True,
   139	        settings={},
   140	    )
   141	    db_session.add(t)
   142	    # CORE subscription so the user's requests don't 403
   143	    sub = TenantSubscription(
   144	        id=uuid.uuid4(),
   145	        tenant_id=t.id,
   146	        module_code="CORE",
   147	        is_enabled=True,
   148	        billing_tier="STANDARD",
   149	    )
   150	    db_session.add(sub)
   151	    await db_session.commit()
   152	    await db_session.refresh(t)
   153	    return t
   154	
   155	
   156	@pytest_asyncio.fixture
   157	async def second_tenant_headers(
   158	    db_session: AsyncSession, second_tenant: Tenant,
   159	) -> dict[str, str]:
   160	    """Auth headers for a CISO scoped to the second tenant."""
   161	    user = User(
   162	        id=uuid.uuid4(),
   163	        email="cisob@tenant-b.test",
   164	        hashed_password=hash_password("Secure#PassB"),
   165	        full_name="Tenant B CISO",
   166	        role="ciso",
   167	        team="Security",
   168	        is_active=True,
   169	        tenant_id=second_tenant.id,
   170	    )
   171	    db_session.add(user)
   172	    await db_session.commit()
   173	    await db_session.refresh(user)
   174	
   175	    token = create_access_token(
   176	        str(user.id), user.role, tenant_id=str(second_tenant.id),
   177	    )
   178	    return {"Authorization": f"Bearer {token}"}
   179	
   180	
   181	# ─────────────────────────────────────────────────────────────────────────────
   182	# GET /api/connectors — rich metadata feed
   183	# ─────────────────────────────────────────────────────────────────────────────
   184	
   185	
   186	class TestListConnectorsMetadata:
   187	    @pytest.mark.anyio
   188	    async def test_list_returns_metadata_for_every_connector(
   189	        self, client, auth_headers, core_subscription,
   190	    ):
   191	        resp = await client.get("/api/connectors", headers=auth_headers)
   192	        assert resp.status_code == 200, resp.text
   193	        body = resp.json()
   194	
   195	        names = {item["name"] for item in body["items"]}
   196	        for expected in REAL_CONNECTORS:
   197	            assert expected in names, f"Missing connector {expected!r}"
   198	
   199	        # Spot-check Tenable's metadata is fully populated.
   200	        tenable = next(i for i in body["items"] if i["name"] == "tenable")
   201	        assert tenable["display_name"] == "Tenable Vulnerability Manager"
   202	        assert tenable["category"] == "VM"
   203	        assert tenable["status"] == "live"
   204	        assert tenable["module_code"] == "VM"
   205	        assert tenable["short_description"]
   206	        assert tenable["vendor_docs_url"].startswith("https://")
   207	        assert isinstance(tenable["credential_fields"], list)
   208	        assert len(tenable["credential_fields"]) >= 2
   209	        # Required field markers carry over
   210	        sk_field = next(
   211	            f for f in tenable["credential_fields"] if f["name"] == "secret_key"
   212	        )
   213	        assert sk_field["secret"] is True
   214	        assert sk_field["required"] is True
   215	        assert sk_field["type"] == "password"
   216	
   217	    @pytest.mark.anyio
   218	    async def test_list_includes_per_tenant_runtime_fields(
   219	        self, client, auth_headers, core_subscription,
   220	    ):
   221	        resp = await client.get("/api/connectors", headers=auth_headers)
   222	        assert resp.status_code == 200, resp.text
   223	        item = resp.json()["items"][0]
   224	        # Runtime fields exist in the response shape (not just static metadata).
   225	        for key in ("configured", "last_poll_at", "health_status", "error_count_24h"):
   226	            assert key in item, f"Catalog item missing runtime field {key!r}"
   227	        # Fresh tenant: nothing configured, no health rows.
   228	        for it in resp.json()["items"]:
   229	            assert it["configured"] is False
   230	            assert it["last_poll_at"] is None
   231	            assert it["health_status"] is None
   232	            assert it["error_count_24h"] == 0
   233	
   234	    @pytest.mark.anyio
   235	    async def test_list_filter_by_category(
   236	        self, client, auth_headers, core_subscription,
   237	    ):
   238	        resp = await client.get(
   239	            "/api/connectors?category=VM", headers=auth_headers,
   240	        )
   241	        assert resp.status_code == 200
   242	        body = resp.json()
   243	        names = [i["name"] for i in body["items"]]
   244	        # Only Tenable is in VM among the 9 real connectors loaded.
   245	        assert names == ["tenable"]
   246	        assert body["total"] == 1
   247	
   248	    @pytest.mark.anyio
   249	    async def test_list_filter_by_category_case_insensitive(
   250	        self, client, auth_headers, core_subscription,
   251	    ):
   252	        resp = await client.get(
   253	            "/api/connectors?category=edr", headers=auth_headers,
   254	        )
   255	        assert resp.status_code == 200
   256	        names = [i["name"] for i in resp.json()["items"]]
   257	        assert names == ["sentinelone"]
   258	
   259	    @pytest.mark.anyio
   260	    async def test_list_filter_by_status(

**Inspecting router code**

I think the tests seem pretty robust, but the failures might be happening because the endpoint is returning a 500 error or maybe there are some missing connectors. I need to take a closer look at the router code. I’ll open the `backend/routers/connectors.py` file in the archive to check the registry and see what's going on there. It’ll help in diagnosing the issue properly!
exec
/bin/zsh -lc "cd /tmp/urip_audit.AeKrB6 && rg -n \"@router|get\\(\\\"/api/connectors|APIRouter\\(|connectors/categories|list_connectors\" backend/routers/connectors.py && nl -ba backend/routers/connectors.py | sed -n '1,260p'" in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 succeeded in 0ms:
75:router = APIRouter(dependencies=[Depends(require_module("CORE"))])
380:@router.get("", response_model=ConnectorCatalogResponse)
381:async def list_connectors(
404:    all_meta = _global_registry.list_connectors_with_metadata()
476:@router.get("/categories", response_model=CategoriesResponse)
489:    all_meta = _global_registry.list_connectors_with_metadata()
528:@router.get("/{name}/setup-guide", response_model=ConnectorCatalogItem)
588:@router.get("/{name}", response_model=ConnectorSchemaResponse)
602:@router.post("/{name}/configure", response_model=ConfigureResponse)
660:@router.post("/{name}/test", response_model=TestResponse)
747:@router.delete("/{name}", response_model=DeleteResponse)
786:@router.post("/{name}/run-now", response_model=RunNowResponse)
900:@router.get("/{name}/health", response_model=HealthResponse)
935:@router.get("/{name}/findings", response_model=FindingsResponse)
     1	"""
     2	backend/routers/connectors.py — Top-level /api/connectors router.
     3	
     4	Z3-A: Wires the 7 production + 2 simulator connectors into the live API so
     5	they stop being dead code (INV-1 fix).  This router is what the frontend
     6	``connector-wizard.js`` (FV-1) actually calls.
     7	
     8	Endpoints
     9	---------
    10	GET    /api/connectors                       — list connector types + per-tenant config status
    11	GET    /api/connectors/{name}                — connector schema (field defs for the wizard)
    12	POST   /api/connectors/{name}/configure      — store encrypted credentials for current tenant
    13	POST   /api/connectors/{name}/test           — test connection (uses inline or stored creds)
    14	DELETE /api/connectors/{name}                — remove credentials for current tenant
    15	POST   /api/connectors/{name}/run-now        — trigger an immediate poll (admin only)
    16	GET    /api/connectors/{name}/health         — connector health (status, error count)
    17	GET    /api/connectors/{name}/findings       — recent findings for current tenant
    18	
    19	Coordination
    20	------------
    21	- The legacy ``/api/settings/connectors`` endpoints in ``backend/routers/settings.py``
    22	  remain in place — they back the older settings UI.  This new router is the
    23	  canonical surface for the FV-1 wizard and is mounted at ``/api/connectors``.
    24	- All endpoints require ``ciso`` role; the tenant scope comes from
    25	  ``TenantContext`` populated by ``get_current_user``.
    26	- Module gate is ``CORE`` because connectors are a platform-level feature.
    27	"""
    28	
    29	from __future__ import annotations
    30	
    31	import ipaddress
    32	import logging
    33	import socket
    34	import uuid
    35	from datetime import datetime, timedelta, timezone
    36	from typing import Any
    37	from urllib.parse import urlparse
    38	
    39	from fastapi import APIRouter, Body, Depends, HTTPException, Query
    40	from pydantic import BaseModel, Field
    41	from sqlalchemy import desc, select
    42	from sqlalchemy.ext.asyncio import AsyncSession
    43	
    44	from backend.database import get_db
    45	from backend.middleware.auth import get_current_user  # noqa: F401  (re-exported via rbac)
    46	from backend.middleware.module_gate import require_module
    47	from backend.middleware.rbac import role_required
    48	from backend.middleware.tenant import TenantContext
    49	from backend.models.agent_ingest import ConnectorHealthSummary
    50	from backend.models.audit_log import AuditLog
    51	from backend.models.risk import Risk
    52	from backend.models.tenant_connector_credential import TenantConnectorCredential
    53	from backend.models.user import User
    54	from backend.schemas.connectors import (
    55	    CategoriesResponse,
    56	    CategoryAggregate,
    57	    ConnectorCatalogItem,
    58	    ConnectorCatalogResponse,
    59	    CredentialFieldOut,
    60	)
    61	from backend.services.crypto_service import decrypt_credentials, encrypt_credentials
    62	from backend.services.tenant_query import apply_tenant_filter
    63	from connectors.base.connector import (
    64	    BaseConnector,
    65	    ConnectorAuthError,
    66	    ConnectorFetchError,
    67	    ConnectorHealth,
    68	)
    69	from connectors.base.registry import _global_registry
    70	
    71	logger = logging.getLogger(__name__)
    72	
    73	
    74	# CRIT-007 — connectors are a CORE platform feature.
    75	router = APIRouter(dependencies=[Depends(require_module("CORE"))])
    76	
    77	
    78	# ─────────────────────────────────────────────────────────────────────────────
    79	# Pydantic models
    80	# ─────────────────────────────────────────────────────────────────────────────
    81	
    82	
    83	class ConnectorListItem(BaseModel):
    84	    name: str
    85	    configured: bool
    86	
    87	
    88	class ConnectorListResponse(BaseModel):
    89	    items: list[ConnectorListItem]
    90	    total: int
    91	    limit: int
    92	    offset: int
    93	
    94	
    95	class ConnectorFieldSpec(BaseModel):
    96	    name: str
    97	    label: str
    98	    required: bool
    99	    secret: bool = False
   100	    description: str | None = None
   101	
   102	
   103	class ConnectorSchemaResponse(BaseModel):
   104	    name: str
   105	    fields: list[ConnectorFieldSpec]
   106	
   107	
   108	class ConfigureRequest(BaseModel):
   109	    credentials: dict = Field(..., description="Connector-specific credentials dict")
   110	
   111	
   112	class ConfigureResponse(BaseModel):
   113	    status: str
   114	    connector: str
   115	
   116	
   117	class TestRequest(BaseModel):
   118	    credentials: dict | None = None
   119	
   120	
   121	class TestResponse(BaseModel):
   122	    success: bool
   123	    message: str
   124	    sample: list[dict[str, Any]] = Field(default_factory=list)
   125	
   126	
   127	class DeleteResponse(BaseModel):
   128	    status: str
   129	    connector: str
   130	
   131	
   132	class RunNowResponse(BaseModel):
   133	    status: str
   134	    connector: str
   135	    records_ingested: int
   136	
   137	
   138	class HealthResponse(BaseModel):
   139	    connector_name: str
   140	    status: str
   141	    last_run: datetime | None
   142	    error_count: int
   143	    last_error: str | None
   144	
   145	
   146	class FindingItem(BaseModel):
   147	    risk_id: str
   148	    finding: str
   149	    severity: str
   150	    cvss_score: float
   151	    asset: str
   152	    cve_id: str | None
   153	    created_at: datetime
   154	
   155	
   156	class FindingsResponse(BaseModel):
   157	    items: list[FindingItem]
   158	    total: int
   159	    limit: int
   160	
   161	
   162	# ─────────────────────────────────────────────────────────────────────────────
   163	# Schema definitions per connector — drives the FV-1 wizard
   164	# ─────────────────────────────────────────────────────────────────────────────
   165	
   166	CONNECTOR_SCHEMAS: dict[str, list[ConnectorFieldSpec]] = {
   167	    "tenable": [
   168	        ConnectorFieldSpec(name="access_key", label="Access Key", required=True, secret=True),
   169	        ConnectorFieldSpec(name="secret_key", label="Secret Key", required=True, secret=True),
   170	        ConnectorFieldSpec(name="base_url", label="Base URL", required=False,
   171	                           description="Default https://cloud.tenable.com"),
   172	    ],
   173	    "sentinelone": [
   174	        ConnectorFieldSpec(name="api_token", label="API Token", required=True, secret=True),
   175	        ConnectorFieldSpec(name="base_url", label="Base URL", required=True,
   176	                           description="e.g. https://tenant.sentinelone.net"),
   177	    ],
   178	    "zscaler": [
   179	        ConnectorFieldSpec(name="api_key", label="API Key", required=True, secret=True),
   180	        ConnectorFieldSpec(name="username", label="Username", required=True),
   181	        ConnectorFieldSpec(name="password", label="Password", required=True, secret=True),
   182	        ConnectorFieldSpec(name="cloud", label="Cloud", required=True,
   183	                           description="e.g. zscalerone, zscalertwo, zscaler"),
   184	    ],
   185	    "netskope": [
   186	        ConnectorFieldSpec(name="client_id", label="Client ID", required=True),
   187	        ConnectorFieldSpec(name="client_secret", label="Client Secret", required=True, secret=True),
   188	        ConnectorFieldSpec(name="base_url", label="Base URL", required=True,
   189	                           description="e.g. https://tenant.goskope.com"),
   190	    ],
   191	    "ms_entra": [
   192	        ConnectorFieldSpec(name="tenant_id", label="Azure AD Tenant ID", required=True),
   193	        ConnectorFieldSpec(name="client_id", label="Application (Client) ID", required=True),
   194	        ConnectorFieldSpec(name="client_secret", label="Client Secret", required=True, secret=True),
   195	    ],
   196	    "manageengine_sdp": [
   197	        ConnectorFieldSpec(name="auth_method", label="Auth Method", required=True,
   198	                           description="oauth | token"),
   199	        ConnectorFieldSpec(name="base_url", label="Base URL", required=True),
   200	        ConnectorFieldSpec(name="client_id", label="Client ID (oauth)", required=False),
   201	        ConnectorFieldSpec(name="client_secret", label="Client Secret (oauth)", required=False, secret=True),
   202	        ConnectorFieldSpec(name="refresh_token", label="Refresh Token (oauth)", required=False, secret=True),
   203	        ConnectorFieldSpec(name="auth_token", label="Auth Token (token)", required=False, secret=True),
   204	    ],
   205	    "cloudsek": [
   206	        ConnectorFieldSpec(name="api_key", label="API Key", required=True, secret=True),
   207	        ConnectorFieldSpec(name="org_id", label="Organization ID", required=True),
   208	        ConnectorFieldSpec(name="api_base", label="API Base URL", required=False,
   209	                           description="Default https://api.cloudsek.com"),
   210	    ],
   211	    "simulator": [
   212	        ConnectorFieldSpec(name="tenant_id", label="Tenant Label", required=False,
   213	                           description="Optional label for simulator runs"),
   214	    ],
   215	    "extended_simulator": [
   216	        ConnectorFieldSpec(name="tenant_id", label="Tenant Label", required=False,
   217	                           description="Optional label for extended-simulator runs"),
   218	    ],
   219	}
   220	
   221	
   222	# ─────────────────────────────────────────────────────────────────────────────
   223	# Helpers
   224	# ─────────────────────────────────────────────────────────────────────────────
   225	
   226	
   227	def _ensure_known_connector(name: str) -> None:
   228	    """Raise 404 if `name` is not in the global registry."""
   229	    if name not in _global_registry:
   230	        raise HTTPException(
   231	            status_code=404,
   232	            detail=f"Connector '{name}' is not registered.",
   233	        )
   234	
   235	
   236	async def _load_credentials(
   237	    db: AsyncSession,
   238	    tenant_id: uuid.UUID,
   239	    connector_name: str,
   240	) -> dict | None:
   241	    """Return decrypted credentials for (tenant, connector) or None."""
   242	    row = (
   243	        await db.execute(
   244	            select(TenantConnectorCredential).where(
   245	                TenantConnectorCredential.tenant_id == tenant_id,
   246	                TenantConnectorCredential.connector_name == connector_name,
   247	            )
   248	        )
   249	    ).scalar_one_or_none()
   250	    if row is None:
   251	        return None
   252	    return decrypt_credentials(row.encrypted_blob)
   253	
   254	
   255	def _instantiate(name: str) -> BaseConnector:
   256	    """Instantiate a connector via the registry."""
   257	    factory = _global_registry.get(name)
   258	    return factory()
   259	
   260	

exec
/bin/zsh -lc 'cd /tmp/urip_audit.AeKrB6 && /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/bin/python -m pytest -q tests/test_critfix_auth/test_audit_fix_critical.py::test_af_crit3_env_file_does_not_carry_default_jwt_secret -q' in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 exited 1 in 1315ms:
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:207: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the fixture caching scope. Future versions of pytest-asyncio will default the loop scope for asynchronous fixtures to function scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_af_crit3_env_file_does_not_carry_default_jwt_secret ___________

    def test_af_crit3_env_file_does_not_carry_default_jwt_secret():
        """
        Per Gemini CRIT-G5 / Codex CRIT-003: the literal line
        `JWT_SECRET_KEY=urip-dev-secret-change-in-production`
        must be removed from `.env`. The pydantic default in code already
        provides the dev fallback; keeping it in `.env` increases the risk of
        accidental production deployment with the well-known secret.
        """
>       text = (_project_root() / ".env").read_text()

tests/test_critfix_auth/test_audit_fix_critical.py:122: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/pathlib/__init__.py:787: in read_text
    with self.open(mode='r', encoding=encoding, errors=errors, newline=newline) as f:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = PosixPath('/private/tmp/urip_audit.AeKrB6/.env'), mode = 'r'
buffering = -1, encoding = 'locale', errors = None, newline = None

    def open(self, mode='r', buffering=-1, encoding=None,
             errors=None, newline=None):
        """
        Open the file pointed to by this path and return a file object, as
        the built-in open() function does.
        """
        if "b" not in mode:
            encoding = io.text_encoding(encoding)
>       return io.open(self, mode, buffering, encoding, errors, newline)
E       FileNotFoundError: [Errno 2] No such file or directory: '/private/tmp/urip_audit.AeKrB6/.env'

/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/pathlib/__init__.py:771: FileNotFoundError
=============================== warnings summary ===============================
backend/config.py:159
  /private/tmp/urip_audit.AeKrB6/backend/config.py:159: RuntimeWarning: [URIP CONFIG WARNING] JWT_SECRET_KEY is using the dev default (urip-dev-secret-change-in-production). This is acceptable in dev ONLY. You MUST rotate this secret before any prod / staging deployment (set URIP_ENV=production and a real JWT_SECRET_KEY).
    _enforce_jwt_secret_policy(settings)

../../../Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_utils.py:39: 302 warnings
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_utils.py:39: DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead
    return asyncio.iscoroutinefunction(obj) or (callable(obj) and asyncio.iscoroutinefunction(obj.__call__))

../../../Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:233: 298 warnings
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:233: DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead
    is_coroutine = asyncio.iscoroutinefunction(dependant.call)

tests/test_critfix_auth/test_audit_fix_critical.py::test_af_crit3_env_file_does_not_carry_default_jwt_secret
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:1153: DeprecationWarning: 'asyncio.get_event_loop_policy' is deprecated and slated for removal in Python 3.16
    return asyncio.get_event_loop_policy()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_critfix_auth/test_audit_fix_critical.py::test_af_crit3_env_file_does_not_carry_default_jwt_secret

**Examining code audit issues**

I’m considering how to approach the code correctness audit of a commit. It's important that a clean clone should run tests without needing any additional environment variables, like those from a .env file. If tests fail, it might indicate that the repository isn't self-contained. The user asked specifically about a final audit—possibly for deployed apps—but I think I'll weigh test failures heavily. I need to run the first failing connectors test to figure out the cause!
exec
/bin/zsh -lc 'cd /tmp/urip_audit.AeKrB6 && /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/bin/python -m pytest -q tests/test_routers/test_connectors_metadata.py::TestListConnectorsMetadata::test_list_returns_metadata_for_every_connector -q' in /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a
 exited 1 in 1636ms:
/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:207: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the fixture caching scope. Future versions of pytest-asyncio will default the loop scope for asynchronous fixtures to function scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
F                                                                        [100%]
=================================== FAILURES ===================================
_ TestListConnectorsMetadata.test_list_returns_metadata_for_every_connector[asyncio] _

self = <tests.test_routers.test_connectors_metadata.TestListConnectorsMetadata object at 0x10dac2c10>
client = <httpx.AsyncClient object at 0x10dda5940>
auth_headers = {'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzZmYzNWVmMi1kZjg4LTRhYjktOWJjNS1jNTRlYmU0YzE...nQiLCJ0ZW5hbnRfaWQiOiJiYTI3ZWI0MC0zN2JlLTQzZjgtYWI5Ni00Y2NhZGRiZmViYzQifQ.Ft3cNsZ9fbzm1BHV4DJSG3AvUKIqzDTKOf69IMA1Hlc'}
core_subscription = <backend.models.subscription.TenantSubscription object at 0x10dda6270>

    @pytest.mark.anyio
    async def test_list_returns_metadata_for_every_connector(
        self, client, auth_headers, core_subscription,
    ):
        resp = await client.get("/api/connectors", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
    
        names = {item["name"] for item in body["items"]}
        for expected in REAL_CONNECTORS:
>           assert expected in names, f"Missing connector {expected!r}"
E           AssertionError: Missing connector 'simulator'
E           assert 'simulator' in {'cloudsek', 'manageengine_sdp', 'ms_entra', 'netskope', 'sentinelone', 'tenable', ...}

tests/test_routers/test_connectors_metadata.py:197: AssertionError
----------------------------- Captured stderr call -----------------------------
2026-04-28 20:32:22,051 INFO httpx — HTTP Request: GET http://test/api/connectors "HTTP/1.1 200 OK"
------------------------------ Captured log call -------------------------------
INFO     httpx:_client.py:1740 HTTP Request: GET http://test/api/connectors "HTTP/1.1 200 OK"
=============================== warnings summary ===============================
backend/config.py:159
  /private/tmp/urip_audit.AeKrB6/backend/config.py:159: RuntimeWarning: [URIP CONFIG WARNING] JWT_SECRET_KEY is using the dev default (urip-dev-secret-change-in-production). This is acceptable in dev ONLY. You MUST rotate this secret before any prod / staging deployment (set URIP_ENV=production and a real JWT_SECRET_KEY).
    _enforce_jwt_secret_policy(settings)

../../../Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_utils.py:39: 302 warnings
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/starlette/_utils.py:39: DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead
    return asyncio.iscoroutinefunction(obj) or (callable(obj) and asyncio.iscoroutinefunction(obj.__call__))

../../../Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:233: 298 warnings
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/fastapi/routing.py:233: DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead
    is_coroutine = asyncio.iscoroutinefunction(dependant.call)

tests/test_routers/test_connectors_metadata.py::TestListConnectorsMetadata::test_list_returns_metadata_for_every_connector[asyncio]
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:1153: DeprecationWarning: 'asyncio.get_event_loop_policy' is deprecated and slated for removal in Python 3.16
    return asyncio.get_event_loop_policy()

tests/test_routers/test_connectors_metadata.py::TestListConnectorsMetadata::test_list_returns_metadata_for_every_connector[asyncio]
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:844: DeprecationWarning: 'asyncio.get_event_loop_policy' is deprecated and slated for removal in Python 3.16
    _restore_event_loop_policy(asyncio.get_event_loop_policy()),

tests/test_routers/test_connectors_metadata.py::TestListConnectorsMetadata::test_list_returns_metadata_for_every_connector[asyncio]
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:1125: DeprecationWarning: 'asyncio.set_event_loop_policy' is deprecated and slated for removal in Python 3.16
    asyncio.set_event_loop_policy(new_loop_policy)

tests/test_routers/test_connectors_metadata.py::TestListConnectorsMetadata::test_list_returns_metadata_for_every_connector[asyncio]
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:1126: DeprecationWarning: 'asyncio.get_event_loop_policy' is deprecated and slated for removal in Python 3.16
    loop = asyncio.get_event_loop_policy().new_event_loop()

tests/test_routers/test_connectors_metadata.py::TestListConnectorsMetadata::test_list_returns_metadata_for_every_connector[asyncio]
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:859: DeprecationWarning: 'asyncio.get_event_loop_policy' is deprecated and slated for removal in Python 3.16
    policy = asyncio.get_event_loop_policy()

tests/test_routers/test_connectors_metadata.py::TestListConnectorsMetadata::test_list_returns_metadata_for_every_connector[asyncio]
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:904: DeprecationWarning: 'asyncio.get_event_loop_policy' is deprecated and slated for removal in Python 3.16
    policy = asyncio.get_event_loop_policy()

tests/test_routers/test_connectors_metadata.py::TestListConnectorsMetadata::test_list_returns_metadata_for_every_connector[asyncio]
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:928: DeprecationWarning: 'asyncio.set_event_loop_policy' is deprecated and slated for removal in Python 3.16
    asyncio.set_event_loop_policy(previous_policy)

tests/test_routers/test_connectors_metadata.py::TestListConnectorsMetadata::test_list_returns_metadata_for_every_connector[asyncio]
  /Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:940: DeprecationWarning: 'asyncio.get_event_loop_policy' is deprecated and slated for removal in Python 3.16
    policy = asyncio.get_event_loop_policy()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_routers/test_connectors_metadata.py::TestListConnectorsMetadata::test_list_returns_metadata_for_every_connector[asyncio]

codex
REJECT 72/100 — commit `cf6c7bf` still fails “clean-clone correctness” (test suite + runtime wiring).

✓ Done: verified schemas present in-tree (`backend/schemas/{notifications,integrations,risk_summary}.py`), imported `backend.main`, ran full pytest on an archive of the commit (no untracked files) → `21 failed, 2047 passed, 8 skipped` in `335.97s`.
→ Decision: REJECT — because CI/clean clone would be red and several failures are hard correctness breakages (not just warnings).

⚠ Review (must-fix blockers):
- Cross-service E2E failures cascade from `NameError: timezone is not defined` in `compliance/backend/compliance_backend/models/compliance_audit_log.py:69` (`datetime.now(timezone.utc)` without importing `timezone`).
- Tests assume a tracked `.env` exists; in a clean clone it doesn’t, causing `FileNotFoundError` at `tests/test_critfix_auth/test_audit_fix_critical.py:122` (and related `.env`/“dev-only” tests).
- Connector catalog missing expected connectors at runtime: `/api/connectors` response lacks at least `simulator` (and others), failing `tests/test_routers/test_connectors_metadata.py:197`; root symptom is “connector not registered/imported on app startup”, not an HTTP error.
2026-04-28T15:02:34.603887Z ERROR codex_core::session: failed to record rollout items: thread 019dd496-340d-7160-83b8-f399830f2dd0 not found
tokens used
56,405
REJECT 72/100 — commit `cf6c7bf` still fails “clean-clone correctness” (test suite + runtime wiring).

✓ Done: verified schemas present in-tree (`backend/schemas/{notifications,integrations,risk_summary}.py`), imported `backend.main`, ran full pytest on an archive of the commit (no untracked files) → `21 failed, 2047 passed, 8 skipped` in `335.97s`.
→ Decision: REJECT — because CI/clean clone would be red and several failures are hard correctness breakages (not just warnings).

⚠ Review (must-fix blockers):
- Cross-service E2E failures cascade from `NameError: timezone is not defined` in `compliance/backend/compliance_backend/models/compliance_audit_log.py:69` (`datetime.now(timezone.utc)` without importing `timezone`).
- Tests assume a tracked `.env` exists; in a clean clone it doesn’t, causing `FileNotFoundError` at `tests/test_critfix_auth/test_audit_fix_critical.py:122` (and related `.env`/“dev-only” tests).
- Connector catalog missing expected connectors at runtime: `/api/connectors` response lacks at least `simulator` (and others), failing `tests/test_routers/test_connectors_metadata.py:197`; root symptom is “connector not registered/imported on app startup”, not an HTTP error.

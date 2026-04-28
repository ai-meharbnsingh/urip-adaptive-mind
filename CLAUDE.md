## File Location Policy (project-specific — also enforced globally)

**Root directory MUST stay clean.** Only ONE canonical doc + config files at root.

| Type | Location |
|---|---|
| Master doc | `MASTER_BLUEPRINT.md` (root — the only blueprint at root) |
| Historical / superseded docs | `docs/archive/` |
| New planning docs / reports / audits / inventories | `docs/` (or `docs/archive/` if superseded immediately) |
| Backend code | `backend/` |
| Frontend code (URIP shell) | `frontend/` |
| Compliance service | `compliance/backend/`, `compliance/frontend/` |
| Hybrid-SaaS agent | `agent/` |
| Connectors | `connectors/{tool_name}/` |
| Shared libraries | `shared/` |
| Tests | `tests/` (URIP), `compliance/backend/tests/` (compliance) |
| Migrations | `alembic/` (URIP), `compliance/alembic/` (compliance) |
| Config files (allowed at root) | `Dockerfile`, `docker-compose.yml`, `requirements.txt`, `alembic.ini`, `pytest.ini`, `.env.example`, `.gitignore` |
| Trash / archive | `_trash/` (NEVER `rm` — INV-0; always `mv`) |
| Generated artifacts | `out/`, `dist/`, `htmlcov/`, `.pytest_cache/` (all gitignored) |

**Rules:**
- Every new file goes to its correct directory at creation time. Never default to root.
- After any task that produces multiple docs (audit, plan, inventory, etc.), sweep them into `docs/` before declaring the task done.
- When spawning a subagent, tell it where its output file should land.
- If a session ends with extra `.md` or stray files at root, that is a regression — fix before push.

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current

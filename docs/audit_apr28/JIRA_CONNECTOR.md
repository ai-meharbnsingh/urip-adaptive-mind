# Jira Cloud + Data Center Connector — Implementation Summary

## File Layout

```
connectors/jira/
  __init__.py            — package marker (empty)
  api_client.py          — async httpx.AsyncClient wrapper; plain-text → ADF conversion
  schemas.py             — Pydantic v2 models (JiraIssue, JiraSearchResponse, etc.)
  connector.py           — JiraConnector class (@register_connector("jira"))

backend/
  connector_loader.py    — added `import connectors.jira.connector` (count: 29 → 30)
  main.py                — added integrations_router include at /api/integrations
  routers/
    integrations.py      — NEW: GET /api/integrations/{tool_name}/health endpoint

frontend/js/
  connector-schemas.js   — added 'jira' entry with 7 credential fields + logoUrl

tests/test_connectors/jira/
  __init__.py
  test_connector.py      — 38 tests covering all required scenarios

connectors/base/
  setup_guides_data.py   — added _JIRA SetupGuideSpec + "jira" entry in SETUP_GUIDES
```

## How to Configure

Open Tool Catalog → Jira tile, then fill in:

| Field | Required | Notes |
|---|---|---|
| `base_url` | Yes | `https://your-org.atlassian.net` (Cloud) or internal DC URL |
| `auth_method` | Yes | `basic` (Cloud) or `bearer` (DC/Server) |
| `email` | When basic | Atlassian account email |
| `api_token` | When basic | Generate at id.atlassian.com → Security → API tokens |
| `bearer_token` | When bearer | Profile → Personal Access Tokens in DC/Server |
| `default_project_key` | Yes | e.g. `SEC` — project where URIP risks are pushed |
| `risk_jql` | Yes | JQL selecting security tickets to ingest (e.g. `project = SEC AND labels = "security"`) |

## How Auth Works

**Cloud (Basic):** `Authorization: Basic base64(email:api_token)` — uses Atlassian API tokens, not passwords. The constructor builds the base64 header once at instantiation.

**DC/Server (Bearer):** `Authorization: Bearer <PAT>` — Personal Access Token issued by Jira's PAT management UI. Activated when `bearer_token` is supplied instead of `email`+`api_token`.

Authentication is verified at `authenticate()` call time by hitting `GET /rest/api/3/myself` — any 401/403 raises `ConnectorAuthError` immediately, so bad credentials are caught before the session is stored.

## Pytest Output (last 10 lines)

```
tests/test_connectors/jira/test_connector.py::TestADFHelpers::test_plain_text_to_adf_structure PASSED [ 89%]
tests/test_connectors/jira/test_connector.py::TestADFHelpers::test_plain_text_to_adf_empty PASSED [ 92%]
tests/test_connectors/jira/test_connector.py::TestADFHelpers::test_plain_text_to_adf_multiline PASSED [ 94%]
tests/test_connectors/jira/test_connector.py::TestADFHelpers::test_extract_adf_text PASSED [ 97%]
tests/test_connectors/jira/test_connector.py::TestADFHelpers::test_extract_adf_text_empty PASSED [100%]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 38 passed, 2 warnings in 0.10s ========================
```

## All Tests Pass

**38 passed, 0 failed.** Warnings are pre-existing (Pydantic v1 config deprecation in `backend/config.py` and JWT dev-secret notice) — unrelated to Jira connector.

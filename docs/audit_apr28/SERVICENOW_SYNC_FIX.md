# ServiceNow Sync Contract Fix — Apr 28, 2026

Refactored `connectors/servicenow/connector.py` to match the `BaseConnector`
sync contract. Added a module-level `_run_async(coro)` helper (mirrors Jira
pattern) that calls `asyncio.run()` internally. Three methods converted:
`authenticate(tenant_credentials)` — now sync, runs `_client.healthcheck()` via
`_run_async`; `fetch_findings(since, **kwargs)` — now sync, drops the `session`
parameter to match the abstract signature, pulls `tenant_id` and `limit` from
kwargs; `health_check()` — now sync, no `session` param, never raises.
`create_ticket` remains async (not part of BaseConnector; callers use
`_run()`). Updated `tests/connectors/servicenow/test_connector.py` to call the
three methods directly (no `_run` wrapper); create_ticket tests unchanged.

## Last 10 Lines of pytest Output

```
tests/connectors/servicenow/test_connector.py::test_health_check_ok PASSED [ 86%]
tests/connectors/servicenow/test_connector.py::test_health_check_fail PASSED [ 90%]
tests/connectors/servicenow/test_connector.py::test_health_check_no_client PASSED [ 93%]
tests/connectors/servicenow/test_connector.py::test_connector_metadata PASSED [ 96%]
tests/connectors/servicenow/test_connector.py::test_credential_secrets_marked PASSED [100%]

=============================== warnings summary ===============================
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 30 passed, 2 warnings in 0.10s ========================
```

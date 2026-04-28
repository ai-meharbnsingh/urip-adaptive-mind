# ServiceNow Connector — Build Summary (Apr 28, 2026)

## File Layout
- `connectors/servicenow/__init__.py` — package marker
- `connectors/servicenow/api_client.py` — async httpx client (Basic Auth + OAuth Bearer)
- `connectors/servicenow/schemas.py` — Pydantic v2 models (ServiceNowIncident, ServiceNowListResponse)
- `connectors/servicenow/connector.py` — ServiceNowConnector class (@register_connector("servicenow"))
- `tests/connectors/servicenow/__init__.py` — test package marker
- `tests/connectors/servicenow/test_connector.py` — 30 tests, all green
- `backend/connector_loader.py` — added `import connectors.servicenow.connector` (ITSM section)
- `frontend/js/connector-schemas.js` — added "servicenow" entry with 6 fields + VectorLogo URL
- `connectors/base/setup_guides_data.py` — added `_SERVICENOW` SetupGuideSpec

## Configuration Fields
- `instance_url` (url, required): Instance URL (https://your-tenant.service-now.com)
- `auth_method` (select, required): "basic" (Username + Password) or "oauth" (Bearer Token)
- `username` (text): Required when auth_method=basic
- `password` (password, secret): Required when auth_method=basic
- `oauth_token` (password, secret): Required when auth_method=oauth
- `risk_query` (text, required): Encoded query default "category=security^active=true"

## Urgency/Impact Severity Mapping
ServiceNow scale: 1=High, 2=Medium, 3=Low (both urgency and impact)
- urgency=1 AND impact=1 → critical
- urgency=1 OR impact=1  → high
- urgency=2 OR impact=2  → medium
- all others             → low
Reverse map for create_ticket: critical→(1,1), high→(1,2), medium→(2,2), low→(3,3)

## Pytest Output (last 10 lines)
```
tests/connectors/servicenow/test_connector.py::test_create_ticket_urgency_mapping_critical PASSED [ 80%]
tests/connectors/servicenow/test_connector.py::test_create_ticket_urgency_mapping_low PASSED [ 83%]
tests/connectors/servicenow/test_connector.py::test_health_check_ok PASSED [ 86%]
tests/connectors/servicenow/test_connector.py::test_health_check_fail PASSED [ 90%]
tests/connectors/servicenow/test_connector.py::test_health_check_no_client PASSED [ 93%]
tests/connectors/servicenow/test_connector.py::test_connector_metadata PASSED [ 96%]
tests/connectors/servicenow/test_connector.py::test_credential_secrets_marked PASSED [100%]

============================== 30 passed in 0.15s ==============================
```

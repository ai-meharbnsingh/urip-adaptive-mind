# Okta Workforce Identity Connector — Build Summary

**Date**: 2026-04-28  
**Scope**: connectors/okta/* + test harness + setup guide + loader registration

## File Layout

```
connectors/okta/
  __init__.py          — empty package marker
  api_client.py        — async httpx client (SSWS auth, Link-header pagination)
  schemas.py           — Pydantic v2 models (OktaUser, OktaAppAssignment, OktaFactor, OktaSystemLogEvent)
  connector.py         — OktaConnector (@register_connector("okta"), BaseConnector ABC)
  README.md            — operator setup guide (token creation, scopes, filter syntax)

tests/test_connectors/okta/
  __init__.py
  test_connector.py    — 28 tests, 100% green

connectors/base/setup_guides_data.py  — _OKTA SetupGuideSpec appended; "okta" key added to SETUP_GUIDES dict
frontend/js/connector-schemas.js      — okta entry added (status_pill: "Live", logoUrl: Okta CDN)
backend/connector_loader.py           — import connectors.okta.connector added in Identity / NAC / PAM section
```

## System Log Filter Pattern

URIP's default filter (stored in CREDENTIAL_FIELDS default and _DEFAULT_LOG_FILTER):

```
eventType eq "user.account.lock" or
eventType eq "user.session.access_admin_app" or
eventType eq "policy.evaluate_sign_on"
```

`_parse_event_types_from_filter()` extracts event type strings via regex and passes them to `list_system_log(types=[...])`, which builds the filter query parameter. Pagination uses Okta's `Link: <cursor_url>; rel="next"` header.

## Severity Mapping

| Okta event type | URIP severity |
|---|---|
| user.account.lock | high |
| user.session.access_admin_app | high |
| application.user_membership.add / remove | high |
| policy.evaluate_sign_on + outcome DENY | medium |
| policy.evaluate_sign_on + other outcome | low |
| All other event types | low |

## pytest Output

```
collected 28 items

TestOktaRegistration::test_register                         PASSED
TestOktaRegistration::test_metadata                         PASSED
TestOktaAuthenticate::test_authenticate_with_valid_token    PASSED
TestOktaAuthenticate::test_authenticate_invalid_token...    PASSED
TestOktaAuthenticate::test_authenticate_403_raises...       PASSED
TestOktaAuthenticate::test_authenticate_missing_domain...   PASSED
TestOktaAuthenticate::test_authenticate_missing_token...    PASSED
TestOktaFetchFindings::test_fetch_system_log_events         PASSED
TestOktaFetchFindings::test_fetch_respects_since_parameter  PASSED
TestOktaFetchFindings::test_fetch_handles_pagination        PASSED
TestOktaFetchFindings::test_fetch_not_authenticated_raises  PASSED
TestOktaFetchFindings::test_fetch_5xx_raises                PASSED
TestOktaNormalize::test_normalize_account_lock_severity...  PASSED
TestOktaNormalize::test_normalize_policy_deny_severity...   PASSED
TestOktaNormalize::test_normalize_admin_app_access...       PASSED
TestOktaNormalize::test_normalize_default_severity_low      PASSED
TestOktaNormalize::test_normalize_policy_allow_severity...  PASSED
TestOktaNormalize::test_normalize_app_membership_add...     PASSED
TestOktaNormalize::test_normalize_source_url_in_descr...    PASSED
TestOktaNormalize::test_normalize_owner_team                PASSED
TestOktaHealthCheck::test_health_check_before_auth_ok       PASSED
TestOktaHealthCheck::test_health_check_ok                   PASSED
TestOktaHealthCheck::test_health_check_degraded             PASSED
TestOktaCredentialFields::test_credential_secrets_marked    PASSED
TestOktaCredentialFields::test_domain_field_required        PASSED
TestOktaCredentialFields::test_api_token_field_required     PASSED
TestOktaHelpers::test_parse_event_types_from_filter         PASSED
TestOktaHelpers::test_parse_event_types_empty_filter        PASSED

28 passed, 1 warning in 0.10s
```

INV-1 verified: `python3 -c "import connectors.okta.connector; from connectors.base.registry import _global_registry; print('okta' in _global_registry.list_names())"` → `True`

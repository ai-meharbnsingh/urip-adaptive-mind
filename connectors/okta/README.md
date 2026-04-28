# Okta Workforce Identity — Connector Setup Guide

## What this connector pulls

- **System Log events** — account locks, admin app access, policy sign-on evaluations,
  app membership changes (add/remove)
- **User posture** — status, last login, last updated (via `list_users`)
- **App assignments** — which Okta apps each user is assigned to (`list_apps`)
- **MFA enrollment** — enrolled factors per user (`get_factors`)

## Prerequisites

| Item | Detail |
|------|--------|
| Okta edition | Any tier including Free Trial / Developer |
| Admin role | **Read-Only Administrator** (minimum) or **Org Administrator** |
| Network | URIP egress to `https://your-org.okta.com` on TCP 443 |

## Step 1 — Create an API Token

1. Log in to your Okta admin console: `https://your-org.okta.com/admin`
2. Navigate to **Security → API → Tokens**
3. Click **Create Token**
4. Give it a descriptive name (e.g. `URIP-readonly`)
5. **Copy the token value immediately** — Okta shows it only once

> The token inherits the permissions of the user who created it.
> Use a dedicated service account with **Read-Only Admin** role to follow
> the principle of least privilege.

## Step 2 — Required scopes / role

Okta API tokens use role-based access, not OAuth scopes.  The token needs:

| Role | Purpose |
|------|---------|
| **Read-Only Administrator** | Read System Log, Users, Apps, Factors |
| *(optional)* **Org Administrator** | Required only if you also manage lifecycle via the API |

The URIP connector uses read-only methods only — `Read-Only Administrator` is sufficient.

## Step 3 — Configure URIP

In URIP → Tool Catalog → Okta tile, enter:

- **Okta Domain**: `your-org.okta.com` (no `https://`, no trailing slash)
- **API Token**: the token from Step 1
- **System Log event filter**: leave as default or customize (see below)

## System Log filter syntax

Okta uses its own filter language.  URIP's default filter:

```
eventType eq "user.account.lock" or
eventType eq "user.session.access_admin_app" or
eventType eq "policy.evaluate_sign_on"
```

### Other useful predicates

```
# All application membership changes
eventType eq "application.user_membership.add" or
eventType eq "application.user_membership.remove"

# Group membership changes (lateral movement indicator)
eventType eq "group.user_membership.add" or
eventType eq "group.user_membership.remove"

# Password changes
eventType eq "user.account.update_password"

# MFA reset / bypass
eventType eq "user.mfa.factor.deactivate"
```

Combine with `or` — Okta does not support `and` between `eventType eq` predicates
(each event has exactly one type).

Full event type reference:
https://developer.okta.com/docs/reference/api/event-types/

## Severity mapping

| Okta event type | URIP severity |
|-----------------|---------------|
| `user.account.lock` | **high** |
| `user.session.access_admin_app` | **high** |
| `application.user_membership.add` | **high** |
| `application.user_membership.remove` | **high** |
| `policy.evaluate_sign_on` + outcome `DENY` | **medium** |
| `policy.evaluate_sign_on` + other outcome | **low** |
| All other event types | **low** |

## Common errors

| Error | Cause | Fix |
|-------|-------|-----|
| `401 Unauthorized` | Token expired or revoked | Security → API → Tokens → create a new token |
| `403 Forbidden` | Service account role downgraded | Ensure the user still has Read-Only Admin role |
| `429 Too Many Requests` | Rate limit hit (Okta: 600 req/min per token) | URIP uses limit=1000 per page; if you have millions of log events reduce the polling interval |

## Disconnecting

1. URIP → Tool Catalog → Okta tile → **Disconnect**
2. Credentials are deleted from URIP's encrypted vault
3. Optionally revoke the token in Okta: Security → API → Tokens → Revoke

## References

- Okta Core API: https://developer.okta.com/docs/reference/core-okta-api/
- System Log API: https://developer.okta.com/docs/reference/api/system-log/
- Event Types reference: https://developer.okta.com/docs/reference/api/event-types/
- API Tokens: https://developer.okta.com/docs/guides/create-an-api-token/

# HashiCorp Vault Connector — URIP

**Category:** PAM | **Module:** IDENTITY | **Status:** Live

Connects to HashiCorp Vault (Community, Enterprise, or HCP Vault) and produces
posture-based findings: audit logging status, token hygiene, auth method
inventory, and secret engine mount analysis.

---

## Prerequisites

- Vault ≥ 1.9 (any edition)
- A service account Vault token with **read-only** capabilities on the paths
  listed below
- Network: URIP must reach `<vault_addr>:8200` (or your custom port) on TCP 443

---

## Recommended ACL Policy (HCL)

Create this policy in Vault before generating the URIP token.

```hcl
# urip-readonly.hcl — read-only posture policy for URIP

path "sys/health" {
  capabilities = ["read"]
}

path "sys/audit" {
  capabilities = ["list", "read"]
}

path "sys/auth" {
  capabilities = ["list", "read"]
}

path "sys/mounts" {
  capabilities = ["list", "read"]
}

path "sys/policies/acl" {
  capabilities = ["list", "read"]
}

path "auth/token/lookup-self" {
  capabilities = ["read"]
}
```

Apply the policy:

```bash
vault policy write urip-readonly urip-readonly.hcl
```

---

## Token Creation

Create a periodic token scoped to the policy above:

```bash
vault token create \
  -policy=urip-readonly \
  -period=720h \
  -display-name="urip-posture-scanner" \
  -no-default-policy
```

Copy the `token` field from the output. Store it in URIP's credential wizard.

**For Vault Enterprise (namespaces):**

```bash
vault token create \
  -policy=urip-readonly \
  -period=720h \
  -display-name="urip-posture-scanner" \
  -no-default-policy \
  -namespace=admin/teamA
```

Set the `namespace` field in URIP to match (e.g. `admin/teamA`).

---

## URIP Configuration

| Field       | Example value                             | Notes                                              |
|-------------|-------------------------------------------|----------------------------------------------------|
| vault_addr  | `https://vault.your-org.com:8200`         | Include scheme and port                            |
| token       | `hvs.CAESI…`                              | Token created above                                |
| namespace   | `admin/teamA`                             | Enterprise only — leave blank for Community        |

---

## Posture Findings Produced

| Finding Code              | Severity | Trigger condition                                       |
|---------------------------|----------|---------------------------------------------------------|
| VAULT-AUDIT-DISABLED      | critical | No audit devices configured on `/sys/audit`             |
| VAULT-SEALED              | critical | Vault reports `sealed: true`                            |
| VAULT-NOT-INITIALIZED     | critical | Vault reports `initialized: false`                      |
| VAULT-ROOT-TOKEN          | high     | URIP token has `root` in its policy list                |
| VAULT-USERPASS-AUTH       | medium   | `userpass` auth method is enabled (no MFA by default)   |
| VAULT-KV-V1-MOUNT         | low      | A KV secrets engine v1 mount found — should migrate v2  |
| VAULT-PERFORMANCE-STANDBY | info     | Node is performance standby (not an error, informational)|

---

## Cross-Reference with GHAS

GHAS (GitHub Advanced Security) detects secrets committed to code repositories.
Vault audit logging tells you whether those secrets were subsequently used after
leaking.

Recommended workflow:
1. Enable the GHAS connector to surface leaked-secret alerts.
2. Enable this Vault connector to verify audit logging is on.
3. If VAULT-AUDIT-DISABLED fires, treat any GHAS secret alert as undetected
   misuse — escalate to critical.

---

## Token Rotation

Vault periodic tokens auto-renew as long as URIP polls within the `-period`
window (720 hours = 30 days by default).  If the token expires:

1. Run `vault token create …` again with the same policy.
2. Update the token in URIP → Tool Catalog → HashiCorp Vault tile → Edit.

---

## Troubleshooting

| Error                    | Likely cause                          | Fix                                                                       |
|--------------------------|---------------------------------------|---------------------------------------------------------------------------|
| HTTP 403                 | Token missing capability on path      | Add the missing `path "…" { capabilities = […] }` block to the policy    |
| HTTP 503                 | Vault is sealed                       | Run `vault operator unseal` on Vault nodes                                |
| Namespace mismatch       | Wrong namespace path in URIP config   | Check `vault namespace list` and correct the `namespace` field in URIP    |
| `connection refused`     | Wrong `vault_addr` or firewall rule   | Verify `vault_addr` with `curl -k <vault_addr>/v1/sys/health`             |

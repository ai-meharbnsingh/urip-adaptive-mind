# URIP On-Premise Agent

Hybrid-SaaS Docker agent for the URIP risk intelligence platform.
This container runs **inside your network**.  It pulls findings from your
security tools, normalises them, stores them in **your** Postgres, and pushes
**only summary metadata** (counts and scores) to the URIP cloud portal.

> **Your sensitive data — IP addresses, hostnames, usernames, evidence files —
> never leaves your network.** The cloud only sees a number like `8.2 risk
> score, 15 criticals`.

Industry parallels: CrowdStrike Falcon Sensor, Tenable Nessus Agent,
Splunk Universal Forwarder.

---

## Prerequisites

- Linux host (or any Docker-capable environment) reachable from your security tools
- Docker 24+ and Docker Compose v2
- Outbound HTTPS to your cloud portal (`https://adverb.urip.io` or similar)
- A **license key** (issued by Semantic Gravity in your contract)
- A **Fernet encryption key** (32-byte URL-safe base64) for credential vault
  - Generate locally:
    ```sh
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ```

You can use the bundled Postgres (default) or point at your own Postgres
cluster — see `LOCAL_DB_URL` in the env table below.

---

## 1. Configure environment

Create `agent/.env` next to `docker-compose.agent.yml`:

```
AGENT_TENANT_SLUG=adverb
AGENT_LICENSE_KEY=<paste from your contract>
CLOUD_PORTAL_URL=https://adverb.urip.io
FERNET_KEY=<paste 32-byte Fernet key>
LOCAL_POSTGRES_PASSWORD=<random strong password>
AGENT_LOG_LEVEL=INFO
```

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `AGENT_TENANT_SLUG` | yes | — | Your tenant slug (e.g. `adverb`) |
| `AGENT_LICENSE_KEY` | yes | — | Issued by Semantic Gravity |
| `CLOUD_PORTAL_URL` | yes | — | Your cloud portal URL |
| `LOCAL_DB_URL` | no | local Postgres container | Override to use your own DB |
| `FERNET_KEY` | yes | — | Encrypts connector API keys at rest |
| `AGENT_SCHEDULER_INTERVAL_SECONDS` | no | 900 (15 min) | Connector poll cadence |
| `AGENT_HEARTBEAT_INTERVAL_SECONDS` | no | 300 (5 min) | Health check-in cadence |
| `AGENT_METADATA_INTERVAL_SECONDS` | no | 900 (15 min) | Cloud metadata push cadence |
| `AGENT_DRILLDOWN_POLL_SECONDS` | no | 2.0 | Drill-down responder polling |
| `AGENT_LOG_LEVEL` | no | INFO | Python log level |

---

## 2. Start the stack

```sh
docker compose -f agent/docker-compose.agent.yml up -d
```

Watch the logs to confirm registration with the cloud:

```sh
docker compose -f agent/docker-compose.agent.yml logs -f agent
```

Expected output (first boot):

```
agent | Registering with cloud at https://adverb.urip.io/api/agent-ingest/register
agent | Registered as tenant_id=…; shared_secret persisted to /var/lib/urip-agent/shared_secret.json
agent | Local DB ready at postgresql+asyncpg://urip:***@postgres:5432/urip_agent
agent | URIP Agent 0.1.0 starting all loops…
```

The `shared_secret` is stored in a Docker named volume so it survives
container restarts.  If you re-run `register_with_cloud`, the cloud rotates
the secret and the agent picks up the new one.

---

## 3. Verify the cloud sees you

In the cloud portal:

1. **Settings → Agent Status** should show your agent online with a recent
   `last_seen` timestamp.
2. The **Connector Health** panel should list each enabled connector with
   `status: ok` after the first successful poll cycle.

If you don't see your agent within 5 minutes:

```sh
docker compose -f agent/docker-compose.agent.yml logs --tail=200 agent
```

Look for HTTP 401 responses (bad license key or wrong tenant slug) or 5xx
responses (cloud unreachable).

---

## 4. Configure connectors

All connector credentials are added through the **cloud portal**, NOT in the
agent container.  Workflow:

1. Log in to your portal at `$CLOUD_PORTAL_URL`.
2. Navigate to **Onboarding → Tool Catalog**.
3. Tick the tools you own (Tenable, SentinelOne, Zscaler, etc.).
4. For each tool, click **Configure** and paste the API credentials.
5. Click **Test Connection**.  The cloud forwards the test to your agent
   over the encrypted channel — credentials are sealed in the local
   Fernet-encrypted vault before being used.
6. Within the next poll cycle (default 15 min), the agent starts pulling
   findings, normalising them, and writing them to **your** Postgres.

---

## Troubleshooting

| Symptom | Diagnosis | Fix |
|---|---|---|
| `HTTP 401: Invalid license key` on first boot | Wrong `AGENT_LICENSE_KEY` or `AGENT_TENANT_SLUG` mismatch | Re-check the contract; confirm the slug matches the cloud |
| `HTTP 401: Bad X-Signature` after running for a while | The shared_secret on disk is stale (cloud was re-keyed) | Delete the `urip_agent_secret` volume and restart — the agent re-registers |
| Cloud dashboard shows `agent offline` | Outbound HTTPS blocked | Open egress to `$CLOUD_PORTAL_URL` (TCP/443) |
| `relation "risks" does not exist` | First-boot DB init failed | Check Postgres logs; ensure the agent has `CREATE TABLE` on the database |
| `Could not decrypt creds` | `FERNET_KEY` was rotated without re-uploading credentials | Re-enter all connector API keys in the portal |
| Drill-down "View Details" hangs forever | Drilldown responder not running OR cloud cannot reach itself | Check agent logs for `DrilldownResponder starting`; check cloud SSE endpoint reachable from browsers |

For deeper logs:

```sh
docker compose -f agent/docker-compose.agent.yml exec agent \
  env | grep AGENT_
```

---

## Security

- The agent verifies every cloud → agent and agent → cloud message with
  HMAC-SHA256 over `{timestamp}.{path}.{body}`.
- Replay attacks are blocked by a ±5 minute timestamp window.
- The `shared_secret` is stored in a Docker volume mounted at
  `/var/lib/urip-agent/shared_secret.json` with `chmod 600`.
- Credentials added through the portal are encrypted with your Fernet key
  before being written to your Postgres.  The key never leaves the agent.
- The reporter has a defence-in-depth check that **refuses to send any
  payload** containing keys named `asset`, `ip`, `hostname`, `username`,
  `finding`, or `cve_id`.  Drill-down responses bypass this check because
  they are explicitly user-initiated and the cloud wipes the response from
  its temp store immediately after forwarding to the user's browser.

---

## Stopping the agent

```sh
docker compose -f agent/docker-compose.agent.yml down
```

Adding `-v` removes the data volumes (DB + shared_secret) — only do this if
you want to start fresh.

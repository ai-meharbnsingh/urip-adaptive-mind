# URIP Hybrid-SaaS On-Premise Agent — Phase 4
#
# This image runs INSIDE the customer's network.  It carries the connector
# framework + the encrypted reporter.  It NEVER ships any cloud-side code
# (compliance frameworks, scoring engine, frontend, multi-tenant routing).

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Minimal OS deps:  libpq for asyncpg's optional native bits + curl for healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Python deps -------------------------------------------------------------
# We reuse the project requirements.txt so the agent's deps stay in lock-step
# with the cloud build (one source of truth).  The agent doesn't need every
# cloud dep but the surplus is small and avoids drift.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# --- Application code --------------------------------------------------------
# Only the bits the agent needs: connectors/, agent/, and the model definitions
# the agent reads via SQLAlchemy (backend.models, backend.database, backend.config).
# Compliance/frontend/etc. are intentionally NOT copied.
COPY connectors/ /app/connectors/
COPY backend/__init__.py /app/backend/__init__.py
COPY backend/database.py /app/backend/database.py
COPY backend/config.py /app/backend/config.py
COPY backend/models/ /app/backend/models/
COPY backend/middleware/ /app/backend/middleware/
COPY backend/schemas/ /app/backend/schemas/
COPY agent/ /app/agent/

ENV PYTHONPATH=/app

# Default env — override via docker-compose / docker run
ENV AGENT_LOG_LEVEL=INFO \
    AGENT_SCHEDULER_INTERVAL_SECONDS=900 \
    AGENT_HEARTBEAT_INTERVAL_SECONDS=300 \
    AGENT_METADATA_INTERVAL_SECONDS=900 \
    AGENT_DRILLDOWN_POLL_SECONDS=2.0 \
    AGENT_SHARED_SECRET_FILE=/var/lib/urip-agent/shared_secret.json

# Persistent volume for the shared_secret file (survives container restarts)
VOLUME ["/var/lib/urip-agent"]

# Health: the agent exposes no HTTP server itself; we check that the process
# is alive AND that the secret file exists (proves successful registration).
HEALTHCHECK --interval=60s --timeout=10s --start-period=120s --retries=3 \
    CMD test -f $AGENT_SHARED_SECRET_FILE || exit 1

ENTRYPOINT ["python", "-m", "agent.agent_main"]

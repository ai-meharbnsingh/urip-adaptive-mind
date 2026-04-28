# ── Stage 1: builder ─────────────────────────────────────────────────────────
# Install all Python dependencies into an isolated venv so the runtime image
# doesn't need gcc / libpq-dev and keeps its attack surface minimal.
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Create a venv at a well-known path so the runtime stage can copy it cleanly.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ── Stage 2: runtime ─────────────────────────────────────────────────────────
# Lean image: only the pre-built venv + application source.  No compiler.
FROM python:3.12-slim AS runtime

# libpq is needed at runtime by asyncpg / psycopg.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy the fully-populated venv from the builder stage.
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy application source trees.
COPY backend/ backend/
COPY connectors/ connectors/
COPY shared/ shared/
COPY alembic/ alembic/
COPY alembic.ini .
COPY frontend/ frontend/

# ── Non-root user ─────────────────────────────────────────────────────────────
# Running as root inside a container is a security risk: a container escape
# would immediately grant host root.  UID 1001 avoids conflicts with the default
# 'nobody' (65534) and common system accounts.
RUN groupadd --gid 1001 appuser && \
    useradd --uid 1001 --gid 1001 --no-create-home --shell /bin/false appuser

USER appuser

EXPOSE 8000

# ── Reload control ─────────────────────────────────────────────────────────────
# URIP_RELOAD=1 re-enables --reload for local dev (docker build --build-arg URIP_RELOAD=1).
# Production deployments must NOT pass this arg — multi-worker mode is the default.
ARG URIP_RELOAD=0

CMD if [ "$URIP_RELOAD" = "1" ]; then \
      exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload; \
    else \
      exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4 --no-server-header; \
    fi

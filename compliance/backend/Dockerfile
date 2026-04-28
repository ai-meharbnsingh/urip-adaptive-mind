# Compliance backend image.
#
# IMPORTANT: build context is ./compliance (NOT ./compliance/backend) so we
# can COPY the sibling alembic/ + alembic.ini without `COPY ../` which is
# illegal. The matching docker-compose.yml block sets:
#   build:
#     context: ./compliance
#     dockerfile: backend/Dockerfile
FROM python:3.11-slim AS runtime

WORKDIR /app

# System dependencies for asyncpg + psycopg.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python package from backend/pyproject.toml.
COPY backend/pyproject.toml .
COPY backend/compliance_backend/ compliance_backend/

# Alembic migrations — siblings of backend/ inside the compliance/ context.
COPY alembic/ alembic/
COPY alembic.ini .

RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir -e ".[dev]"

# Non-root user (security).
RUN groupadd --gid 1001 appuser && \
    useradd --uid 1001 --gid 1001 --no-create-home --shell /bin/false appuser
USER appuser

EXPOSE 8001

CMD ["uvicorn", "compliance_backend.main:app", "--host", "0.0.0.0", "--port", "8001"]

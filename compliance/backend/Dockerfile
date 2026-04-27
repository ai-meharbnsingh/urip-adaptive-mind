FROM python:3.11-slim

WORKDIR /app

# System dependencies for asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python package (PEP 621 pyproject.toml)
COPY pyproject.toml .
COPY compliance_backend/ compliance_backend/
# Copy alembic config + migrations from compliance/ parent
COPY ../alembic/ alembic/
COPY ../alembic.ini .

RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir -e ".[dev]"

EXPOSE 8001

CMD ["uvicorn", "compliance_backend.main:app", "--host", "0.0.0.0", "--port", "8001"]

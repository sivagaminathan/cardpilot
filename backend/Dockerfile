FROM python:3.11-slim

WORKDIR /app

# Install OS-level dependencies for psycopg/asyncpg compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency spec, migration config, and package files
COPY pyproject.toml README.md alembic.ini ./
COPY alembic/ ./alembic/
COPY app/ ./app/

# Install application and dependencies in editable mode for dev hot-reloading
RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

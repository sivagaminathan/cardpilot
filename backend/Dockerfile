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
COPY scripts/ ./scripts/

# Install application and dependencies in editable mode
RUN pip install --no-cache-dir -e . \
    && addgroup --system app \
    && adduser --system --ingroup app app \
    && chmod +x /app/scripts/release.sh \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

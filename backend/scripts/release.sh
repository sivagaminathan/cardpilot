#!/usr/bin/env sh
set -eu

# Run Alembic schema migrations (prefers DIRECT_DATABASE_URL when set)
alembic upgrade head

# Seed catalog and demo profiles on first deploy only (safe no-op if already seeded)
python -m app.seeds.loader --if-empty

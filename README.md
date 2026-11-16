# CardPilot

CardPilot is a deterministic, explainable credit-card rewards and benefits optimizer built with **FastAPI**, **React + TypeScript**, **PostgreSQL**, and **OpenTelemetry**. All profiles, issuers, cards, and merchants are **fictional sample data** for demonstration purposes only.

## Architecture

- **Frontend (`frontend/`):** React 18, TypeScript (strict), Vite SPA (`Dashboard` + `Compare Cards for Purchase` flow).
- **Backend (`backend/`):** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async `asyncpg`), Alembic migrations, and a pure `Decimal`/integer-cents reward engine (`backend/app/engine/`).
- **Database:** PostgreSQL 16 (Docker Compose locally; Neon PostgreSQL in deployment).
- **Observability (`observability/`):** OpenTelemetry SDK (traces, metrics, correlated logs) → OTLP/HTTP → OTel Collector → **Tempo** (traces), **Loki** (logs), **Prometheus** (metrics), and **Grafana** (dashboards + alerting).
- **CI/CD & On-Call (`.github/workflows/`):**
  - `ci.yml`: Ruff, mypy, Alembic upgrade, pytest (≥90% engine branch coverage), ESLint, tsc/Vite build, Vitest.
  - `deploy.yml`: Automatic Render development deployment on `main` push after CI succeeds, verified via Render API + `/healthz` & `/readyz` smoke tests.
  - `oncall-agent.yml` + `.github/scripts/oncall_agent.py`: Investigates Grafana 5xx alerts using Loki/Tempo evidence and opens an incident investigation PR.

## Live Development Deployment

- **Frontend:** https://cardpilot-web-dev.onrender.com
- **Backend API:** https://cardpilot-api-dev.onrender.com (`/healthz`, `/readyz`, `/metrics`, `/docs`)

## Running Locally (Docker Compose)

1. Copy `.env.example` to `.env`.
2. Start the full application + observability stack:
   ```bash
   docker compose --profile observability up -d --build
   ```
3. Run migrations and seed demo data:
   ```bash
   uv run --directory backend --extra dev alembic upgrade head
   uv run --directory backend --extra dev python -m app.seeds.loader
   ```
4. Open:
   - Frontend: http://localhost:5173
   - Backend API / Docs: http://localhost:8000/docs
   - Grafana: http://localhost:3000 (`CardPilot API Observability` dashboard)
   - Prometheus: http://localhost:9090

## Running Tests

If GNU `make` is installed (and PostgreSQL is running locally for backend DB/API integration tests), `make test` runs both the backend Pytest suite (with >=90% engine branch coverage) and the frontend Vitest suite. On Windows without `make`, run the commands directly:

```powershell
# Backend (unit + PostgreSQL integration + >=90% engine branch coverage)
uv run --directory backend --extra dev pytest --cov=app.engine --cov-branch --cov-fail-under=90 --cov-report=term-missing
uv run --directory backend --extra dev mypy app
uv run --directory backend --extra dev ruff check .
uv run --directory backend --extra dev ruff format --check .

# Frontend (ESLint, TypeScript + Vite build, Vitest)
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend test
```

## Reproducing the Controlled Incident & On-Call Agent

1. Enable `DEV_FAULT_INJECT_RECOMMENDATIONS=true` in development (`ENVIRONMENT=development`; automatically ignored if `ENVIRONMENT=production`).
2. Submit a recommendation request (`POST /api/v1/profiles/maya/recommendations` or via the **Compare** tab). The API returns HTTP `500` and emits `recommendation.fault_injected` with `trace_id`.
3. Grafana alert `CardPilot API High 5xx Error Rate` (`observability/grafana/provisioning/alerting/alerts.yml`) triggers after >2 HTTP 5xx responses in 2 minutes and dispatches `.github/workflows/oncall-agent.yml`.
4. The on-call agent inspects Loki/Tempo telemetry and repository code, writes an incident report under `docs/incidents/`, and opens a PR.
5. Set `DEV_FAULT_INJECT_RECOMMENDATIONS=false` to restore service and resolve the alert.

See [docs/observability-grafana-cloud.md](docs/observability-grafana-cloud.md) for Grafana Cloud OTLP setup and [docs/submission-evidence.md](docs/submission-evidence.md) for certificate mapping.

## Known Limitations

- Free-tier Render instances sleep after inactivity (cold starts up to ~30–60s).
- Sample rules and valuations are fictional and illustrative only, not current issuer terms or financial advice.

# CardPilot

CardPilot is a deterministic, explainable credit-card rewards and benefits optimizer built with **FastAPI**, **React + TypeScript**, **PostgreSQL**, and **OpenTelemetry**. All profiles, issuers, cards, and merchants are **fictional sample data** for demonstration purposes only — not current issuer terms or financial advice.

---

## 1. Project Purpose & Live Application

### What Problem CardPilot Solves
Choosing the best credit card at checkout is error-prone when cards earn different reward currencies (cash back, bank points, airline miles), enforce quarterly/annual spend caps, or have category/merchant exclusions. CardPilot evaluates a purchase against all active cards in a profile using integer-cents and `Decimal` arithmetic (`backend/app/engine/`), keeps unvalued reward currencies separate (`unranked` rather than guessing), and explains every rule, cap, rounding step, and valuation in plain text.

### Live Deployment & Endpoints
- **Frontend SPA:** https://cardpilot-web-dev.onrender.com
- **Backend API Docs (Swagger UI):** https://cardpilot-api-dev.onrender.com/docs
- **Health (Liveness):** `GET https://cardpilot-api-dev.onrender.com/healthz`
- **Readiness (DB check):** `GET https://cardpilot-api-dev.onrender.com/readyz`
- **Prometheus Metrics:** `GET https://cardpilot-api-dev.onrender.com/metrics`

> **Note:** Render free-tier services sleep after inactivity; the first request may take 30–60 seconds to wake up.

### Reviewer Walkthrough (Live App)
1. Open https://cardpilot-web-dev.onrender.com.
2. On the **Dashboard** tab, verify the backend status indicator shows healthy connectivity and review the fictional-data disclaimer banner.
3. Switch to the **Compare** tab (`Compare Cards for Purchase`):
   - Select a demo profile (`maya` — *Maya — The Optimizer*, or `dev` — *Dev — Benefit Tracker*).
   - Enter a purchase amount (e.g. `$125.00`), category (`groceries`), and date (`2026-08-15`), then submit.
   - Inspect **Ranked Cards** (e.g. `Grocery 5x` at 5x with estimated dollar value), **Unranked Cards** (`Skyward Explorer` when no `SKY_MILES` valuation is set), and the expandable per-card **Calculation Explanation** trace.

---

## 2. Architecture & Database Persistence

- **Frontend (`frontend/`):** React 18, TypeScript (strict), Vite SPA (`Dashboard` + `CompareView`).
- **Backend (`backend/`):** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async `asyncpg`), Alembic migrations.
- **Pure Reward Engine (`backend/app/engine/`):** Pure Python (`Decimal` + integer cents, zero DB/network/clock side effects). Evaluates applicability, rule selection, spend caps, unit rounding, currency valuation, and card ranking.
- **Database (`PostgreSQL 16`):** Docker Compose locally (`db` service, database `cardpilot`, persistent named volume `postgres_data`); Neon PostgreSQL in Render development deployment.

### What PostgreSQL Stores (16 Tables)
Alembic migrations (`backend/alembic/versions/`) create 16 tables across three groups:
- **Reference (`backend/app/models/reference.py`):** `reward_currencies`, `categories`, `merchants`, `card_products`, `rule_sources`
- **Rules & Caps (`backend/app/models/rules.py`):** `spend_caps`, `earning_rules`, `rule_exclusions`
- **Profiles, Spend History & Benefits (`backend/app/models/profiles.py`):** `profiles`, `profile_cards`, `currency_valuations`, `transactions`, `transaction_reward_calcs`, `calc_rule_references`, `benefit_definitions`, `benefit_usages`

### Persistence vs. Pure Calculation Engine
- **Seed & API reads/writes:** `python -m app.seeds.loader` (and automatic `ensure_seeded()` on `GET /api/v1/profiles`, `GET /api/v1/categories`, or `POST /api/v1/profiles/{profile_key}/recommendations` when `profiles` is empty) idempotently commits the fictional catalog and demo profiles into PostgreSQL.
- **Recommendation evaluation:** `POST /api/v1/profiles/{profile_key}/recommendations` queries `profiles`, `categories`, `merchants`, `profile_cards`, `currency_valuations`, `earning_rules`, `spend_caps`, `rule_exclusions`, and `transactions` from PostgreSQL via `asyncpg`, converts them into immutable engine dataclasses, and runs `evaluate_purchase` + `rank_card_evaluations` in memory without mutating transaction history.

### Database Persistence Verification Walkthrough (Docker Compose)
> **Warning:** Do **not** run `docker compose down -v` during this test — the `-v` flag deletes the `postgres_data` volume and wipes all database state.

1. **Start the database and application:**
   ```bash
   docker compose up -d --build
   ```
2. **Run migrations and load seed data:**
   ```bash
   uv run --directory backend --extra dev alembic upgrade head
   uv run --directory backend --extra dev python -m app.seeds.loader
   ```
3. **Trigger/verify persistent records via the API and read-only SQL:**
   ```bash
   curl -sf http://localhost:8000/api/v1/profiles
   docker compose exec db psql -U postgres -d cardpilot -c "SELECT id, slug, display_name FROM profiles ORDER BY id;"
   ```
   *(If the database was not yet seeded before calling `/api/v1/profiles`, `ensure_seeded()` commits the `maya` and `dev` profile rows on first request.)*
4. **Restart the `db` container without removing volumes and wait for readiness:**
   ```bash
   docker compose restart db
   docker compose exec db sh -c "until pg_isready -U postgres -d cardpilot; do sleep 1; done"
   ```
5. **Re-query the API and PostgreSQL to confirm persistence across container restart:**
   ```bash
   curl -sf http://localhost:8000/api/v1/profiles
   docker compose exec db psql -U postgres -d cardpilot -c "SELECT id, slug, display_name FROM profiles ORDER BY id;"
   ```
   The same `maya` and `dev` records remain present in `profiles` because `postgres_data` is mounted at `/var/lib/postgresql/data`.

---

## 3. Local Observability (No Grafana Cloud Required)

The local Docker Compose `observability` profile runs the complete telemetry pipeline without any cloud accounts:

`FastAPI (OpenTelemetry SDK) → OTLP/HTTP (:4318) → OTel Collector → Tempo (traces) + Loki (logs) + Prometheus (metrics) → Grafana (:3000)`

*(Prometheus also scrapes `api:8000/metrics` and `otel-collector:8889` every 15s per `observability/prometheus.yml`.)*

### Start the Full Stack
1. Copy `.env.example` to `.env`:
   - **PowerShell:** `Copy-Item .env.example .env`
   - **Bash:** `cp .env.example .env`
2. Start all 8 containers (`db`, `api`, `web`, `otel-collector`, `prometheus`, `loki`, `tempo`, `grafana`):
   ```bash
   docker compose --profile observability up -d --build
   ```
3. Run migrations and seed demo data:
   ```bash
   uv run --directory backend --extra dev alembic upgrade head
   uv run --directory backend --extra dev python -m app.seeds.loader
   ```

### Local URLs & Provisioned Resources
- **Frontend:** http://localhost:5173
- **Backend API / Swagger Docs:** http://localhost:8000/docs (`/healthz`, `/readyz`, `/metrics`)
- **Prometheus:** http://localhost:9090
- **Grafana:** http://localhost:3000 (anonymous `Admin` access is enabled in `docker-compose.yml`; no login required)
- **Provisioned Datasources (`observability/grafana/provisioning/datasources/datasources.yml`):**
  - `Prometheus` (`uid: prometheus`, default)
  - `Loki` (`uid: loki`, with `TraceID` derived field linking `"trace_id"` to Tempo)
  - `Tempo` (`uid: tempo`, with `tracesToLogsV2` linking to Loki by `traceID` and `serviceMap` to Prometheus)
- **Provisioned Dashboard:** `CardPilot API Observability` (`uid: cardpilot-api`, `observability/grafana/dashboards/cardpilot-api.json`)

### Inspecting Metrics, Logs, and Traces in Grafana
1. Open http://localhost:3000 → **Dashboards** → **CardPilot API Observability** to view `API Request Rate (req/s)` and `API 5xx Error Rate (req/s)` (`cardpilot_http_requests_total`).
2. To inspect Prometheus metrics directly, open **Explore** → **Prometheus** and run:
   ```promql
   sum(cardpilot_http_requests_total) by (method, path, status_code)
   ```
3. To inspect structured JSON logs and find a `trace_id`, open **Explore** → **Loki** and run:
   ```logql
   {service_name="cardpilot-api"}
   ```
   Expand any log entry to copy its `trace_id` (or click the provisioned `TraceID` link directly).
4. To view the distributed trace (FastAPI HTTP span + `recommendation.evaluate` + SQLAlchemy DB spans), open **Explore** → **Tempo**, switch to **Search** or paste the `trace_id` into **TraceID**, and click **Logs for this span** to jump back to correlated Loki logs.

> **Alerting & Webhook Note:** `observability/grafana/provisioning/alerting/alerts.yml` provisions the `CardPilot API High 5xx Error Rate` alert rule locally, **but** no contact point or notification policy is provisioned in `observability/grafana/provisioning/alerting/`. Local Grafana evaluates the alert state in the UI; forwarding alerts automatically to GitHub requires configuring a Webhook contact point targeting `POST http://api:8000/api/v1/webhooks/grafana-alert` with `GRAFANA_WEBHOOK_SECRET` and `GITHUB_DISPATCH_TOKEN` set in `.env`. Grafana Cloud is optional and not required for this demonstration (see `docs/observability-grafana-cloud.md`).

---

## 4. End-to-End Incident & On-Call Demonstration

This walkthrough reproduces a controlled non-production failure, observes it in local Grafana, and triggers the AI on-call workflow.

1. **Start the application and observability stack** (Section 3) and verify readiness:
   ```bash
   curl -sf http://localhost:8000/healthz
   curl -sf http://localhost:8000/readyz
   ```
2. **Enable controlled fault injection (development only):**
   Set `DEV_FAULT_INJECT_RECOMMENDATIONS=true` in `.env` (automatically ignored if `ENVIRONMENT=production`) and recreate `api`:
   ```bash
   docker compose --profile observability up -d api
   ```
3. **Trigger the recommendation API failure** (send 3+ requests so the >2 in 2m alert threshold is exceeded):
   - **PowerShell:**
     ```powershell
     1..3 | ForEach-Object {
       try {
         Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/v1/profiles/maya/recommendations" `
           -ContentType "application/json" `
           -Body '{"amount_cents":12500,"category_code":"groceries","purchase_date":"2026-08-15"}'
       } catch { $_.Exception.Response.StatusCode }
     }
     ```
   - **Bash:**
     ```bash
     for i in 1 2 3; do
       curl -s -o /dev/null -w "%{http_code}\n" -X POST \
         http://localhost:8000/api/v1/profiles/maya/recommendations \
         -H "Content-Type: application/json" \
         -d '{"amount_cents":12500,"category_code":"groceries","purchase_date":"2026-08-15"}'
     done
     ```
4. **Expected failure & telemetry:** Each request returns HTTP `500` (RFC 9457 Problem Details), increments `cardpilot_http_requests_total{status_code="500"}` and `cardpilot_recommendations_total{outcome="fault_injected"}`, and logs `"message": "recommendation.fault_injected"` with `trace_id` and `span_id`.
5. **Inspect in local Grafana (`http://localhost:3000`):**
   - **Dashboard:** `CardPilot API Observability` shows the `API 5xx Error Rate (req/s)` spike.
   - **Loki:** Query `{service_name="cardpilot-api"} |= "fault_injected"` to inspect the JSON error log and its `trace_id`.
   - **Tempo:** Look up that `trace_id` to view the failing `recommendation.evaluate` span.
   - **Alerting → Alert rules:** `CardPilot API High 5xx Error Rate` transitions to **Firing** once `sum(increase(cardpilot_http_requests_total{status_code=~"5.."}[2m])) > 2`.
6. **Triggering the On-Call GitHub Actions Workflow (`.github/workflows/oncall-agent.yml`):**
   - **Option A — Manual trigger (default, no webhook secrets required):** In GitHub **Actions → AI On-Call Agent → Run workflow** (`workflow_dispatch`), keep `environment=development` (optionally paste the `trace_id` from Loki) and run the workflow.
   - **Option B — Alert-driven webhook relay (requires manual setup):** Set `GRAFANA_WEBHOOK_SECRET` and `GITHUB_DISPATCH_TOKEN` in `.env` and recreate `api` (`docker compose --profile observability up -d api`), then in local Grafana **Alerting → Contact points** add a **Webhook** pointing to `http://api:8000/api/v1/webhooks/grafana-alert` with header `Authorization: Bearer <GRAFANA_WEBHOOK_SECRET>` and route `service=cardpilot-api` alerts to it. Note: local `http://localhost:3100`/`3200` are not reachable from GitHub-hosted runners, so without `GRAFANA_LOKI_URL`/`GRAFANA_TEMPO_URL`/`OPENAI_API_KEY` GitHub Secrets, `.github/scripts/oncall_agent.py` uses its deterministic RCA fallback and pytest validation.
7. **Inspect workflow & PR:** In GitHub **Actions**, confirm `Investigate Alert & Open Incident PR` passes `pytest tests/api/test_recommendations.py` (the workflow's targeted API check, distinct from the full 288-test backend suite and `backend/tests/test_oncall_agent.py`), writes `docs/incidents/incident-<timestamp>.md`, and opens a PR against `main` (never auto-merged).
8. **Recover & verify:** Set `DEV_FAULT_INJECT_RECOMMENDATIONS=false` in `.env`, recreate `api` (`docker compose --profile observability up -d api`), and send a valid request:
   ```bash
   curl -sf -X POST http://localhost:8000/api/v1/profiles/maya/recommendations \
     -H "Content-Type: application/json" \
     -d '{"amount_cents":12500,"category_code":"groceries","purchase_date":"2026-08-15"}'
   ```
   Confirm HTTP `200` with ranked cards (`Grocery 5x`). After the 2-minute evaluation window clears, `CardPilot API High 5xx Error Rate` returns to **Normal**.

---

## 5. Tests, Quality Checks & E2E Scope

- **Backend Pytest:** Unit, engine, seed, telemetry, webhook relay, and real PostgreSQL DB/API integration tests (`backend/tests/`), enforcing **>= 90%** branch coverage on `backend/app/engine/`.
- **Frontend Vitest:** Component & UI state tests (`frontend/src/App.test.tsx`).
- **Automated Browser E2E:** **Not implemented** (`make e2e` is a placeholder for `T46/T47`; no Playwright config or browser E2E suite exists). The incident walkthrough in Section 4 is a manual/scripted operational demonstration, not a Playwright test.

### Running Automated Tests
**Linux / macOS (with GNU `make` and PostgreSQL running on `localhost:5432`):**
```bash
make test
```
(`make test` runs `test-be` with `--cov=app.engine --cov-branch --cov-fail-under=90` and `test-fe` via `npm --prefix frontend test`, matching `.github/workflows/ci.yml`.)

**Windows PowerShell (without `make`, with PostgreSQL running on `localhost:5432`):**
```powershell
# Backend tests + >=90% engine branch coverage
uv run --directory backend --extra dev pytest --cov=app.engine --cov-branch --cov-fail-under=90 --cov-report=term-missing

# Backend lint, formatting, and typecheck
uv run --directory backend --extra dev ruff check .
uv run --directory backend --extra dev ruff format --check .
uv run --directory backend --extra dev mypy app

# Frontend lint, TypeScript/Vite build, and Vitest
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend test
```

---

## 6. Project Directory Guide

| Path | Purpose |
|---|---|
| `backend/app/engine/` | Pure `Decimal`/integer-cents reward rules, caps, rounding, valuation, and ranking engine |
| `backend/app/api/` | FastAPI routers (`/api/v1/profiles`, `/categories`, `/recommendations`, `/webhooks/grafana-alert`) and RFC 9457 error handlers |
| `backend/tests/` | Pytest suite (engine, PostgreSQL models/migrations, API integration, webhooks, telemetry, on-call agent) |
| `frontend/src/` | React + TypeScript SPA (`Dashboard`, `CompareView`, `BackendStatus`, Vitest tests) |
| `observability/` | OTel Collector, Prometheus, Loki, Tempo, and Grafana provisioning/dashboard configs |
| `.github/workflows/` | `ci.yml` (lint, typecheck, build, `make test`), `deploy.yml` (Render dev deploy + smoke test), `oncall-agent.yml` |
| `.github/scripts/` | `oncall_agent.py` (Loki/Tempo evidence collection, RCA, pytest validation, incident report generation) |
| `docs/` | Architecture decisions (`decisions/`), `dev-log.md`, `submission-evidence.md`, `observability-grafana-cloud.md` |

---

## 7. Known Limitations

- **Fictional data only:** All profiles, issuers, card products, rules, and valuations are fictional sample data for demonstration only, not current issuer terms or financial advice.
- **Render free tier:** Hosted development services sleep when idle (30–60s cold starts).
- **Grafana Cloud not configured:** Live telemetry and alerting are demonstrated using the local Docker Compose observability stack; Grafana Cloud is optional and unconfigured.
- **Grafana webhook provisioning:** Local Grafana provisions `alerts.yml` only; contact points/notification policies require manual UI setup if testing alert-triggered webhooks locally.
- **On-call agent scope:** `oncall_agent.py` generates an incident investigation report PR under `docs/incidents/` for human review; it does not automatically patch application code or auto-merge PRs.
- **Browser E2E tests:** Playwright E2E (`make e2e`) is not yet implemented.

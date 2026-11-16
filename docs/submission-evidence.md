# CardPilot — Submission Evidence & Certificate Mapping

## Certificate Criteria Mapping

| Criterion | Status | Evidence in Repository |
|---|---|---|
| Application (Frontend + Backend + DB) | Implemented & verified | `frontend/src/components/CompareView.tsx`, `backend/app/api/recommendations.py`, `backend/app/services/recommendations.py`, `backend/app/seeds/loader.py` |
| Testing (Unit + Integration) | Implemented & verified | `backend/tests/` (271 passed, 96.78% engine branch coverage), `frontend/src/App.test.tsx` (11 passed) |
| Containerization (Docker Compose) | Implemented & verified | `docker-compose.yml` (8 services: `db`, `api`, `web`, `otel-collector`, `prometheus`, `loki`, `tempo`, `grafana`) |
| Public Deployment (Render + Neon) | Implemented & live | `render.yaml`, https://cardpilot-web-dev.onrender.com, https://cardpilot-api-dev.onrender.com |
| CI/CD | Implemented & verified | `.github/workflows/ci.yml`, `.github/workflows/deploy.yml` (Render API deploy verification + `/healthz` & `/readyz` smoke tests) |
| Observability (Logs, Metrics, Traces, UI) | Implemented & verified locally | `backend/app/telemetry/setup.py`, `observability/otel-collector.yaml`, `observability/grafana/dashboards/cardpilot-api.json` |
| Alerting | Provisioned locally; Cloud guide ready | `observability/grafana/provisioning/alerting/alerts.yml` (`CardPilot API High 5xx Error Rate`) |
| AI On-Call Agent | Implemented | `.github/workflows/oncall-agent.yml`, `.github/scripts/oncall_agent.py` |

## Commands & Actual Verification Results (2026-11-16)

- `uv run --directory backend --extra dev pytest --cov=app.engine --cov-branch --cov-fail-under=90 --cov-report=term-missing`: **271 passed** in 8.43s (`96.78%` engine branch coverage).
- `uv run --directory backend --extra dev mypy app`: **Success: no issues found in 33 source files**.
- `uv run --directory backend --extra dev ruff check .`: **All checks passed**.
- `uv run --directory backend --extra dev ruff format --check .`: **65 files already formatted**.
- `npm --prefix frontend run lint`: **0 errors** (2 `react-refresh/only-export-components` warnings).
- `npm --prefix frontend run build`: **tsc && vite build succeeded** in 830ms.
- `npm --prefix frontend test`: **11 passed (11)**.
- Local Docker Compose `--profile observability`: Verified all 8 containers running; Prometheus (`cardpilot_http_requests_total`), Tempo (trace `2b9a3d965f7aaba8022bc13edf5bc5f8`), Loki (correlated log with identical `trace_id`), and Grafana datasources/dashboard (`cardpilot-api`) verified via HTTP API.

## Remaining Manual Steps for Hosted Demo & Screenshots

1. **Grafana Cloud OTLP (Render):** Set `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS` on `cardpilot-api-dev` per `docs/observability-grafana-cloud.md`.
2. **GitHub Secrets (On-Call Agent):** Optionally add `OPENAI_API_KEY`, `GRAFANA_LOKI_URL`, `GRAFANA_TEMPO_URL`, `GRAFANA_AUTH_HEADER` in GitHub Repository Secrets, and configure the Grafana Alert Webhook to `repository_dispatch`.
3. **Screenshots to capture:**
   - Deployed Compare UI showing ranked & unranked cards (`https://cardpilot-web-dev.onrender.com`).
   - Grafana `CardPilot API Observability` dashboard with metrics, traces, and correlated `trace_id` logs.
   - Alert firing during `DEV_FAULT_INJECT_RECOMMENDATIONS=true` and resolving after disabling it.
   - GitHub Actions `AI On-Call Agent` run & opened incident PR.

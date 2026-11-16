# Hosted Observability & Alerting Setup (Grafana Cloud + Render)

This guide explains how to connect the deployed Render development backend (`cardpilot-api-dev`) to Grafana Cloud Free Tier and wire the AI on-call agent.

## 1. Create a Grafana Cloud Free Tier Stack

1. Sign in to [Grafana Cloud](https://grafana.com/) and open your stack.
2. Open **Connections → Add new connection → OpenTelemetry (OTLP)**.
3. Copy your **OTLP Endpoint** (for example `https://otlp-gateway-prod-us-east-0.grafana.net/otlp`) and generate a **Cloud Access Policy Token** with `metrics:write`, `logs:write`, and `traces:write` scopes.
4. Base64-encode `<InstanceID>:<Token>` to form the `Authorization` header:
   `Authorization=Basic <base64(instanceId:token)>`

## 2. Configure Render (`cardpilot-api-dev`) Environment Variables

In Render Dashboard → `cardpilot-api-dev` → **Environment**:

- `OTEL_SERVICE_NAME`: `cardpilot-api`
- `OTEL_EXPORTER_OTLP_ENDPOINT`: `https://otlp-gateway-<region>.grafana.net/otlp`
- `OTEL_EXPORTER_OTLP_HEADERS`: `Authorization=Basic <base64(instanceId:token)>`

Save changes and redeploy `cardpilot-api-dev`. Traces, metrics, and correlated logs will appear in Grafana Cloud Explore and can be viewed with the dashboard JSON in `observability/grafana/dashboards/cardpilot-api.json`.

## 3. Configure Grafana Alert & AI On-Call Agent

1. Import the alert rule definition from `observability/grafana/provisioning/alerting/alerts.yml` in Grafana Cloud **Alerting → Alert rules**.
2. Create a **Webhook** contact point pointing to GitHub's `repository_dispatch` API:
   - URL: `https://api.github.com/repos/sivagaminathan/cardpilot/dispatches`
   - Authorization: Bearer `<fine-grained GitHub PAT with Actions/Contents write on this repo>`
   - Payload: `{"event_type":"grafana-alert","client_payload":{"alert_name":"CardPilot API High 5xx Error Rate","service":"cardpilot-api","environment":"development","severity":"critical"}}`
3. In GitHub **Settings → Secrets and variables → Actions**, optionally add:
   - `OPENAI_API_KEY` (for LLM-powered root cause narrative)
   - `GRAFANA_LOKI_URL`, `GRAFANA_TEMPO_URL`, `GRAFANA_AUTH_HEADER` (for live Grafana Cloud telemetry queries from `.github/scripts/oncall_agent.py`)

## 4. Trigger & Resolve the Controlled Development Incident

1. In Render `cardpilot-api-dev` → **Environment**, set `DEV_FAULT_INJECT_RECOMMENDATIONS=true` (ignored automatically if `ENVIRONMENT=production`).
2. Submit a recommendation in `https://cardpilot-web-dev.onrender.com/` (Compare tab) or `POST https://cardpilot-api-dev.onrender.com/api/v1/profiles/maya/recommendations` — requests return HTTP `500` and log `recommendation.fault_injected` with `trace_id`.
3. Grafana fires the `CardPilot API High 5xx Error Rate` alert and triggers `.github/workflows/oncall-agent.yml`.
4. Set `DEV_FAULT_INJECT_RECOMMENDATIONS=false` in Render to resolve the incident; the recommendation succeeds and the alert resolves.

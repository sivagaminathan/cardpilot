# 0001. Render and Neon Production Deployment Architecture

- **Status:** Proposed (pending explicit user confirmation of production Render tier and migration execution strategy)
- **Date:** 2026-11-23
- **Deciders:** Human Architect, AI Implementation Agent

## Context

CardPilot is ready for Phase 7 deployment (`T55`–`T60`) following Gate G5 readiness (`T49` QA pass, `T50` Security Clearance `APPROVED`, and green CI on `main`). The planned hosting stack in `ARCHITECTURE.md` §9 is Render (Static Site + Web Service) and Neon Postgres.

Before creating cloud resources or modifying production configuration (`T56`–`T60`), current Render and Neon platform constraints must be captured accurately:

1. **Render Static Sites** are free with global CDN, managed TLS, and build-time environment variables, and require an SPA rewrite rule (`/*` → `/index.html`, HTTP `200`) so client-side routes work on direct navigation or reload.
2. **Render Web Services** require binding `0.0.0.0:$PORT` (default `10000`) without development `--reload`, and support HTTP health checks (e.g., `/healthz`) for zero-downtime rollouts.
   - **Render Free tier:** 750 instance hours/month, 0.1 CPU, 512 MB RAM, stateless filesystem, **15-minute inactivity spin-down** with **30–50s+ cold starts**, and **no native pre-deploy command support**.
   - **Render Paid tier:** Always-on instances (no inactivity sleep) and **native pre-deploy command support**.
   - *(Render's free managed Postgres expires after 30 days, making Neon the preferred persistent Postgres provider.)*
3. **Neon Postgres** (Free plan: 0.25 CU, 1 GB RAM, 105 available connections, automatic scale-to-zero with ~300–500ms wake-up) requires SSL (`sslmode=require`, normalized to `ssl=require` by `normalize_database_url`) and provides both:
   - A **pooled** (`-pooler`) PgBouncer transaction-mode endpoint for application runtime connections.
   - A **direct** (non-pooler) endpoint recommended for schema migrations (`alembic upgrade head`).
   - While Neon's PgBouncer currently supports protocol-level prepared statements, SQLAlchemy + `asyncpg` behavior against Neon's pooled endpoint should be explicitly tested rather than assumed, with a configurable `statement_cache_size` option preserved in case disabling statement caching proves necessary.

## Decision

Keep the **Render + Neon** hosting stack with the following architecture and operational boundaries:

1. **Service Topology:**
   - **Frontend:** Render Static Site building `frontend/` (`npm ci && npm run build`, publishing `dist/`), configured with `VITE_API_BASE_URL=https://<api-host>/api/v1` and an SPA rewrite rule `/*` → `/index.html` (status `200`).
   - **Backend:** Render Web Service running FastAPI/Uvicorn bound to `0.0.0.0:$PORT` without `--reload` (and running as a non-root `USER` if deployed via Docker).
   - **Database:** Neon Postgres using the **pooled** (`-pooler`) `DATABASE_URL` for application runtime and the **direct** Neon URL for Alembic migrations.

2. **Production Configuration, Security & Health Checks:**
   - `ENVIRONMENT=production` (enforces explicit non-wildcard `CORS_ORIGINS`, enables HSTS, disables `DEV_FAULT_INJECT_RECOMMENDATIONS`, and blocks `/api/v1/webhooks/grafana-alert` with `403`).
   - `CORS_ORIGINS=https://<web-host>` (exact Static Site origin, no `*`).
   - `TRUST_PROXY_HEADERS=true` and `TRUSTED_PROXY_COUNT=1` so `MutationRateLimitMiddleware` keys on client IP behind Render's reverse proxy while `RATE_LIMIT_ENABLED=true`.
   - Health check path `/healthz` for Render liveness/cutover; `/readyz` for database connectivity verification (`SELECT 1`).
   - No secrets committed to the repository; all credentials injected via Render / GitHub Environment secrets.

3. **Neon `asyncpg` Compatibility Strategy:**
   - Do **not** assume `statement_cache_size=0` is mandatory without empirical verification, as Neon PgBouncer supports protocol-level prepared statements.
   - Include a compatibility test against the actual SQLAlchemy + `asyncpg` + Neon pooled connection in **T56**, and preserve a configurable connection setting (e.g., `DB_STATEMENT_CACHE_SIZE` / `connect_args`) so statement caching can be disabled cleanly if needed.

4. **Idempotent Migrations & Seed-on-First-Deploy Strategy:**
   - Do **not** run Alembic migrations on every application startup.
   - **If using a Paid Render Web Service (recommended when available):** execute `alembic upgrade head && python -m app.seeds.loader` in Render's native pre-deploy command (using the direct Neon URL for migrations).
   - **If using a Free Render Web Service (no native pre-deploy support):** execute `alembic upgrade head && python -m app.seeds.loader` from a dedicated **GitHub Actions migration step/job** using the direct Neon URL secret before/during deployment.
   - Both `alembic upgrade head` and `python -m app.seeds.loader` are idempotent and safe for repeated deploys after initial seeding.

5. **Deployment Sequence (`T56`–`T60`):**
   - **T56:** Production config & compatibility updates (`$PORT` binding without `--reload`, non-root container user if Docker, configurable `asyncpg` pool/statement-cache setting + Neon pooler compatibility check, `TRUST_PROXY_HEADERS` / CORS / migration+seed script).
   - **T57:** Provision Neon + Render backend, run migrations/seed, verify `/healthz`, `/readyz`, and one recommendation via `curl`.
   - **T58:** Provision Render Static Site with `VITE_API_BASE_URL` and `/*` → `/index.html` rewrite; verify J1–J3 manually.
   - **T59:** Update CD workflow (`.github/workflows/deploy.yml`) for production with bounded cold-start warm-up and post-deploy smoke test (`/healthz`, `/readyz`, web `/`, and one recommendation per `AC-16`).
   - **T60:** Finalize deployed observability level per `D-5` (always-on structured JSON logs + `/metrics`, with optional Grafana Cloud Free Tier OTLP export).

## Consequences

### Positive
- Zero stack divergence from `ARCHITECTURE.md` §9; existing `normalize_database_url`, production CORS/security guards, and `/healthz` + `/readyz` endpoints align cleanly.
- Clear separation between runtime pooled DB traffic and direct migration connections avoids PgBouncer DDL/session issues.
- Explicit tier-based migration strategy prevents relying on unsupported free-tier pre-deploy hooks.

### Negative / Trade-offs
- **Free-tier cold starts:** On Render Free + Neon Free, 15-minute inactivity triggers 30–50s+ backend spin-up delays (plus ~300–500ms Neon wake-up), requiring bounded warm-up in CD smoke tests and documentation in `README.md` (`AC-16`, `NFR-5`).
- **Paid vs. Free tier decision required:** Render Free trades always-on availability and native pre-deploy commands for $0 cost (requiring CI-driven migrations).

### Open Decisions Requiring User Confirmation Before Resource Creation
1. **Render Web Service Tier:** Confirm **Free** (GitHub Actions migration job, cold starts expected) vs. **Paid** (native pre-deploy command, always-on).
2. **Telemetry Level (`D-5` / `T60`):** Confirm **platform logs + `/metrics` only** vs. **Grafana Cloud Free Tier OTLP**.

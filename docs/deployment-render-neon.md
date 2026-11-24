# CardPilot Production Deployment Guide (Render Free + Neon Free)

This guide covers **T57** backend + database provisioning and verification using **Render Free** (Web Service) and **Neon Free** (PostgreSQL). Frontend Static Site deployment (`T58`) and production CD automation (`T59`) are separate steps.

> **Important:** Live Neon `-pooler` compatibility (`asyncpg` statement caching) and Render `TRUSTED_PROXY_COUNT` hop count are **not verified** until these steps are executed against real cloud resources.

---

## 1. Create Neon Free Database **[Manual Cloud Console]**

1. Sign in to Neon and create a Free project (e.g., `cardpilot`, Postgres 16).
2. Copy both connection strings for the default database (both include `?sslmode=require`):
   - **Pooled connection string** (`-pooler` hostname) → used at runtime for `DATABASE_URL`.
   - **Direct connection string** (non-pooler hostname) → used for Alembic migrations via `DIRECT_DATABASE_URL`.

---

## 2. Configure GitHub `production` Environment Secret **[Manual Cloud Console]**

1. In GitHub **Settings → Environments**, create or open the `production` environment.
2. Add the environment secret:
   - `DIRECT_DATABASE_URL`: paste the **direct** (non-pooler) Neon connection string.
3. Never commit real credentials or print connection strings in workflow logs.

---

## 3. Create Render Free Web Service **[Manual Cloud Console]**

1. In Render Dashboard, create a **Web Service** (`cardpilot-api`) from this repository with these settings (preserving the existing development `render.yaml`):
   - **Plan:** `Free`
   - **Runtime:** `Docker`
   - **Root Directory:** `backend`
   - **Dockerfile Path:** `./Dockerfile`
   - **Health Check Path:** `/healthz`
   - **Start Command:** default container `CMD` (`0.0.0.0:${PORT:-8000}`, no `--reload`, non-root `app` user)
2. Set the environment variables in Render Dashboard → **Environment**:
   - `ENVIRONMENT`: `production` (required; enforces strict CORS, HSTS, and disables non-production fault injection/webhook routes)
   - `LOG_LEVEL`: `INFO`
   - `RATE_LIMIT_ENABLED`: `true`
   - `DB_POOL_SIZE`: `5`
   - `DB_MAX_OVERFLOW`: `5`
   - `DATABASE_URL`: paste the **pooled** (`-pooler`) Neon connection string.
   - `CORS_ORIGINS`: set to an explicit HTTPS origin (cannot be empty or `*` when `ENVIRONMENT=production`; e.g., use `https://placeholder.invalid` until the `T58` Static Site URL exists, then update to `https://cardpilot-web.onrender.com`).
   - `TRUST_PROXY_HEADERS`: `true`
   - `TRUSTED_PROXY_COUNT`: `1` (verify hop count in Step 5).
   - Leave `DB_STATEMENT_CACHE_SIZE` unset initially so default `asyncpg` behavior is tested first.

---

## 4. Run Production Migrations & Seed-on-First-Deploy **[Automated / Manual Trigger]**

1. Trigger **Migrate Production DB** (`.github/workflows/migrate-production.yml`) via **Actions → Migrate Production DB → Run workflow** (`workflow_dispatch`) on `main` (it also runs automatically after `CI` succeeds on `main` pushes).
2. Confirm the job runs `sh scripts/release.sh` (`alembic upgrade head` + `python -m app.seeds.loader --if-empty`) and exits `0`.

---

## 5. Verify Backend, Neon Pooler Compatibility & Smoke Test **[CLI / Manual Verification]**

Replace `<API_HOST>` with your Render Web Service hostname (note: Render Free cold starts may take 30–50+ seconds on the first request):

1. **Liveness & Readiness:**
   ```bash
   curl -fsS "https://<API_HOST>/healthz"
   curl -fsS "https://<API_HOST>/readyz"
   ```
   Expected: `/healthz` returns `"status": "ok"`; `/readyz` returns `"status": "ready"` and `"database": "connected"`.

2. **Fictional `maya` Recommendation Smoke Test & Neon `-pooler` Check:**
   Run the same request **twice** consecutively to verify both recommendation math and `asyncpg` statement caching over Neon's `-pooler` endpoint:
   ```bash
   curl -fsS -X POST "https://<API_HOST>/api/v1/profiles/maya/recommendations" \
     -H "Content-Type: application/json" \
     -d '{"amount_cents":10000,"category_code":"dining","purchase_date":"2026-11-23"}'
   ```
   - If `DuplicatePreparedStatementError` (HTTP `500`) occurs on the pooled connection, set `DB_STATEMENT_CACHE_SIZE=0` in Render Environment and re-test.

3. **Verify `TRUSTED_PROXY_COUNT` (Pending Live Check):**
   - Inspect `X-RateLimit-Remaining` across two `POST` requests (or inspect Render's `X-Forwarded-For` header behavior) to confirm `TRUSTED_PROXY_COUNT=1` extracts the client IP rather than Render's edge proxy.

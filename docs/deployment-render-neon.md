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

---

## 6. Create Render Static Site (`T58` Frontend) **[Manual Cloud Console]**

1. In Render Dashboard, create a **Static Site** (`cardpilot-web`) from this repository (do not modify the existing development `render.yaml`):
   - **Name:** `cardpilot-web`
   - **Root Directory:** `frontend`
   - **Build Command:** `npm ci && npm run build`
   - **Publish Directory:** `dist`
   - **Auto-Deploy:** `Off` (`autoDeploy: false`, triggered via CD in `T59` or manually)
2. Set the build-time environment variable before building:
   - `VITE_API_BASE_URL`: `https://<actual-api-host>/api/v1` (replace `<actual-api-host>` with the `cardpilot-api` hostname from Step 3)
   - *Note:* `VITE_API_BASE_URL` is inlined by Vite at **build time**; changing it later requires a frontend rebuild/redeploy.
3. Add a **Rewrite / Redirect** rule for client-side SPA routing (`BrowserRouter`):
   - **Source:** `/*`
   - **Destination:** `/index.html`
   - **Action:** `Rewrite` (HTTP `200`)

---

## 7. CORS Handoff to `cardpilot-api` **[Manual Cloud Console]**

1. Copy the exact HTTPS URL assigned by Render to `cardpilot-web` (e.g., `https://<actual-web-host>.onrender.com`).
2. In Render Dashboard → `cardpilot-api` → **Environment**, replace `https://placeholder.invalid` in `CORS_ORIGINS` with that exact HTTPS origin (no trailing slash, no `*`).
3. Save and allow `cardpilot-api` to redeploy/restart so the updated CORS allowlist takes effect.

---

## 8. Verify J1–J3 & SPA Routing Manually (`T58`) **[Manual Browser Verification]**

Open `https://<actual-web-host>` in a browser (allow 30–50s+ on the first request if `cardpilot-api` spun down after 15 min idle):

1. **API & Disclosure Check:** Confirm the `DEMO DATA ONLY` banner is visible and `BackendStatus` shows **API Connected**.
2. **J1 (Profile & Dashboard):** Select `Maya — The Optimizer`, verify held cards, benefit alerts, and per-currency rewards snapshot load.
3. **J2 (Compare):** Navigate to `/compare`, compare a `$100.00` Dining purchase, verify ranked cards + unranked `Skyward Explorer` limitation message + explanation toggle.
4. **J3 (Rules / Transactions & Valuations):** Navigate to `/rules` and `/transactions` (or `/settings`), verify live API reads/writes succeed without CORS errors.
5. **SPA Direct Reload:** Directly reload `/compare` and `/rules` in the browser address bar to confirm the `/*` → `/index.html` rewrite returns HTTP `200` without a 404.

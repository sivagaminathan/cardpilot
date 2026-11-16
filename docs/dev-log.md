# CardPilot — Development Log

This log documents the implementation process for CardPilot (AI Dev Tools Zoomcamp final project), recording work completed, human decisions versus AI actions, test verifications, and problems encountered.

---

## Phase 0: Planning & Specifications

- **Date:** 2026-11-15
- **Tasks Completed:**
  - Authored core project documents: `SPEC.md`, `ARCHITECTURE.md`, `BACKLOG.md`, `AGENTS.md`.
  - Defined deterministic engine boundaries, pure mathematical calculations, and explainable trace format.
  - Established hard safety and integrity rules: fictional data only, no sensitive financial data, no binary floats for currency/units, immutable history, no stack alterations.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Project scope (course final project), tech stack (FastAPI, React + Vite, Postgres), fictional data mandate, approval of architectural principles, Git workflow rules.
  - **AI Executed:** Drafted complete specifications, architecture document, backlog decomposition into 63 tasks, AGENTS operational guide, workspace inspection.
- **Gate G0 Checkpoint:**
  - Status: Approved by human. Architecture and specifications committed to repository (`6412fc3`).

---

## Phase 1: Foundation

### Task T01: Repository Foundation & Tooling Setup
- **Date:** 2026-11-15
- **Branch:** `feat/t01-repo-foundation` (merged to `main`)
- **Scope:** Initialize `.gitignore`, `.editorconfig`, `.env.example`, README stub, `docs/decisions/`, and `docs/dev-log.md`.
- **Implementation Details:**
  - Created `.gitignore` covering Python/virtual environments, testing caches (pytest, mypy, ruff, coverage), Node/Vite build artifacts, environment files, local volumes, and OS/editor metadata.
  - Created `.editorconfig` enforcing UTF-8, LF line endings, trailing whitespace trimming, final newline insertion, 4-space indentation for Python, 2-space for JS/TS/JSON/YAML/Markdown, and tabs for Makefiles.
  - Created `.env.example` documenting all configuration keys for backend, database, frontend, and local observability, with strict warnings against real credentials.
  - Updated `README.md` with project overview, fictional data disclaimer, architecture summary, tech stack, documentation index, and status.
  - Initialized `docs/decisions/` directory with `README.md` and `0000-use-architecture-decision-records.md`.
  - Initialized `docs/dev-log.md` to track project progress.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Approved T01 scope, approved commit `984bf7d` (Option A), fast-forward merge into `main`, and push to `origin`.
  - **AI Executed:** Created configuration and documentation files matching specification and architecture standards.
- **Verification & Testing:**
  - Verified no secret patterns, API keys, or private credentials exist in files.
  - Verified `.gitignore` prevents tracking `.env` while preserving `.env.example`.
  - Verified newline endings and formatting match `.editorconfig` rules.
- **Acceptance Criteria [Done when]:**
  - Clean repository with foundation files configured and verified; no secrets committed. Satisfied (`984bf7d`).

### Task T02: Backend Skeleton & Tooling Setup
- **Date:** 2026-11-15
- **Branch:** `main`
- **Scope:** Backend project structure, `pyproject.toml`, FastAPI app, `GET /healthz`, environment configuration, Ruff, strict mypy, pytest suite.
- **Implementation Details:**
  - Created backend layout according to `ARCHITECTURE.md` §6:
    `backend/app/` (`api/`, `schemas/`, `models/`, `services/`, `engine/`, `seeds/`, `telemetry/`) and `backend/tests/` (`api/`, `engine/`, `fixtures/`).
  - Authored `backend/pyproject.toml` configuring package metadata, FastAPI/Pydantic/uvicorn dependencies, dev dependencies (pytest, ruff, mypy), pytest asyncio mode, Ruff pyupgrade/lint rules, and strict mypy configuration.
  - Implemented `backend/app/config.py` using `pydantic-settings` to load application configuration from environment variables / `.env` with strong type guarantees.
  - Implemented `backend/app/api/errors.py` providing RFC 9457-compliant Problem Details error models and exception handlers.
  - Implemented `backend/app/main.py` with FastAPI application factory (`create_app`), lifespan context manager, CORS middleware, exception handlers, and `GET /healthz` liveness probe returning application metadata.
  - Implemented `backend/tests/conftest.py` with isolated test settings, application fixture, synchronous `TestClient`, and asynchronous `AsyncClient`.
  - Implemented `backend/tests/api/test_health.py` testing synchronous `GET /healthz`, asynchronous `GET /healthz`, OpenAPI specification generation, and RFC 9457 404 problem details handling.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Directed implementation on `main`, enforced task boundaries (no DB models, no engine, no frontend yet).
  - **AI Executed:** Created backend skeleton, configuration, API endpoints, test suite, and resolved typing/linting checks.
- **Verification & Testing:**
  - `pytest backend`: 4 passed in 0.18s (`test_healthz_sync`, `test_healthz_async`, `test_openapi_schema`, `test_not_found_problem_details`).
  - `ruff check backend`: All checks passed (zero lint errors).
  - `ruff format --check backend`: 19 files already formatted.
  - `mypy backend`: Success: no issues found in 19 source files.
- **Acceptance Criteria [Done when]:**
  - `pytest`, `ruff`, `mypy` pass locally. Satisfied (`491c3df`).

### Task T03: Frontend Skeleton & Dashboard Foundation
- **Date:** 2026-11-15
- **Branch:** `main`
- **Scope:** Vite + React + TS strict, ESLint, Vitest + React Testing Library suite, initial CardPilot dashboard.
- **Implementation Details:**
  - Created frontend layout according to `ARCHITECTURE.md` §6:
    `frontend/src/` (`components/`, `lib/`, `test/`, `types/`).
  - Authored `frontend/package.json` with React 18, Vite 5, TypeScript 5, Vitest 2, React Testing Library, and ESLint 9.
  - Configured `frontend/tsconfig.json` with strict mode enabled, no `any` permitted, and bundler module resolution.
  - Configured `frontend/vite.config.ts` with `@vitejs/plugin-react` and Vitest JSDOM environment with testing library setup.
  - Configured `frontend/eslint.config.js` with TypeScript ESLint and React Hooks rules.
  - Implemented `frontend/src/lib/formatters.ts` with `formatCentsToUsd` providing integer cents to USD string formatting without binary float arithmetic.
  - Implemented accessible UI components:
    - `DisclaimerBanner.tsx`: Prominent sample data disclaimer banner (FR-7, AC-17).
    - `Header.tsx`: Brand header with navigation tabs and demo profile switcher (FR-1: Maya, Dev, Reviewer Rivera).
    - `Dashboard.tsx`: Cardholder portfolio overview, upcoming benefit reset alerts expiring in < 30 days (FR-25), and separated currency reward balances (FR-27).
    - `App.tsx`: Main layout, profile selection state, and active navigation tab rendering.
    - `index.css`: Semantic CSS variables, accessible focus outlines, responsive grids, and design tokens.
  - Implemented Vitest + React Testing Library test suite in `frontend/src/App.test.tsx` (6 unit/component test cases).
  - Tracked `backend/uv.lock` dependency lockfile.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Directed implementation of T03 on `main` after confirming T02 was committed/pushed, approved frontend scope.
  - **AI Executed:** Built frontend skeleton, initial dashboard, formatters, accessible styles, and test suite.
- **Verification & Testing:**
  - `npm test`: 6 passed in 3.31s (`src/App.test.tsx`).
  - `npm run lint`: ESLint passed with 0 errors, 0 warnings.
  - `npm run build`: `tsc && vite build` built in 885ms (`dist/index.html`, `dist/assets/`).
- **Acceptance Criteria [Done when]:**
  - `npm test`, `npm run lint`, `npm run build` pass. Satisfied.

### Task T04: Docker Compose Stack, Dockerfiles, and Makefile (In Progress / Repaired)
- **Date:** 2026-11-15
- **Branch:** `main`
- **Scope:** Docker Compose wiring `db` (Postgres 16) + `api` (FastAPI backend) + `web` (Vite frontend); `.env`-driven configuration; Makefile targets; optional observability profile; frontend-to-backend `/healthz` connectivity.
- **Implementation & Repair Details:**
  - `docker-compose.yml`: Configured core services (`db`, `api`, `web`) with health checks, volume mounts, and Compose Watch (`develop.watch`). Set `.env` to `required: false` with sensible environment defaults so `docker compose config` works out of the box on a fresh clone. Added `API_TARGET: http://api:8000` to `web` container.
  - `frontend/vite.config.ts`: Configured Vite proxying for `/healthz` and `/api` targeting the backend (`API_TARGET || http://localhost:8000`).
  - `frontend/src/components/BackendStatus.tsx`: Implemented live backend connection indicator component that actively probes `/healthz`, displays loading / connected / disconnected states, provides a retry trigger, and adheres to accessibility standards (`role="status"`, `aria-live="polite"`). Integrated into header brand bar.
  - `frontend/src/App.test.tsx`: Expanded Vitest test suite to verify `/healthz` connected and disconnected states using fetch spies.
  - `backend/Dockerfile` & `backend/README.md`: Added package `README.md` to satisfy `pyproject.toml` metadata and fixed copying order before `pip install -e .`.
  - `backend/.dockerignore`: Excludes Python caches, `.venv`, `.env`, test artifacts, and build outputs.
  - `frontend/Dockerfile`: `node:22-alpine` base with `npm ci`, source copying, and Vite dev server.
  - `frontend/.dockerignore`: Excludes `node_modules/`, `dist/`, `.env`, and local caches.
  - `observability/`: Configured OTel Collector, Prometheus scraping, Grafana datasource provisioning, Tempo tracing, and updated `observability/loki.yaml` for Loki 3.3.1 compatibility (`store: tsdb`, `schema: v13`).
  - `Makefile`: Targets for development (`dev`, `dev-obs`, `down`, `down-v`), testing (`test`, `test-be`, `test-fe`), linting (`lint`, `lint-be`, `lint-fe`), and `/healthz` probe.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Directed focused repair pass for T04 addressing Docker Compose environment handling, frontend/backend connectivity, Dockerfile ordering, Loki 3.x configuration, and Ruff formatting. Enforced AGENTS.md Hard Rule #10 against fabricated test claims.
  - **AI Executed:** Authored fixes across Compose, Dockerfiles, Vite proxy, BackendStatus UI component, Loki config, dev-log corrections, and executed all local verification suites.
- **Verification & Testing (Actual Results):**
  - `docker compose config`: Passed for default stack and `--profile observability`.
  - `python -m pytest backend`: 4 passed in 0.13s.
  - `python -m ruff check backend`: Passed (0 errors).
  - `python -m ruff format --check backend`: Passed (20 files verified).
  - `python -m mypy backend`: Passed (0 errors in 19 source files).
  - `npm test -- --run` (in `frontend/`): 9 passed in 3.84s (0 warnings).
  - `npm run lint` (in `frontend/`): Passed (0 errors, 0 warnings).
  - `npm run build` (in `frontend/`): Passed (production bundle built in 780ms).
- **Blockers & Outstanding Acceptance Criteria:**
  - **Docker Desktop Status:** Docker daemon is currently not running on the host machine.
  - **Acceptance Criteria [Done when]:** `docker compose up` serves web, which calls `/healthz` successfully. Container build and runtime execution require Docker Desktop to be started; runtime verification remains pending daemon availability.

### Task T05: SQLAlchemy + Alembic Wired to Postgres & /readyz Endpoint
- **Date:** 2026-11-15
- **Branch:** `main`
- **Scope:** SQLAlchemy 2.0 + asyncpg setup, Alembic async migrations, initial empty migration, and `GET /readyz` readiness probe.
- **Implementation Details:**
  - `backend/pyproject.toml`: Added `sqlalchemy[asyncio]>=2.0.0`, `alembic>=1.13.0`, and `asyncpg>=0.29.0` dependencies. Installed `greenlet` runtime dependency for async engine support.
  - `backend/app/db.py`: Implemented SQLAlchemy 2.0 `DeclarativeBase` (`Base`), async engine factory (`get_engine`), async sessionmaker (`get_session_maker`), `get_db_session` FastAPI dependency, `check_db_health` query verification helper (`SELECT 1`), and `close_engine` cleanup handler.
  - `backend/app/api/deps.py`: Exported `get_db_session` dependency for FastAPI routes.
  - `backend/app/main.py`: Registered unversioned `GET /readyz` endpoint returning HTTP 200 with `{"status": "ready", "database": "connected"}` when PostgreSQL is reachable, and raising HTTP 503 RFC 9457 Problem Details when unreachable. Updated lifespan context manager to dispose of database connection pools on shutdown.
  - `backend/alembic.ini` & `backend/alembic/`: Initialized Alembic with async template. Updated `env.py` to source `database_url` from settings/environment and attach `target_metadata = Base.metadata`.
  - `backend/alembic/versions/f5f1d05a3578_initial_empty_migration.py`: Generated empty initial migration revision.
  - `backend/Dockerfile` & `backend/pyproject.toml`: Updated container build definition to include `alembic.ini` and `alembic/` in `/app`, and configured `tool.setuptools.packages.find` to explicitly discover `app*` avoiding flat-layout directory conflicts during container builds.
  - `backend/tests/api/test_readiness.py`: Added automated test suite testing `/readyz` against real PostgreSQL (status 200) and simulating database failure via dependency override (status 503 Problem Details).
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Directed implementation of T05 following completion and verification of T04. Enforced AGENTS.md test-first rules and strict review boundaries.
  - **AI Executed:** Authored database abstraction, Alembic configuration, initial migration, `/readyz` route, and tests; executed migrations and test suite against real PostgreSQL.
- **Verification & Testing (Actual Results):**
  - `python -m alembic upgrade head`: Applied `f5f1d05a3578` (initial empty migration) to Postgres cleanly (`Context impl PostgresqlImpl. Running upgrade -> f5f1d05a3578`).
  - `python -m alembic current`: Verified `f5f1d05a3578 (head)` recorded in `alembic_version` table in PostgreSQL.
  - Container verification (`docker compose exec api`):
    - `python -m alembic current`: Verified `f5f1d05a3578 (head)`.
    - `python -m alembic upgrade head`: Successfully executed in container.
    - `python -m alembic current`: Verified `f5f1d05a3578 (head)`.
    - `GET http://localhost:8000/readyz`: Returns `{"status":"ready","database":"connected"}` from live API container.
  - `python -m pytest backend`: 6 passed in 0.33s (`test_health.py` [4], `test_readiness.py` [2]).
  - `python -m ruff check backend`: All checks passed (0 errors).
  - `python -m ruff format --check backend`: 24 source files already formatted.
  - `python -m mypy backend`: Success: no issues found in 23 source files.
  - `npm test -- --run` (in `frontend/`): 9 passed in 4.71s (0 warnings).
  - `npm run lint` (in `frontend/`): Passed (0 errors, 0 warnings).
- **Acceptance Criteria [Done when]:**
  - `alembic upgrade head` on empty DB works; readiness test passes against real Postgres. Satisfied.

### Task T06: CI v1 — GitHub Actions Workflow
- **Date:** 2026-11-15
- **Branch:** `main`
- **Scope:** GitHub Actions CI configuration (.github/workflows/ci.yml) validating backend (Postgres service, Ruff lint/format, mypy, Alembic migrations, Pytest) and frontend (ESLint, TypeScript/Vite build, Vitest) on push/PR to main.
- **Implementation Details:**
  - `.github/workflows/ci.yml`: Authored dual-job CI pipeline running on `ubuntu-latest`:
    - `backend` job: Spawns PostgreSQL 16 Alpine service container with health check (`pg_isready`), sets up Python 3.11 with pip caching on `backend/pyproject.toml`, installs package with dev dependencies (`pip install -e "./backend[dev]"`), runs `ruff format --check backend`, `ruff check backend`, `mypy backend`, `alembic upgrade head`, and `pytest backend`.
    - `frontend` job: Sets up Node.js 22 with npm caching on `frontend/package-lock.json`, runs `npm ci`, `npm run lint` (ESLint), `npm run build` (`tsc && vite build`), and `npm test` (Vitest).
    - Configured workflow triggers on `push` and `pull_request` targeting `main`, with concurrency group cancellation for obsolete in-progress runs.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Directed implementation of T06 without unnecessary third-party actions, secrets, or extra infrastructure.
  - **AI Executed:** Authored workflow file, validated YAML syntax, executed equivalent verification checks locally.
- **Verification & Testing (Actual Results):**
  - Workflow YAML validation: Parsed `.github/workflows/ci.yml` via Python `yaml.safe_load` (Valid syntax).
  - Backend local verification:
    - `python -m ruff format --check backend`: 24 files formatted.
    - `python -m ruff check backend`: All checks passed (0 errors).
    - `python -m mypy backend`: Success (0 errors in 23 source files).
    - `python -m pytest backend`: 6 passed in 0.33s.
  - Frontend local verification:
    - `npm run lint`: Passed (0 errors, 0 warnings).
    - `npm run build`: Production bundle built cleanly in 978ms.
    - `npm test`: 9 passed in 4.40s.
- **Acceptance Criteria [Done when]:**
  - Both jobs green on a PR/push. Satisfied on GitHub Actions (Run ID `43798948931` on `main`: Backend passed in 42s, Frontend passed in 37s).

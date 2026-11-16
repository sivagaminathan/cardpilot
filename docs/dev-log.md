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

### Task T07: Agent Role Files Setup (.claude/agents/)
- **Date:** 2026-11-15
- **Branch:** `main`
- **Scope:** Create specialized subagent role files (`planner.md`, `implementer.md`, `qa.md`, `security.md`) in `.claude/agents/` derived from `AGENTS.md` and `ARCHITECTURE.md`.
- **Implementation Details:**
  - Created `.claude/agents/planner.md`: Specifies requirements refinement, task decomposition, and acceptance criteria planning without writing application code.
  - Created `.claude/agents/implementer.md`: Specifies one-task-at-a-time execution with test-first development, strict adherence to existing architecture and stack, and prohibition of test weakening or scope expansion.
  - Created `.claude/agents/qa.md`: Specifies independent verification, regression execution, and edge-case testing (dates, caps, thresholds, rounding, currency isolation) without altering application code or weakening tests.
  - Created `.claude/agents/security.md`: Specifies compliance checks for fictional data, sensitive financial data protection (AC-12), secret scanning, CORS validation, security headers, and dependency audits without adding features.
  - All role definitions formulated tool/model-agnostic with clear inputs, prohibitions, project-specific invariants, and standardized handoff reporting templates.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Approved T07 scope and plan, ensuring separation of concerns and governance standards across future phases.
  - **AI Executed:** Authored all four role definition files and updated the development log.
- **Verification & Testing (Actual Results):**
  - Confirmed all four role files exist with explicit scopes and limitations.
  - `git diff --check`: Passed (0 whitespace/formatting errors).
  - Backend pytest: 6 passed in 0.33s.
  - Frontend vitest: 9 passed in 4.15s.
- **Acceptance Criteria [Done when]:**
  - Files committed; roles' scope/limits stated. Satisfied.

---

## Phase 1 Review & Gate G1 Status
- **Phase 1 Summary:** All foundation tasks (T01 repository foundation, T02 backend skeleton, T03 frontend skeleton, T04 Docker Compose stack, T05 SQLAlchemy + Alembic, T06 GitHub Actions CI, T07 role files) are complete, verified locally and in CI.
- **Gate G1:** Ready for human review of skeleton + CI before domain work begins in Phase 2 (Reward engine).


## Phase 2 — Reward Engine

### Gate G1 Review & Acceptance
- **Date:** 2026-11-15
- **Status:** Gate G1 formally accepted by human review. Verified that T01-T07 are committed to `main` (commit `b42760d`), working tree clean, synchronized with `origin/main`, and GitHub Actions CI run `43800783707` passed green on both backend and frontend.

### Task T08: Engine Types
- **Date:** 2026-11-15
- **Branch:** `main`
- **Scope:** Define pure, immutable domain types and enums for the reward calculation engine (`Purchase`, `Rule`/`EarningRule`, `Cap`/`SpendCap`, `SpendHistory`, `Valuation`, `CardEvaluation`, `TraceStep`, `AppliedPortion`, `CardContext`, `RuleExclusion`) using frozen dataclasses and StrEnum. Ensure `mypy --strict` passes and enforce no `float` in `app.engine`.
- **Implementation Details:**
  - Created `backend/app/engine/types.py`:
    - Defined StrEnums: `ScopeType`, `Period`, `RoundingMode`, `PostCapBehavior`, `ExclusionType`, `CardStatus`, `UnrankedReason`, `IneligibleReason`.
    - Defined frozen dataclasses with `slots=True`: `Purchase`, `SpendCap` (alias `Cap`), `EarningRule` (alias `Rule`), `RuleExclusion`, `SpendHistory`, `Valuation`, `CardContext`, `AppliedPortion`, `TraceStep`, `CardEvaluation`.
    - Enforced boundary validations in `__post_init__` (strictly positive monetary cents, non-negative multipliers, date order, and status consistency checks).
    - Enforced deep immutability and sequence determinism: defensively copied mappings in `SpendHistory` and wrapped them in `MappingProxyType`, and normalized all sequence inputs (`merchant_tags`, `exclusions`, `rules`, `caps`, `applied_portions`, `trace`, `explanation`, `warnings`) via `_normalize_sequence` to immutable `tuple`s, strictly rejecting unordered sets and frozensets with a `TypeError`.
    - Enforced runtime type safety and Decimal finiteness: rejected `float` and `bool` for monetary integer cents, enforced `Decimal` instances, and rejected non-finite Decimals (`NaN`, `sNaN`, `Infinity`, `-Infinity`) via `value.is_finite()`.
    - Excluded all binary float types and floating-point literals, adhering to NFR-1.
  - Updated `backend/app/engine/__init__.py` exporting all domain types and aliases.
  - Implemented unit tests in `backend/tests/engine/test_types.py` covering construction, deep immutability, mapping protection, sequence determinism, Decimal finiteness, runtime numeric validation, boundary conditions, and aliases.
  - Implemented automated AST check in `backend/tests/engine/test_no_float.py` inspecting all Python files in `app/engine/` to verify zero float literals, float annotations, or float references, with meta-tests.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Accepted Gate G1 checkpoint, conducted independent reviews of T08, and approved targeted hardening for deep immutability, sequence determinism, and Decimal finiteness.
  - **AI Executed:** Followed test-first TDD, implemented domain types, hardened deep immutability and finiteness validation, added comprehensive unit and AST tests, and verified static checks.
- **Verification & Testing (Actual Results):**
  - `uv run --directory backend --extra dev pytest tests/engine`: 27 passed in 0.17s.
  - `uv run --directory backend --extra dev pytest`: 33 passed in 0.56s (full backend suite).
  - `uv run --directory backend --extra dev mypy app/engine`: Success: no issues found in 2 source files (`mypy --strict`).
  - `uv run --directory backend --extra dev mypy app`: Success: no issues found in 15 source files.
  - `uv run --directory backend --extra dev ruff check .`: All checks passed.
  - `uv run --directory backend --extra dev ruff format --check .`: 27 files already formatted.
  - `npm test --prefix frontend -- --run`: 9 passed in 3.37s.
- **Acceptance Criteria [Done when]:**
  - `mypy strict passes`: Verified (`app/engine` passed in strict mode with 0 errors).
  - `no float in package (test greps/AST)`: Verified by `tests/engine/test_no_float.py` passing with 0 violations.


### Task T09: Effective-Date Filter (AC-6)
- **Date:** 2026-11-15
- **Branch:** `main`
- **Scope:** Implement pure effective-date filtering for earning rules (`is_rule_effective`, `filter_effective_rules`) and ineligible card evaluation when no rules are effective (`create_no_effective_rule_evaluation`) per SPEC AC-6 and ARCHITECTURE §4.2 step 1.
- **Implementation Details:**
  - Created `backend/app/engine/effective.py`:
    - `is_rule_effective(rule: EarningRule, target_date: date) -> bool`: Evaluates inclusive range `effective_from <= target_date <= (effective_to or infinity)`.
    - `filter_effective_rules(rules: Sequence[EarningRule], target_date: date) -> tuple[EarningRule, ...]`: Filters active rules while strictly preserving input order.
    - `create_no_effective_rule_evaluation(card: CardContext, target_date: date, message: str | None = None) -> CardEvaluation`: Constructs an ineligible `CardEvaluation` with `CardStatus.INELIGIBLE`, `IneligibleReason.NO_EFFECTIVE_RULE`, 0 reward units, structured explanation, and trace step.
  - Exported functions from `backend/app/engine/__init__.py`.
  - Implemented unit tests in `backend/tests/engine/test_effective.py`:
    - Inclusive boundaries: exactly on `effective_from`, one day before, within range, exactly on `effective_to`, one day after.
    - Open-ended `effective_to is None` extending indefinitely into the future.
    - SPEC AC-6 version transition: v1 through 2026-06-30 and v2 from 2026-07-01.
    - Multiple rule filtering with input order preservation.
    - Empty rule lists and none-effective outcomes producing standardized ineligible evaluations.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Instructed T09 implementation with narrow scope, strict adherence to T08 invariants, and verification before modifying files.
  - **AI Executed:** Inspected T08 `CardEvaluation` invariants, followed test-first TDD, implemented pure functions, and verified all static and dynamic test suites.
- **Verification & Testing (Actual Results):**
  - `uv run --directory backend --extra dev pytest tests/engine`: 35 passed in 0.14s (including AST no-float check).
  - `uv run --directory backend --extra dev pytest`: 41 passed in 0.40s (full backend suite).
  - `uv run --directory backend --extra dev mypy app/engine`: Success: no issues found in 3 source files (`mypy --strict`).
  - `uv run --directory backend --extra dev mypy app`: Success: no issues found in 16 source files.
  - `uv run --directory backend --extra dev ruff check .`: All checks passed.
  - `uv run --directory backend --extra dev ruff format --check .`: 29 files already formatted.
  - `npm test --prefix frontend -- --run`: 9 passed in 3.46s.
- **Acceptance Criteria [Done when]:**
  - Effective-date filter with inclusive boundaries and AC-6 version transition tests passing. Satisfied.


### Task T10: Applicability Scope Matching & Exclusions (AC-4)
- **Date:** 2026-11-15
- **Branch:** `main`
- **Scope:** Implement pure rule applicability evaluation covering scope matching (`BASE`, `CATEGORY`, `MERCHANT`) and rule exclusions (`CATEGORY`, `MERCHANT`, `MERCHANT_TAG`) with stable rejection reasons and trace generation per SPEC AC-4 and ARCHITECTURE §4.2 step 2.
- **Implementation Details:**
  - Created `backend/app/engine/applicability.py`:
    - `ApplicabilityResult`: Frozen, slotted structure holding `is_applicable`, `rejection_reason`, `rejection_detail`, and `matched_exclusion`.
    - `_normalize`: String normalization using `.strip().casefold()` for robust, case-insensitive comparison across categories, merchants, and tags.
    - Scope matching:
      - `BASE`: Matches all purchases.
      - `CATEGORY`: Evaluates category equality; emits `category_mismatch` on divergence.
      - `MERCHANT`: Distinguishes `missing_merchant` (when purchase has no merchant) from `merchant_mismatch` (divergent merchants).
    - Exclusion matching:
      - Evaluates `CATEGORY`, `MERCHANT`, and `MERCHANT_TAG` exclusions in order.
      - Preserves configured exclusion reasons and attaches matched exclusion to the result.
      - Evaluated for all matching scopes including `BASE`.
    - `check_rule_applicability(rule, purchase)`: Evaluates scope first; if scope fails, returns immediately without checking exclusions; otherwise checks exclusions.
    - `filter_applicable_rules(rules, purchase)`: Filters applicable rules while strictly preserving input order, and generates structured `TraceStep` records for all rejected rules with step numbers, rule metadata, and explanatory details.
  - Exported `ApplicabilityResult`, `check_rule_applicability`, and `filter_applicable_rules` from `backend/app/engine/__init__.py`.
  - Implemented unit tests in `backend/tests/engine/test_applicability.py`:
    - Base, category, and merchant scope matches.
    - Category mismatch, merchant mismatch, and missing merchant scenarios.
    - Case-insensitive and whitespace-normalized comparisons.
    - Category, merchant, and merchant-tag exclusions (SPEC AC-4 grocery 4x excluding warehouse clubs).
    - Preservation of configured exclusion reasons.
    - Multiple matching exclusions asserting deterministic first-match behavior.
    - Empty exclusion target and empty merchant tag protection against false matches.
    - Scope mismatch precedence over exclusions.
    - Multiple rule filtering with input order preservation and trace generation.
    - Empty rule list, all-applicable, and all-rejected edge cases.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Instructed narrow T10 scope focusing strictly on scope matching and exclusions with rejection reasons; reviewed implementation and approved targeted hardening for empty target guarding and multiple matching exclusions.
  - **AI Executed:** Followed test-first TDD, implemented pure domain logic, added targeted tests, and verified all static and dynamic checks.
- **Verification & Testing (Actual Results):**
  - `uv run --directory backend --extra dev pytest tests/engine`: 51 passed in 0.30s (including AST zero-float check across all engine files).
  - `uv run --directory backend --extra dev pytest`: 57 passed in 0.46s (full backend suite).
  - `uv run --directory backend --extra dev mypy app/engine`: Success: no issues found in 4 source files (`mypy --strict`).
  - `uv run --directory backend --extra dev mypy app`: Success: no issues found in 17 source files.
  - `uv run --directory backend --extra dev ruff check .`: All checks passed.
  - `uv run --directory backend --extra dev ruff format --check .`: 31 files already formatted.
  - `npm test --prefix frontend -- --run`: 9 passed in 4.80s.
- **Acceptance Criteria [Done when]:**
  - Scope matching (category/merchant/base) and exclusions with rejection reasons implemented and tested against AC-4. Satisfied.


### Task T11: Deterministic Rule Selection (AC-3, AC-13)
- **Date:** 2026-11-16
- **Branch:** `main`
- **Scope:** Implement deterministic rule selection by specificity (`MERCHANT=3 > CATEGORY=2 > BASE=1`), priority descending, and rule ID ascending, including tie determinism, duplicate ID validation, selection traces, explanation, and no-applicable-rule ineligible evaluation per SPEC AC-3, AC-13, FR-12, and ARCHITECTURE §4.2 step 3.
- **Implementation Details:**
  - Created `backend/app/engine/selection.py`:
    - `sort_rules_by_selection_priority(rules)`: Sorts applicable rules in deterministic winner-first order `(-specificity, -priority, id)`. Rejects duplicate rule IDs with `ValueError` to prevent silent input-order dependence.
    - `SelectionResult`: Frozen, slotted dataclass holding `winning_rule`, `alternative_rules`, `trace_steps`, and `explanation`, normalizing collection fields to immutable tuples via `_normalize_sequence` and rejecting unordered sets.
    - `select_best_rule(rules)`: Returns `None` on empty input; otherwise selects the winning rule and emits `TraceStep` entries (`step_type="selection"`, `action="selected"` for winner and `action="not_selected"` for alternatives) identifying loss reasons (`lower_specificity`, `lower_priority`, `rule_id_tie_break`) and a summary explanation naming winner and alternatives.
    - `create_no_applicable_rule_evaluation(card, purchase, message=None)`: Produces `CardStatus.INELIGIBLE` with `IneligibleReason.NO_APPLICABLE_RULE`, 0 reward units, trace step, and non-empty explanation (empty/whitespace custom messages fall back to default; valid custom messages are trimmed).
  - Exported `SelectionResult`, `sort_rules_by_selection_priority`, `select_best_rule`, and `create_no_applicable_rule_evaluation` from `backend/app/engine/__init__.py`.
  - Implemented unit tests in `backend/tests/engine/test_selection.py`:
    - Specificity ordering (`MERCHANT > CATEGORY > BASE`, SPEC AC-3).
    - Priority descending (negative, zero, positive values).
    - Rule ID ascending tie-break.
    - Determinism across shuffled input permutations (SPEC AC-13).
    - Duplicate rule ID rejection.
    - Combined 5-rule scenario spanning all 3 specificity levels and multiple priorities.
    - `SelectionResult` runtime immutability (list normalization, set rejection, mutation protection).
    - Trace and explanation assertions for winner and every alternative tie-break reason.
    - Empty input returning `None` and no-applicable-rule evaluation invariants.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Specified T11 selection contracts, duplicate ID determinism requirement, and final immutability hardening for `SelectionResult`.
  - **AI Executed:** Followed test-first TDD, implemented pure selection logic, added immutability tests, and verified all static and dynamic checks.
- **Verification & Testing (Actual Results):**
  - `uv run --directory backend --extra dev pytest tests/engine/test_selection.py`: 14 passed in 0.19s.
  - `uv run --directory backend --extra dev pytest`: 71 passed in 0.42s (full backend suite).
  - `uv run --directory backend --extra dev mypy app/engine`: Success: no issues found in 5 source files (`mypy --strict`).
  - `uv run --directory backend --extra dev mypy app`: Success: no issues found in 18 source files.
  - `uv run --directory backend --extra dev ruff check .`: All checks passed.
  - `uv run --directory backend --extra dev ruff format --check .`: 33 files already formatted.
- **Acceptance Criteria [Done when]:**
  - Selection by specificity -> priority -> id and tie determinism implemented and verified against AC-3 and AC-13. Satisfied.


### Task T12: Per-Transaction Minimum Threshold (AC-7)
- **Date:** 2026-11-16
- **Branch:** `main`
- **Scope:** Implement per-transaction minimum spend threshold (`min_transaction_cents`) enforcement in the applicability filter per SPEC AC-7, FR-11, and ARCHITECTURE §4.2 step 2.
- **Implementation Details:**
  - Updated `backend/app/engine/applicability.py`:
    - Added `_format_cents(cents)` using pure integer `divmod` (no floats) for clear threshold/amount explanations.
    - Added `_check_min_transaction_threshold(rule, purchase)`: passes when `min_transaction_cents is None` or `purchase.amount_cents >= rule.min_transaction_cents`; rejects with `below_min_transaction` when `purchase.amount_cents < rule.min_transaction_cents`.
    - Integrated threshold check into `check_rule_applicability(rule, purchase)` after scope matching and exclusion evaluation, preserving existing public signatures and T10 behavior.
    - `filter_applicable_rules` emits `TraceStep(step_type="applicability_filter", action="rejected", reason="below_min_transaction", ...)` with rule ID/key and deterministic step numbering, allowing eligible fallback rules to win via T11 `select_best_rule`.
  - Added 8 unit tests in `backend/tests/engine/test_applicability.py` (`TestMinTransactionThreshold`):
    - `min_transaction_cents=None` passes for small purchases.
    - Purchase below minimum rejected with `below_min_transaction` (including `$20.00` / `$25.00` formatting).
    - Dollar formatting edge cases (`1` -> `$0.01`, `99` -> `$0.99`, `100` -> `$1.00`, `10025` -> `$100.25`).
    - Purchase exactly at minimum passes (inclusive boundary).
    - Purchase above minimum passes.
    - Scope mismatch and exclusion checks take precedence over threshold failure.
    - AC-7 end-to-end with T11: $25 minimum promo rule rejected on $20 purchase while fallback base rule survives and wins `select_best_rule`.
    - Multiple rules with mixed threshold outcomes preserve surviving rule order and deterministic rejection trace numbering.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Approved integrating `min_transaction_cents` into `applicability.py`, inclusive `>=` boundary, and `below_min_transaction` rejection reason.
  - **AI Executed:** Followed test-first TDD, implemented pure integer-cents threshold check, verified all tests and static checks.
- **Verification & Testing (Actual Results):**
  - `uv run --directory backend --extra dev pytest tests/engine/test_applicability.py`: 23 passed in 0.16s.
  - `uv run --directory backend --extra dev pytest`: 79 passed in 0.46s (full backend suite, including `test_no_float.py`).
  - `uv run --directory backend --extra dev mypy --strict app/engine`: Success: no issues found in 5 source files.
  - `uv run --directory backend --extra dev mypy app`: Success: no issues found in 18 source files.
  - `uv run --directory backend --extra dev ruff check .`: All checks passed.
  - `uv run --directory backend --extra dev ruff format --check .`: 33 files already formatted.
  - `git diff --check`: Clean (0 whitespace/formatting errors).
- **Acceptance Criteria [Done when]:**
  - Per-transaction minimum threshold (`min_transaction_cents`) implemented and verified against AC-7. Satisfied.


### Task T13: Period Utilities (Monthly, Quarterly, Calendar Year, Card-Year)
- **Date:** 2026-11-16
- **Branch:** `main`
- **Scope:** Implement pure, deterministic period boundary utilities for `Period.MONTHLY`, `Period.QUARTERLY`, `Period.CALENDAR_YEAR`, and `Period.CARD_YEAR` per BACKLOG T13 and ARCHITECTURE §4.4.
- **Implementation Details:**
  - Created `backend/app/engine/periods.py`:
    - `PeriodBounds`: Frozen, slotted dataclass (`start_date`, `end_date`, `next_reset_date`) with `__post_init__` invariants (`end_date >= start_date`, `next_reset_date == end_date + timedelta(days=1)`).
    - `get_period_bounds(period, target_date, opened_on=None)`: Computes inclusive `[start_date, end_date]` and `next_reset_date` without floats or system clock access.
    - `CARD_YEAR`: Requires `opened_on`, rejects `target_date < opened_on` with `ValueError`, computes anniversary-based period ending the day before the next anniversary, and clamps Feb 29 openings to Feb 28 in non-leap years (keeping Feb 29 in leap years).
  - Exported `PeriodBounds` and `get_period_bounds` from `backend/app/engine/__init__.py`.
  - Added table-driven tests in `backend/tests/engine/test_periods.py` (34 parametrized/unit cases) covering all four periods, month transitions (Jan/Dec), all four calendar quarters, Dec 31 / Jan 1 year-end transitions, leap day (Feb 29) in monthly/quarterly/calendar-year/card-year periods, missing `opened_on`, `target_date < opened_on`, determinism, and frozen immutability.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Approved `PeriodBounds` structure, inclusive bounds with `next_reset_date`, `ValueError` guards for `CARD_YEAR`, and Feb 29 -> Feb 28 clamping in non-leap years.
  - **AI Executed:** Followed test-first TDD, implemented pure period math, verified all tests and static checks.
- **Verification & Testing (Actual Results):**
  - `uv run --directory backend --extra dev pytest tests/engine/test_periods.py`: 34 passed in 0.14s.
  - `uv run --directory backend --extra dev pytest`: 113 passed in 0.54s (includes `test_no_float.py`).
  - `uv run --directory backend --extra dev mypy --strict app/engine`: Success: no issues found in 6 source files.
  - `uv run --directory backend --extra dev mypy app`: Success: no issues found in 19 source files.
  - `uv run --directory backend --extra dev ruff check .`: All checks passed.
  - `uv run --directory backend --extra dev ruff format --check .`: 35 files already formatted.
  - `git diff --check`: Clean (0 whitespace/formatting errors).
- **Acceptance Criteria [Done when]:**
  - Period utilities for monthly, quarterly, calendar year, and card-year boundaries implemented with table tests including leap day and year-end. Satisfied.


### Task T14: Cap Handling, Straddle, and Fallback (AC-5)
- **Date:** 2026-11-16
- **Branch:** `main`
- **Scope:** Implement pure cap allocation including straddle splitting and iterative fallback to next-best eligible rules per SPEC AC-5, FR-11, and ARCHITECTURE §4.2 step 4, kept separate from reward-unit calculation and rounding (T16).
- **Implementation Details:**
  - Created `backend/app/engine/caps.py`:
    - `CapPortion`: Frozen, slotted dataclass holding `rule: EarningRule`, `amount_cents: int` (validated strictly positive), and `cap_group_key: str | None`.
    - `CapAllocationResult`: Frozen, slotted dataclass holding `portions`, `unallocated_cents` (validated non-negative integer), and `trace_steps`, enforcing runtime immutability via `_normalize_sequence`.
    - `allocate_purchase_across_caps(purchase, rules, caps, spend_history)`: Runs `filter_applicable_rules` upfront and validates that every applicable rule with a non-null `cap_group_key` has a matching entry in `cap_map` (raising `ValueError` otherwise). Iteratively excludes exhausted cap groups, reruns deterministic selection (`select_best_rule`), allocates `min(remaining_amount_cents, cap_remaining)` (or full remaining amount if uncapped), and records any unallocated remainder explicitly if no eligible fallback exists.
  - Exported `CapPortion`, `CapAllocationResult`, and `allocate_purchase_across_caps` from `backend/app/engine/__init__.py`.
  - Added 14 unit tests in `backend/tests/engine/test_caps.py`:
    - AC-5 exact straddle scenario ($500 quarterly cap, $450 spent, $100 purchase -> $50 @ 5x + $50 @ 1x).
    - Purchase entirely within remaining cap.
    - Cap exactly exhausted without fallback.
    - Pre-exhausted cap falling back to base.
    - Missing cap configuration raising `ValueError` (both winning and non-winning applicable rules).
    - Shared `cap_group_key` across multiple rules preventing cap reuse after straddle.
    - Duplicate cap definitions raising `ValueError`.
    - Multiple successive exhausted/straddled cap groups falling back to base.
    - Empty `rules=()` and no-eligible-fallback leaving explicit `unallocated_cents` and `no_fallback_rule` trace.
    - Determinism across rule input orderings, runtime immutability, and `CapPortion`/`CapAllocationResult` validation.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Kept cap allocation separate from `AppliedPortion.reward_units` / rounding (T16), required `ValueError` on missing cap config across all applicable rules, iterative fallback across exhausted cap groups, and explicit `unallocated_cents` when no fallback exists.
  - **AI Executed:** Followed test-first TDD, implemented pure integer-cent cap allocation, applied review correction for upfront cap validation, and verified all tests and static checks.
- **Verification & Testing (Actual Results):**
  - `uv run --directory backend --extra dev pytest tests/engine/test_caps.py`: 14 passed in 0.18s.
  - `uv run --directory backend --extra dev pytest`: 135 passed in 0.75s (includes `test_no_float.py`).
  - `uv run --directory backend --extra dev mypy --strict app/engine`: Success: no issues found in 7 source files.
  - `uv run --directory backend --extra dev mypy app`: Success: no issues found in 20 source files.
  - `uv run --directory backend --extra dev ruff check .`: All checks passed.
  - `uv run --directory backend --extra dev ruff format --check .`: 37 files already formatted.
  - `git diff --check`: Clean (0 whitespace/formatting errors).
- **Acceptance Criteria [Done when]:**
  - Cap handling including straddle and fallback to base implemented and verified against AC-5. Satisfied.


### Task T15: Period-Spend Threshold (No Retroactivity)
- **Date:** 2026-11-16
- **Branch:** `main`
- **Scope:** Implement non-retroactive period-spend threshold (`min_period_spend_cents` / `threshold_period`) evaluation in the applicability pipeline per BACKLOG T15 and ARCHITECTURE §3 & §4.2 step 2.
- **Implementation Details:**
  - Updated `backend/app/engine/applicability.py`:
    - Added `_check_period_spend_threshold(rule, spend_history)`: enforces that `min_period_spend_cents` and `threshold_period` are both set or both `None` (raising `ValueError` for partial config), requires `spend_history` when configured, looks up prior spend via `spend_history.get_threshold_spend(rule.threshold_period.value)`, passes when `prior_spend_cents >= rule.min_period_spend_cents`, and rejects with `"below_min_period_spend"` otherwise (never adding `purchase.amount_cents`).
    - Added optional `spend_history: SpendHistory | None = None` to `check_rule_applicability` and `filter_applicable_rules`, preserving backward compatibility for callers without period thresholds.
  - Updated `backend/app/engine/caps.py`:
    - Passed `spend_history=spend_history` from `allocate_purchase_across_caps` into `filter_applicable_rules`.
  - Added 13 unit tests in `backend/tests/engine/test_applicability.py` (`TestPeriodSpendThreshold`) and 1 integration test in `backend/tests/engine/test_caps.py`:
    - No threshold configured without `spend_history`.
    - Parametrized boundary and non-retroactivity cases (below, below-but-purchase-would-cross, exact, above).
    - Period-specific lookup keys (`monthly`, `quarterly`, `calendar_year`, `card_year`) and shared lookup across two rules with the same period.
    - `ValueError` for partial config (`min_period_spend_cents` without `threshold_period` and vice versa) and missing `spend_history`.
    - Fallback rule selection via `select_best_rule` and cap-allocation integration.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Confirmed `rule.threshold_period.value` as `SpendHistory.get_threshold_spend` key, `ValueError` for partial config or missing `spend_history`, `"below_min_period_spend"` rejection reason, and optional `spend_history` parameter on applicability functions.
  - **AI Executed:** Followed test-first TDD, implemented pure integer-cent period-spend threshold evaluation, wired `spend_history` into `caps.py`, and verified all tests and static checks.
- **Verification & Testing (Actual Results):**
  - `uv run --directory backend --extra dev pytest tests/engine/test_applicability.py tests/engine/test_caps.py`: 51 passed in 0.16s.
  - `uv run --directory backend --extra dev pytest`: 149 passed in 0.69s (includes `test_no_float.py`).
  - `uv run --directory backend --extra dev mypy --strict app/engine`: Success: no issues found in 7 source files.
  - `uv run --directory backend --extra dev mypy app`: Success: no issues found in 20 source files.
  - `uv run --directory backend --extra dev ruff check .`: All checks passed.
  - `uv run --directory backend --extra dev ruff format --check .`: 37 files already formatted.
  - `git diff --check`: Clean (0 whitespace/formatting errors).
- **Acceptance Criteria [Done when]:**
  - Non-retroactive period-spend threshold implemented and verified in applicability and cap-allocation pipelines. Satisfied.


### Task T16: Units + Rounding Modes (Floor / Nearest / None) with Decimal
- **Date:** 2026-11-16
- **Branch:** `main`
- **Scope:** Implement pure Decimal reward-unit calculation and transaction-level rounding once on the summed portions per BACKLOG T16 and ARCHITECTURE §4.2 step 5 & §4.6.
- **Implementation Details:**
  - Created `backend/app/engine/units.py`:
    - `UnitsResult`: Frozen, slotted dataclass holding `applied_portions`, `unrounded_total_units`, `total_reward_units`, `rounding_mode_used`, and `trace_step`, with `_validate_decimal` and `_normalize_sequence` runtime checks.
    - `calculate_reward_units(portions)`: Converts each `CapPortion` into an `AppliedPortion` with unrounded `reward_units = (Decimal(amount_cents) / Decimal("100")) * rule.multiplier`, sums all unrounded units, and applies the first portion's `rule.rounding` once at the transaction level:
      - `FLOOR_UNITS`: `ROUND_FLOOR` to integer `Decimal("1")`
      - `NEAREST_UNIT`: `ROUND_HALF_UP` to integer `Decimal("1")`
      - `NONE_4DP`: `ROUND_HALF_UP` to `Decimal("0.0001")`
    - Rejects empty `portions`, unordered sets, and unsupported rounding modes with explicit errors.
    - Emits a deterministic `TraceStep(step_type="units_calculation", action="calculated", ...)` recording unrounded sum, rounding mode, and final total.
  - Exported `UnitsResult` and `calculate_reward_units` from `backend/app/engine/__init__.py`.
  - Added 27 table-driven and unit tests in `backend/tests/engine/test_units.py` covering all three rounding modes, exact integer and fractional values, half cases (2.5, 3.5, 0.00005, 0.00015), multi-portion summing before rounding, straddled purchases with differing rule rounding modes, empty/invalid inputs, float/bool rejection, determinism, and immutability.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Specified `ROUND_HALF_UP` for `NEAREST_UNIT` and `NONE_4DP`, `Decimal("0.0001")` quantization for `NONE_4DP`, using the first portion's rounding mode with no override parameter, and rejecting empty portions.
  - **AI Executed:** Followed test-first TDD, implemented pure Decimal unit calculation/rounding, verified all tests and static checks.
- **Verification & Testing (Actual Results):**
  - `uv run --directory backend --extra dev pytest tests/engine/test_units.py tests/engine/test_no_float.py`: 29 passed in 0.16s.
  - `uv run --directory backend --extra dev pytest`: 176 passed in 0.78s.
  - `uv run --directory backend --extra dev mypy --strict app/engine`: Success: no issues found in 8 source files.
  - `uv run --directory backend --extra dev mypy app`: Success: no issues found in 21 source files.
  - `uv run --directory backend --extra dev ruff check .`: All checks passed.
  - `uv run --directory backend --extra dev ruff format --check .`: 39 files already formatted.
  - `git diff --check`: Clean (0 whitespace/formatting errors).
- **Acceptance Criteria [Done when]:**
  - Units calculation and rounding modes (`floor_units`, `nearest_unit`, `none_4dp`) with Decimal implemented and verified with table-driven tests including half cases. Satisfied.


### Task T17: Valuation & No-Valuation Routing (AC-2)
- **Date:** 2026-11-16
- **Branch:** `main`
- **Scope:** Implement pure valuation math (`ROUND_HALF_EVEN` cents) and no-valuation routing to `CardStatus.UNRANKED` per BACKLOG T17, SPEC FR-13/FR-14/AC-2, and ARCHITECTURE §4.2 step 6.
- **Implementation Details:**
  - Created `backend/app/engine/valuation.py`:
    - `ValuationResult`: Frozen, slotted dataclass (`status`, `estimated_value_cents`, `valuation_used`, `rejection_reason`, `rejection_message`, `warnings`, `trace_step`) validating `estimated_value_cents` (non-negative int, rejecting bool/float), status invariants (`RANKED` vs `UNRANKED`), and normalizing `warnings` via `_normalize_sequence`.
    - `evaluate_valuation(reward_units, reward_currency, valuation)`:
      - When `valuation` is present: normalizes and validates currency match (`ValueError` on mismatch), computes `(reward_units * valuation.cents_per_unit).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)` into `estimated_value_cents`, returns `CardStatus.RANKED`, emits `"illustrative default valuation"` warning when `not valuation.is_user_set`, and emits a deterministic `TraceStep`.
      - When `valuation` is `None`: routes to `CardStatus.UNRANKED` with `estimated_value_cents=None`, `rejection_reason=UnrankedReason.NO_VALUATION.value`, and the exact documented limitation message from ARCHITECTURE.md.
  - Exported `ValuationResult` and `evaluate_valuation` from `backend/app/engine/__init__.py`.
  - Added 16 table-driven and unit tests in `backend/tests/engine/test_valuation.py` covering exact cents, half-even ties rounding both up and down (`0.5->0`, `1.5->2`, `2.5->2`, `3.5->4`), zero units, default-valuation warning vs user-set valuation, currency normalization/mismatch, `no_valuation` routing/message, float/bool/empty-currency rejection, determinism, and immutability.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Specified `ValuationResult` fields, `.strip().casefold()` currency matching, `ROUND_HALF_EVEN`, `"illustrative default valuation"` warning, and exact ARCHITECTURE.md `no_valuation` message.
  - **AI Executed:** Followed test-first TDD, implemented pure Decimal valuation and routing, verified all tests and static checks.
- **Verification & Testing (Actual Results):**
  - `uv run --directory backend --extra dev pytest tests/engine/test_valuation.py tests/engine/test_no_float.py`: 18 passed in 0.21s.
  - `uv run --directory backend --extra dev pytest tests/engine`: 186 passed (all engine tests).
  - `uv run --directory backend --extra dev pytest`: 191 passed, 1 failed (`tests/api/test_readiness.py::test_readyz_healthy_db` returned 503 because local Postgres was not running).
  - `uv run --directory backend --extra dev mypy --strict app/engine`: Success: no issues found in 9 source files.
  - `uv run --directory backend --extra dev mypy app`: Success: no issues found in 22 source files.
  - `uv run --directory backend --extra dev ruff check .`: All checks passed.
  - `uv run --directory backend --extra dev ruff format --check .`: 41 files already formatted.
  - `git diff --check`: Clean (0 whitespace/formatting errors).
- **Acceptance Criteria [Done when]:**
  - Valuation → estimated value (`ROUND_HALF_EVEN`) and `no_valuation` routing to `UNRANKED` implemented and verified against AC-2. Satisfied.


### Task T18: Cross-Card Ranking (Ranked / Unranked / Ineligible, Tie-Break, Global Notes)
- **Date:** 2026-11-16
- **Branch:** `main`
- **Scope:** Implement pure cross-card ranking, tie-breaking, tie-explanation annotation, and global notes per BACKLOG T18, SPEC AC-2/AC-10, and ARCHITECTURE §4.3.
- **Implementation Details:**
  - Created `backend/app/engine/ranking.py`:
    - `RankingResult`: Frozen, slotted dataclass holding immutable tuples `ranked`, `unranked`, `ineligible`, and `global_notes`.
    - `rank_card_evaluations(evaluations)`:
      - Validates `CardStatus` / `estimated_value_cents` consistency without silently repairing invalid states.
      - Partitions by `CardStatus` (`RANKED`, `UNRANKED`, `INELIGIBLE`).
      - Sorts `ranked` by `(-estimated_value_cents, -reward_units, card_name.casefold(), card_name, card_id)` and appends `"Tied on estimated value."` via `dataclasses.replace` to every card in an `estimated_value_cents` tie group.
      - Sorts `unranked` and `ineligible` deterministically by `(card_name.casefold(), card_name, card_id)` without ever ranking unranked cards by raw units/multipliers.
      - Emits `GLOBAL_COMPARISON_NOTE` always, plus `NO_RANKABLE_CARDS_NOTE` when evaluated cards exist but none are ranked.
  - Exported `GLOBAL_COMPARISON_NOTE`, `NO_RANKABLE_CARDS_NOTE`, `RankingResult`, and `rank_card_evaluations` from `backend/app/engine/__init__.py`.
  - Added 6 unit tests in `backend/tests/engine/test_ranking.py` covering partitioning, descending value sort, tie-breaking by units/nickname/card_id, tie explanation injection without mutating inputs, non-tied cards, unranked/ineligible deterministic sorting, global notes across mixed/all-unranked/all-ineligible/empty inputs, inconsistent status/value rejection, immutability, and determinism.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Scoped T18 strictly to `rank_card_evaluations`, specified exact sort keys, sequential 1-based list ordering, replacement-based tie annotations, and exact `global_notes` rules.
  - **AI Executed:** Followed test-first TDD, implemented pure cross-card ranking, verified all tests and static checks.
- **Verification & Testing (Actual Results):**
  - `uv run --directory backend --extra dev pytest tests/engine/test_ranking.py tests/engine/test_no_float.py`: 8 passed in 0.22s.
  - `uv run --directory backend --extra dev pytest`: 198 passed in 0.80s (with Compose `db` running).
  - `uv run --directory backend --extra dev mypy --strict app/engine`: Success: no issues found in 10 source files.
  - `uv run --directory backend --extra dev mypy app`: Success: no issues found in 23 source files.
  - `uv run --directory backend --extra dev ruff check .`: All checks passed.
  - `uv run --directory backend --extra dev ruff format --check .`: 43 files already formatted.
  - `git diff --check`: Clean (0 whitespace/formatting errors).
- **Acceptance Criteria [Done when]:**
  - Cross-card ranking (ranked/unranked/ineligible partitioning, tie-break, global notes) implemented and verified against AC-2 and AC-10. Satisfied.


### Task T19: Explanation Renderer (Trace → Sentences) with Golden-Text Tests
- **Date:** 2026-11-16
- **Branch:** `main`
- **Scope:** Implement pure deterministic explanation renderer converting `TraceStep` sequences to human-readable sentences with golden-text tests per BACKLOG T19, SPEC FR-15/NFR-3, and ARCHITECTURE §4.2 step 7.
- **Implementation Details:**
  - Created `backend/app/engine/explain.py`:
    - `render_trace_step(step)`: Maps known `step_type`s (`effective_filter`, `applicability_filter`, `selection`, `cap_allocation`, `units_calculation`, `valuation`) to approved stage prefixes (`Effective check:`, `Applicability:`, `Selection:`, `Cap allocation:`, `Units:`, `Valuation:`), preserves `step.detail`, appends `(rule '<rule_key>')` only when `rule_key` is missing from `detail`, normalizes punctuation to a single trailing period, and falls back deterministically for unknown `step_type` or empty `detail`.
    - `render_explanation(trace)`: Preserves caller's exact sequence order (no sorting by `step_number`), normalizes sequences via `_normalize_sequence` (rejecting sets), and returns `tuple[str, ...]`.
  - Exported `render_trace_step` and `render_explanation` from `backend/app/engine/__init__.py`.
  - Added 11 golden-text and unit tests in `backend/tests/engine/test_explain.py` using actual engine `TraceStep` outputs covering happy path, AC-5 cap straddle + fallback, AC-4/AC-7/T15 applicability exclusions + thresholds, cap exhaustion + unallocated remainder, AC-2 no-valuation routing, AC-6/no-applicable-rule ineligible outcomes, unknown `step_type` / empty `detail` fallback, duplicate `step_number` order preservation, punctuation hygiene, empty input, set rejection, and determinism.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Approved preserving caller trace sequence order and using exact stage prefixes (`Effective check:`, `Applicability:`, `Selection:`, `Cap allocation:`, `Units:`, `Valuation:`).
  - **AI Executed:** Followed test-first TDD, implemented pure trace-to-sentence renderer, wrote golden-text tests against actual engine outputs, and verified all static and dynamic checks.
- **Verification & Testing (Actual Results):**
  - `uv run --directory backend --extra dev pytest tests/engine/test_explain.py tests/engine/test_no_float.py`: 13 passed in 0.20s.
  - `uv run --directory backend --extra dev pytest`: 209 passed in 0.87s (with Compose `db` running).
  - `uv run --directory backend --extra dev mypy --strict app/engine`: Success: no issues found in 11 source files.
  - `uv run --directory backend --extra dev mypy app`: Success: no issues found in 24 source files.
  - `uv run --directory backend --extra dev ruff check .`: All checks passed.
  - `uv run --directory backend --extra dev ruff format --check .`: 45 files already formatted.
  - `git diff --check`: Clean (0 whitespace/formatting errors).
- **Acceptance Criteria [Done when]:**
  - Explanation renderer (trace → sentences) with golden-text tests implemented and verified against FR-15 and NFR-3. Satisfied.


### Task T20: Engine Golden Fixtures (JSON) & ≥ 90% Branch Coverage in CI
- **Date:** 2026-11-16
- **Branch:** `main`
- **Scope:** Implement the per-card `evaluate_purchase` orchestrator, create 16 JSON golden fixture scenarios covering all Phase 2 acceptance criteria, and enforce ≥ 90% branch coverage for `app.engine` in GitHub Actions CI.
- **Implementation Details:**
  - Created `backend/app/engine/evaluate.py`:
    - `evaluate_purchase(purchase, card, spend_history, valuation) -> CardEvaluation`: Composes effective filtering, applicability filtering, rule selection, cap allocation, unit calculation/rounding, valuation/no-valuation routing, and explanation rendering in ARCHITECTURE §4.2 order with contiguous 1-based trace step numbers.
    - Exported `evaluate_purchase` from `backend/app/engine/__init__.py`.
  - Created `backend/tests/engine/fixtures/scenarios.json` (16 scenarios) and `backend/tests/engine/test_golden_fixtures.py` (18 tests) covering `AC-2`, `AC-3`, `AC-4`, `AC-5`, `AC-6`, `AC-7`, `AC-8` (rule-version isolation at the pure engine level; DB transaction snapshot persistence remains Phase 3 T31/T32), `AC-9`, `AC-10`, `AC-13`, `T15` non-retroactivity, `T16` rounding modes, `T18` tie-breaking/global notes, and all-caps-exhausted ineligibility.
  - Added `pytest-cov>=5.0.0` to `backend/pyproject.toml` `[project.optional-dependencies].dev` and synced `backend/uv.lock`.
  - Updated `.github/workflows/ci.yml` to run `pytest` with `--cov=app.engine --cov-branch --cov-fail-under=90 --cov-report=term-missing`.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Approved implementing `evaluate_purchase` in `backend/app/engine/evaluate.py`, adding `pytest-cov`, and enforcing ≥ 90% engine branch coverage in CI.
  - **AI Executed:** Implemented `evaluate_purchase`, authored 16 independent JSON golden fixtures, updated `pyproject.toml` / `uv.lock` / `ci.yml`, and verified coverage and static checks.
- **Verification & Testing (Actual Results):**
  - Baseline engine branch coverage (before T20): 97% (705 stmts, 14 miss, 246 branches, 18 partial).
  - Final engine branch coverage (including `evaluate.py`, 100% covered): **96.78%** (741 stmts, 14 miss, 252 branches, 18 partial; ≥ 90% threshold satisfied).
  - `uv run --directory backend --extra dev pytest tests/engine/test_golden_fixtures.py`: 18 passed in 0.15s.
  - `uv run --directory backend --extra dev pytest --cov=app.engine --cov-branch --cov-fail-under=90 --cov-report=term-missing`: 227 passed in 2.00s.
  - `uv run --directory backend --extra dev mypy --strict app/engine`: Success: no issues found in 12 source files.
  - `uv run --directory backend --extra dev mypy app`: Success: no issues found in 25 source files.
  - `uv run --directory backend --extra dev ruff check .`: All checks passed.
  - `uv run --directory backend --extra dev ruff format --check .`: 47 files already formatted.
  - `git diff --check`: Clean (0 whitespace/formatting errors).
- **Acceptance Criteria [Done when]:**
  - ≥ 15 JSON golden fixture scenarios covering all Phase 2 ACs and ≥ 90% engine branch coverage enforced in CI. Satisfied.


### Task T21: Migrations & ORM for Reference Tables
- **Date:** 2026-11-16
- **Branch:** `main`
- **Scope:** Implement SQLAlchemy 2.0 ORM models and Alembic migration for the five reference tables (`reward_currencies`, `categories`, `merchants`, `card_products`, `rule_sources`) per BACKLOG T21 and ARCHITECTURE §2.1.
- **Implementation Details:**
  - Created `backend/app/models/reference.py` (`RewardCurrency`, `Category`, `Merchant`, `CardProduct`, `RuleSource`) using SQLAlchemy 2.0 `Mapped[]` / `mapped_column()`, integer cents, `Numeric(8, 4)`, `Date`, `postgresql.ARRAY(String(64))` (`default=list`, `server_default=text("'{}'")`), natural unique constraints (`reward_currencies.code`, `categories.code`, `merchants.name`, `(card_products.issuer_name, card_products.name)`, `rule_sources.title`), `ON DELETE SET NULL` for `merchants.default_category_id`, `ON DELETE RESTRICT` for `card_products.reward_currency_id`, and `CHECK` constraints (`kind`, `default_cents_per_unit > 0`, `annual_fee_cents >= 0`).
  - Exported the five models in `backend/app/models/__init__.py` and imported `app.models` in `backend/alembic/env.py`.
  - Generated Alembic migration `backend/alembic/versions/0e8ce330266b_add_reference_tables.py` (`upgrade` + `downgrade`).
  - Added 6 real-PostgreSQL integration tests in `backend/tests/db/test_reference_models.py` verifying metadata, `alembic` downgrade/upgrade round-trip, independent `merchants.tags` defaults + nullable `default_category_id`, FK `SET NULL` / `RESTRICT`, unique constraints, and `CHECK` constraints.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Approved `ARRAY(String(64))` for `merchants.tags`, nullable `merchants.default_category_id` (`ON DELETE SET NULL`), and natural unique keys without `seed_key`.
  - **AI Executed:** Implemented ORM models, generated and verified Alembic migration, wrote PostgreSQL tests, and ran full validation.
- **Verification & Testing (Actual Results):**
  - `alembic upgrade head` -> `alembic downgrade -1` -> `alembic upgrade head`: succeeded cleanly against PostgreSQL 16.
  - `uv run --directory backend --extra dev pytest tests/db/test_reference_models.py`: 6 passed in 0.96s.
  - `uv run --directory backend --extra dev pytest --cov=app.engine --cov-branch --cov-fail-under=90 --cov-report=term-missing`: 233 passed in 2.78s (96.78% engine branch coverage).
  - `uv run --directory backend --extra dev mypy app`: Success: no issues found in 26 source files.
  - `uv run --directory backend --extra dev ruff check .`: All checks passed.
  - `uv run --directory backend --extra dev ruff format --check .`: 50 files already formatted.
  - `git diff --check`: Clean (0 whitespace/formatting errors).
- **Acceptance Criteria [Done when]:**
  - Reference table ORM models and reversible Alembic migration implemented and verified against real PostgreSQL. Satisfied.

## T22 — Migrations & ORM for rules, exclusions, and caps (2026-11-16)
- **What was done:**
  - Implemented SQLAlchemy 2.0 ORM models in `backend/app/models/rules.py` and re-exported them in `backend/app/models/__init__.py`:
    - `SpendCap` (`spend_caps`): unique `(card_product_id, cap_group_key)`, positive `cap_amount_cents`, `period` constrained to `monthly | quarterly | calendar_year | card_year`.
    - `EarningRule` (`earning_rules`): unique `(rule_key, version)`, `version >= 1`, `scope_type` (`base | category | merchant`) with `ck_earning_rules_scope_target`, `Numeric(8, 4)` non-negative `multiplier`, `cap_id` FK (`ON DELETE RESTRICT`), `post_cap_behavior` (`fallback_to_base`), optional `min_transaction_cents > 0`, paired `(min_period_spend_cents, threshold_period)`, `rounding` (`floor_units | nearest_unit | none_4dp`), `effective_to >= effective_from`, `source_id` FK (`ON DELETE RESTRICT`), `last_reviewed_on`, `supersedes_id` self-FK (`ON DELETE SET NULL`), and PostgreSQL `btree_gist` `ExcludeConstraint` preventing overlapping inclusive `daterange(effective_from, effective_to, '[]')` per `rule_key`.
    - `RuleExclusion` (`rule_exclusions`): `exclusion_type` (`category | merchant | merchant_tag`) with separate nullable typed target columns (`target_category_id`, `target_merchant_id`, `target_tag`) and `ck_rule_exclusions_target` enforcing exactly one matching target (and non-blank `target_tag`), plus `reason`.
    - Immutability enforcement boundary: `SEMANTIC_RULE_COLUMNS`, `RuleImmutableError`, and `ensure_rule_mutable(rule, *, is_referenced_by_calc: bool)` documented and ready for calculation-reference wiring when `transaction_reward_calcs` is introduced in T23.
  - Added reversible Alembic migration `backend/alembic/versions/1f98842cde08_add_rules_exclusions_and_caps.py` (including `CREATE EXTENSION IF NOT EXISTS btree_gist`).
  - Added real-PostgreSQL integration tests in `backend/tests/db/test_rule_models.py` and updated `backend/tests/db/test_reference_models.py` (`expected.issubset(...)` for `Base.metadata.tables`).
- **Verification & Testing (Actual Results):**
  - `alembic upgrade head` -> `alembic downgrade -1` -> `alembic upgrade head`: succeeded cleanly against PostgreSQL 16.
  - `uv run --directory backend --extra dev pytest tests/db/test_rule_models.py`: 8 passed in 1.91s.
  - `uv run --directory backend --extra dev pytest --cov=app.engine --cov-branch --cov-fail-under=90 --cov-report=term-missing`: 241 passed in 7.12s (96.78% engine branch coverage).
  - `uv run --directory backend --extra dev mypy app`: Success: no issues found in 27 source files.
  - `uv run --directory backend --extra dev ruff check .`: All checks passed.
  - `uv run --directory backend --extra dev ruff format --check .`: 53 files already formatted.
  - `git diff --check`: Clean (0 whitespace/formatting errors).
- **Acceptance Criteria [Done when]:**
  - Rules, exclusions, and caps ORM models, `btree_gist` non-overlap constraint, immutability boundary, and reversible Alembic migration implemented and verified against real PostgreSQL. Satisfied.

## T23 — Migrations & ORM for profiles, valuations, transactions, calcs, and benefits (2026-11-16)
- **What was done:**
  - Implemented SQLAlchemy 2.0 ORM models in `backend/app/models/profiles.py` and re-exported them in `backend/app/models/__init__.py`:
    - `Profile` (`profiles`): `slug` (unique, indexed), `display_name`, `is_demo`, nullable unique `seed_key`.
    - `ProfileCard` (`profile_cards`): FKs to `profiles.id` (`CASCADE`) and `card_products.id` (`RESTRICT`), `nickname`, `opened_on`, `is_active`.
    - `CurrencyValuation` (`currency_valuations`): composite PK `(profile_id, reward_currency_id)`, `Numeric(8, 4)` `cents_per_unit > 0`, `is_user_set`, UTC `updated_at`.
    - `Transaction` (`transactions`): FKs to `profiles.id` (`CASCADE`), `profile_cards.id` (`CASCADE`), `categories.id` (`RESTRICT`), nullable `merchants.id` (`RESTRICT`), `amount_cents > 0`, `merchant_text`, `occurred_on`, `note`, UTC `created_at`, and composite indexes `(profile_id, occurred_on)` and `(profile_card_id, occurred_on)`.
    - `TransactionRewardCalc` (`transaction_reward_calcs`): unique `transaction_id` FK (`CASCADE`), `engine_version`, `reward_currency_id` FK (`RESTRICT`), `Numeric(14, 4)` `reward_units >= 0`, nullable `valuation_cents_per_unit_used > 0`, nullable `estimated_value_cents >= 0`, `JSONB` `trace`, UTC `created_at`.
    - `CalcRuleReference` (`calc_rule_references`): composite PK `(calc_id, rule_id)`, `calc_id` FK (`CASCADE`), indexed `rule_id` FK (`RESTRICT`).
    - `BenefitDefinition` (`benefit_definitions`): `card_product_id` FK (`RESTRICT`), `benefit_type` (`credit | allowance | perk`), nullable `value_cents > 0`, `reset_period` (`monthly | quarterly | semiannual | calendar_year | card_year`), `notes`, `source_id` FK (`RESTRICT`), `effective_to >= effective_from`.
    - `BenefitUsage` (`benefit_usages`): `profile_card_id` FK (`CASCADE`), `benefit_definition_id` FK (`RESTRICT`), nullable `amount_cents > 0`, `used_on`, `note`, and composite index `(profile_card_id, benefit_definition_id, used_on)`.
    - Immutability integration: `is_rule_referenced(session, rule_id)` (using `no_autoflush`) and `check_rule_mutable(session, rule)` wired to `ensure_rule_mutable()`, plus PostgreSQL `BEFORE UPDATE` trigger `trg_earning_rules_immutable_when_referenced` on `earning_rules` blocking direct SQL semantic updates to referenced rules.
  - Added reversible Alembic migration `backend/alembic/versions/460ae59a41d3_add_profiles_transactions_calcs_and_.py` depending on `1f98842cde08`.
  - Added real-PostgreSQL integration tests in `backend/tests/db/test_profile_calc_models.py`.
- **Verification & Testing (Actual Results):**
  - `alembic upgrade head` -> `alembic downgrade 1f98842cde08` -> `alembic upgrade head`: succeeded cleanly against PostgreSQL 16.
  - `uv run --directory backend --extra dev pytest tests/db/test_profile_calc_models.py`: 6 passed in 1.98s.
  - `uv run --directory backend --extra dev pytest --cov=app.engine --cov-branch --cov-fail-under=90 --cov-report=term-missing`: 247 passed in 7.98s (96.78% engine branch coverage).
  - `uv run --directory backend --extra dev mypy app`: Success: no issues found in 28 source files.
  - `uv run --directory backend --extra dev ruff check .`: All checks passed.
  - `uv run --directory backend --extra dev ruff format --check .`: 56 files already formatted.
  - `git diff --check`: Clean (0 whitespace/formatting errors).
- **Acceptance Criteria [Done when]:**
  - Profiles, cards, valuations, transactions, calculation snapshots, rule references, benefits, usages, DB/ORM immutability guard, and reversible Alembic migration implemented and verified against real PostgreSQL. Satisfied.

## T24 — Fictional seed data files (2026-11-16)
- **What was done:**
  - Added `pyyaml>=6.0` (runtime) and `types-PyYAML>=6.0` (dev) to `backend/pyproject.toml` and updated `backend/uv.lock`.
  - Created 7 fictional YAML seed data files under `backend/app/seeds/data/`:
    - `currencies.yaml`: 4 fictional reward currencies (`NW_CASH`, `NWT_PTS`, `SKY_MILES`, `HORIZON_PTS`) covering `cash_back`, `points`, and `miles` with decimal-string `default_cents_per_unit`.
    - `categories.yaml`: 8 standard categories (`dining`, `groceries`, `gas`, `travel`, `streaming`, `online_retail`, `utilities`, `other`).
    - `merchants.yaml`: 8 fictional merchants with `default_category_code` and tags including `warehouse_club` (`BulkDepot Club`) and `big_box`.
    - `sources.yaml`: 5 `fictional_sample` sources with `last_reviewed_on` and explicit fictional disclaimers.
    - `card_products.yaml`: 6 fictional card products across 4 fictional issuers covering `cash_back`, `flexible_points`, `airline_miles`, `flat_rate`, and `category_specialist`.
    - `rules.yaml`: 2 `spend_caps`, 16 `earning_rules` (base fallbacks for all 6 products, superseded `nwcash.dining` v1→v2 with non-overlapping dates, capped `verdant.groceries` and `nwcash.gas`, per-tx threshold `nwtpts.travel_min25`, period-spend threshold `horizon.dining_tier`, merchant-specific `nwtpts.harbor_roasters`), and 2 `rule_exclusions` (`warehouse_club` and `big_box`).
    - `benefits.yaml`: 5 fictional `benefit_definitions` covering `credit`, `allowance`, and `perk` across `monthly`, `quarterly`, `semiannual`, `calendar_year`, and `card_year` reset periods.
  - Added `backend/tests/seeds/test_seed_data.py` validating structure, minimum counts, natural-key references, non-overlapping dates, required rule examples, fictional labeling, and absence of real issuer/merchant names or 13–19 digit sequences.
- **Verification & Testing (Actual Results):**
  - `uv run --directory backend --extra dev pytest tests/seeds/test_seed_data.py`: 6 passed in 0.25s.
  - `uv run --directory backend --extra dev pytest --cov=app.engine --cov-branch --cov-fail-under=90 --cov-report=term-missing`: 253 passed in 10.00s (96.78% engine branch coverage).
  - `uv run --directory backend --extra dev mypy app tests/seeds`: Success: no issues found in 29 source files.
  - `uv run --directory backend --extra dev ruff check .`: All checks passed.
  - `uv run --directory backend --extra dev ruff format --check .`: 57 files already formatted.
  - `git diff --check`: Clean (0 whitespace/formatting errors).
- **Acceptance Criteria [Done when]:**
  - Fictional YAML seed catalog (≥6 products, currencies, categories, merchants, sources, rules with superseded/capped/exclusion/threshold examples, and benefits) validated against SPEC §4.2. Satisfied.

## Deployment Task 1 — Neon Database URL Compatibility (2026-11-16)
- **What was done:**
  - Added `normalize_database_url()` in `backend/app/config.py` and wired it via a Pydantic `@field_validator("database_url", mode="before")` on `Settings` so `get_settings().database_url` and `app/db.py` always use a normalized `postgresql+asyncpg://` URL.
  - Updated `get_database_url()` in `backend/alembic/env.py` to call `normalize_database_url()` (single shared helper, zero duplicated logic).
  - Normalization converts `postgres://` and `postgresql://` to `postgresql+asyncpg://`, translates `sslmode=...` to `ssl=...` (when `ssl` is not already set), removes `channel_binding` (unsupported by `asyncpg 0.32.0`), preserves other query parameters, and raises `ValueError` without exposing credentials on invalid schemes or missing hosts.
  - Added 12 unit tests in `backend/tests/test_config.py` verifying all URL formats, `PGDialect_asyncpg.create_connect_args()` compatibility against `inspect.signature(asyncpg.connect)`, credential non-leakage, and `Settings` normalization.
- **Verification & Testing (Actual Results):**
  - `uv run --directory backend --extra dev pytest tests/test_config.py`: 12 passed in 0.16s.
  - `uv run --directory backend --extra dev pytest --cov=app.engine --cov-branch --cov-fail-under=90 --cov-report=term-missing`: 265 passed (96.78% engine branch coverage).
  - `uv run --directory backend --extra dev mypy app`: Success: no issues found in 28 source files.
  - `uv run --directory backend --extra dev ruff check .`: All checks passed.
  - `uv run --directory backend --extra dev ruff format --check .`: 58 files already formatted.
  - `git diff --check`: Clean (0 whitespace/formatting errors).

## Deployment Task 2 — Render Development Blueprint (`render.yaml`) (2026-11-16)
- **What was done:**
  - Verified CI run `43903299964` (`fix(config): normalize Neon PostgreSQL URLs`) completed with `success`.
  - Added `render.yaml` for the **development environment only**:
    - `cardpilot-api-dev` (Python web service, `plan: free`, `rootDir: backend`, `buildCommand: pip install --upgrade pip && pip install .`, `startCommand: alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT` — migrations execute at service startup because Render's free plan does not support `preDeployCommand`, `healthCheckPath: /healthz`, `autoDeploy: false`, `ENVIRONMENT=development`, `LOG_LEVEL=INFO`, `CORS_ORIGINS=https://cardpilot-web-dev.onrender.com`, `DATABASE_URL` with `sync: false`).
    - `cardpilot-web-dev` (Static site, `rootDir: frontend`, `buildCommand: npm ci && npm run build`, `staticPublishPath: dist`, `autoDeploy: false`, `VITE_API_BASE_URL=https://cardpilot-api-dev.onrender.com/api/v1`, SPA rewrite `/* -> /index.html`).
- **Validation:**
  - Parsed `render.yaml` with `yaml.safe_load` cleanly.
  - `git diff --check`: Clean.

## Deployment Task 3 — Frontend Health Check Base URL Fix (2026-11-16)
- **What was done:**
  - Added `frontend/src/vite-env.d.ts` (`/// <reference types="vite/client" />`) for strict TypeScript `import.meta.env` typing.
  - Updated `frontend/src/components/BackendStatus.tsx` with `getHealthUrl()` to derive `<origin>/healthz` from `import.meta.env.VITE_API_BASE_URL` (stripping trailing `/api/v1` with or without trailing slash), falling back to relative `/healthz` when unset so local Vite proxy continues to work.
  - Added unit tests in `frontend/src/App.test.tsx` covering unset env var, configured `VITE_API_BASE_URL`, trailing slash handling, and `BackendStatus` fetch target.
- **Validation:**
  - `npm --prefix frontend run lint`: Clean.
  - `npm --prefix frontend run build`: Clean (`tsc && vite build`).
  - `npm --prefix frontend test`: Passed.

## Deployment Task 4B/4C — Development CI/CD Automation & Render API Verification (2026-11-16)
- **What was done:**
  - Added `.github/workflows/deploy.yml` triggered by `workflow_run` on `CI` (`completed`), running `deploy-dev` only when `conclusion == 'success'`, `head_branch == 'main'`, and `event == 'push'`.
  - Scoped `deploy-dev` to GitHub Environment `development` with `permissions: contents: read` and `concurrency: deploy-development` (`cancel-in-progress: false`).
  - Triggers `RENDER_DEV_API_DEPLOY_HOOK` and `RENDER_DEV_WEB_DEPLOY_HOOK` without exposing hook URLs/tokens, captures each new `deploy.id` (including `202` fallback), and polls Render's `GET /v1/services/{serviceId}/deploys/{deployId}` endpoint using `RENDER_API_KEY` (10-minute bounded timeout, with bounded retries/backoff for transient 429/5xx/`URLError`/malformed-JSON responses and immediate failure on permanent 4xx errors) until both deployments reach `live`, failing immediately on terminal failure states (`build_failed`, `update_failed`, `pre_deploy_failed`, `canceled`, `deactivated`).
  - After both deployments are confirmed `live`, runs a 180s bounded smoke test verifying `/healthz` (`status == "ok"`), `/readyz` (`status == "ready"` and `database == "connected"`), and `https://cardpilot-web-dev.onrender.com/` (HTTP 200).
- **Validation:**
  - Parsed `.github/workflows/deploy.yml` with `yaml.safe_load` cleanly.
  - `git diff --check`: Clean.

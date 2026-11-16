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
  - `pytest`, `ruff`, `mypy` pass locally. Satisfied.

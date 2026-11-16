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
- **Branch:** `feat/t01-repo-foundation`
- **Scope:** Initialize `.gitignore`, `.editorconfig`, `.env.example`, README stub, `docs/decisions/`, and `docs/dev-log.md`.
- **Implementation Details:**
  - Created `.gitignore` covering Python/virtual environments, testing caches (pytest, mypy, ruff, coverage), Node/Vite build artifacts, environment files, local volumes, and OS/editor metadata.
  - Created `.editorconfig` enforcing UTF-8, LF line endings, trailing whitespace trimming, final newline insertion, 4-space indentation for Python, 2-space for JS/TS/JSON/YAML/Markdown, and tabs for Makefiles.
  - Created `.env.example` documenting all configuration keys for backend, database, frontend, and local observability, with strict warnings against real credentials.
  - Updated `README.md` with project overview, fictional data disclaimer, architecture summary, tech stack, documentation index, and status.
  - Initialized `docs/decisions/` directory with `README.md` and `0000-use-architecture-decision-records.md`.
  - Initialized `docs/dev-log.md` to track project progress.
- **Human Decisions vs. AI Work:**
  - **Human Decided:** Approved T01 scope and feature branch creation.
  - **AI Executed:** Created configuration and documentation files matching specification and architecture standards.
- **Verification & Testing:**
  - Verified no secret patterns, API keys, or private credentials exist in files.
  - Verified `.gitignore` prevents tracking `.env` while preserving `.env.example`.
  - Verified newline endings and formatting match `.editorconfig` rules.
- **Acceptance Criteria [Done when]:**
  - Clean repository with foundation files configured and verified; no secrets committed.


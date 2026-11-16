# Implementer Role — CardPilot

The **Implementer** agent is responsible for executing exactly one backlog task at a time, writing production-grade code and automated tests, verifying quality locally, and presenting honest results for review.

---

## 1. Responsibilities & Scope

- **Task Execution:** Implement one task from `BACKLOG.md` adhering to its exact "Done when" acceptance criteria.
- **Test-First Development:** Write failing tests before writing application code for all calculation engine and business rule logic.
- **Small Reviewable Diffs:** Focus code changes strictly on the active task; avoid touching unrelated files.
- **Local Quality Verification:** Actually run and verify:
  - Backend: `python -m pytest backend`, `python -m ruff check backend`, `python -m ruff format --check backend`, `python -m mypy backend`.
  - Frontend: `npm test`, `npm run lint`, `npm run build`.
- **Documentation:** Record factual work completed, human decisions versus AI actions, and actual test outputs in `docs/dev-log.md`.
- **Commit Preparation:** Formulate clear Conventional Commit messages (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).

---

## 2. Required Inputs

1. Active task entry from `BACKLOG.md` and associated plan from the Planner.
2. `AGENTS.md` — Core rules, coding conventions, and Git workflow.
3. `SPEC.md` — Requirements and acceptance criteria for the feature.
4. `ARCHITECTURE.md` — Layered architecture guidelines and API schemas.
5. Existing codebase in `backend/app/` and `frontend/src/`.

---

## 3. Explicit Limitations ("Must Not")

- **Must NOT implement multiple backlog tasks at once.**
- **Must NOT expand scope** or add "nice-to-have" features beyond the active task.
- **Must NOT change the technology stack or add major dependencies** without explaining the reason and obtaining human approval first.
- **Must NOT fabricate test results or command outputs**—never state a test passed unless run and observed directly.
- **Must NOT weaken, comment out, or delete existing tests** to force a suite to pass.
- **Must NOT introduce floats for money or reward quantities**—always use integer cents and `Decimal`.
- **Must NOT introduce I/O, database access, network calls, or system clocks into `backend/app/engine/`.**
- **Must NOT commit or push automatically** without presenting changes and obtaining human approval.

---

## 4. Project-Specific Engineering Conventions

- **Backend (FastAPI, SQLAlchemy 2.0, Pydantic v2):**
  - Dependency direction: `api → services → engine/models`.
  - Routers remain thin: validate request schema, call service, return response schema.
  - Strict typing: `mypy --strict` on `app/engine/`, standard mypy elsewhere.
  - RFC 9457 Problem Details for all HTTP errors.
  - Queries must be scoped by `profile_id`.
  - All database schema updates must be managed via Alembic migrations.
- **Frontend (React 18, TypeScript strict, Vite):**
  - No `any` types; use `unknown` with type narrowing.
  - No reward calculation logic in the browser—render API responses and engine trace explanations.
  - Money formatting exclusively via integer cents helpers (`formatCentsToUsd`).
  - Accessible HTML: proper labels, keyboard navigation, and semantic roles.

---

## 5. Expected Handoff Format

Handoffs from the Implementer must follow this structure:

```markdown
### Task Implementation Report: [Task ID] — [Task Title]

1. **What Was Implemented:**
   - Summary of features and behaviors added
2. **Files Created & Modified:**
   - [List of files with paths]
3. **Commands Executed & Actual Results:**
   - [pytest output]
   - [ruff / mypy outputs]
   - [npm test / lint / build outputs]
4. **Acceptance Criteria Verification:**
   - [AC-1: Satisfied / Details]
5. **Proposed Conventional Commit Message:**
   - [feat/fix/etc. message with bulleted summary]
```

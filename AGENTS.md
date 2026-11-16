# AGENTS.md — CardPilot project rules

Read this file, `SPEC.md`, `ARCHITECTURE.md`, and `BACKLOG.md` before changing anything. If instructions conflict, the order of precedence is: human's latest instruction → this file → SPEC → ARCHITECTURE → BACKLOG.

## 1. What this project is
CardPilot is a **demo** credit card rewards optimizer for a course final project: deterministic, explainable, fictional data. Priority: complete, reliable, tested, publicly deployed. **Do not over-engineer.**

## 2. Hard rules (never violate)
1. **Fictional data only.** Fictional issuers, card names, profiles, merchants. No real issuer names in seed data unless a human approves.
2. **No sensitive data.** Never add fields/code for card numbers, CVV, bank credentials, SSNs. No bank/Plaid/issuer integrations.
3. **Never claim sample rules are current issuer terms.** Every rule has a source, effective dates, last-reviewed date; UI shows a disclaimer.
4. **Reward currencies stay separate.** Never add or rank raw units across currencies. Cross-currency comparison happens only via user-configured valuations; otherwise "unranked" + limitation message.
5. **Deterministic engine.** Reward math lives in `backend/app/engine/`, which is pure: no DB, network, clock, randomness, or logging side effects. Pass dates in.
6. **No floats for money or rewards.** Use integer cents and `Decimal`. Serialize decimals as strings.
7. **History is immutable.** Never mutate a rule version that a calculation references; create a new version. Never recompute stored snapshots.
8. **No LLM or external AI service inside the application.**
9. **No stack changes, new major dependencies, or architecture changes without asking first** (explain reason and trade-offs).
10. **Do not fabricate.** Never claim a test passed, a command succeeded, or a feature works unless you ran it and saw the output. Report failures plainly.
11. **No deployment** until the app works locally and the human approves (Gate G5).
12. **No secrets in the repo**, logs, or screenshots. Use `.env` (gitignored) and `.env.example`.

## 3. Working process
- Work **one backlog task at a time**, in order. Reference the task id in commits/PRs (`T14: cap straddle`).
- **Test first** for engine and business rules: write the failing test, then the code.
- Small, reviewable diffs. Don't refactor unrelated code in a task.
- Before marking a task done: run the relevant lint, typecheck, and tests; paste real results in the PR/dev-log.
- Update `docs/dev-log.md` after each phase: what was done, what AI did vs. human decided, problems found.
- Record non-obvious decisions as short ADRs in `docs/decisions/NNNN-title.md`.
- Stop and ask when: requirements are ambiguous in a way that changes behavior, a task needs a new dependency, a gate is reached, or something in SPEC appears wrong.

## 4. Roles / subagents (Claude Code)
Use focused roles; each may be a `.claude/agents/*.md` subagent. A role should stay inside its scope.

| Role | Scope | Must not |
|---|---|---|
| **Planner** | Refine SPEC/BACKLOG, clarify acceptance criteria, propose tasks | Write app code |
| **Implementer** | Implement one backlog task with tests | Expand scope, change stack, edit specs silently |
| **QA** | Review diffs against ACs, write/extend tests, run suites, hunt edge cases (dates, caps, rounding) | Fix by weakening tests |
| **Security reviewer** | Check data-handling rules, validation, headers/CORS, dependencies, secrets, log content | Add features |

Handoffs are written (PR description or dev-log), not assumed.

## 5. Conventions

### Backend (Python 3.12, FastAPI, Pydantic v2)
- Layout per ARCHITECTURE §6. Dependency direction `api → services → engine/models`.
- Type hints everywhere; `mypy --strict` on `engine/`, standard mypy elsewhere. `ruff` for lint + format.
- Routers are thin: validate, call a service, return a schema. No business logic in routers.
- SQLAlchemy 2.0 style; every schema change via Alembic migration (never edit applied migrations; add new ones).
- Queries are always scoped by `profile_id`.
- Errors: problem-details JSON; no stack traces to clients.
- Naming: `snake_case` functions/modules, `PascalCase` classes, UTC timestamps, dates as ISO 8601.
- Seeds: YAML in `seeds/data/`, idempotent upserts by stable keys. Every rule carries `source`, `effective_from`, `last_reviewed_on`.

### Frontend (React, TypeScript strict, Vite)
- Function components + hooks. No `any` (use `unknown` + narrowing).
- API types are **generated** from `docs/openapi.json`; never hand-write duplicates.
- No reward math in the browser; render API results and explanation text.
- Show amounts via a single formatting helper that takes cents/strings (no float arithmetic on money).
- Accessible by default: labels, keyboard focus, semantic HTML, no color-only meaning.
- Every page handles loading, empty, and error states.

### Testing
- Backend: Pytest; engine tests table-driven; API tests use real Postgres.
- Frontend: Vitest + React Testing Library (query by role/label).
- E2E: Playwright, deterministic data via the reset endpoint.
- A bug fix includes a regression test.

### Git
- Branch per task or phase; conventional-style messages (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
- `main` stays green. No force-push to `main`.

## 6. Commands (to be finalized in T04; do not assume they exist until then)
```
make dev        # docker compose up
make test       # backend + frontend tests
make lint       # ruff, mypy, eslint, tsc
make openapi    # regenerate docs/openapi.json and frontend types
make seed       # load fictional seed data
make e2e        # Playwright
```

## 7. Definition of done (per task)
- [ ] Behavior matches the task's "Done when" and relevant ACs
- [ ] Tests added/updated and **actually run**; results reported honestly
- [ ] Lint + typecheck clean
- [ ] No hard-rule violations (section 2)
- [ ] Docs/ADR/dev-log updated if behavior or decisions changed
- [ ] OpenAPI + generated types updated if the API changed

## 8. Domain glossary
- **Reward currency**: unit earned (e.g., cash back USD, bank points, airline miles).
- **Multiplier**: reward units per $1 of eligible spend.
- **Valuation**: user's estimated cents-per-unit for a currency; used only for comparison/estimates.
- **Rule version**: immutable row for a rule_key with effective dates; superseded by a newer version.
- **Snapshot**: stored calculation result + trace for a transaction.
- **Unranked**: eligible card that can't be compared in dollars because no valuation exists.

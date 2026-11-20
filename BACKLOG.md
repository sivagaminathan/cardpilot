# CardPilot — Backlog

Status: **Draft v0.1 — nothing started.** Implementation begins only after human approval of SPEC/ARCHITECTURE/this backlog.

Conventions
- Tasks are small (≈ ≤ 2 hours / one PR). Do them **in order**; dependencies are noted when not the previous task.
- Each task: **Done when** = observable, verifiable outcome. A task is not done until its tests were actually run and passed.
- `[AC-n]` / `[FR-n]` reference SPEC.md.
- Gate = a human checkpoint before continuing.

---

## Phase 0 — Planning (this task)
- [x] SPEC.md, ARCHITECTURE.md, BACKLOG.md, AGENTS.md drafted
- [ ] **Gate G0:** human approves docs and answers open decisions (D-1 … D-10)

## Phase 1 — Foundation (repo, tooling, "hello" end-to-end)
- [x] **T01** Init git repo, `.gitignore`, `.editorconfig`, `.env.example`, README stub, `docs/decisions/` and `docs/dev-log.md`. *Done when:* clean repo with first commit; no secrets.
- [x] **T02** Backend skeleton: `pyproject.toml`, FastAPI app, `/healthz`, config via env, ruff + mypy config, one pytest. *Done when:* `pytest`, `ruff`, `mypy` pass locally.
- [x] **T03** Frontend skeleton: Vite + React + TS strict, ESLint/Prettier, Vitest + RTL with one test. *Done when:* `npm test`, `npm run lint`, `npm run build` pass.
- [x] **T04** Docker Compose: `db` + `api` + `web`; `.env` wiring; Makefile targets. *Done when:* `docker compose up` serves web, which calls `/healthz` successfully.
- [x] **T05** SQLAlchemy + Alembic wired to Postgres; `/readyz` checks DB; empty initial migration. *Done when:* `alembic upgrade head` on empty DB works; readiness test passes against real Postgres.
- [x] **T06** CI v1: GitHub Actions for backend (Postgres service) and frontend lint/typecheck/test/build. *Done when:* both jobs green on a PR.
- [x] **T07** Create `.claude/agents/` role files (planner, implementer, qa, security) derived from AGENTS.md. *Done when:* files committed; roles' scope/limits stated.
- [ ] **Gate G1:** human reviews skeleton + CI before domain work.

## Phase 2 — Reward engine (pure Python, test-first) [AC-2…AC-9, AC-13]
- [x] **T08** Engine types: `Purchase`, `Rule`, `Cap`, `SpendHistory`, `Valuation`, `CardEvaluation`, trace step types (frozen dataclasses/Pydantic). *Done when:* mypy strict passes; no `float` in package (test greps).
- [x] **T09** Effective-date filter + tests (inclusive boundaries, none effective ⇒ ineligible). [AC-6]
- [x] **T10** Applicability: scope match + exclusions (category/merchant/tag) with rejection reasons. [AC-4]
- [x] **T11** Selection by specificity → priority → id; tie determinism. [AC-3, AC-13]
- [x] **T12** Per-transaction minimum threshold. [AC-7]
- [x] **T13** Period utilities: monthly, quarterly, calendar year, card-year boundaries. *Done when:* table tests incl. leap day and year-end.
- [x] **T14** Cap handling incl. straddle and fallback to base. [AC-5]
- [x] **T15** Period-spend threshold (no retroactivity).
- [x] **T16** Units + rounding modes (floor/nearest/none) with Decimal. *Done when:* tests for each mode and half cases.
- [x] **T17** Valuation → estimated value; no-valuation routing. [AC-2]
- [x] **T18** Cross-card ranking: ranked / unranked / ineligible, tie-break, global notes. [AC-2, AC-10]
- [x] **T19** Explanation renderer (trace → sentences) with golden-text tests.
- [x] **T20** Engine golden fixtures (JSON): ≥15 scenarios incl. all ACs; coverage ≥ 90% branch reported by CI.
- [ ] **Gate G2:** human reviews engine behavior against fixtures (sample rules/limitations confirmed).

## Phase 3 — Data model, seeds, API [AC-1, AC-8, AC-11, AC-12, AC-14]
- [x] **T21** Migrations + ORM for reference tables (currencies, categories, merchants, products, sources).
- [x] **T22** Migrations + ORM for rules, exclusions, caps (+ non-overlap constraint or loader check; immutability guard).
- [x] **T23** Migrations + ORM for profiles, profile_cards, valuations, transactions, calcs, benefits, usages.
- [x] **T24** Seed data files: ≥6 fictional products, currencies, categories, merchants, sources, rules (include one superseded rule version, one capped rule, one exclusion, one threshold). *Done when:* data review against SPEC §4.2 checklist; every rule has source + last-reviewed date and is labeled fictional.
- [x] **T25** Idempotent seed loader + demo profiles (≥2) + `POST /profiles/{id}/reset`. [AC-1]
- [x] **T26** Reference + profile + cards endpoints with schemas and tests.
- [x] **T27** Valuations endpoints (validation range, `is_user_set`).
- [x] **T28** Service layer: assemble engine inputs from DB (rules, caps, spend history). *Done when:* integration test matches engine fixtures through the DB.
- [x] **T29** `POST /recommendations` endpoint + tests (all key ACs through HTTP). [AC-2…AC-7, AC-9, AC-13]
- [x] **T30** Sensitive-data guard (13–19 digit sequences) shared validator. [AC-12]
- [x] **T31** Transactions endpoints with snapshot persistence. [AC-8]
- [ ] **T32** History-preservation test: load rule v2, assert old snapshot unchanged, new calc differs. [AC-8]
- [ ] **T33** Benefits: period math + status + usage endpoints. [AC-11]
- [ ] **T34** Rewards summary endpoint (per-currency units; separate estimated USD). [AC-10]
- [ ] **T35** Error format (problem details), CORS, security headers, rate limit on mutations.
- [ ] **T36** OpenAPI 3.1 export script + CI diff check; TS type generation script. [AC-14]
- [ ] **Gate G3:** human demo of API via Swagger UI/curl; confirm contract before UI.

## Phase 4 — Frontend [FR-1…FR-31, AC-17]
- [ ] **T37** API client + generated types + app shell, router, layout, disclaimer banner, profile picker.
- [ ] **T38** Dashboard: cards list + benefit alerts + rewards snapshot.
- [ ] **T39** Cards page: add/remove from catalog; rules viewer with sources/dates/staleness flag.
- [ ] **T40** Compare page: form, ranked/unranked/ineligible rendering, explanation expand/collapse, warnings.
- [ ] **T41** Settings: valuations editor with "illustrative default" labels.
- [ ] **T42** Transactions page: create/list/filter/delete with reward result display.
- [ ] **T43** Benefits page: status, usage logging, reset dates.
- [ ] **T44** Rewards page: per-currency table + estimated value section (clearly separated).
- [ ] **T45** Empty/loading/error states; accessibility pass (labels, focus, contrast); component tests for each page's main flow.
- [ ] **Gate G4:** human walks through J1–J7 locally.

## Phase 5 — E2E and quality hardening
- [ ] **T46** Playwright setup + deterministic reset-before-test fixture.
- [ ] **T47** E2E specs: compare (ranked+unranked), add transaction → summary, valuation change → reorder, benefit usage.
- [ ] **T48** CI e2e job + trace artifacts; security job (pip-audit, npm audit, gitleaks).
- [ ] **T49** QA review pass: re-run ACs checklist; fix gaps; log results (actual) in `docs/dev-log.md`.
- [ ] **T50** Security review pass (subagent): headers, validation, CORS, dependency audit, secrets, logging of free text.
- [ ] **Gate G5:** all CI green on `main`; human approves starting deployment.

## Phase 6 — Local observability
- [ ] **T51** Structured JSON logging with request id; Prometheus metrics endpoint.
- [ ] **T52** OTel instrumentation (FastAPI, SQLAlchemy) + custom engine/recommendation spans.
- [ ] **T53** Compose `observability` profile: Collector, Prometheus, Loki, Tempo, Grafana with provisioning.
- [ ] **T54** Grafana dashboard JSON committed; README screenshots from a real run.

## Phase 7 — Deployment (only after Gate G5)
- [ ] **T55** Verify current Render/Neon constraints; record in ADR; adjust plan if needed (ask first if stack changes).
- [ ] **T56** Production config: env vars, CORS, pooled DB URL, migration-on-deploy, seed-on-first-deploy.
- [ ] **T57** Deploy backend + DB; verify `/healthz`, `/readyz`, one recommendation via curl.
- [ ] **T58** Deploy frontend; wire API URL; verify J1–J3 manually.
- [ ] **T59** CD workflow + post-deploy smoke test (with warm-up for cold start).
- [ ] **T60** Decide/implement deployed telemetry level per D-5.

## Phase 8 — Finish
- [ ] **T61** README: overview, architecture diagram, run/test/deploy instructions, limitations, disclaimer, AI-process summary.
- [ ] **T62** Final acceptance run: every AC marked pass/fail with evidence links.
- [ ] **T63** Demo script (≈5 min) and tagged release.

## Stretch (only if all above complete)
Rule editor UI · refunds · cap groups across cards · optional additive bonuses · CSV export · dark mode.

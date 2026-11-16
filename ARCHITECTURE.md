# CardPilot — Architecture

Status: **Draft v0.1 — awaiting human approval** (2026-11-15)
Principle: simplest thing that is correct, testable, and deployable. A **pure reward engine** is the heart; everything else is plumbing around it.

---

## 1. Component architecture

```
 Browser (React + TS + Vite SPA)
     │  HTTPS, JSON, types generated from OpenAPI
     ▼
 FastAPI app (Python)
  ├─ api/        routers + Pydantic schemas (thin; validation + HTTP only)
  ├─ services/   use cases: load rules/caps from DB → call engine → persist
  ├─ engine/     PURE reward engine (no DB, no clock, no I/O)   ◄── most tests live here
  ├─ models/     SQLAlchemy ORM
  ├─ seeds/      idempotent loader for fictional data (YAML/JSON → DB)
  └─ telemetry/  OTel setup, structured logging, Prometheus metrics
     │  SQLAlchemy + Alembic
     ▼
 PostgreSQL (Docker locally, Neon when deployed)

 Local-only observability: OTel Collector → Tempo (traces), Loki (logs), Prometheus (metrics) → Grafana
```

**Dependency rule:** `api → services → (engine, models)`. `engine` imports nothing from the app. The frontend never reimplements reward math; it renders what the API returns (including the explanation trace).

**Frontend structure (simple):** React Router pages (Dashboard, Cards, Compare, Transactions, Benefits, Rewards, Settings/Valuations, Rules), a typed API client, TanStack Query for fetching/caching (see decision D-8), plain CSS modules or a small CSS approach (no UI framework unless approved).

**Auth model (MVP):** no authentication. The user picks a seeded demo profile; requests carry `profile_id` in the URL path (`/profiles/{id}/...`). All queries are scoped by `profile_id`. Acceptable because all data is fictional; see risk R-6.

## 2. Database design

All money is **integer cents**. Reward units and valuations are `NUMERIC` (never float). Dates are `DATE`; timestamps `TIMESTAMPTZ` (UTC).

### 2.1 Entities

**Reference / catalog data (seeded, read-only in MVP)**

| Table | Key columns |
|---|---|
| `reward_currencies` | `id`, `code` (e.g. `NWT_PTS`), `name`, `kind` (`cash_back` \| `points` \| `miles`), `is_cash_equivalent` bool, `default_cents_per_unit` NUMERIC(8,4) (illustrative) |
| `categories` | `id`, `code` (`dining`, `groceries`, `gas`, `travel`, `streaming`, `online_retail`, `utilities`, `other` …), `name` |
| `merchants` | `id`, `name`, `default_category_id`, `tags` (e.g. `warehouse_club`, `big_box`) |
| `card_products` | `id`, `issuer_name` (fictional), `name`, `reward_currency_id`, `annual_fee_cents`, `network_label` (display only), `description` |
| `rule_sources` | `id`, `title`, `kind` (`fictional_sample` \| `public_doc_example`), `url` NULL, `notes`, `last_reviewed_on` DATE |
| `earning_rules` | see 2.2 |
| `rule_exclusions` | `id`, `rule_id`, `exclusion_type` (`category` \| `merchant` \| `merchant_tag`), `target_id/tag`, `reason` |
| `spend_caps` | `id`, `cap_group_key`, `card_product_id`, `cap_amount_cents`, `period` (`monthly` \| `quarterly` \| `calendar_year` \| `card_year`) |
| `benefit_definitions` | `id`, `card_product_id`, `name`, `benefit_type` (`credit` \| `allowance` \| `perk`), `value_cents` NULL, `reset_period`, `notes`, `source_id`, `effective_from`, `effective_to` |

**User/profile data (mutable)**

| Table | Key columns |
|---|---|
| `profiles` | `id`, `slug`, `display_name`, `is_demo` bool, `seed_key` |
| `profile_cards` | `id`, `profile_id`, `card_product_id`, `nickname`, `opened_on`, `is_active` |
| `currency_valuations` | `profile_id`, `reward_currency_id`, `cents_per_unit` NUMERIC(8,4), `is_user_set` bool, `updated_at` — PK `(profile_id, reward_currency_id)` |
| `transactions` | `id`, `profile_id`, `profile_card_id`, `amount_cents` (>0), `category_id`, `merchant_id` NULL, `merchant_text` NULL, `occurred_on`, `note`, `created_at` |
| `transaction_reward_calcs` | `id`, `transaction_id` UNIQUE, `engine_version`, `reward_currency_id`, `reward_units` NUMERIC(14,4), `valuation_cents_per_unit_used` NULL, `estimated_value_cents` NULL, `trace` JSONB (full explanation + rule ids/versions + cap parts), `created_at` — **immutable** |
| `benefit_usages` | `id`, `profile_card_id`, `benefit_definition_id`, `amount_cents` NULL, `used_on`, `note` |

### 2.2 `earning_rules` (versioned, immutable once referenced)

| Column | Notes |
|---|---|
| `id` | PK (this *version's* id; referenced by snapshots) |
| `rule_key` | stable logical id, e.g. `nwcash.dining` |
| `version` | int, unique with `rule_key` |
| `card_product_id`, `reward_currency_id` | |
| `scope_type` | `base` \| `category` \| `merchant` |
| `category_id` / `merchant_id` | per scope |
| `multiplier` | NUMERIC(8,4) units per $1 |
| `priority` | int tie-break (default 0) |
| `cap_id` NULL, `post_cap_behavior` | `fallback_to_base` (MVP only) |
| `min_transaction_cents` NULL | per-transaction threshold |
| `min_period_spend_cents` NULL, `threshold_period` | "applies once period spend ≥ X," evaluated on spend *before* this transaction (no retroactivity) |
| `rounding` | `floor_units` (default) \| `nearest_unit` \| `none_4dp` |
| `effective_from` DATE, `effective_to` DATE NULL | inclusive range |
| `source_id` FK, `last_reviewed_on` DATE | |
| `supersedes_id` NULL | link to previous version |

Constraints: `CHECK(effective_to IS NULL OR effective_to >= effective_from)`; no overlapping effective ranges for the same `rule_key` (exclusion constraint on `daterange`, requires `btree_gist`, available on Neon; otherwise enforced in the seed loader + test). A DB trigger or service guard rejects `UPDATE`s to semantic columns once a calc references the rule.

### 2.3 Key indexes
`transactions(profile_id, occurred_on)`, `transactions(profile_card_id, occurred_on)`, `earning_rules(card_product_id, effective_from)`, `benefit_usages(profile_card_id, benefit_definition_id, used_on)`.

### 2.4 Migrations & seeds
Alembic owns schema. Seed data lives as YAML in `backend/app/seeds/data/`, loaded by an **idempotent** upsert keyed on stable keys (`seed_key`, `rule_key+version`). "Reset demo data" deletes a demo profile's mutable rows and re-applies its seed.

## 3. API design

REST, JSON, prefix `/api/v1`. FastAPI generates OpenAPI 3.1; the file is committed at `docs/openapi.json` and checked in CI. Errors use RFC 9457-style problem details (`type`, `title`, `status`, `detail`, `errors[]`).

| Area | Endpoints |
|---|---|
| Meta | `GET /healthz`, `GET /readyz`, `GET /metrics` (unversioned) |
| Reference | `GET /categories`, `GET /merchants`, `GET /reward-currencies`, `GET /card-products`, `GET /card-products/{id}/rules`, `GET /card-products/{id}/benefits` |
| Profiles | `GET /profiles`, `GET /profiles/{pid}`, `POST /profiles/{pid}/reset` |
| Cards | `GET/POST /profiles/{pid}/cards`, `PATCH/DELETE /profiles/{pid}/cards/{cid}` |
| Valuations | `GET /profiles/{pid}/valuations`, `PUT /profiles/{pid}/valuations/{currency_id}` |
| Recommend | `POST /profiles/{pid}/recommendations` |
| Transactions | `GET/POST /profiles/{pid}/transactions`, `DELETE /profiles/{pid}/transactions/{tid}` |
| Benefits | `GET /profiles/{pid}/benefits` (status per card), `POST /profiles/{pid}/benefits/{bid}/usages`, `DELETE …/usages/{uid}` |
| Rewards | `GET /profiles/{pid}/rewards/summary` |

### 3.1 Recommendation contract (sketch)

Request:
```json
{ "amount_cents": 10000, "category_code": "dining", "merchant_id": null,
  "purchase_date": "2026-11-15", "profile_card_ids": null }
```
Response (abridged):
```json
{
  "request_echo": { "...": "..." },
  "ranked": [
    { "rank": 1, "profile_card_id": 3, "reward_currency": "NW_CASH",
      "reward_units": "3.00", "estimated_value_cents": 300,
      "valuation": { "cents_per_unit": "1.0000", "source": "user_set" },
      "applied": [ { "portion_cents": 10000, "rule_id": 12, "rule_key": "nwcash.dining",
                     "rule_version": 1, "multiplier": "3.0" } ],
      "explanation": ["Matched category rule 'Dining 3×' (v1, effective 2026-01-01…).", "…"],
      "warnings": [] }
  ],
  "unranked": [
    { "profile_card_id": 5, "reward_currency": "SKY_MILES", "reward_units": "4.00",
      "reason": "no_valuation", "message": "No estimated value is set for Skyward Miles, so this card cannot be reliably compared in dollars. Set a valuation in Settings." }
  ],
  "ineligible": [ { "profile_card_id": 7, "reason": "no_effective_rule", "message": "…" } ],
  "global_notes": ["Annual fees and benefit credits are not included in this comparison."],
  "engine_version": "1.0.0"
}
```
Decimals are serialized as strings to avoid float drift.

## 4. Reward calculation design

### 4.1 Engine interface

```python
def evaluate_purchase(
    purchase: Purchase,            # amount_cents, category, merchant(+tags), date
    card: CardContext,             # product, currency, rules (all versions), caps
    spend_history: SpendHistory,   # prior spend per cap_group / threshold period as of purchase.date
    valuation: Valuation | None,   # cents_per_unit for card's currency, or None
) -> CardEvaluation                # pure; no I/O; same input ⇒ same output
```
`services/` assembles inputs from the DB; `engine/` does only math and explanation.

### 4.2 Algorithm (per card)

1. **Effective filter.** Keep rule versions with `effective_from ≤ date ≤ effective_to|∞`. None ⇒ `ineligible: no_effective_rule`.
2. **Applicability filter.** Drop rules whose scope does not match (category/merchant), that are excluded (exclusion by category, merchant, or merchant tag — record *why*), or that fail `min_transaction_cents`, or whose period-spend threshold is not met. Record each rejection reason in the trace.
3. **Selection.** Sort remaining by specificity (merchant=3, category=2, base=1), then `priority` desc, then `rule_id` asc. First wins. If none (no base rule), `ineligible: no_applicable_rule`.
4. **Cap handling.** If the winner has a cap: `remaining = max(0, cap − spend_in_current_period(cap_group))`. Portion at the rule's rate = `min(amount, remaining)`; the remainder is re-run through steps 2–3 **excluding capped rules whose cap is exhausted** (falls to next best, normally base). Result is a list of `applied` parts.
5. **Units.** Per part: `units = (portion_cents / 100) × multiplier` as `Decimal`. Sum parts, then apply the rule's `rounding` **once per transaction** on the sum (documented; avoids per-part rounding artifacts).
6. **Valuation.** If valuation present: `estimated_value_cents = round_half_even(units × cents_per_unit)`. Else `None` and the card is routed to `unranked` with reason `no_valuation`.
7. **Trace.** Emit structured steps (rejections, selection, cap math, rounding, valuation) + rendered sentences.

### 4.3 Ranking (across cards)

- Rank only cards with `estimated_value_cents` not null, descending.
- Tie-break: higher `reward_units`, then card nickname asc; state "tied on estimated value" in the explanation.
- Cards whose currency has no valuation → `unranked` (never compared on raw multiplier).
- Cash-equivalent currencies default to 1.0¢/unit but remain user-editable; defaults carry a "illustrative default" warning until the user sets a value.
- If *all* cards are unranked, return an explicit limitation note.

### 4.4 Period boundaries
- `monthly`, `quarterly` (calendar quarters), `calendar_year`: derived from the purchase date.
- `card_year`: derived from `profile_cards.opened_on` anniversary.
- Period spend = sum of `amount_cents` of this profile's transactions on that card (or cap group across the product's cards, default per-card) within the period and **on/before** the purchase date (ties by creation order).

### 4.5 History preservation
- On `POST transactions`, service runs the engine and writes `transaction_reward_calcs` with full `trace`, `engine_version`, rule ids/versions, and the valuation used.
- Rule changes create **new rows**; old rows are never mutated after being referenced.
- Backdated or deleted transactions do **not** trigger recomputation of other snapshots (documented limitation; see decision D-6).
- Rewards summary sums `reward_units` from snapshots per currency; estimated value uses *current* valuations (labeled) and optionally shows the at-calculation value.

### 4.6 Rounding and precision
`Decimal` with explicit context, quantize with named rounding modes. Money: integer cents. No `float` in `engine/` (lint rule/test grep).

## 5. Testing strategy

| Layer | Tool | What |
|---|---|---|
| Engine unit | Pytest (+ Hypothesis optional, see D-9) | Table-driven cases mapped 1:1 to AC-2…AC-9: specificity, exclusions, cap straddle, thresholds, date boundaries (inclusive ends), rounding modes, no-valuation routing, determinism, no-float invariant |
| Service/API | Pytest + HTTPX `AsyncClient` against **real Postgres** (Compose locally; service container in CI) | Contract, validation (AC-12), history preservation (AC-8), benefits period math (AC-11), seed idempotency (AC-1), profile scoping |
| Schema/contract | CI script | Generated `openapi.json` matches committed; frontend types regenerate cleanly (AC-14) |
| Frontend unit/component | Vitest + React Testing Library | Forms, validation messages, ranked/unranked rendering, explanation display, valuation edit; API mocked at the client boundary (MSW only if approved) |
| E2E | Playwright (Chromium only) | (1) pick profile → compare → see ranked/unranked; (2) add transaction → rewards summary updates; (3) edit valuation → order changes; (4) log benefit usage |
| Static | ruff, mypy, ESLint, tsc, Prettier | CI gates |
| Security | `pip-audit`, `npm audit` (high+), secret scan (gitleaks), a QA/security review checklist per phase | CI + review |
| Smoke | curl/Playwright against deployed URL | AC-16 |

Rules: tests are written (or at least specified) **before** engine code for each rule type; no test result is reported unless it was executed; flaky tests are fixed or removed, not retried blindly.

## 6. Repository structure (proposed)

```
cardpilot/
├─ AGENTS.md  SPEC.md  ARCHITECTURE.md  BACKLOG.md  README.md
├─ docker-compose.yml          # db, api, web (+ observability profile)
├─ Makefile                    # dev, test, lint, openapi, seed shortcuts
├─ .env.example
├─ .github/workflows/          # ci.yml, deploy.yml (later)
├─ .claude/agents/             # planner.md, implementer.md, qa.md, security.md
├─ docs/
│  ├─ openapi.json
│  ├─ decisions/               # short ADRs
│  └─ dev-log.md               # AI-assisted process notes for the course
├─ backend/
│  ├─ pyproject.toml  alembic.ini
│  ├─ alembic/versions/
│  ├─ app/
│  │  ├─ main.py  config.py  db.py
│  │  ├─ api/{routes,deps.py,errors.py}
│  │  ├─ schemas/
│  │  ├─ models/
│  │  ├─ services/
│  │  ├─ engine/               # pure: types.py rules.py caps.py rank.py explain.py
│  │  ├─ seeds/{loader.py,data/*.yaml}
│  │  └─ telemetry/
│  └─ tests/{engine,api,fixtures}
├─ frontend/
│  ├─ package.json  vite.config.ts  tsconfig.json
│  └─ src/{api,pages,components,lib,test}
├─ e2e/{playwright.config.ts,tests/}
└─ observability/{otel-collector.yaml,prometheus.yml,loki.yaml,tempo.yaml,grafana/}
```

## 7. Local infrastructure

`docker-compose.yml` services: `db` (postgres:16), `api` (hot reload), `web` (Vite dev server); optional `--profile observability` adds OTel Collector, Prometheus, Loki, Tempo, Grafana with provisioned datasources and one dashboard. Makefile targets wrap common commands. `.env.example` only; real secrets never committed.

## 8. CI/CD

GitHub Actions, on PR and `main`:
1. **backend**: ruff, mypy, pytest (Postgres service container), coverage report, OpenAPI diff check.
2. **frontend**: eslint, tsc, vitest, build.
3. **e2e**: bring up stack, run Playwright; upload traces on failure.
4. **security**: pip-audit, npm audit, gitleaks.
5. **deploy** (Phase 6, only after local app passes): on `main` success, trigger Render deploy; run smoke test.

## 9. Deployment and observability approach

**Deployment (to be verified at implementation time — I could not confirm current free-tier terms from this environment):**
- Frontend: Render Static Site. Backend: Render Web Service (Docker or native Python). Database: Neon Postgres (pooled connection string; SSL required).
- Migrations run as a pre-deploy/release step; seed loader runs once and is idempotent.
- Config via env vars; CORS allowlist = frontend origin.
- Expect free-tier cold starts and possible resource limits; mitigate with a README note and a smoke-test warm-up.

**Observability:**
- **Always on (deployed and local):** structured JSON logs with request id, `/healthz`, `/readyz`, Prometheus-format `/metrics` (request count/latency, recommendation count, engine duration), OTel SDK instrumentation for FastAPI and SQLAlchemy.
- **Local (Compose profile):** full OTel Collector → Tempo/Loki/Prometheus → Grafana, with a provisioned dashboard (request rate/latency/errors, recommendation latency, DB time).
- **Deployed Grafana stack:** running Tempo+Loki+Prometheus+Grafana on free tiers is likely impractical. Default plan: demonstrate the full stack locally (screenshots/recorded demo in README) and use platform logs deployed; optionally point OTLP to a hosted Grafana Cloud free tier if approved (decision D-5).
- No PII exists, but logs still must not record request bodies for free-text fields.

## 10. Key design decisions (summary)

| # | Decision | Reason |
|---|---|---|
| A-1 | Pure engine separated from DB/HTTP | Testability, determinism, explainability |
| A-2 | Rules as immutable, versioned data with provenance | Satisfies history, effective-date, and source requirements |
| A-3 | Snapshot trace per transaction | Preserves history even if rules/valuations change |
| A-4 | Decimal/cents everywhere; strings in JSON | Avoids float errors |
| A-5 | No auth; profile-scoped routes | Fictional data; keeps scope appropriate |
| A-6 | Unranked bucket instead of forced comparison | Meets "don't rank by raw multiplier" requirement |
| A-7 | Rules edited via seed files, no editor UI in MVP | Saves time; editor is a stretch |

# CardPilot — Product Specification

Status: **Draft v0.1 — awaiting human approval** (2026-11-15)
Scope: course final project. Demo-friendly, deterministic, fictional data only.

---

## 1. Problem statement

People who hold several rewards credit cards struggle to answer three everyday questions:

1. *"Which card should I use for this purchase?"* Earning rates differ by category, merchant, caps, and date, and each card earns a different **reward currency** (cash back, bank points, airline miles), so raw multipliers are not comparable.
2. *"Am I using the benefits I'm paying for?"* Credits, allowances, and perks reset on different schedules and are easy to forget.
3. *"What have I actually earned?"* Rewards are scattered across issuers and currencies.

CardPilot is a demo application that organizes cards, recommends the best card for a purchase using **explainable, deterministic** math, tracks benefit usage, records transactions, and summarizes rewards per currency. It uses **fictional profiles and fictional card configurations only**.

## 2. Target users

| Persona | Description | Primary need |
|---|---|---|
| **Maya — the optimizer** | Holds 3–5 cards, enjoys maximizing value | Fast "best card for this purchase" with a clear explanation |
| **Dev — the forgetful benefit-payer** | Pays annual fees, forgets credits | See unused credits and what resets when |
| **Prof. Rivera — the course reviewer** | Evaluates the project | Public URL, seeded demo data, visible tests/CI, traceable engineering process |

Users are assumed to be adults comfortable with basic rewards concepts. No financial-advice claim is made.

## 3. User journeys

**J1 — Explore the demo.** Reviewer opens the public URL, picks a seeded demo profile, sees a dashboard with cards, upcoming benefit resets, and rewards totals per currency.

**J2 — Compare cards for a purchase.** User enters amount, category (and optionally a merchant), and date. CardPilot lists each card's eligibility, the rule applied, reward earned (in its own currency), estimated value using the user's valuations, and a plain-language explanation. Cards whose currencies cannot be reliably compared are shown separately with a stated limitation.

**J3 — Record a transaction.** User records a purchase on a chosen card. The system calculates and **snapshots** the reward (rule version, multiplier, cap effects, valuation) so later rule changes never alter it. Caps remaining are updated.

**J4 — Track benefits.** User views each card's benefits (credits, allowances, perks), logs usage against them, and sees remaining amount and reset date.

**J5 — Understand rewards.** User views earned rewards grouped by currency, with an estimated dollar value computed from their own valuation settings, shown separately from the raw balances.

**J6 — Adjust valuations.** User edits their estimated cents-per-unit for each reward currency and immediately sees recommendations and summaries change; historical snapshots remain unchanged.

**J7 — Inspect rule provenance.** User opens a card's rules and sees the source, effective dates, last-reviewed date, and a banner that these are sample rules, not current issuer terms.

## 4. Functional requirements

Priority: **M** = must (MVP), **S** = should, **C** = could (stretch).

### 4.1 Profiles and cards
- **FR-1 (M)** Provide ≥2 seeded fictional demo profiles; user selects one (no passwords, no real identity).
- **FR-2 (M)** Dashboard lists the profile's cards with nickname, product, reward currency, and status.
- **FR-3 (M)** User can add a card to their profile from the fictional catalog (≥6 products covering cash back, flexible points, airline miles, flat-rate, and category-specialist styles), and deactivate/remove it.
- **FR-4 (M)** The application never asks for card numbers, CVV, expiry, bank logins, or real names. Free-text fields carry a "do not enter real card data" hint and server-side rejection of 13–19 digit sequences (basic guard).

### 4.2 Reward rules
- **FR-5 (M)** Earning rules are data (seed files → DB), not code. Each rule has: card product, reward currency, category and/or merchant scope, multiplier, optional exclusions, optional spend cap, optional thresholds, rounding mode, effective-from / effective-to, **source reference**, and **last-reviewed date**.
- **FR-6 (M)** Rules are **versioned and immutable once used** by any calculation. A change creates a new version with new effective dates.
- **FR-7 (M)** UI shows rule source, effective dates, last-reviewed date, and a sample-data disclaimer.
- **FR-8 (S)** Flag rules whose last-reviewed date is older than a configurable staleness threshold (default 180 days).
- **FR-9 (C)** Rule editor UI. (MVP edits rules via seed files + migration/seed loader.)

### 4.3 Recommendation
- **FR-10 (M)** Input: amount (USD, cents precision), category, optional merchant, purchase date (default today), optional subset of cards.
- **FR-11 (M)** For each card: determine whether a rule applies on that date, apply merchant/category exclusions, thresholds, and caps (including partial application when a purchase straddles a cap), and compute reward in the card's currency.
- **FR-12 (M)** Rule selection is deterministic: most specific scope wins (merchant > category > base), then explicit priority, then stable rule id. Rules do **not** stack in MVP (a rule's multiplier is the total rate for the matched spend).
- **FR-13 (M)** Estimated value = reward units × user-configured cents-per-unit for that currency. Rank by estimated value **only among cards whose currency has a configured valuation**.
- **FR-14 (M)** Cards whose currency has no valuation are listed in an **Unranked** section with the message that they cannot be reliably compared, and what to configure. Never silently rank by raw multiplier across different currencies.
- **FR-15 (M)** Each result includes an ordered, human-readable explanation (rule matched, exclusions checked, cap remaining, rounding, valuation used) and warnings (e.g., stale rule, illustrative default valuation, cap nearly exhausted).
- **FR-16 (M)** Ties are broken deterministically and the tie is stated.
- **FR-17 (S)** Recommendation excludes annual fees and benefit credits from ranking; the UI states this.

### 4.4 Transactions
- **FR-18 (M)** Create, list (filter by card/category/date), and delete transactions. Fields: card, amount (USD), category, merchant (seeded list or free text without digits-guard violations), date, note.
- **FR-19 (M)** On create, calculate reward with the same engine as the recommender and persist an immutable calculation snapshot.
- **FR-20 (M)** Deleting a transaction removes its snapshot and frees cap capacity for **later** calculations; it does not recompute other transactions' snapshots.
- **FR-21 (S)** Backdated transactions are allowed, calculated against caps as of their own date; other snapshots are not recomputed (documented limitation).
- **FR-22 (C)** Refunds / negative amounts.

### 4.5 Benefits
- **FR-23 (M)** Each card product defines benefits: name, type (credit / allowance / perk), value (USD or count), reset period (monthly, quarterly, semiannual, calendar year, card-anniversary year), and optional eligibility notes.
- **FR-24 (M)** User logs usage entries (amount, date, note). System shows used / remaining for the current period and next reset date.
- **FR-25 (M)** Dashboard surfaces unused benefits expiring within 30 days.
- **FR-26 (S)** Mark a benefit as "not planning to use".

### 4.6 Rewards summary and valuations
- **FR-27 (M)** Rewards summary shows earned units **per currency** (never summed across currencies) and, separately, an estimated USD value using user valuations.
- **FR-28 (M)** User edits cents-per-unit per currency (validated range, e.g., 0 < v ≤ 10). Seeded defaults are labeled "illustrative default".
- **FR-29 (M)** Changing a valuation affects future recommendations and summary estimates, not stored calculation snapshots' *units* (snapshots also record the valuation used at calc time for transparency).

### 4.7 Platform
- **FR-30 (M)** "Reset demo data" action restores a profile to its seeded state.
- **FR-31 (M)** Backend exposes a versioned REST API with a published OpenAPI 3.1 document; the frontend uses types generated from it.
- **FR-32 (M)** Health (`/healthz`) and readiness (`/readyz`) endpoints; Prometheus metrics at `/metrics`.

## 5. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 Correctness | All money handled as integer cents or `Decimal`; no binary floats in calculations or storage. |
| NFR-2 Determinism | Same inputs + same rule data ⇒ identical output. Engine is a pure function with no I/O, clock, or randomness (date passed in). |
| NFR-3 Explainability | Every calculation returns a structured trace rendered to text. |
| NFR-4 Test quality | Engine ≥ 90% branch coverage; overall backend ≥ 80% line coverage; frontend tests for each page's main flow; ≥ 3 Playwright journeys. Coverage is reported by CI, not asserted by hand. |
| NFR-5 Performance | Recommendation p95 < 300 ms on seeded data under local conditions. Free-tier cold starts are documented, not optimized. |
| NFR-6 Security/privacy | No real financial data; input validation via Pydantic; CORS restricted; no secrets in repo; dependency audit in CI; security headers; basic rate limiting on mutating endpoints. |
| NFR-7 Accessibility | Keyboard-navigable forms, labeled inputs, sufficient contrast, no color-only meaning. Target: no critical axe violations on main pages. |
| NFR-8 Maintainability | Typed code (mypy/pyright strict on engine, TypeScript strict), linters + formatters enforced in CI, small modules. |
| NFR-9 Reproducibility | `docker compose up` brings up DB + API + web locally; seeds are idempotent; migrations run from empty DB. |
| NFR-10 Observability | Structured JSON logs with request ids; traces and metrics exported via OpenTelemetry; local Grafana dashboards. Deployed observability level is a human decision (see ARCHITECTURE §9). |
| NFR-11 Transparency | Visible disclaimer: sample data, not issuer terms, not financial advice. |
| NFR-12 Process traceability | Each backlog item maps to a commit/PR; AI-assisted changes follow `AGENTS.md`; test results come from actual runs. |

## 6. Explicitly out of scope

- Bank/issuer/Plaid/aggregator integration, OAuth to financial institutions.
- Real card data of any kind; real user accounts, passwords, email, payments.
- Real, current issuer terms; scraping or auto-updating rules from issuer sites.
- Credit scores, approvals, sign-up bonus tracking, application advice, 5/24-style rules.
- Redemption/transfer-partner modeling, award-chart search, travel booking.
- Statement import (CSV/PDF), transaction auto-categorization, merchant category code (MCC) lookup.
- Foreign currency and foreign transaction fees; non-USD amounts.
- Stacking/portal/offer/shopping-link bonuses (MVP); refunds (stretch).
- LLM features inside the app.
- Mobile native apps; multi-tenant auth; email/push notifications.
- Annual fee ROI optimization (displayed info only, if at all).

## 7. Acceptance criteria

Each criterion is verifiable by an automated test unless noted. Examples use fictional data.

**AC-1 Seed & startup.** *Given* an empty database, *when* migrations and seed run, *then* ≥2 profiles, ≥6 card products, their rules, sources, and benefits exist; re-running seed creates no duplicates.

**AC-2 Cross-currency honesty.** *Given* a cash-back card (1.5%) and a points card (3 pts/$) and valuations for both, *when* comparing a $100 purchase, *then* ranking is by estimated USD value (e.g., $1.50 vs 3 × cpp). *Given* the points currency has no valuation, *then* that card appears under Unranked with a limitation message and is not placed in the ranked list.

**AC-3 Specificity.** *Given* a base 1× rule, a dining 3× rule, and a merchant-specific 5× rule, *when* purchasing at that merchant, *then* the 5× rule is chosen and the explanation names it and the rejected alternatives.

**AC-4 Exclusions.** *Given* a grocery 4× rule excluding warehouse-club merchants, *when* the merchant is a warehouse club, *then* the rule is not applied and the explanation says why; the base rule applies.

**AC-5 Cap straddle.** *Given* a 5× rule with $500/quarter cap, base 1×, and $450 already spent in the period, *when* a $100 purchase occurs, *then* $50 earns at 5× and $50 at 1×, total shown with both parts.

**AC-6 Effective dates.** *Given* rule v1 effective through 2026-06-30 and v2 from 2026-07-01, *when* calculating for 2026-06-30 and 2026-07-01, *then* v1 and v2 are used respectively. *Given* no rule is effective, *then* the card is ineligible with an explanatory message.

**AC-7 Threshold.** *Given* a rule with a $25 minimum transaction, *when* a $20 purchase is evaluated, *then* the rule does not apply and the fallback rule does.

**AC-8 History preserved.** *Given* a saved transaction with a snapshot, *when* a new rule version is loaded that would change the result, *then* the stored snapshot (units, rule version id, trace) is unchanged and a new identical calculation request uses the new version.

**AC-9 Valuation configurability.** *When* the user changes a currency's cents-per-unit, *then* recommendation order can change accordingly, and rewards-summary estimated value updates; stored unit totals do not change.

**AC-10 Rewards separation.** The rewards summary never displays a single total across different currencies except a clearly labeled estimated USD value computed from valuations.

**AC-11 Benefits.** *Given* a $15 monthly credit with $10 logged this month, *then* remaining is $5 and the next reset date is the first of next month; logging more than remaining is rejected or flagged per the documented rule.

**AC-12 Sensitive-data guard.** *When* a note/merchant field contains a 13–19 digit sequence, *then* the API returns 422 and nothing is stored.

**AC-13 Determinism.** Repeating the same recommendation request twice yields byte-identical JSON (excluding request ids/timestamps).

**AC-14 API contract.** The committed `openapi.json` equals the document generated from the running app (CI check); it validates as OpenAPI 3.1; frontend types are regenerated without diff in CI.

**AC-15 Quality gates.** CI runs lint, typecheck, unit, API (against real Postgres), frontend, and E2E tests on every PR and they pass on `main`.

**AC-16 Deployment.** A public HTTPS URL serves the app with seeded data; a smoke test hits `/healthz` and runs one recommendation against the deployed instance; README states known free-tier limitations.

**AC-17 Disclosure (manual check).** Disclaimer about sample data is visible on dashboard, compare, and rules pages.

# CardPilot

> **CardPilot** is a deterministic, explainable credit card rewards and benefits optimizer built as an AI Dev Tools Zoomcamp final project.

---

### Important Disclaimer
**Fictional Data Only.** All card issuers, products, reward programs, rules, merchants, and user profiles used in this application are entirely fictional demo data created for illustrative and testing purposes. CardPilot does not represent actual credit card terms and does not provide financial advice. Never input real card numbers, CVVs, expiration dates, or bank credentials into this application.

---

## Overview

People managing multiple rewards cards face three key challenges:
1. **Purchase Optimization:** Determining the optimal card for a given purchase, category, or merchant when currencies (cash back, points, miles) and rules (caps, thresholds, exclusions) differ.
2. **Benefit Tracking:** Remembering statement credits, allowances, and annual perks before reset dates expire.
3. **Reward Visibility:** Tracking and estimating total reward balances separated cleanly by currency without misleading cross-currency sums.

CardPilot solves these challenges through:
- **A Pure, Deterministic Engine:** Mathematical evaluation with no clock, database, or network side effects.
- **Explainable Traces:** Every calculation produces a step-by-step human-readable audit trail explaining rule selection, exclusions, caps, and rounding.
- **Strict Separation of Currencies:** Points, miles, and cash back are never conflated; cross-currency ranking only occurs through explicit user-configured valuations.
- **Immutable Snapshots:** Transaction records preserve the exact rule version, multiplier, and valuation active at calculation time.

---

## Tech Stack

- **Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic
- **Database:** PostgreSQL (Docker locally, Neon in production)
- **Frontend:** React, TypeScript (strict), Vite, TanStack Query
- **Observability:** OpenTelemetry (OTel), Prometheus, Grafana, Loki, Tempo
- **Testing:** Pytest (table-driven engine tests, AsyncClient with Postgres), Vitest, Playwright

---

## Project Documentation

- [SPEC.md](SPEC.md) — Product specification, user journeys, functional and non-functional requirements, and acceptance criteria.
- [ARCHITECTURE.md](ARCHITECTURE.md) — Technical architecture, database schema, API design, engine specification, and component interactions.
- [BACKLOG.md](BACKLOG.md) — Phased task breakdown and sequential implementation roadmap.
- [AGENTS.md](AGENTS.md) — Operational guidelines, coding standards, and subagent boundaries.
- [docs/dev-log.md](docs/dev-log.md) — Development log tracking progress, decisions, test results, and AI/human collaboration.
- [docs/decisions/](docs/decisions/) — Architecture Decision Records (ADRs).

---

## Project Status

- **Phase 0 (Planning):** Approved.
- **Phase 1 (Foundation):** In progress (Task T01).

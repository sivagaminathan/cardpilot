# Makefile for CardPilot

.DEFAULT_GOAL := help

# ── Help ──────────────────────────────────────────────────────────────────────
.PHONY: help
help:
	@echo ""
	@echo "CardPilot — Available targets:"
	@echo ""
	@echo "  make dev          Bring up db + api + web with hot-reload (Docker Compose)"
	@echo "  make dev-obs      Bring up full stack + observability profile"
	@echo "  make down         Stop and remove containers (keep volumes)"
	@echo "  make down-v       Stop containers and delete volumes (destructive)"
	@echo ""
	@echo "  make test         Run backend pytest + frontend vitest"
	@echo "  make test-be      Run backend pytest only"
	@echo "  make test-fe      Run frontend vitest only"
	@echo ""
	@echo "  make lint         Run ruff + mypy + eslint + tsc"
	@echo "  make lint-be      Run ruff check + mypy on backend"
	@echo "  make lint-fe      Run eslint + tsc on frontend"
	@echo ""
	@echo "  make seed         Load fictional seed data into the running DB"
	@echo "  make openapi      Regenerate docs/openapi.json and frontend types"
	@echo "  make e2e          Run Playwright E2E tests"
	@echo ""
	@echo "  make healthz      Probe /healthz on the running API (requires Docker)"
	@echo ""

# ── Docker Compose ────────────────────────────────────────────────────────────
.PHONY: dev
dev:
	docker compose up --build --watch

.PHONY: dev-obs
dev-obs:
	docker compose --profile observability up --build --watch

.PHONY: down
down:
	docker compose down

.PHONY: down-v
down-v:
	docker compose down -v

# ── Backend Tests & Quality ───────────────────────────────────────────────────
.PHONY: test-be
test-be:
	cd backend && python -m pytest

.PHONY: lint-be
lint-be:
	cd backend && python -m ruff check . && python -m ruff format --check . && python -m mypy .

# ── Frontend Tests & Quality ──────────────────────────────────────────────────
.PHONY: test-fe
test-fe:
	cd frontend && npm test

.PHONY: lint-fe
lint-fe:
	cd frontend && npm run lint && npm run build

# ── Combined ──────────────────────────────────────────────────────────────────
.PHONY: test
test: test-be test-fe

.PHONY: lint
lint: lint-be lint-fe

# ── Seed & OpenAPI ────────────────────────────────────────────────────────────
.PHONY: seed
seed:
	@echo "Seed loader not yet implemented (T24/T25)."

.PHONY: openapi
openapi:
	@echo "OpenAPI export not yet implemented (T36)."

# ── E2E ───────────────────────────────────────────────────────────────────────
.PHONY: e2e
e2e:
	@echo "Playwright E2E not yet implemented (T46/T47)."

# ── Health Probe ─────────────────────────────────────────────────────────────
.PHONY: healthz
healthz:
	curl -sf http://localhost:8000/healthz | python -m json.tool

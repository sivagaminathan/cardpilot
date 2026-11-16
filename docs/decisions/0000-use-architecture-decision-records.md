# 0000. Use Architecture Decision Records

- **Status:** Accepted
- **Date:** 2026-11-15
- **Deciders:** Human Architect, AI Implementation Agent

## Context

CardPilot is an educational and portfolio project for the AI Dev Tools Zoomcamp. Significant architectural decisions are made throughout development regarding technology choices, data representation, observability, and engine boundaries. Without a structured recording mechanism, the rationale behind design choices and trade-offs can be lost or obscured.

## Decision

We will use Architecture Decision Records (ADRs) stored in `docs/decisions/` formatted as Markdown files (`NNNN-title.md`) to capture significant, non-obvious technical and architectural decisions.

Key architectural decisions summarized in `ARCHITECTURE.md` §10 (e.g., A-1 through A-7) and decisions D-1 through D-10 will be recorded here when elaborated.

## Consequences

### Positive
- Decisions are version-controlled alongside code and documentation.
- Trade-offs, rationale, and consequences remain transparent to reviewers and course evaluators.
- Clear audit trail of what was human-directed versus AI-recommended.

### Negative
- Minor maintenance overhead to author and update ADRs as architecture evolves.


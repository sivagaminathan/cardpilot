# Security Reviewer Role — CardPilot

The **Security Reviewer** agent is responsible for auditing compliance with data protection policies, validating security headers and input sanitization, auditing dependencies, and preventing credential or PII leakage.

---

## 1. Responsibilities & Scope

- **Sensitive Financial Data Guard (AC-12):** Enforce that CardPilot never stores, logs, or processes real credit card numbers (PANs), CVVs, SSNs, or banking credentials. Verify input validators reject 13–19 digit numeric sequences.
- **Fictional Data Compliance:** Verify that all issuers, card products, reward currencies, merchants, and user profiles are explicitly fictional. Flag any real financial institution names in seed data or code.
- **Secret Scanning & Configuration Audit:** Ensure no API keys, tokens, passwords, or production credentials exist in git history, `.env.example`, Dockerfiles, workflows, or logs.
- **API Security & Headers:** Audit CORS configuration (origins must be restricted; no wildcard `*` with credentials), security headers, and rate limiting on mutation endpoints.
- **Log Privacy:** Ensure structured logs record request metadata and request IDs but never serialize raw payloads or free-text fields containing user input.
- **Dependency Vulnerability Audits:** Review package manifests (`pyproject.toml`, `package.json`, `package-lock.json`) for known vulnerabilities or unapproved additions.

---

## 2. Required Inputs

1. Git diff, staged changes, and newly created files.
2. `AGENTS.md` — Section 2 Hard Rules (Never Violate).
3. `SPEC.md` — Non-functional security requirements and AC-12 (Sensitive-data guard).
4. `ARCHITECTURE.md` — Section 3 (API design, error handling, CORS) and Section 9 (Deployment & observability).
5. Environment and configuration files (`.env.example`, `docker-compose.yml`, `.github/workflows/ci.yml`).

---

## 3. Explicit Limitations ("Must Not")

- **Must NOT add product features or modify business logic.**
- **Must NOT weaken security boundaries, CORS policies, or input validation** to make tests pass or resolve communication errors.
- **Must NOT stage, commit, or push files.**
- **Must NOT use real credit card numbers or real banking credentials** in tests, fixtures, or examples (use fictional dummy data only).
- **Must NOT permit third-party LLM or external AI API calls** inside the application runtime.

---

## 4. Security Invariants & Audit Checklist

- [ ] **No Secrets in Repo:** Confirm `.env` is gitignored and `.env.example` contains only placeholder values.
- [ ] **Fictional Term Disclaimer:** Confirm disclaimer notices ("Sample data only. Not real issuer terms.") are present on reward rules and UI surfaces.
- [ ] **No Card Numbers (PANs):** Confirm schemas reject any string containing 13 to 19 contiguous or delimiter-separated digits.
- [ ] **Database Integrity:** Confirm SQL queries use SQLAlchemy parameterized expressions; zero raw string interpolation in SQL.
- [ ] **CORS Isolation:** Confirm `CORS_ORIGINS` is parsed as an explicit list and only allows configured frontend origins.
- [ ] **Error Information Leakage:** Confirm unhandled exceptions return generic RFC 9457 Problem Details without exposing internal stack traces to clients.

---

## 5. Expected Handoff Format

Handoffs from the Security Reviewer must follow this structure:

```markdown
### Security Review Report: [Task ID / Milestone]

1. **Audit Scope:**
   - Files, configurations, and diffs inspected
2. **Hard Rules Verification:**
   - Fictional data only: [PASS / FAIL]
   - Sensitive financial data protection: [PASS / FAIL]
   - Secret scanning & `.env` safety: [PASS / FAIL]
   - Disclaimers & terms compliance: [PASS / FAIL]
3. **Application & Infrastructure Security:**
   - CORS & Security headers: [PASS / FAIL]
   - Input validation & schema boundaries: [PASS / FAIL]
   - Log sanitization: [PASS / FAIL]
4. **Vulnerability & Dependency Findings:**
   - **Critical:** [Immediate security hazard or credential leak]
   - **High:** [Missing validation or permissive security rule]
   - **Medium:** [Configuration hardening needed]
   - **Low:** [Informational recommendation]
5. **Security Clearance:** [APPROVED / BLOCKED]
```

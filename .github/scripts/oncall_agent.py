"""CardPilot AI On-Call Agent — investigates Grafana alerts using telemetry and repo evidence."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
INCIDENTS_DIR = REPO_ROOT / "docs" / "incidents"


def _http_get_json(url: str, headers: dict[str, str] | None = None) -> Any:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_loki_evidence(
    loki_url: str,
    auth_header: str | None,
    trace_id: str,
) -> list[dict[str, Any]]:
    if not loki_url:
        return []
    base = loki_url.rstrip("/")
    query = '{service_name="cardpilot-api"}'
    if trace_id and re.fullmatch(r"[0-9a-fA-F]{16,32}", trace_id):
        query = f'{{service_name="cardpilot-api"}} |= "{trace_id}"'
    params = urllib.parse.urlencode({"query": query, "limit": "20"})
    headers = {"Accept": "application/json"}
    if auth_header:
        headers["Authorization"] = auth_header
    try:
        data = _http_get_json(f"{base}/loki/api/v1/query_range?{params}", headers=headers)
        results = data.get("data", {}).get("result", [])
        evidence: list[dict[str, Any]] = []
        for stream in results:
            labels = stream.get("stream", {})
            for ts, line in stream.get("values", [])[:5]:
                evidence.append(
                    {
                        "timestamp": ts,
                        "line": line,
                        "status_code": labels.get("status_code"),
                        "path": labels.get("path"),
                        "trace_id": labels.get("trace_id"),
                    }
                )
        return evidence
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        return [{"error": f"Failed to query Loki: {type(exc).__name__}"}]


def _fetch_tempo_trace(
    tempo_url: str,
    auth_header: str | None,
    trace_id: str,
) -> dict[str, Any]:
    if not tempo_url or not trace_id or not re.fullmatch(r"[0-9a-fA-F]{16,32}", trace_id):
        return {}
    base = tempo_url.rstrip("/")
    headers = {"Accept": "application/json"}
    if auth_header:
        headers["Authorization"] = auth_header
    try:
        return dict(_http_get_json(f"{base}/api/traces/{trace_id}", headers=headers))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        return {"error": f"Failed to query Tempo: {type(exc).__name__}"}


def _call_openai_analysis(prompt: str, api_key: str) -> str | None:
    if not api_key:
        return None
    body = json.dumps(
        {
            "model": "gpt-4o-mini",
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an on-call SRE investigating a CardPilot API alert. "
                        "Base your root cause strictly on the provided telemetry and code. "
                        "If the failure is caused by DEV_FAULT_INJECT_RECOMMENDATIONS, state that "
                        "clearly and do not invent a code defect."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return str(data["choices"][0]["message"]["content"])
    except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError, TimeoutError):
        return None


def _run_pytest_check() -> tuple[int, str]:
    proc = subprocess.run(
        ["python3", "-m", "pytest", "tests/api/test_recommendations.py"],
        cwd=str(REPO_ROOT / "backend"),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout[-1500:]


def main() -> int:
    alert_name = os.environ.get("ALERT_NAME", "CardPilot API High 5xx Error Rate")
    service = os.environ.get("ALERT_SERVICE", "cardpilot-api")
    environment = os.environ.get("ALERT_ENVIRONMENT", "development")
    severity = os.environ.get("ALERT_SEVERITY", "critical")
    summary = os.environ.get("ALERT_SUMMARY", "HTTP 5xx error threshold exceeded")
    trace_id = os.environ.get("ALERT_TRACE_ID", "").strip()

    if environment.lower() == "production":
        print("Refusing automated on-call remediation on production environment.", file=sys.stderr)
        return 1

    loki_url = os.environ.get("GRAFANA_LOKI_URL", "").strip()
    tempo_url = os.environ.get("GRAFANA_TEMPO_URL", "").strip()
    grafana_auth = os.environ.get("GRAFANA_AUTH_HEADER", "").strip() or None
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()

    loki_evidence = _fetch_loki_evidence(loki_url, grafana_auth, trace_id)
    tempo_trace = _fetch_tempo_trace(tempo_url, grafana_auth, trace_id)

    rec_service_snippet = (
        (REPO_ROOT / "backend" / "app" / "services" / "recommendations.py")
        .read_text(encoding="utf-8")[:3500]
    )

    prompt = (
        f"Alert: {alert_name}\nService: {service}\nEnvironment: {environment}\n"
        f"Severity: {severity}\nSummary: {summary}\nTrace ID: {trace_id or 'N/A'}\n\n"
        f"Loki Evidence:\n{json.dumps(loki_evidence, indent=2)}\n\n"
        f"Tempo Trace Present: {bool(tempo_trace and 'error' not in tempo_trace)}\n\n"
        f"Relevant Code (recommendations.py):\n{rec_service_snippet}\n"
    )
    llm_report = _call_openai_analysis(prompt, openai_key)

    has_fault_log = any(
        "fault_injected" in json.dumps(item) for item in loki_evidence
    ) or "DEV_FAULT_INJECT_RECOMMENDATIONS" in summary

    deterministic_rca = (
        "Telemetry and code inspection indicate the HTTP 500s on "
        "`POST /api/v1/profiles/{profile_key}/recommendations` were triggered by the "
        "controlled development fault-injection flag (`DEV_FAULT_INJECT_RECOMMENDATIONS=true` "
        "in `backend/app/config.py` / `backend/app/services/recommendations.py`). "
        "This is an intentional non-production fault-injection setting, not a code defect. "
        "Remediation: set `DEV_FAULT_INJECT_RECOMMENDATIONS=false` in the Render `cardpilot-api-dev` "
        "environment and re-verify `/api/v1/profiles/maya/recommendations`."
        if has_fault_log
        else "Investigated `POST /api/v1/profiles/{profile_key}/recommendations` and telemetry. "
        "Review attached Loki/Tempo evidence to confirm whether `DEV_FAULT_INJECT_RECOMMENDATIONS` "
        "or a downstream database/Neon connectivity issue caused the 5xx responses."
    )

    rc, pytest_out = _run_pytest_check()
    ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    INCIDENTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = INCIDENTS_DIR / f"incident-{ts}.md"

    report_content = (
        f"# Incident Report — {alert_name} ({ts})\n\n"
        f"- **Service:** `{service}`\n"
        f"- **Environment:** `{environment}`\n"
        f"- **Severity:** `{severity}`\n"
        f"- **Summary:** {summary}\n"
        f"- **Trace ID:** `{trace_id or 'not provided'}`\n\n"
        f"## Root Cause Analysis\n\n"
        f"{llm_report or deterministic_rca}\n\n"
        f"## Telemetry Evidence (Loki)\n\n"
        f"```json\n{json.dumps(loki_evidence, indent=2)}\n```\n\n"
        f"## Validation (`pytest tests/api/test_recommendations.py`, exit={rc})\n\n"
        f"```\n{pytest_out}\n```\n"
    )
    report_path.write_text(report_content, encoding="utf-8")
    print(f"Wrote incident report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

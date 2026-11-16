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


_TRACE_ID_RE = re.compile(r"^[0-9a-fA-F]{16,32}$")


def _is_valid_trace_id(value: str | None) -> bool:
    return bool(value and _TRACE_ID_RE.fullmatch(value.strip()))


def _parse_log_entry(ts: str, line: str, labels: dict[str, Any]) -> dict[str, Any]:
    """Parse a Loki log line, preferring structured JSON fields over stream labels."""
    parsed: dict[str, Any] = {}
    try:
        loaded = json.loads(line)
        if isinstance(loaded, dict):
            parsed = loaded
    except json.JSONDecodeError:
        parsed = {}

    return {
        "timestamp": ts,
        "level": parsed.get("level") or labels.get("level"),
        "message": parsed.get("message") or labels.get("message"),
        "status_code": parsed.get("status_code") or labels.get("status_code"),
        "path": parsed.get("path") or labels.get("path"),
        "trace_id": parsed.get("trace_id") or labels.get("trace_id"),
        "span_id": parsed.get("span_id") or labels.get("span_id"),
        "line": line,
    }


def _query_loki_range(
    loki_url: str,
    auth_header: str | None,
    query: str,
) -> list[dict[str, Any]]:
    base = loki_url.rstrip("/")
    params = urllib.parse.urlencode({"query": query, "limit": "20"})
    headers = {"Accept": "application/json"}
    if auth_header:
        headers["Authorization"] = auth_header
    data = _http_get_json(f"{base}/loki/api/v1/query_range?{params}", headers=headers)
    results = data.get("data", {}).get("result", [])
    evidence: list[dict[str, Any]] = []
    for stream in results:
        labels = stream.get("stream", {})
        for ts, line in stream.get("values", [])[:10]:
            evidence.append(_parse_log_entry(ts, line, labels))
    return evidence


def _fetch_loki_evidence(
    loki_url: str,
    auth_header: str | None,
    trace_id: str,
) -> list[dict[str, Any]]:
    if not loki_url:
        return []
    if _is_valid_trace_id(trace_id):
        query = f'{{service_name="cardpilot-api"}} |= "{trace_id.strip()}"'
    else:
        query = (
            '{service_name="cardpilot-api"} '
            '|~ "fault_injected|ERROR|\\"status_code\\":\\\\s*5[0-9]{2}"'
        )
    try:
        evidence = _query_loki_range(loki_url, auth_header, query)
        if not evidence and not _is_valid_trace_id(trace_id):
            evidence = _query_loki_range(loki_url, auth_header, '{service_name="cardpilot-api"}')
        return evidence
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        return [{"error": f"Failed to query Loki: {type(exc).__name__}"}]


def _extract_trace_id(loki_evidence: list[dict[str, Any]]) -> str:
    """Extract the most relevant valid trace_id from Loki log entries."""
    fallback = ""
    for item in loki_evidence:
        tid = str(item.get("trace_id") or "").strip()
        if not _is_valid_trace_id(tid):
            continue
        status_code = item.get("status_code")
        is_error = (
            item.get("level") == "ERROR"
            or "fault_injected" in str(item.get("message") or "")
            or "fault_injected" in str(item.get("line") or "")
            or (isinstance(status_code, int) and status_code >= 500)
            or (isinstance(status_code, str) and status_code.isdigit() and int(status_code) >= 500)
        )
        if is_error:
            return tid
        if not fallback:
            fallback = tid
    return fallback


def _fetch_tempo_trace(
    tempo_url: str,
    auth_header: str | None,
    trace_id: str,
) -> dict[str, Any]:
    if not tempo_url or not _is_valid_trace_id(trace_id):
        return {}
    base = tempo_url.rstrip("/")
    headers = {"Accept": "application/json"}
    if auth_header:
        headers["Authorization"] = auth_header
    try:
        return dict(_http_get_json(f"{base}/api/traces/{trace_id.strip()}", headers=headers))
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
    effective_trace_id = (
        trace_id if _is_valid_trace_id(trace_id) else _extract_trace_id(loki_evidence)
    )
    tempo_trace = _fetch_tempo_trace(tempo_url, grafana_auth, effective_trace_id)
    tempo_present = bool(tempo_trace and "error" not in tempo_trace)

    rec_service_source = (
        REPO_ROOT / "backend" / "app" / "services" / "recommendations.py"
    ).read_text(encoding="utf-8")

    prompt = (
        f"Alert: {alert_name}\nService: {service}\nEnvironment: {environment}\n"
        f"Severity: {severity}\nSummary: {summary}\n"
        f"Trace ID: {effective_trace_id or 'N/A'}\n\n"
        f"Loki Evidence:\n{json.dumps(loki_evidence, indent=2)}\n\n"
        f"Tempo Trace Present: {tempo_present}\n\n"
        f"Relevant Code (recommendations.py):\n{rec_service_source}\n"
    )
    llm_report = _call_openai_analysis(prompt, openai_key)

    has_fault_log = (
        any("fault_injected" in json.dumps(item) for item in loki_evidence)
        or "DEV_FAULT_INJECT_RECOMMENDATIONS" in summary
    )

    deterministic_rca = (
        "Telemetry and code inspection indicate the HTTP 500s on "
        "`POST /api/v1/profiles/{profile_key}/recommendations` were triggered by the "
        "controlled development fault-injection flag (`DEV_FAULT_INJECT_RECOMMENDATIONS=true` "
        "in `backend/app/config.py` / `backend/app/services/recommendations.py`). "
        "This is an intentional non-production fault-injection setting, not a code defect. "
        "Remediation: set `DEV_FAULT_INJECT_RECOMMENDATIONS=false` in the Render "
        "`cardpilot-api-dev` environment and re-verify `/api/v1/profiles/maya/recommendations`."
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
        f"- **Trace ID:** `{effective_trace_id or 'not provided'}`\n"
        f"- **Tempo Trace Correlated:** `{tempo_present}`\n\n"
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

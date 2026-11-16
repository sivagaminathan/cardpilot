"""Unit tests for the AI on-call agent evidence collection and correlation."""

from __future__ import annotations

import importlib.util
import json
import sys
import urllib.error
from pathlib import Path
from typing import Any

import pytest

_AGENT_PATH = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "oncall_agent.py"


def _load_agent_module() -> Any:
    spec = importlib.util.spec_from_file_location("oncall_agent", _AGENT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["oncall_agent"] = module
    spec.loader.exec_module(module)
    return module


def test_fetch_loki_evidence_prioritizes_errors_and_parses_json_body(monkeypatch) -> None:
    """Loki query filters for errors when trace_id is absent and parses JSON log fields."""
    agent = _load_agent_module()
    seen_urls: list[str] = []

    def fake_get_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        seen_urls.append(url)
        return {
            "data": {
                "result": [
                    {
                        "stream": {"service_name": "cardpilot-api"},
                        "values": [
                            [
                                "1700000000000000000",
                                json.dumps(
                                    {
                                        "level": "ERROR",
                                        "message": "recommendation.fault_injected",
                                        "status_code": 500,
                                        "path": "/api/v1/profiles/{profile_key}/recommendations",
                                        "trace_id": "2b9a3d965f7aaba8022bc13edf5bc5f8",
                                        "span_id": "1234567890abcdef",
                                    }
                                ),
                            ],
                            ["1700000000000000001", "non-json-malformed-line"],
                        ],
                    }
                ]
            }
        }

    monkeypatch.setattr(agent, "_http_get_json", fake_get_json)

    evidence = agent._fetch_loki_evidence("http://loki:3100", "Basic secret", "")
    assert len(seen_urls) == 1
    assert "fault_injected" in seen_urls[0]
    assert len(evidence) == 2
    assert evidence[0]["level"] == "ERROR"
    assert evidence[0]["status_code"] == 500
    assert evidence[0]["trace_id"] == "2b9a3d965f7aaba8022bc13edf5bc5f8"
    assert evidence[1]["line"] == "non-json-malformed-line"
    assert evidence[1]["trace_id"] is None


def test_extract_trace_id_prefers_error_entries() -> None:
    """_extract_trace_id picks the error/5xx trace_id over informational log entries."""
    agent = _load_agent_module()
    evidence = [
        {
            "level": "INFO",
            "message": "http.request",
            "status_code": 200,
            "trace_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        },
        {
            "level": "ERROR",
            "message": "recommendation.fault_injected",
            "status_code": 500,
            "trace_id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        },
    ]
    assert agent._extract_trace_id(evidence) == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    assert agent._extract_trace_id([{"trace_id": "not-hex"}]) == ""


def test_loki_and_tempo_handle_unavailable_telemetry_safely(monkeypatch) -> None:
    """Telemetry failures return safe error dicts without leaking auth headers."""

    def fake_get_json(url: str, headers: dict[str, str] | None = None) -> Any:
        raise urllib.error.URLError("connection refused")

    agent = _load_agent_module()
    monkeypatch.setattr(agent, "_http_get_json", fake_get_json)

    loki_res = agent._fetch_loki_evidence("http://loki:3100", "Basic top_secret_token", "")
    tempo_res = agent._fetch_tempo_trace(
        "http://tempo:3200",
        "Basic top_secret_token",
        "2b9a3d965f7aaba8022bc13edf5bc5f8",
    )

    assert loki_res == [{"error": "Failed to query Loki: URLError"}]
    assert tempo_res == {"error": "Failed to query Tempo: URLError"}
    assert "top_secret_token" not in json.dumps(loki_res)
    assert "top_secret_token" not in json.dumps(tempo_res)


def test_main_correlates_loki_trace_with_tempo_and_reads_full_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """main() extracts trace_id from Loki for Tempo lookup and sends full recommendations.py."""
    agent = _load_agent_module()
    captured_tempo_ids: list[str] = []
    captured_prompts: list[str] = []

    monkeypatch.setenv("ALERT_ENVIRONMENT", "development")
    monkeypatch.setenv("ALERT_TRACE_ID", "")
    monkeypatch.setenv("GRAFANA_LOKI_URL", "http://loki:3100")
    monkeypatch.setenv("GRAFANA_TEMPO_URL", "http://tempo:3200")
    monkeypatch.setenv("GRAFANA_AUTH_HEADER", "Basic secret-do-not-leak")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-do-not-leak")
    monkeypatch.setattr(agent, "INCIDENTS_DIR", tmp_path)

    monkeypatch.setattr(
        agent,
        "_fetch_loki_evidence",
        lambda loki_url, auth, tid: [
            {
                "timestamp": "1",
                "level": "ERROR",
                "message": "recommendation.fault_injected",
                "status_code": 500,
                "trace_id": "2b9a3d965f7aaba8022bc13edf5bc5f8",
                "line": '{"message":"recommendation.fault_injected"}',
            }
        ],
    )

    def fake_tempo(tempo_url: str, auth: str | None, tid: str) -> dict[str, Any]:
        captured_tempo_ids.append(tid)
        return {"batches": [{"resource": {}}]}

    def fake_openai(prompt: str, api_key: str) -> str:
        captured_prompts.append(prompt)
        return "Root cause: DEV_FAULT_INJECT_RECOMMENDATIONS=true."

    monkeypatch.setattr(agent, "_fetch_tempo_trace", fake_tempo)
    monkeypatch.setattr(agent, "_call_openai_analysis", fake_openai)
    monkeypatch.setattr(agent, "_run_pytest_check", lambda: (0, "2 passed"))

    rc = agent.main()
    assert rc == 0
    assert captured_tempo_ids == ["2b9a3d965f7aaba8022bc13edf5bc5f8"]
    assert len(captured_prompts) == 1
    assert "is_dev_fault_injection_active" in captured_prompts[0]
    assert "recommendation.fault_injected" in captured_prompts[0]
    assert "rank_card_evaluations" in captured_prompts[0]
    assert "Tempo Trace Present: True" in captured_prompts[0]

    reports = list(tmp_path.glob("incident-*.md"))
    assert len(reports) == 1
    report_text = reports[0].read_text(encoding="utf-8")
    assert "2b9a3d965f7aaba8022bc13edf5bc5f8" in report_text
    assert "Tempo Trace Correlated:** `True`" in report_text
    assert "secret-do-not-leak" not in report_text


def test_main_refuses_production_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() refuses to run when ALERT_ENVIRONMENT is production."""
    agent = _load_agent_module()
    monkeypatch.setenv("ALERT_ENVIRONMENT", "production")
    assert agent.main() == 1

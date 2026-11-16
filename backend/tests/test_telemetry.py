"""Focused tests for structured JSON logging, /metrics, and OpenTelemetry tracing."""

from __future__ import annotations

import json
import logging

import pytest
from httpx import ASGITransport, AsyncClient
from opentelemetry import trace as otel_trace

from app.config import Settings
from app.main import create_app
from app.telemetry.setup import JsonLogFormatter, _request_id_ctx


def test_json_log_formatter_includes_required_fields_and_trace_context() -> None:
    formatter = JsonLogFormatter(service_name="cardpilot-api", environment="test")
    tracer = otel_trace.get_tracer("test.tracer")
    token = _request_id_ctx.set("req-12345")
    try:
        with tracer.start_as_current_span("test-span") as span:
            record = logging.LogRecord(
                name="cardpilot.test",
                level=logging.INFO,
                pathname=__file__,
                lineno=1,
                msg="hello telemetry",
                args=(),
                exc_info=None,
            )
            record.method = "GET"
            record.path = "/api/v1/test"
            record.status_code = 200
            record.duration_ms = 1.25

            parsed = json.loads(formatter.format(record))
            span_ctx = span.get_span_context()

            assert parsed["level"] == "INFO"
            assert parsed["logger"] == "cardpilot.test"
            assert parsed["message"] == "hello telemetry"
            assert parsed["service"] == "cardpilot-api"
            assert parsed["environment"] == "test"
            assert parsed["request_id"] == "req-12345"
            assert parsed["trace_id"] == format(span_ctx.trace_id, "032x")
            assert parsed["span_id"] == format(span_ctx.span_id, "016x")
            assert parsed["method"] == "GET"
            assert parsed["path"] == "/api/v1/test"
            assert parsed["status_code"] == 200
            assert parsed["duration_ms"] == 1.25
            assert "timestamp" in parsed
    finally:
        _request_id_ctx.reset(token)


def test_settings_parses_otlp_configuration() -> None:
    settings = Settings(
        OTEL_SERVICE_NAME="cardpilot-dev",
        OTEL_EXPORTER_OTLP_ENDPOINT="https://otlp-gateway.example.net/otlp",
        OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic dXNlcjpzZWNyZXQ=,X-Custom=abc",
    )
    assert settings.otel_service_name == "cardpilot-dev"
    assert settings.otel_exporter_otlp_endpoint == "https://otlp-gateway.example.net/otlp"
    assert settings.otlp_headers_dict == {
        "Authorization": "Basic dXNlcjpzZWNyZXQ=",
        "X-Custom": "abc",
    }


@pytest.mark.asyncio
async def test_request_id_propagation_and_generation_without_otlp() -> None:
    app = create_app(Settings(OTEL_EXPORTER_OTLP_ENDPOINT=None))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.get("/healthz")
        assert r1.status_code == 200
        assert r1.headers.get("X-Request-ID")

        r2 = await client.get("/healthz", headers={"X-Request-ID": "custom-req-99"})
        assert r2.status_code == 200
        assert r2.headers.get("X-Request-ID") == "custom-req-99"


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_otel_http_metrics_and_excludes_secrets(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = create_app(Settings(OTEL_EXPORTER_OTLP_ENDPOINT=None))

    @app.get("/api/v1/test-items/{item_id}")
    async def read_test_item(item_id: str) -> dict[str, str]:
        return {"item_id": item_id}

    transport = ASGITransport(app=app)
    secret_auth = "Bearer super-secret-jwt-token"
    secret_cookie = "session=secret-cookie-value"
    secret_body = '{"note": "sensitive-body-12345"}'

    capsys.readouterr()
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health_res = await client.get("/healthz")
        assert health_res.status_code == 200

        item_res = await client.get("/api/v1/test-items/secret-42")
        assert item_res.status_code == 200

        res = await client.post(
            "/api/v1/nonexistent-endpoint",
            content=secret_body,
            headers={
                "Authorization": secret_auth,
                "Cookie": secret_cookie,
                "X-Request-ID": "req-metrics-check",
            },
        )
        assert res.status_code == 404
        assert res.headers.get("X-Request-ID") == "req-metrics-check"

        metrics_res = await client.get("/metrics")
        assert metrics_res.status_code == 200
        assert "text/plain" in metrics_res.headers["content-type"]
        body = metrics_res.text
        assert "cardpilot_http_requests" in body
        assert "cardpilot_http_request_duration_ms" in body
        assert 'path="/api/v1/test-items/{item_id}"' in body
        assert 'path="unmatched"' in body
        assert "secret-42" not in body
        assert "/api/v1/nonexistent-endpoint" not in body
        assert 'path="/healthz"' not in body
        assert 'path="/metrics"' not in body

    stdout_lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    http_logs = [
        json.loads(line)
        for line in stdout_lines
        if json.loads(line).get("logger") == "cardpilot.http"
    ]
    assert len(http_logs) == 2

    for entry in http_logs:
        assert len(entry["trace_id"]) == 32
        assert int(entry["trace_id"], 16) != 0
        assert len(entry["span_id"]) == 16
        assert int(entry["span_id"], 16) != 0

    joined = "\n".join(json.dumps(entry) for entry in http_logs)
    assert "http.request" in joined
    assert "/api/v1/test-items/{item_id}" in joined
    assert "unmatched" in joined
    assert "/healthz" not in joined
    assert "/metrics" not in joined
    assert secret_auth not in joined
    assert secret_cookie not in joined
    assert "sensitive-body-12345" not in joined

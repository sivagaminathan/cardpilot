"""Tests for the Grafana Alerting webhook relay endpoint."""

from __future__ import annotations

import io
import urllib.error
from typing import Any

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services import webhooks as webhook_service

_WEBHOOK_URL = "/api/v1/webhooks/grafana-alert"


def _make_client(
    *,
    environment: str = "development",
    webhook_secret: str | None = "test-webhook-secret",
    github_token: str | None = "ghp_secret_test_token_12345",
) -> TestClient:
    settings = Settings(
        ENVIRONMENT=environment,
        GRAFANA_WEBHOOK_SECRET=webhook_secret,
        GITHUB_DISPATCH_TOKEN=github_token,
    )
    return TestClient(create_app(settings=settings))


def _firing_payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "status": "firing",
        "receiver": "cardpilot-oncall",
        "commonLabels": {
            "alertname": "CardPilot API High 5xx Error Rate",
            "service": "cardpilot-api",
            "environment": "development",
            "severity": "warning",
        },
        "commonAnnotations": {
            "summary": "Common summary",
        },
        "externalURL": "http://localhost:3000",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "severity": "critical",
                    "trace_id": "2b9a3d965f7aaba8022bc13edf5bc5f8",
                },
                "annotations": {
                    "summary": "More than 2 HTTP 5xx responses in 2m",
                },
            }
        ],
    }
    base.update(overrides)
    return base


def test_valid_firing_alert_dispatches_expected_github_payload(monkeypatch) -> None:
    """Valid authenticated firing alert dispatches expected repository_dispatch payload."""
    captured: dict[str, Any] = {}

    def fake_dispatch(
        url: str,
        body: dict[str, Any],
        token: str,
        timeout: float = 10.0,
    ) -> int:
        captured["url"] = url
        captured["body"] = body
        captured["token"] = token
        captured["timeout"] = timeout
        return 204

    monkeypatch.setattr(webhook_service, "_post_github_dispatch", fake_dispatch)

    with _make_client() as client:
        res = client.post(
            _WEBHOOK_URL,
            json=_firing_payload(),
            headers={"Authorization": "Bearer test-webhook-secret"},
        )

    assert res.status_code == 202
    assert res.json()["dispatched"] is True
    assert captured["url"] == "https://api.github.com/repos/sivagaminathan/cardpilot/dispatches"
    assert captured["token"] == "ghp_secret_test_token_12345"
    assert captured["body"] == {
        "event_type": "grafana-alert",
        "client_payload": {
            "alert_name": "CardPilot API High 5xx Error Rate",
            "service": "cardpilot-api",
            "environment": "development",
            "severity": "critical",
            "summary": "More than 2 HTTP 5xx responses in 2m",
            "trace_id": "2b9a3d965f7aaba8022bc13edf5bc5f8",
            "status": "firing",
        },
    }


def test_missing_authorization_returns_401() -> None:
    """Missing Authorization header returns 401."""
    with _make_client() as client:
        res = client.post(_WEBHOOK_URL, json=_firing_payload())
    assert res.status_code == 401


def test_incorrect_authorization_returns_401() -> None:
    """Incorrect Bearer token returns 401."""
    with _make_client() as client:
        res = client.post(
            _WEBHOOK_URL,
            json=_firing_payload(),
            headers={"Authorization": "Bearer wrong-secret"},
        )
    assert res.status_code == 401


def test_missing_webhook_secret_prevents_dispatch(monkeypatch) -> None:
    """Missing GRAFANA_WEBHOOK_SECRET returns 503 and does not dispatch."""
    called = False

    def fake_dispatch(*args: Any, **kwargs: Any) -> int:
        nonlocal called
        called = True
        return 204

    monkeypatch.setattr(webhook_service, "_post_github_dispatch", fake_dispatch)

    with _make_client(webhook_secret=None) as client:
        res = client.post(
            _WEBHOOK_URL,
            json=_firing_payload(),
            headers={"Authorization": "Bearer anything"},
        )
    assert res.status_code == 503
    assert called is False


def test_missing_github_token_prevents_dispatch(monkeypatch) -> None:
    """Missing GITHUB_DISPATCH_TOKEN returns 503 and does not dispatch."""
    called = False

    def fake_dispatch(*args: Any, **kwargs: Any) -> int:
        nonlocal called
        called = True
        return 204

    monkeypatch.setattr(webhook_service, "_post_github_dispatch", fake_dispatch)

    with _make_client(github_token=None) as client:
        res = client.post(
            _WEBHOOK_URL,
            json=_firing_payload(),
            headers={"Authorization": "Bearer test-webhook-secret"},
        )
    assert res.status_code == 503
    assert called is False


def test_production_environment_rejects_endpoint(monkeypatch) -> None:
    """Production environment always rejects webhook relay with 403."""
    called = False

    def fake_dispatch(*args: Any, **kwargs: Any) -> int:
        nonlocal called
        called = True
        return 204

    monkeypatch.setattr(webhook_service, "_post_github_dispatch", fake_dispatch)

    with _make_client(environment="production") as client:
        res = client.post(
            _WEBHOOK_URL,
            json=_firing_payload(),
            headers={"Authorization": "Bearer test-webhook-secret"},
        )
    assert res.status_code == 403
    assert called is False


def test_malformed_json_structure_is_rejected() -> None:
    """Malformed JSON or wrong schema returns 422."""
    with _make_client() as client:
        res = client.post(
            _WEBHOOK_URL,
            content="{not-valid-json",
            headers={
                "Authorization": "Bearer test-webhook-secret",
                "Content-Type": "application/json",
            },
        )
    assert res.status_code == 422


def test_missing_alert_information_is_rejected() -> None:
    """Firing payload with empty alerts or missing alertname returns 422."""
    with _make_client() as client:
        empty_alerts = client.post(
            _WEBHOOK_URL,
            json=_firing_payload(alerts=[]),
            headers={"Authorization": "Bearer test-webhook-secret"},
        )
        missing_name = client.post(
            _WEBHOOK_URL,
            json=_firing_payload(
                commonLabels={"service": "cardpilot-api"},
                alerts=[{"status": "firing", "labels": {}, "annotations": {}}],
            ),
            headers={"Authorization": "Bearer test-webhook-secret"},
        )
    assert empty_alerts.status_code == 422
    assert missing_name.status_code == 422


def test_resolved_alert_does_not_dispatch(monkeypatch) -> None:
    """Resolved alert returns 200 and does not call GitHub dispatch."""
    called = False

    def fake_dispatch(*args: Any, **kwargs: Any) -> int:
        nonlocal called
        called = True
        return 204

    monkeypatch.setattr(webhook_service, "_post_github_dispatch", fake_dispatch)

    payload = _firing_payload(
        status="resolved",
        alerts=[
            {"status": "resolved", "labels": {"alertname": "CardPilot API High 5xx Error Rate"}}
        ],
    )
    with _make_client() as client:
        res = client.post(
            _WEBHOOK_URL,
            json=payload,
            headers={"Authorization": "Bearer test-webhook-secret"},
        )
    assert res.status_code == 200
    assert res.json()["dispatched"] is False
    assert res.json()["alert_status"] == "resolved"
    assert called is False


def test_individual_alert_labels_and_annotations_take_precedence(monkeypatch) -> None:
    """Individual firing alert labels/annotations override commonLabels/commonAnnotations."""
    captured: dict[str, Any] = {}

    def fake_dispatch(url: str, body: dict[str, Any], token: str, timeout: float = 10.0) -> int:
        captured["body"] = body
        return 204

    monkeypatch.setattr(webhook_service, "_post_github_dispatch", fake_dispatch)

    payload = _firing_payload(
        commonLabels={
            "alertname": "Common Alert",
            "service": "common-service",
            "environment": "staging",
            "severity": "warning",
        },
        commonAnnotations={"summary": "Common summary"},
        alerts=[
            {"status": "resolved", "labels": {"alertname": "Ignored Resolved"}},
            {
                "status": "firing",
                "labels": {
                    "alertname": "Specific Alert",
                    "service": "cardpilot-api",
                    "environment": "development",
                    "severity": "critical",
                },
                "annotations": {"summary": "Specific firing summary"},
            },
        ],
    )
    with _make_client() as client:
        res = client.post(
            _WEBHOOK_URL,
            json=payload,
            headers={"Authorization": "Bearer test-webhook-secret"},
        )

    assert res.status_code == 202
    client_payload = captured["body"]["client_payload"]
    assert client_payload["alert_name"] == "Specific Alert"
    assert client_payload["service"] == "cardpilot-api"
    assert client_payload["environment"] == "development"
    assert client_payload["severity"] == "critical"
    assert client_payload["summary"] == "Specific firing summary"


def test_github_api_failure_handled_without_exposing_credentials(monkeypatch) -> None:
    """GitHub HTTP error returns 502 and never leaks tokens or secrets."""
    secret_token = "ghp_super_secret_do_not_leak"

    def fake_dispatch(*args: Any, **kwargs: Any) -> int:
        raise urllib.error.HTTPError(
            url=webhook_service.GITHUB_DISPATCH_URL,
            code=422,
            msg=f"Unprocessable Entity ({secret_token})",
            hdrs=None,  # type: ignore[arg-type]
            fp=io.BytesIO(b"error"),
        )

    monkeypatch.setattr(webhook_service, "_post_github_dispatch", fake_dispatch)

    with _make_client(github_token=secret_token) as client:
        res = client.post(
            _WEBHOOK_URL,
            json=_firing_payload(),
            headers={"Authorization": "Bearer test-webhook-secret"},
        )

    assert res.status_code == 502
    assert secret_token not in res.text
    assert "test-webhook-secret" not in res.text


def test_github_api_timeout_handled_safely(monkeypatch) -> None:
    """GitHub timeout returns 504 without exposing credentials."""
    secret_token = "ghp_timeout_secret_token"

    def fake_dispatch(*args: Any, **kwargs: Any) -> int:
        raise TimeoutError("timed out")

    monkeypatch.setattr(webhook_service, "_post_github_dispatch", fake_dispatch)

    with _make_client(github_token=secret_token) as client:
        res = client.post(
            _WEBHOOK_URL,
            json=_firing_payload(),
            headers={"Authorization": "Bearer test-webhook-secret"},
        )

    assert res.status_code == 504
    assert secret_token not in res.text

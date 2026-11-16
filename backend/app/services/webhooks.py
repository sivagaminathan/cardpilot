"""Service layer for validating Grafana alerts and dispatching GitHub workflows."""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
from typing import Any

from fastapi import HTTPException, status

from app.schemas.webhooks import (
    GrafanaAlertItem,
    GrafanaWebhookPayload,
    WebhookDispatchResponse,
)

GITHUB_DISPATCH_URL = "https://api.github.com/repos/sivagaminathan/cardpilot/dispatches"
GITHUB_EVENT_TYPE = "grafana-alert"
GITHUB_DISPATCH_TIMEOUT_SECONDS = 10.0

_logger = logging.getLogger("cardpilot.webhooks")


def _extract_first_firing_alert(payload: GrafanaWebhookPayload) -> GrafanaAlertItem:
    """Return the first firing alert or raise 422 if none is usable."""
    for alert in payload.alerts:
        effective_status = (alert.status or payload.status).strip().lower()
        if effective_status == "firing":
            return alert
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Firing webhook payload must include at least one firing alert.",
    )


def _post_github_dispatch(
    url: str,
    body: dict[str, Any],
    token: str,
    timeout: float = GITHUB_DISPATCH_TIMEOUT_SECONDS,
) -> int:
    """Send a repository_dispatch POST request to GitHub and return the HTTP status code."""
    encoded = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=encoded,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "cardpilot-webhook-relay",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return int(resp.status)


async def handle_grafana_alert(
    payload: GrafanaWebhookPayload,
    *,
    github_token: str,
) -> WebhookDispatchResponse:
    """Process a Grafana webhook payload and dispatch firing non-production alerts."""
    top_status = payload.status.strip().lower()
    if top_status not in {"firing", "resolved"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported Grafana alert status: {payload.status!r}.",
        )

    if top_status == "resolved":
        _logger.info("webhook.grafana_resolved_ignored")
        return WebhookDispatchResponse(
            status="ignored",
            dispatched=False,
            alert_status="resolved",
            alert_name=payload.common_labels.get("alertname"),
            detail="Resolved alert notification does not trigger an investigation.",
        )

    first_alert = _extract_first_firing_alert(payload)
    merged_labels = {**payload.common_labels, **first_alert.labels}
    merged_annotations = {**payload.common_annotations, **first_alert.annotations}

    alert_name = (
        merged_labels.get("alertname") or merged_annotations.get("alertname") or ""
    ).strip()
    if not alert_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Firing alert is missing 'alertname' label or annotation.",
        )

    service = (merged_labels.get("service") or "cardpilot-api").strip()
    environment = (merged_labels.get("environment") or "development").strip()
    if environment.lower() == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Automated on-call dispatch is disabled for production alerts.",
        )

    severity = (merged_labels.get("severity") or "critical").strip()
    summary = (
        merged_annotations.get("summary")
        or merged_annotations.get("description")
        or f"{alert_name} firing"
    ).strip()
    trace_id = (merged_labels.get("trace_id") or merged_annotations.get("trace_id") or "").strip()

    dispatch_body: dict[str, Any] = {
        "event_type": GITHUB_EVENT_TYPE,
        "client_payload": {
            "alert_name": alert_name,
            "service": service,
            "environment": environment,
            "severity": severity,
            "summary": summary,
            "trace_id": trace_id,
            "status": top_status,
        },
    }

    try:
        gh_status = await asyncio.to_thread(
            _post_github_dispatch,
            GITHUB_DISPATCH_URL,
            dispatch_body,
            github_token,
        )
    except urllib.error.HTTPError as exc:
        _logger.error("webhook.github_dispatch_http_error", extra={"status_code": exc.code})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub repository_dispatch failed with HTTP {exc.code}.",
        ) from exc
    except TimeoutError as exc:
        _logger.error("webhook.github_dispatch_timeout")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="GitHub repository_dispatch request timed out.",
        ) from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            _logger.error("webhook.github_dispatch_timeout")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="GitHub repository_dispatch request timed out.",
            ) from exc
        _logger.error("webhook.github_dispatch_network_error")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub repository_dispatch request failed.",
        ) from exc

    if not (200 <= gh_status < 300):
        _logger.error("webhook.github_dispatch_unexpected_status", extra={"status_code": gh_status})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub repository_dispatch returned unexpected HTTP {gh_status}.",
        )

    _logger.info("webhook.github_dispatch_succeeded")
    return WebhookDispatchResponse(
        status="dispatched",
        dispatched=True,
        alert_status=top_status,
        alert_name=alert_name,
        detail="Dispatched grafana-alert to GitHub Actions.",
    )

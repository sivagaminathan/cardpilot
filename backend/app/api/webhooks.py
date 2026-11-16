"""API routes for Grafana Alerting webhook relay."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status

from app.config import Settings, get_settings
from app.schemas.webhooks import GrafanaWebhookPayload, WebhookDispatchResponse
from app.services.webhooks import handle_grafana_alert

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _extract_bearer_token(authorization: str | None) -> str:
    """Extract Bearer token from Authorization header or raise 401."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format.",
        )
    return token.strip()


@router.post("/grafana-alert", response_model=WebhookDispatchResponse)
async def post_grafana_alert(
    payload: GrafanaWebhookPayload,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> WebhookDispatchResponse:
    """Receive a Grafana webhook notification and forward firing alerts to GitHub."""
    if settings.environment.strip().lower() == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Grafana webhook relay is disabled in production.",
        )

    expected_secret = (settings.grafana_webhook_secret or "").strip()
    github_token = (settings.github_dispatch_token or "").strip()
    if not expected_secret or not github_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Grafana webhook relay is not configured.",
        )

    provided_token = _extract_bearer_token(authorization)
    if not secrets.compare_digest(provided_token, expected_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook authorization token.",
        )

    result = await handle_grafana_alert(payload, github_token=github_token)
    response.status_code = status.HTTP_202_ACCEPTED if result.dispatched else status.HTTP_200_OK
    return result

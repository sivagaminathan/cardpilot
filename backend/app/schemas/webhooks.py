"""Pydantic schemas for the Grafana Alerting webhook relay."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GrafanaAlertItem(BaseModel):
    """Single alert entry inside a Grafana Alerting webhook notification."""

    model_config = ConfigDict(extra="ignore")

    status: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)


class GrafanaWebhookPayload(BaseModel):
    """Standard Grafana Alerting webhook notification payload."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    status: str
    receiver: str | None = None
    alerts: list[GrafanaAlertItem] = Field(default_factory=list)
    common_labels: dict[str, str] = Field(default_factory=dict, alias="commonLabels")
    common_annotations: dict[str, str] = Field(default_factory=dict, alias="commonAnnotations")
    external_url: str | None = Field(default=None, alias="externalURL")


class WebhookDispatchResponse(BaseModel):
    """Response returned by the Grafana webhook relay endpoint."""

    status: str
    dispatched: bool
    alert_status: str
    alert_name: str | None = None
    detail: str

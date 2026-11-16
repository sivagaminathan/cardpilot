"""OpenTelemetry tracing, metrics, Prometheus /metrics, and structured JSON logging."""

from __future__ import annotations

import json
import logging
import sys
import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from opentelemetry import metrics as otel_metrics
from opentelemetry import trace as otel_trace
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import Settings
from app.db import get_engine

_EXCLUDED_PATHS = frozenset({"/healthz", "/readyz", "/metrics"})
_EXTRA_LOG_FIELDS = ("method", "path", "status_code", "duration_ms")

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

_logger = logging.getLogger("cardpilot.http")

_providers_initialized = False
_tracer_provider: TracerProvider | None = None
_meter_provider: MeterProvider | None = None
_logger_provider: LoggerProvider | None = None
_otel_log_handler: LoggingHandler | None = None
_http_requests_counter: otel_metrics.Counter | None = None
_http_duration_histogram: otel_metrics.Histogram | None = None


def get_request_id() -> str | None:
    """Return the current request ID from contextvars, if any."""
    return _request_id_ctx.get()


class JsonLogFormatter(logging.Formatter):
    """Structured JSON log formatter with request_id and OpenTelemetry trace context."""

    def __init__(self, *, service_name: str, environment: str) -> None:
        super().__init__()
        self._service_name = service_name
        self._environment = environment

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self._service_name,
            "environment": self._environment,
        }

        request_id = get_request_id()
        if request_id is not None:
            payload["request_id"] = request_id

        span = otel_trace.get_current_span()
        span_ctx = span.get_span_context()
        if span_ctx.is_valid:
            payload["trace_id"] = format(span_ctx.trace_id, "032x")
            payload["span_id"] = format(span_ctx.span_id, "016x")

        for field in _EXTRA_LOG_FIELDS:
            val = getattr(record, field, None)
            if val is not None:
                payload[field] = val

        if record.exc_info and record.exc_info[0] is not None:
            payload["exception"] = record.exc_info[0].__name__

        return json.dumps(payload, default=str)


def _normalize_otlp_base(endpoint: str | None) -> str | None:
    if not endpoint:
        return None
    cleaned = endpoint.strip().rstrip("/")
    return cleaned or None


def configure_logging(
    settings: Settings,
    *,
    logger_provider: LoggerProvider | None = None,
) -> None:
    """Configure root JSON stdout logging and optional OTLP log export."""
    global _otel_log_handler
    root = logging.getLogger()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root.setLevel(level)
    logging.getLogger("cardpilot").disabled = False
    logging.getLogger("cardpilot.http").disabled = False

    # Replace existing CardPilot JSON stream handlers to avoid duplicate stdout lines
    kept_handlers: list[logging.Handler] = [
        h
        for h in root.handlers
        if not isinstance(getattr(h, "formatter", None), JsonLogFormatter)
        and h is not _otel_log_handler
    ]
    root.handlers = kept_handlers

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(
        JsonLogFormatter(
            service_name=settings.otel_service_name,
            environment=settings.environment,
        )
    )
    root.addHandler(stream_handler)

    if logger_provider is not None:
        otel_handler = LoggingHandler(level=level, logger_provider=logger_provider)
        _otel_log_handler = otel_handler
        root.addHandler(otel_handler)


def _init_providers(settings: Settings) -> None:
    """Initialize global OpenTelemetry trace, metric, and log providers once."""
    global _providers_initialized, _tracer_provider, _meter_provider
    global _logger_provider, _http_requests_counter, _http_duration_histogram
    if _providers_initialized:
        return

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": settings.app_version,
            "deployment.environment": settings.environment,
        }
    )

    otlp_base = _normalize_otlp_base(settings.otel_exporter_otlp_endpoint)
    otlp_headers = settings.otlp_headers_dict

    # Tracing
    tracer_provider = TracerProvider(resource=resource)
    if otlp_base is not None:
        tracer_provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(
                    endpoint=f"{otlp_base}/v1/traces",
                    headers=otlp_headers or None,
                )
            )
        )
    otel_trace.set_tracer_provider(tracer_provider)
    _tracer_provider = tracer_provider

    # Metrics (single source: OTel SDK -> PrometheusMetricReader + optional OTLP)
    readers: list[MetricReader] = [PrometheusMetricReader()]
    if otlp_base is not None:
        readers.append(
            PeriodicExportingMetricReader(
                OTLPMetricExporter(
                    endpoint=f"{otlp_base}/v1/metrics",
                    headers=otlp_headers or None,
                )
            )
        )
    meter_provider = MeterProvider(resource=resource, metric_readers=readers)
    otel_metrics.set_meter_provider(meter_provider)
    _meter_provider = meter_provider

    meter = meter_provider.get_meter("cardpilot.http")
    _http_requests_counter = meter.create_counter(
        name="cardpilot_http_requests",
        description="Total HTTP requests processed by CardPilot API",
    )
    _http_duration_histogram = meter.create_histogram(
        name="cardpilot_http_request_duration_ms",
        unit="ms",
        description="HTTP request duration in milliseconds",
    )

    # Logs (stdout JSON + optional OTLP export)
    logger_provider: LoggerProvider | None = None
    if otlp_base is not None:
        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(
                OTLPLogExporter(
                    endpoint=f"{otlp_base}/v1/logs",
                    headers=otlp_headers or None,
                )
            )
        )
        _logger_provider = logger_provider

    configure_logging(settings, logger_provider=logger_provider)

    # Instrument SQLAlchemy engine once
    sqlalchemy_instrumentor = SQLAlchemyInstrumentor()
    if not sqlalchemy_instrumentor.is_instrumented_by_opentelemetry:
        sqlalchemy_instrumentor.instrument(
            engine=get_engine().sync_engine,
            tracer_provider=tracer_provider,
        )

    _providers_initialized = True


class RequestTelemetryMiddleware(BaseHTTPMiddleware):
    """Propagate/generate X-Request-ID, record OTel HTTP metrics, and log requests."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming_id = request.headers.get("X-Request-ID", "").strip()
        request_id = incoming_id or uuid4().hex
        token = _request_id_ctx.set(request_id)
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000.0, 2)
            raw_path = request.url.path
            if raw_path not in _EXCLUDED_PATHS:
                route = request.scope.get("route")
                route_path = getattr(route, "path", None)
                metric_path = route_path if isinstance(route_path, str) else "unmatched"
                attrs: dict[str, str | int] = {
                    "method": request.method,
                    "path": metric_path,
                    "status_code": status_code,
                }
                if _http_requests_counter is not None:
                    _http_requests_counter.add(1, attrs)
                if _http_duration_histogram is not None:
                    _http_duration_histogram.record(duration_ms, attrs)
                _logger.info(
                    "http.request",
                    extra={
                        "method": request.method,
                        "path": metric_path,
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                    },
                )
            _request_id_ctx.reset(token)


def setup_telemetry(app: FastAPI, settings: Settings) -> None:
    """Initialize logging, OTel tracing/metrics, /metrics route, and FastAPI instrumentation."""
    _init_providers(settings)
    configure_logging(settings, logger_provider=_logger_provider)

    app.add_middleware(RequestTelemetryMiddleware)

    @app.get("/metrics", tags=["meta"], include_in_schema=False)
    async def metrics() -> Response:
        """Expose Prometheus-formatted metrics from OpenTelemetry MetricReader."""
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=_tracer_provider,
        excluded_urls="healthz,readyz,metrics",
    )


def shutdown_telemetry() -> None:
    """Flush OpenTelemetry providers on application exit."""
    if _tracer_provider is not None:
        _tracer_provider.force_flush()
    if _meter_provider is not None:
        _meter_provider.force_flush()
    if _logger_provider is not None:
        _logger_provider.force_flush()

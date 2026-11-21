"""Application configuration using environment variables."""

from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ALLOWED_DB_SCHEMES = frozenset({"postgres", "postgresql", "postgresql+asyncpg"})


def normalize_database_url(raw_url: str) -> str:
    """Normalize a PostgreSQL connection URL for SQLAlchemy + asyncpg.

    Converts ``postgres://`` and ``postgresql://`` schemes to ``postgresql+asyncpg://``,
    translates ``sslmode=...`` to ``ssl=...`` when ``ssl`` is not already set, and
    strips ``channel_binding`` (unsupported by asyncpg). Raises ``ValueError`` without
    exposing credentials on invalid input.
    """
    if not isinstance(raw_url, str) or not raw_url.strip():
        raise ValueError("Database URL must be a non-empty PostgreSQL URL.")

    parsed = urlsplit(raw_url.strip())
    if parsed.scheme not in _ALLOWED_DB_SCHEMES:
        raise ValueError(f"Unsupported database URL scheme: {parsed.scheme!r}.")
    if not parsed.hostname:
        raise ValueError("Database URL must include a host.")

    params = parse_qsl(parsed.query, keep_blank_values=True)
    has_ssl = any(key == "ssl" for key, _ in params)
    normalized_params: list[tuple[str, str]] = []

    for key, value in params:
        if key == "channel_binding":
            continue
        if key == "sslmode":
            if not has_ssl and value:
                normalized_params.append(("ssl", value))
                has_ssl = True
            continue
        normalized_params.append((key, value))

    return urlunsplit(
        (
            "postgresql+asyncpg",
            parsed.netloc,
            parsed.path,
            urlencode(normalized_params),
            "",
        )
    )


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "CardPilot"
    app_version: str = "0.1.0"
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # API
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")
    trust_proxy_headers: bool = Field(default=False, alias="TRUST_PROXY_HEADERS")
    trusted_proxy_count: int = Field(default=1, ge=1, alias="TRUSTED_PROXY_COUNT")

    # Rate limiting on mutating API endpoints
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_requests: int = Field(default=60, gt=0, alias="RATE_LIMIT_REQUESTS")
    rate_limit_window_seconds: int = Field(default=60, gt=0, alias="RATE_LIMIT_WINDOW_SECONDS")

    # Database (PostgreSQL)
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/cardpilot",
        alias="DATABASE_URL",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    # Observability (OpenTelemetry / OTLP)
    otel_service_name: str = Field(default="cardpilot-api", alias="OTEL_SERVICE_NAME")
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    otel_exporter_otlp_headers: str | None = Field(default=None, alias="OTEL_EXPORTER_OTLP_HEADERS")

    # Controlled development fault injection (impossible in production)
    dev_fault_inject_recommendations: bool = Field(
        default=False, alias="DEV_FAULT_INJECT_RECOMMENDATIONS"
    )

    # On-call webhook relay (non-production only)
    grafana_webhook_secret: str | None = Field(default=None, alias="GRAFANA_WEBHOOK_SECRET")
    github_dispatch_token: str | None = Field(default=None, alias="GITHUB_DISPATCH_TOKEN")

    @model_validator(mode="after")
    def _validate_cors_origins(self) -> "Settings":
        origins = self.cors_origin_list
        if self.is_production and (not origins or "*" in origins):
            raise ValueError(
                "Production CORS_ORIGINS must specify explicit origins and cannot contain '*'."
            )
        for origin in origins:
            if origin == "*":
                continue
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(f"Invalid CORS origin: {origin!r}.")
        return self

    @property
    def is_production(self) -> bool:
        """Return True when running in the production environment."""
        return self.environment.strip().lower() == "production"

    @property
    def is_dev_fault_injection_active(self) -> bool:
        """Return True only when fault injection is enabled outside production."""
        return (
            self.dev_fault_inject_recommendations
            and self.environment.strip().lower() != "production"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        """Return normalized, deduplicated CORS origins parsed as a list of strings."""
        normalized: list[str] = []
        for raw in self.cors_origins.split(","):
            item = raw.strip()
            if not item:
                continue
            if item != "*":
                item = item.rstrip("/")
            if item not in normalized:
                normalized.append(item)
        return normalized

    @property
    def otlp_headers_dict(self) -> dict[str, str]:
        """Parse comma-separated ``Key=Value`` OTLP headers without logging values."""
        if not self.otel_exporter_otlp_headers:
            return {}
        headers: dict[str, str] = {}
        for pair in self.otel_exporter_otlp_headers.split(","):
            item = pair.strip()
            if "=" not in item:
                continue
            key, val = item.split("=", 1)
            k = key.strip()
            v = val.strip()
            if k:
                headers[k] = v
        return headers


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()

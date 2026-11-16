"""Application configuration using environment variables."""

from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator
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

    # Database (PostgreSQL)
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/cardpilot",
        alias="DATABASE_URL",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @property
    def cors_origin_list(self) -> list[str]:
        """Return CORS origins parsed as a list of strings."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()

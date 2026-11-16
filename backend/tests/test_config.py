"""Unit tests for database URL normalization and Settings (Neon + local Postgres)."""

from __future__ import annotations

import inspect

import asyncpg  # type: ignore[import-untyped]
import pytest
from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg
from sqlalchemy.engine import make_url

from app.config import Settings, normalize_database_url


def test_normalize_standard_postgresql_url() -> None:
    raw = "postgresql://user:pass@localhost:5432/cardpilot"
    assert normalize_database_url(raw) == "postgresql+asyncpg://user:pass@localhost:5432/cardpilot"


def test_normalize_postgres_scheme_url() -> None:
    raw = "postgres://user:pass@db.example.com:5432/cardpilot"
    assert (
        normalize_database_url(raw)
        == "postgresql+asyncpg://user:pass@db.example.com:5432/cardpilot"
    )


def test_normalize_already_asyncpg_url_unchanged() -> None:
    raw = "postgresql+asyncpg://postgres:postgres@localhost:5432/cardpilot"
    assert normalize_database_url(raw) == raw


def test_normalize_neon_sslmode_and_channel_binding_compatible_with_asyncpg() -> None:
    raw = (
        "postgresql://neondb_owner:secret@ep-cool-host-1234.us-east-2.aws.neon.tech/"
        "neondb?sslmode=require&channel_binding=require"
    )
    normalized = normalize_database_url(raw)
    assert normalized == (
        "postgresql+asyncpg://neondb_owner:secret@ep-cool-host-1234.us-east-2.aws.neon.tech/"
        "neondb?ssl=require"
    )

    # Verify SQLAlchemy's asyncpg dialect produces only kwargs accepted by installed asyncpg.connect
    _, connect_kwargs = PGDialect_asyncpg().create_connect_args(make_url(normalized))  # type: ignore[no-untyped-call]
    accepted_params = set(inspect.signature(asyncpg.connect).parameters.keys())
    assert set(connect_kwargs.keys()).issubset(accepted_params)
    assert connect_kwargs["ssl"] == "require"
    assert "channel_binding" not in connect_kwargs
    assert "sslmode" not in connect_kwargs


def test_normalize_preserves_unrelated_query_parameters() -> None:
    raw = (
        "postgresql://user:pass@host.example.com:5432/db"
        "?sslmode=require&channel_binding=require&application_name=cardpilot&timeout=30"
    )
    normalized = normalize_database_url(raw)
    assert normalized == (
        "postgresql+asyncpg://user:pass@host.example.com:5432/db"
        "?ssl=require&application_name=cardpilot&timeout=30"
    )


def test_normalize_preserves_existing_ssl_param_over_sslmode() -> None:
    raw = "postgresql+asyncpg://user:pass@host:5432/db?ssl=verify-full&sslmode=require"
    assert (
        normalize_database_url(raw) == "postgresql+asyncpg://user:pass@host:5432/db?ssl=verify-full"
    )


@pytest.mark.parametrize(
    ("bad_url", "secret_fragment"),
    [
        ("", ""),
        ("   ", ""),
        ("sqlite:///./test.db", ""),
        ("mysql://admin:supersecret@db.example.com:3306/app", "supersecret"),
        ("postgresql://admin:supersecret@/missing_host", "supersecret"),
    ],
)
def test_normalize_rejects_invalid_urls_without_leaking_credentials(
    bad_url: str,
    secret_fragment: str,
) -> None:
    with pytest.raises(ValueError) as exc_info:
        normalize_database_url(bad_url)
    if secret_fragment:
        assert secret_fragment not in str(exc_info.value)


def test_settings_normalizes_neon_database_url() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://u:p@ep-test.neon.tech/neondb?sslmode=require&channel_binding=require"
    )
    assert settings.database_url == "postgresql+asyncpg://u:p@ep-test.neon.tech/neondb?ssl=require"

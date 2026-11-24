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


def test_settings_db_pool_defaults_and_validation() -> None:
    from pydantic import ValidationError

    defaults = Settings()
    assert defaults.db_statement_cache_size is None
    assert defaults.db_pool_size == 5
    assert defaults.db_max_overflow == 5

    empty_cache = Settings(DB_STATEMENT_CACHE_SIZE="")  # type: ignore[arg-type]
    assert empty_cache.db_statement_cache_size is None

    custom = Settings(DB_STATEMENT_CACHE_SIZE=0, DB_POOL_SIZE=8, DB_MAX_OVERFLOW=2)
    assert custom.db_statement_cache_size == 0
    assert custom.db_pool_size == 8
    assert custom.db_max_overflow == 2

    with pytest.raises(ValidationError):
        Settings(DB_STATEMENT_CACHE_SIZE=-1)
    with pytest.raises(ValidationError):
        Settings(DB_POOL_SIZE=0)
    with pytest.raises(ValidationError):
        Settings(DB_MAX_OVERFLOW=-1)


def test_settings_production_cors_and_fault_injection_guards() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production", CORS_ORIGINS="*")
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production", CORS_ORIGINS=" , ")

    prod = Settings(
        ENVIRONMENT="production",
        CORS_ORIGINS="https://cardpilot.onrender.com/",
        DEV_FAULT_INJECT_RECOMMENDATIONS=True,
    )
    assert prod.is_production is True
    assert prod.cors_origin_list == ["https://cardpilot.onrender.com"]
    assert prod.is_dev_fault_injection_active is False


def test_get_engine_omits_statement_cache_size_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import db as db_mod

    captured: dict[str, object] = {}

    def fake_create_async_engine(url: str, **kwargs: object) -> object:
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_session_maker", None)
    monkeypatch.setattr(
        db_mod,
        "get_settings",
        lambda: Settings(
            DATABASE_URL="postgresql://u:p@ep-pooler.neon.tech/db?sslmode=require",
            DIRECT_DATABASE_URL="postgresql://u:p@ep-direct.neon.tech/db?sslmode=require",
        ),
    )
    monkeypatch.setattr(db_mod, "create_async_engine", fake_create_async_engine)

    db_mod.get_engine()
    assert captured["url"] == "postgresql+asyncpg://u:p@ep-pooler.neon.tech/db?ssl=require"
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["pool_size"] == 5
    assert kwargs["max_overflow"] == 5
    assert kwargs["connect_args"] == {}

    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(
        db_mod,
        "get_settings",
        lambda: Settings(
            DATABASE_URL="postgresql://u:p@ep-pooler.neon.tech/db?sslmode=require",
            DB_STATEMENT_CACHE_SIZE=0,
            DB_POOL_SIZE=3,
            DB_MAX_OVERFLOW=1,
        ),
    )
    db_mod.get_engine()
    kwargs2 = captured["kwargs"]
    assert isinstance(kwargs2, dict)
    assert kwargs2["pool_size"] == 3
    assert kwargs2["max_overflow"] == 1
    assert kwargs2["connect_args"] == {"statement_cache_size": 0}

    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_session_maker", None)


def test_alembic_get_database_url_prefers_direct_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import contextlib
    import importlib.util
    import types
    from pathlib import Path

    from alembic import context

    dummy_cfg = types.SimpleNamespace(
        config_file_name=None,
        get_main_option=lambda _k: "driver://user:pass@localhost/dbname",
    )
    monkeypatch.setattr(context, "config", dummy_cfg, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: True, raising=False)
    monkeypatch.setattr(context, "configure", lambda **_kw: None, raising=False)
    monkeypatch.setattr(
        context, "begin_transaction", lambda: contextlib.nullcontext(), raising=False
    )
    monkeypatch.setattr(context, "run_migrations", lambda: None, raising=False)

    env_path = Path(__file__).resolve().parents[1] / "alembic" / "env.py"
    spec = importlib.util.spec_from_file_location("cardpilot_alembic_env", env_path)
    assert spec is not None and spec.loader is not None
    alembic_env = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(alembic_env)

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@ep-pooler.neon.tech/db?sslmode=require")
    monkeypatch.setenv(
        "DIRECT_DATABASE_URL", "postgresql://u:p@ep-direct.neon.tech/db?sslmode=require"
    )
    assert (
        alembic_env.get_database_url()
        == "postgresql+asyncpg://u:p@ep-direct.neon.tech/db?ssl=require"
    )

    monkeypatch.delenv("DIRECT_DATABASE_URL")
    assert (
        alembic_env.get_database_url()
        == "postgresql+asyncpg://u:p@ep-pooler.neon.tech/db?ssl=require"
    )


async def test_loader_if_empty_uses_ensure_seeded_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.seeds import loader as loader_mod

    called = {"ensure": 0, "seed_all": 0, "closed": 0}

    class _FakeSession:
        def begin(self) -> _FakeSession:
            return self

        async def __aenter__(self) -> _FakeSession:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

    async def fake_ensure(_session: object) -> None:
        called["ensure"] += 1

    async def fake_seed_all(_session: object) -> dict[str, int]:
        called["seed_all"] += 1
        return {}

    async def fake_close() -> None:
        called["closed"] += 1

    monkeypatch.setattr(loader_mod, "get_session_maker", lambda: lambda: _FakeSession())
    monkeypatch.setattr(loader_mod, "ensure_seeded", fake_ensure)
    monkeypatch.setattr(loader_mod, "seed_all", fake_seed_all)
    monkeypatch.setattr(loader_mod, "close_engine", fake_close)

    await loader_mod._main(if_empty=True)
    assert called == {"ensure": 1, "seed_all": 0, "closed": 1}

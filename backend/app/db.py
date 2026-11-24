"""Database engine and async session configuration using SQLAlchemy 2.0."""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base class for SQLAlchemy ORM models."""

    pass


# Global singleton engine and sessionmaker
_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return or initialize cached async SQLAlchemy engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args: dict[str, int] = {}
        if settings.db_statement_cache_size is not None:
            connect_args["statement_cache_size"] = settings.db_statement_cache_size
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            connect_args=connect_args,
        )
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Return or initialize cached async session factory."""
    global _session_maker
    if _session_maker is None:
        engine = get_engine()
        _session_maker = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_maker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    session_factory = get_session_maker()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def check_db_health(session: AsyncSession) -> bool:
    """Execute a simple query to verify database connectivity."""
    result = await session.execute(text("SELECT 1"))
    return result.scalar() == 1


async def close_engine() -> None:
    """Dispose of the database engine connection pool."""
    global _engine, _session_maker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_maker = None

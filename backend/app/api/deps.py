"""Common dependency providers for FastAPI routes."""

from app.config import Settings, get_settings
from app.db import get_db_session

__all__ = ["Settings", "get_current_settings", "get_db_session"]


def get_current_settings() -> Settings:
    """Dependency for injecting settings into route handlers."""
    return get_settings()

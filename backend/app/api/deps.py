"""Common dependency providers for FastAPI routes."""

from app.config import Settings, get_settings


def get_current_settings() -> Settings:
    """Dependency for injecting settings into route handlers."""
    return get_settings()


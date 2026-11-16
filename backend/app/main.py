"""FastAPI application entry point for CardPilot."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.deps import get_db_session
from app.api.errors import http_exception_handler, validation_exception_handler
from app.api.routes import api_router
from app.config import Settings, get_settings
from app.db import check_db_health, close_engine
from app.telemetry import setup_telemetry, shutdown_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager."""
    # Startup tasks
    yield
    # Shutdown tasks
    shutdown_telemetry()
    await close_engine()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure FastAPI application instance."""
    app_settings = settings or get_settings()

    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        description="Deterministic, explainable credit card rewards and benefits optimizer API.",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register error handlers
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # Unversioned health check endpoint
    @app.get("/healthz", tags=["meta"], summary="Liveness probe")
    async def healthz() -> dict[str, str]:
        """Liveness health check endpoint."""
        return {
            "status": "ok",
            "app": app_settings.app_name,
            "version": app_settings.app_version,
            "environment": app_settings.environment,
        }

    # Unversioned readiness check endpoint
    @app.get("/readyz", tags=["meta"], summary="Readiness probe")
    async def readyz(
        session: Annotated[AsyncSession, Depends(get_db_session)],
    ) -> dict[str, str]:
        """Readiness health check endpoint verifying database connectivity."""
        try:
            is_healthy = await check_db_health(session)
            if not is_healthy:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Database readiness check returned unhealthy status",
                )
            return {
                "status": "ready",
                "database": "connected",
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Database unreachable: {exc}",
            ) from exc

    # Mount versioned API routes
    app.include_router(api_router)

    # Configure structured logging, /metrics, and OpenTelemetry tracing/metrics
    setup_telemetry(app, app_settings)

    return app


app = create_app()

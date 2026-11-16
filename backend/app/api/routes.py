"""API v1 router definition."""

from fastapi import APIRouter

from app.api.recommendations import router as recommendations_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(recommendations_router)

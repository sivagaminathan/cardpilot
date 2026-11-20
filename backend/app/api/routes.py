"""API v1 router definition."""

from fastapi import APIRouter

from app.api.benefits import router as benefits_router
from app.api.catalog import router as catalog_router
from app.api.recommendations import router as recommendations_router
from app.api.rewards import router as rewards_router
from app.api.transactions import router as transactions_router
from app.api.webhooks import router as webhooks_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(benefits_router)
api_router.include_router(catalog_router)
api_router.include_router(recommendations_router)
api_router.include_router(rewards_router)
api_router.include_router(transactions_router)
api_router.include_router(webhooks_router)

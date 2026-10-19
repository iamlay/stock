from fastapi import APIRouter

from app.api.v1 import data, market, plans

api_router = APIRouter()
api_router.include_router(data.router)
api_router.include_router(market.router)
api_router.include_router(plans.router)

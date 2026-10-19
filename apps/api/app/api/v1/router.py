from fastapi import APIRouter

from app.api.v1 import auth, data, etfs, market, plans

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(data.router)
api_router.include_router(etfs.router)
api_router.include_router(market.router)
api_router.include_router(plans.router)

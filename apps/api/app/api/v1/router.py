from fastapi import APIRouter

from app.api.v1 import admin, auth, backtests, data, etfs, market, plans, stocks, watchlist

api_router = APIRouter()
api_router.include_router(admin.router)
api_router.include_router(auth.router)
api_router.include_router(backtests.router)
api_router.include_router(data.router)
api_router.include_router(etfs.router)
api_router.include_router(market.router)
api_router.include_router(stocks.router)
api_router.include_router(stocks.admin_router)
api_router.include_router(watchlist.router)
api_router.include_router(plans.router)

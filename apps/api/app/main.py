from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.settings import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="ETF 行情、估值、策略回测 API。站内不提供支付与微信登录。",
        docs_url="/docs" if settings.env != "production" else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=settings.cors_origin_regex or None,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/healthz", tags=["ops"], summary="健康检查")
    def healthz() -> dict[str, object]:
        return {
            "status": "ok",
            "service": "stocklab-api",
            "version": settings.version,
            "email_configured": settings.email_configured,
        }

    return app


app = create_app()

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/market", tags=["market"])


class IndexQuote(BaseModel):
    name: str
    value: float
    change_pct: float


class MarketOverview(BaseModel):
    trade_date: str
    demo: bool
    indices: list[IndexQuote]
    advancing: int
    declining: int
    turnover_billion: float
    valuation_percentile_5y: int
    note: str


@router.get("/overview", response_model=MarketOverview, summary="今日市场概览")
def market_overview() -> MarketOverview:
    """Sprint 0 returns demo data; W3 replaces it with the ETL-backed query."""

    return MarketOverview(
        trade_date="2026-10-19",
        demo=True,
        indices=[
            IndexQuote(name="上证指数", value=3342.12, change_pct=0.62),
            IndexQuote(name="沪深 300", value=4018.55, change_pct=0.48),
            IndexQuote(name="创业板指", value=2311.09, change_pct=-0.35),
        ],
        advancing=3124,
        declining=1893,
        turnover_billion=1870.0,
        valuation_percentile_5y=38,
        note="示例数据，接入数据管道后替换。",
    )

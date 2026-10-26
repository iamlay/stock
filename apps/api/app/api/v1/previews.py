"""Fixed teaching examples and a separately gated, account-bound stock preview."""

from hashlib import sha256
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import (
    Instrument,
    MarketDaily,
    StockFinancial,
    StockMetric,
    StockProfile,
    StockWatchlist,
    User,
)
from app.security import get_current_user
from app.services.bollinger import compute_bollinger
from app.services.membership import has_premium_access, lock_user
from app.settings import settings

router = APIRouter(prefix="/previews", tags=["previews"])


class PreviewCard(BaseModel):
    feature: Literal["grid", "bollinger", "financial"]
    title: str
    purpose: str
    as_of: str | None
    metrics: dict[str, str]
    scope: str


class Preview(BaseModel):
    kind: Literal["sample", "personal"]
    code: str
    name: str
    cards: list[PreviewCard]


class Choice(BaseModel):
    code: str
    name: str


class PreviewState(BaseModel):
    enabled: bool
    selected_code: str | None = None
    choices: list[Choice] = []
    preview: Preview | None = None
    message: str | None = None


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(pattern=r"^[0-9]{6}$")


PURPOSES = {
    "grid": "将股息率换算为观察价格，理解价格与股息率的关系；不代表收益保证或买入建议。",
    "bollinger": "观察价格在近 20 个交易日波动区间的位置；靠近下轨不等于即将上涨。",
    "financial": "结合利润增长与净资产收益率理解经营表现；单期数据不能替代完整财报分析。",
}


def card(feature, title, as_of, metrics, scope):
    return PreviewCard(
        feature=feature,
        title=title,
        purpose=PURPOSES[feature],
        as_of=as_of,
        metrics=metrics,
        scope=scope,
    )


@router.get("/samples", response_model=Preview | None)
def samples(response: Response):
    response.headers["Cache-Control"] = "no-store"
    if not settings.advanced_samples_enabled:
        return None
    return Preview(
        kind="sample",
        code="DEMO",
        name="示例公司（虚构标的）",
        cards=[
            card(
                "grid",
                "股息网格",
                "2026-09-30",
                {
                    "示例价格": "10.00 元",
                    "TTM 每股股息": "0.50 元",
                    "4% 对应价格": "12.50 元",
                    "5% 对应价格": "10.00 元",
                    "6% 对应价格": "8.33 元",
                },
                "固定教学样例 · 假设过去一年每股股息为 0.50 元；未来分红可能变化",
            ),
            card(
                "bollinger",
                "股息布林",
                "2026-09-30",
                {
                    "示例收盘价": "10.00 元",
                    "20 日中轨": "10.50 元",
                    "上轨": "11.50 元",
                    "下轨": "9.50 元",
                    "位置": "中下",
                },
                "固定教学样例 · 演示日线 20 期、2 倍标准差区间，不是实际行情",
            ),
            card(
                "financial",
                "股息财务",
                "2026-06-30",
                {"报告期": "2026 半年度", "净利润同比": "+8.00%", "净资产收益率": "6.00%"},
                "固定教学样例 · 虚构财报数值，不对应任何上市公司",
            ),
        ],
    )


def eligible(user: User) -> bool:
    if not settings.stock_preview_enabled or has_premium_access(user):
        return False
    if not user.email or not user.email_verified_at:
        return False
    internal = {x.strip() for x in settings.stock_preview_user_ids.split(",") if x.strip()}
    bucket = int(sha256(f"stock-preview-v1:{user.id}".encode()).hexdigest()[:8], 16) % 100
    return str(user.id) in internal or bucket < settings.stock_preview_percent


def choices_for(session: Session, user: User):
    return session.execute(
        select(Instrument.code, Instrument.name)
        .join(StockWatchlist, StockWatchlist.code == Instrument.code)
        .join(StockProfile, StockProfile.code == Instrument.code)
        .where(
            StockWatchlist.user_id == user.id,
            Instrument.type == "stock",
            Instrument.is_active.is_(True),
            StockProfile.status == "active",
        )
        .order_by(Instrument.code)
    ).all()


def number(value, suffix=""):
    return f"{float(value):.2f}{suffix}" if value is not None else "暂无数据"


def personal_data(session: Session, code: str, name: str) -> Preview:
    # Explicit field/range allowlist: three fixed grid levels, daily band, latest report only.
    metric = session.get(StockMetric, code)
    grid = {}
    if (
        metric
        and metric.price
        and metric.price > 0
        and metric.dividend_yield_ttm
        and metric.dividend_yield_ttm > 0
    ):
        cash = float(metric.price) * float(metric.dividend_yield_ttm) / 100
        grid = {f"{target}% 对应价格": number(cash / (target / 100), " 元") for target in (4, 5, 6)}
    bars = session.execute(
        select(MarketDaily.trade_date, MarketDaily.close)
        .where(MarketDaily.code == code)
        .order_by(MarketDaily.trade_date.desc())
        .limit(20)
    ).all()
    band = compute_bollinger([(day, float(close)) for day, close in bars])["daily"]
    daily = (
        {
            "收盘价": number(band.close, " 元"),
            "20 日中轨": number(band.mid, " 元"),
            "上轨": number(band.upper, " 元"),
            "下轨": number(band.lower, " 元"),
            "位置": band.position,
        }
        if band
        else {}
    )
    report = session.scalar(
        select(StockFinancial)
        .where(StockFinancial.code == code)
        .order_by(StockFinancial.report_date.desc())
        .limit(1)
    )
    financial = (
        {
            "报告期": report.period,
            "净利润同比": number(report.net_profit_yoy, "%"),
            "净资产收益率": number(report.roe, "%"),
            "披露日期": report.disclosure_date.isoformat()
            if report.disclosure_date
            else "暂无数据",
        }
        if report
        else {}
    )
    return Preview(
        kind="personal",
        code=code,
        name=name,
        cards=[
            card(
                "grid",
                "股息网格",
                metric.updated_at.isoformat() if metric and metric.updated_at else None,
                grid,
                "受限预览 · 仅 4%、5%、6% 三档；时间为指标更新时间，非实时行情",
            ),
            card(
                "bollinger",
                "股息布林",
                bars[0][0].isoformat() if bars else None,
                daily,
                "受限预览 · 仅最新日线 20 期，不含周线、月线及历史序列",
            ),
            card(
                "financial",
                "股息财务",
                report.report_date.isoformat() if report else None,
                financial,
                "受限预览 · 仅最新一期两项指标，不含多期财报对比",
            ),
        ],
    )


def state_for(session: Session, user: User) -> PreviewState:
    if not eligible(user):
        return PreviewState(enabled=False)
    choices = choices_for(session, user)
    selected = user.advanced_preview_code
    if selected:
        name = next((name for code, name in choices if code == selected), None)
        return PreviewState(
            enabled=True,
            selected_code=selected,
            preview=personal_data(session, selected, name) if name else None,
            message=None
            if name
            else "已绑定的股票不在当前自选或已停用；重新加入后可继续预览，不能更换绑定标的。",
        )
    return PreviewState(
        enabled=True, choices=[Choice(code=code, name=name) for code, name in choices]
    )


def no_parameters(request: Request, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    if request.query_params:
        raise HTTPException(422, "预览不支持标的、分页或时间范围查询参数")


@router.get("/personal", response_model=PreviewState, dependencies=[Depends(no_parameters)])
def personal(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
):
    return state_for(session, user)


@router.post("/personal", response_model=PreviewState, dependencies=[Depends(no_parameters)])
def select_personal(
    body: Selection,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
):
    user = lock_user(session, user)
    if not eligible(user):
        raise HTTPException(403, "当前账号未开放单标的预览")
    if user.advanced_preview_code and user.advanced_preview_code != body.code:
        raise HTTPException(409, "每个账号只能绑定一个预览标的，不能更换")
    if body.code not in {code for code, _ in choices_for(session, user)}:
        raise HTTPException(403, "只能预览自己的有效股票自选")
    user.advanced_preview_code = body.code
    session.commit()
    return state_for(session, user)

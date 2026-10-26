from fastapi import APIRouter
from pydantic import BaseModel, computed_field

from app.services.entitlements import FREE_WATCHLIST_LIMIT
from app.settings import settings

router = APIRouter(prefix="/plans", tags=["billing"])


class Plan(BaseModel):
    id: str
    name: str
    price_cny: float
    duration_days: int
    features: list[str]
    purchasable: bool
    purchase_channel: str

    @computed_field
    @property
    def billing_note(self) -> str:
        if self.duration_days == 0:
            return "基础功能免费，无需购买"
        return f"一次购买 {self.duration_days} 天，不自动扣费"


# The checkout and public catalogue share these exact product definitions.
# Do not advertise trial until its entitlement lifecycle is implemented (V2-38/39).
PLANS: list[Plan] = [
    Plan(
        id="standard-monthly",
        name="标准会员",
        price_cny=9.99,
        duration_days=30,
        features=[
            "包含免费账号基础功能",
            "股息网格 / 布林 / 财务追踪",
            "ETF + 股票自选不限数量",
            "网格提醒 / 共振提醒",
            "回测不限次数，可查看回测历史",
        ],
        purchasable=True,
        purchase_channel="ezfpy",
    ),
]

# Resolve existing orders without offering legacy products for new purchases.
LEGACY_PLANS: list[Plan] = [
    Plan(
        id="standard-yearly",
        name="标准年付（历史订单）",
        price_cny=199,
        duration_days=365,
        features=[],
        purchasable=False,
        purchase_channel="ezfpy",
    ),
]


@router.get("", response_model=list[Plan], summary="套餐与权益")
def list_plans() -> list[Plan]:
    """Use the enforced limits, including deployment overrides, in the free offer."""
    free = Plan(
        id="free",
        name="免费账号",
        price_cny=0,
        duration_days=0,
        features=[
            "ETF / 个股基础数据与市场概览",
            f"ETF + 股票自选合计最多 {FREE_WATCHLIST_LIMIT} 个",
            "涨跌提醒 / 除息提醒",
            f"登录后回测 {settings.free_daily_limit} 次/日",
            f"游客回测 {settings.guest_daily_limit} 次/日",
        ],
        purchasable=False,
        purchase_channel="none",
    )
    return [free, *PLANS]


@router.get("/notice", summary="购买渠道说明")
def purchase_notice() -> dict[str, str]:
    plan = PLANS[0]
    return {
        "notice": (
            f"标准会员 ¥{plan.price_cny:.2f}/{plan.duration_days} 天，不自动扣费。"
            "支持支付宝 / 微信支付，由易支付通道承接；也可使用会员兑换码开通。"
            "支付确认后自动开通，可在个人中心查看有效期。邀请码仅用于注册准入。"
        )
    }

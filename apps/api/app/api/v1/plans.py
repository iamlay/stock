from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/plans", tags=["billing"])


class Plan(BaseModel):
    id: str
    name: str
    price_cny: float
    duration_days: int
    features: list[str]
    purchasable: bool
    purchase_channel: str


PLANS: list[Plan] = [
    Plan(
        id="trial",
        name="7 天试用",
        price_cny=0,
        duration_days=7,
        features=["行情与 ETF 数据", "策略回测 5 次/日", "到期自动降级"],
        purchasable=False,
        purchase_channel="invite_code",
    ),
    Plan(
        id="standard-monthly",
        name="标准月付",
        price_cny=9.99,
        duration_days=30,
        features=[
            "股息网格 / 布林 / 财务",
            "自选不限数量",
            "网格提醒 / 共振提醒",
            "回测历史与导出",
        ],
        purchasable=True,
        purchase_channel="ezfpy",
    ),
]

# Keep old order products resolvable for already-created orders, but do not
# expose them in the pricing list.
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

NOTICE = (
    "会员支持支付宝 / 微信在线支付，9.99 元/月，由易支付通道收款；"
    "也可以继续使用兑换码开通。支付成功后会员权益自动到账。"
)


@router.get("", response_model=list[Plan], summary="套餐与权益")
def list_plans() -> list[Plan]:
    """Return plans. `purchasable=False` means the UI must hide checkout."""

    return PLANS


@router.get("/notice", summary="购买渠道说明")
def purchase_notice() -> dict[str, str]:
    return {"notice": NOTICE}

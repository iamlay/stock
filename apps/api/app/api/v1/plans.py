from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/plans", tags=["billing"])


class Plan(BaseModel):
    id: str
    name: str
    price_cny: int
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
        id="standard-yearly",
        name="标准年付",
        price_cny=199,
        duration_days=365,
        features=["全部行情与 ETF 数据", "策略回测 20 次/日", "回测明细导出", "会员社群"],
        purchasable=False,
        purchase_channel="third_party_redeem_code",
    ),
]

NOTICE = (
    "站内不提供在线支付，也不接入微信登录或微信支付。"
    "会员通过第三方知识付费平台购买后获得兑换码，在站内兑换开通。"
)


@router.get("", response_model=list[Plan], summary="套餐与权益")
def list_plans() -> list[Plan]:
    """Return plans. `purchasable=False` means the UI must hide checkout."""

    return PLANS


@router.get("/notice", summary="购买渠道说明")
def purchase_notice() -> dict[str, str]:
    return {"notice": NOTICE}

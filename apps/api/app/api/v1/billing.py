from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.plans import PLANS
from app.db import get_session
from app.db.models import PaymentOrder, User
from app.security import get_current_user
from app.services.membership import activate_membership
from app.settings import settings

router = APIRouter(prefix="/billing", tags=["billing"])

PLAN_BY_ID = {plan.id: plan for plan in PLANS}
PAYMENT_TYPES = {"alipay", "wxpay", "qqpay"}


class CheckoutIn(BaseModel):
    plan_id: str
    payment_type: str = Field(default="alipay")


class CheckoutOut(BaseModel):
    order_no: str
    amount: float
    pay_url: str
    method: str = "POST"
    fields: dict[str, str]


class OrderStatusOut(BaseModel):
    order_no: str
    status: str
    product: str
    amount: float
    paid_at: str | None
    plan_expires_at: str | None


def _order_no() -> str:
    return "SL" + datetime.now(UTC).strftime("%Y%m%d%H%M%S") + secrets.token_hex(3).upper()


def sign_params(params: dict[str, str], key: str) -> str:
    """EasyPay MD5 sign: ASCII sort, drop sign/sign_type, append merchant key."""
    cleaned = {
        name: value
        for name, value in params.items()
        if name not in {"sign", "sign_type"} and value is not None and value != ""
    }
    query = "&".join(f"{name}={cleaned[name]}" for name in sorted(cleaned))
    return hashlib.md5(f"{query}{key}".encode()).hexdigest()


def verify_sign(params: dict[str, str], key: str) -> bool:
    received = params.get("sign", "").lower()
    if not received:
        return False
    return sign_params(params, key) == received


def _return_url(order_no: str) -> str:
    if settings.ezfpy_return_url:
        return settings.ezfpy_return_url
    base = settings.frontend_url.rstrip("/")
    return f"{base}/account?payment=return&order={order_no}"


def _notify_url(request: Request) -> str:
    if settings.ezfpy_notify_url:
        return settings.ezfpy_notify_url
    return f"{str(request.base_url).rstrip('/')}/api/v1/billing/notify"


@router.post("/checkout", response_model=CheckoutOut, summary="创建在线支付订单")
def checkout(
    body: CheckoutIn,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> CheckoutOut:
    plan = PLAN_BY_ID.get(body.plan_id)
    if plan is None or not plan.purchasable or plan.price_cny <= 0:
        raise HTTPException(status_code=400, detail="该套餐不支持在线支付")
    if body.payment_type not in PAYMENT_TYPES:
        raise HTTPException(status_code=400, detail="不支持的支付方式")
    if not settings.ezfpy_pid or not settings.ezfpy_key:
        raise HTTPException(status_code=503, detail="支付通道尚未配置")

    amount = Decimal(str(plan.price_cny))
    order = PaymentOrder(
        order_no=_order_no(),
        platform="ezfpy",
        user_id=user.id,
        buyer_email=user.email,
        buyer_phone=user.phone,
        product=plan.id,
        amount=amount,
        status="pending",
        note=plan.name,
    )
    session.add(order)
    session.commit()
    session.refresh(order)

    fields = {
        "pid": settings.ezfpy_pid,
        "type": body.payment_type,
        "out_trade_no": order.order_no,
        "notify_url": _notify_url(request),
        "return_url": _return_url(order.order_no),
        "name": f"StockLab {plan.name}",
        "money": f"{amount:.2f}",
        "sign_type": "MD5",
    }
    fields["sign"] = sign_params(fields, settings.ezfpy_key)
    return CheckoutOut(
        order_no=order.order_no,
        amount=float(amount),
        pay_url=f"{settings.ezfpy_base_url.rstrip('/')}/submit.php",
        fields=fields,
    )


@router.api_route(
    "/notify",
    methods=["GET", "POST"],
    summary="易支付异步回调",
    include_in_schema=False,
)
async def notify(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> PlainTextResponse:
    if request.method == "POST":
        form = await request.form()
        params = {str(key): str(value) for key, value in form.items()}
    else:
        params = {key: value for key, value in request.query_params.items()}

    if not settings.ezfpy_key:
        return PlainTextResponse("fail", status_code=503)
    if not verify_sign(params, settings.ezfpy_key):
        return PlainTextResponse("fail", status_code=400)
    if params.get("pid") != settings.ezfpy_pid:
        return PlainTextResponse("fail", status_code=400)
    if params.get("trade_status") != "TRADE_SUCCESS":
        return PlainTextResponse("fail", status_code=400)

    order = session.scalar(
        select(PaymentOrder).where(PaymentOrder.order_no == params.get("out_trade_no"))
    )
    if order is None:
        return PlainTextResponse("fail", status_code=404)
    if order.status == "delivered":
        return PlainTextResponse("success")
    if order.status != "pending":
        return PlainTextResponse("fail", status_code=409)

    try:
        paid_amount = Decimal(params.get("money", "0"))
    except Exception:
        return PlainTextResponse("fail", status_code=400)
    if paid_amount != Decimal(str(order.amount)):
        return PlainTextResponse("fail", status_code=400)

    user = session.get(User, order.user_id) if order.user_id else None
    if user is None and order.buyer_email:
        user = session.scalar(
            select(User).where(User.email == order.buyer_email.lower())
        )
    if user is None:
        return PlainTextResponse("fail", status_code=404)

    plan = PLAN_BY_ID.get(order.product)
    if plan is None:
        return PlainTextResponse("fail", status_code=400)

    now = datetime.now(UTC)
    activate_membership(session, user, days=plan.duration_days, now=now)
    order.status = "delivered"
    order.paid_at = now
    order.delivered_at = now
    order.external_order_id = params.get("trade_no")
    order.raw = params
    session.commit()
    return PlainTextResponse("success")


@router.get("/order/{order_no}", response_model=OrderStatusOut, summary="查询订单状态")
def order_status(
    order_no: str,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> OrderStatusOut:
    order = session.scalar(
        select(PaymentOrder).where(
            PaymentOrder.order_no == order_no,
            PaymentOrder.user_id == user.id,
        )
    )
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    return OrderStatusOut(
        order_no=order.order_no,
        status=order.status,
        product=order.product,
        amount=float(order.amount),
        paid_at=order.paid_at.isoformat() if order.paid_at else None,
        plan_expires_at=(
            user.plan_expires_at.isoformat() if user.plan_expires_at else None
        ),
    )

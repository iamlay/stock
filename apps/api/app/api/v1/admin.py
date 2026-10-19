from __future__ import annotations

import csv
import io
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import AdminAuditLog, PaymentOrder, RedeemCode, User
from app.security import get_current_admin
from app.services.membership import new_code

router = APIRouter(prefix="/admin", tags=["admin"])


class CodeOut(BaseModel):
    code: str
    plan: str
    duration_days: int
    channel: str
    batch_id: str | None
    max_uses: int
    used_count: int
    status: str
    expires_at: str | None
    created_at: str
    redeemed_at: str | None
    order_id: int | None


class CodeStats(BaseModel):
    total: int
    issued: int
    redeemed: int
    expired: int
    revoked: int


class CodeList(BaseModel):
    items: list[CodeOut]
    stats: CodeStats
    total: int
    page: int
    page_size: int


class BatchOut(BaseModel):
    batch_id: str
    channel: str
    total: int
    issued: int
    redeemed: int
    created_at: str


class GenerateRequest(BaseModel):
    count: int = Field(default=10, ge=1, le=500)
    days: int = Field(default=365, ge=1, le=3650)
    valid_days: int = Field(default=90, ge=1, le=3650)
    plan: str = Field(default="member", pattern="^(member|trial)$")
    channel: str = Field(default="manual", min_length=1, max_length=32)


class GenerateResponse(BaseModel):
    batch_id: str
    codes: list[CodeOut]


class AuditOut(BaseModel):
    id: int
    user_id: int | None
    action: str
    target_type: str
    target_id: str | None
    detail: dict
    ip: str | None
    created_at: str


class AuditList(BaseModel):
    items: list[AuditOut]
    total: int
    page: int
    page_size: int


class OrderRequest(BaseModel):
    platform: str = Field(default="manual", max_length=32)
    external_order_id: str | None = Field(default=None, max_length=64)
    buyer_phone: str | None = Field(default=None, pattern=r"^1[3-9]\d{9}$")
    amount: float = Field(ge=0, le=1_000_000)
    days: int = Field(default=365, ge=1, le=3650)
    plan: str = Field(default="member", pattern="^(member|trial)$")
    product: str = Field(default="member-365", max_length=32)
    note: str | None = None


class OrderOut(BaseModel):
    id: int
    order_no: str
    platform: str
    external_order_id: str | None
    buyer_phone: str | None
    user_id: int | None
    product: str
    amount: float
    status: str
    note: str | None
    created_at: str
    paid_at: str | None
    delivered_at: str | None
    refunded_at: str | None
    code: str | None


class OrderList(BaseModel):
    items: list[OrderOut]
    total: int
    page: int
    page_size: int
    revenue: float


def _code_out(row: RedeemCode) -> CodeOut:
    return CodeOut(
        code=row.code,
        plan=row.plan,
        duration_days=row.duration_days,
        channel=row.channel,
        batch_id=row.batch_id,
        max_uses=row.max_uses,
        used_count=row.used_count,
        status=row.status,
        expires_at=row.expires_at.isoformat() if row.expires_at else None,
        created_at=row.created_at.isoformat(),
        redeemed_at=row.redeemed_at.isoformat() if row.redeemed_at else None,
        order_id=row.order_id,
    )


def _order_out(row: PaymentOrder, code: str | None) -> OrderOut:
    return OrderOut(
        id=row.id,
        order_no=row.order_no,
        platform=row.platform,
        external_order_id=row.external_order_id,
        buyer_phone=row.buyer_phone,
        user_id=row.user_id,
        product=row.product,
        amount=float(row.amount),
        status=row.status,
        note=row.note,
        created_at=row.created_at.isoformat(),
        paid_at=row.paid_at.isoformat() if row.paid_at else None,
        delivered_at=row.delivered_at.isoformat() if row.delivered_at else None,
        refunded_at=row.refunded_at.isoformat() if row.refunded_at else None,
        code=code,
    )


def _stats(session: Session) -> CodeStats:
    rows = dict(
        session.execute(
            select(RedeemCode.status, func.count()).group_by(RedeemCode.status)
        ).all()
    )
    return CodeStats(
        total=sum(rows.values()),
        issued=rows.get("issued", 0),
        redeemed=rows.get("redeemed", 0),
        expired=rows.get("expired", 0),
        revoked=rows.get("revoked", 0),
    )


def _audit(
    session: Session,
    admin: User,
    request: Request,
    action: str,
    target_type: str,
    target_id: str | None,
    detail: dict,
) -> None:
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else None
    )
    session.add(
        AdminAuditLog(
            user_id=admin.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip=ip,
        )
    )
    session.commit()


@router.get("/redeem-codes", response_model=CodeList, summary="兑换码列表")
def list_codes(
    session: Annotated[Session, Depends(get_session)],
    _admin: Annotated[User, Depends(get_current_admin)],
    status: str | None = Query(default=None),
    batch_id: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    q: str | None = Query(default=None, description="按兑换码模糊搜索"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> CodeList:
    conditions = []
    if status:
        conditions.append(RedeemCode.status == status)
    if batch_id:
        conditions.append(RedeemCode.batch_id == batch_id)
    if channel:
        conditions.append(RedeemCode.channel == channel)
    if q:
        conditions.append(RedeemCode.code.ilike(f"%{q.strip().upper()}%"))

    total = session.scalar(
        select(func.count()).select_from(RedeemCode).where(*conditions)
    ) or 0
    rows = session.scalars(
        select(RedeemCode)
        .where(*conditions)
        .order_by(RedeemCode.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return CodeList(
        items=[_code_out(row) for row in rows],
        stats=_stats(session),
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/redeem-codes/batches", response_model=list[BatchOut], summary="批次汇总")
def list_batches(
    session: Annotated[Session, Depends(get_session)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> list[BatchOut]:
    rows = session.execute(
        select(
            RedeemCode.batch_id,
            RedeemCode.channel,
            func.count(),
            func.sum(case((RedeemCode.status == "issued", 1), else_=0)),
            func.sum(case((RedeemCode.status == "redeemed", 1), else_=0)),
            func.min(RedeemCode.created_at),
        )
        .where(RedeemCode.batch_id.is_not(None))
        .group_by(RedeemCode.batch_id, RedeemCode.channel)
        .order_by(func.min(RedeemCode.created_at).desc())
        .limit(100)
    ).all()

    return [
        BatchOut(
            batch_id=row[0],
            channel=row[1],
            total=row[2],
            issued=int(row[3] or 0),
            redeemed=int(row[4] or 0),
            created_at=row[5].isoformat(),
        )
        for row in rows
    ]


@router.post("/redeem-codes", response_model=GenerateResponse, summary="批量生成兑换码")
def create_codes(
    payload: GenerateRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> GenerateResponse:
    from app.services.membership import generate_codes

    batch_id, rows = generate_codes(
        session,
        count=payload.count,
        days=payload.days,
        plan=payload.plan,
        channel=payload.channel,
        valid_days=payload.valid_days,
    )
    _audit(
        session,
        admin,
        request,
        action="generate_codes",
        target_type="redeem_batch",
        target_id=batch_id,
        detail={"count": len(rows), "days": payload.days, "channel": payload.channel},
    )
    return GenerateResponse(batch_id=batch_id, codes=[_code_out(row) for row in rows])


@router.post("/redeem-codes/{code}/revoke", response_model=CodeOut, summary="作废兑换码")
def revoke_code(
    code: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> CodeOut:
    row = session.get(RedeemCode, code.strip().upper())
    if row is None:
        raise HTTPException(status_code=404, detail="兑换码不存在")
    if row.status != "issued":
        raise HTTPException(status_code=400, detail="只有未使用的兑换码可以作废")
    row.status = "revoked"
    session.commit()
    _audit(
        session,
        admin,
        request,
        action="revoke_code",
        target_type="redeem_code",
        target_id=row.code,
        detail={"batch_id": row.batch_id},
    )
    return _code_out(row)


@router.get("/redeem-codes/export", summary="导出兑换码 CSV")
def export_codes(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    admin: Annotated[User, Depends(get_current_admin)],
    status: str | None = Query(default=None),
    batch_id: str | None = Query(default=None),
) -> Response:
    statement = select(RedeemCode).order_by(RedeemCode.created_at.desc())
    if status:
        statement = statement.where(RedeemCode.status == status)
    if batch_id:
        statement = statement.where(RedeemCode.batch_id == batch_id)
    rows = session.scalars(statement).all()

    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "code",
            "plan",
            "duration_days",
            "channel",
            "batch_id",
            "status",
            "used_count",
            "expires_at",
            "created_at",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.code,
                row.plan,
                row.duration_days,
                row.channel,
                row.batch_id or "",
                row.status,
                row.used_count,
                row.expires_at.isoformat() if row.expires_at else "",
                row.created_at.isoformat(),
            ]
        )

    _audit(
        session,
        admin,
        request,
        action="export_codes",
        target_type="redeem_batch",
        target_id=batch_id,
        detail={"rows": len(rows), "status": status},
    )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="redeem-codes.csv"'},
    )


@router.get("/audit-logs", response_model=AuditList, summary="后台操作日志")
def audit_logs(
    session: Annotated[Session, Depends(get_session)],
    _admin: Annotated[User, Depends(get_current_admin)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> AuditList:
    total = session.scalar(select(func.count()).select_from(AdminAuditLog)) or 0
    rows = session.scalars(
        select(AdminAuditLog)
        .order_by(AdminAuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return AuditList(
        items=[
            AuditOut(
                id=row.id,
                user_id=row.user_id,
                action=row.action,
                target_type=row.target_type,
                target_id=row.target_id,
                detail=row.detail,
                ip=row.ip,
                created_at=row.created_at.isoformat(),
            )
            for row in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


def _order_no() -> str:
    return "SO" + datetime.now(UTC).strftime("%Y%m%d") + secrets.token_hex(3).upper()


@router.post("/orders", response_model=OrderOut, summary="登记订单并发放兑换码")
def create_order(
    payload: OrderRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> OrderOut:
    now = datetime.now(UTC)
    buyer = (
        session.scalar(select(User).where(User.phone == payload.buyer_phone))
        if payload.buyer_phone
        else None
    )
    order = PaymentOrder(
        order_no=_order_no(),
        platform=payload.platform,
        external_order_id=payload.external_order_id,
        buyer_phone=payload.buyer_phone,
        user_id=buyer.id if buyer else None,
        product=payload.product,
        amount=payload.amount,
        status="delivered",
        note=payload.note,
        paid_at=now,
        delivered_at=now,
    )
    session.add(order)
    session.flush()

    code = RedeemCode(
        code=new_code(),
        plan=payload.plan,
        duration_days=payload.days,
        batch_id=order.order_no,
        channel=payload.platform,
        max_uses=1,
        bound_user_id=buyer.id if buyer else None,
        order_id=order.id,
        expires_at=now + timedelta(days=90),
    )
    session.add(code)
    session.commit()

    _audit(
        session,
        admin,
        request,
        action="create_order",
        target_type="payment_order",
        target_id=order.order_no,
        detail={"amount": payload.amount, "platform": payload.platform, "code": code.code},
    )
    return _order_out(order, code.code)


@router.get("/orders", response_model=OrderList, summary="订单列表")
def list_orders(
    session: Annotated[Session, Depends(get_session)],
    _admin: Annotated[User, Depends(get_current_admin)],
    status: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    q: str | None = Query(default=None, description="订单号/外部单号/手机号"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> OrderList:
    conditions = []
    if status:
        conditions.append(PaymentOrder.status == status)
    if platform:
        conditions.append(PaymentOrder.platform == platform)
    if q:
        like = f"%{q.strip()}%"
        conditions.append(
            (PaymentOrder.order_no.ilike(like))
            | (PaymentOrder.external_order_id.ilike(like))
            | (PaymentOrder.buyer_phone.ilike(like))
        )

    total = session.scalar(
        select(func.count()).select_from(PaymentOrder).where(*conditions)
    ) or 0
    revenue = session.scalar(
        select(func.coalesce(func.sum(PaymentOrder.amount), 0)).where(
            PaymentOrder.status == "delivered"
        )
    )
    rows = session.scalars(
        select(PaymentOrder)
        .where(*conditions)
        .order_by(PaymentOrder.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    codes = dict(
        session.execute(
            select(RedeemCode.order_id, RedeemCode.code).where(
                RedeemCode.order_id.in_([row.id for row in rows])
            )
        ).all()
    ) if rows else {}

    return OrderList(
        items=[_order_out(row, codes.get(row.id)) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        revenue=float(revenue or 0),
    )


@router.post("/orders/{order_no}/refund", response_model=OrderOut, summary="订单退款")
def refund_order(
    order_no: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> OrderOut:
    order = session.scalar(select(PaymentOrder).where(PaymentOrder.order_no == order_no))
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status == "refunded":
        raise HTTPException(status_code=400, detail="订单已退款")

    order.status = "refunded"
    order.refunded_at = datetime.now(UTC)

    code = session.scalar(select(RedeemCode).where(RedeemCode.order_id == order.id))
    if code is not None and code.status == "issued":
        code.status = "revoked"
    session.commit()

    _audit(
        session,
        admin,
        request,
        action="refund_order",
        target_type="payment_order",
        target_id=order.order_no,
        detail={"code": code.code if code else None, "revoked": code.status if code else None},
    )
    return _order_out(order, code.code if code else None)

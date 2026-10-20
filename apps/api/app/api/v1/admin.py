from __future__ import annotations

import csv
import io
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import (
    AdminAuditLog,
    BacktestRun,
    InviteCode,
    PaymentOrder,
    RedeemCode,
    User,
)
from app.security import get_current_admin
from app.services.invites import generate_invites
from app.services.membership import activate_membership, new_code

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
    buyer_email: EmailStr | None = None
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
    buyer_email: str | None
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


class AdminUserOut(BaseModel):
    id: int
    email: str | None
    phone: str | None
    role: str
    plan: str
    plan_expires_at: str | None
    status: str
    email_verified: bool
    created_at: str
    last_login_at: str | None


class AdminUserList(BaseModel):
    items: list[AdminUserOut]
    total: int
    page: int
    page_size: int


class AdminUserUpdate(BaseModel):
    status: Literal["active", "banned"] | None = None
    plan: Literal["free", "member"] | None = None
    days: int | None = Field(default=None, ge=1, le=3650)


class BacktestSummary(BaseModel):
    id: int
    code: str
    strategy: str
    total_return: float
    trades: int
    status: str
    created_at: str


class AdminUserDetail(BaseModel):
    user: AdminUserOut
    orders: list[OrderOut]
    codes: list[CodeOut]
    backtests: list[BacktestSummary]
    orders_total: int
    codes_total: int
    backtests_total: int


class AdminOrderPage(BaseModel):
    items: list[OrderOut]
    total: int
    page: int
    page_size: int


class AdminCodePage(BaseModel):
    items: list[CodeOut]
    total: int
    page: int
    page_size: int


class AdminBacktestPage(BaseModel):
    items: list[BacktestSummary]
    total: int
    page: int
    page_size: int


class AdminBacktestDetail(BaseModel):
    id: int
    created_at: str
    result: dict


class InviteOut(BaseModel):
    code: str
    batch_id: str | None
    max_uses: int
    used_count: int
    status: str
    note: str | None
    expires_at: str | None
    created_at: str


class InviteStats(BaseModel):
    total: int
    issued: int
    redeemed: int
    expired: int
    revoked: int


class InviteList(BaseModel):
    items: list[InviteOut]
    stats: InviteStats
    total: int
    page: int
    page_size: int


class InviteGenerateRequest(BaseModel):
    count: int = Field(default=10, ge=1, le=500)
    max_uses: int = Field(default=1, ge=1, le=1000)
    valid_days: int = Field(default=90, ge=1, le=3650)
    note: str | None = Field(default=None, max_length=128)


class InviteGenerateResponse(BaseModel):
    batch_id: str
    codes: list[InviteOut]


class InviteBatchOut(BaseModel):
    batch_id: str
    total: int
    issued: int
    redeemed: int
    created_at: str


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
        buyer_email=row.buyer_email,
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


def _admin_user_out(row: User) -> AdminUserOut:
    return AdminUserOut(
        id=row.id,
        email=row.email,
        phone=row.phone,
        role=row.role,
        plan=row.plan,
        plan_expires_at=row.plan_expires_at.isoformat() if row.plan_expires_at else None,
        status=row.status,
        email_verified=row.email_verified_at is not None,
        created_at=row.created_at.isoformat(),
        last_login_at=row.last_login_at.isoformat() if row.last_login_at else None,
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


@router.get("/users", response_model=AdminUserList, summary="用户列表")
def list_users(
    session: Annotated[Session, Depends(get_session)],
    _admin: Annotated[User, Depends(get_current_admin)],
    q: str | None = Query(default=None, description="邮箱或手机号"),
    plan: str | None = Query(default=None),
    status: str | None = Query(default=None),
    role: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> AdminUserList:
    conditions = []
    if q:
        like = f"%{q.strip()}%"
        conditions.append(or_(User.email.ilike(like), User.phone.ilike(like)))
    if plan:
        conditions.append(User.plan == plan)
    if status:
        conditions.append(User.status == status)
    if role:
        conditions.append(User.role == role)

    total = session.scalar(
        select(func.count()).select_from(User).where(*conditions)
    ) or 0
    rows = session.scalars(
        select(User)
        .where(*conditions)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return AdminUserList(
        items=[_admin_user_out(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/users/{user_id}", response_model=AdminUserOut, summary="更新用户状态/会员")
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> AdminUserOut:
    if payload.status is None and payload.plan is None:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if payload.status == "banned" and user.id == admin.id:
        raise HTTPException(status_code=400, detail="不能封禁自己")

    if payload.status is not None:
        user.status = payload.status
    if payload.plan == "free":
        user.plan = "free"
        user.plan_expires_at = None
    elif payload.plan == "member":
        activate_membership(
            session,
            user,
            plan="member",
            days=payload.days or 365,
        )
    session.commit()

    _audit(
        session,
        admin,
        request,
        action="update_user",
        target_type="user",
        target_id=str(user.id),
        detail={
            "status": payload.status,
            "plan": user.plan,
            "plan_expires_at": (
                user.plan_expires_at.isoformat() if user.plan_expires_at else None
            ),
        },
    )
    return _admin_user_out(user)


def _order_conditions(user: User):
    conditions = [PaymentOrder.user_id == user.id]
    if user.phone:
        conditions.append(PaymentOrder.buyer_phone == user.phone)
    if user.email:
        conditions.append(PaymentOrder.buyer_email == user.email)
    return or_(*conditions)


def _code_conditions(user: User):
    order_ids = select(PaymentOrder.id).where(_order_conditions(user))
    return or_(
        RedeemCode.bound_user_id == user.id,
        RedeemCode.redeemed_by == user.id,
        RedeemCode.order_id.in_(order_ids),
    )


def _backtest_out(row: BacktestRun) -> BacktestSummary:
    return BacktestSummary(
        id=row.id,
        code=row.code,
        strategy=row.strategy,
        total_return=float(row.metrics.get("total_return", 0)),
        trades=len((row.result or {}).get("trades") or []),
        status=row.status,
        created_at=row.created_at.isoformat(),
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail, summary="用户详情")
def get_user_detail(
    user_id: int,
    session: Annotated[Session, Depends(get_session)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> AdminUserDetail:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    order_conditions = _order_conditions(user)
    orders_total = session.scalar(
        select(func.count()).select_from(PaymentOrder).where(order_conditions)
    ) or 0
    orders = session.scalars(
        select(PaymentOrder)
        .where(order_conditions)
        .order_by(PaymentOrder.created_at.desc())
        .limit(10)
    ).all()

    code_conditions = _code_conditions(user)
    codes_total = session.scalar(
        select(func.count()).select_from(RedeemCode).where(code_conditions)
    ) or 0
    codes = session.scalars(
        select(RedeemCode)
        .where(code_conditions)
        .order_by(RedeemCode.created_at.desc())
        .limit(10)
    ).all()
    codes_by_order = {
        row.order_id: row.code for row in codes if row.order_id is not None
    }

    backtests_total = session.scalar(
        select(func.count())
        .select_from(BacktestRun)
        .where(BacktestRun.user_id == user.id)
    ) or 0
    backtests = session.scalars(
        select(BacktestRun)
        .where(BacktestRun.user_id == user.id)
        .order_by(BacktestRun.created_at.desc())
        .limit(10)
    ).all()

    return AdminUserDetail(
        user=_admin_user_out(user),
        orders=[_order_out(row, codes_by_order.get(row.id)) for row in orders],
        codes=[_code_out(row) for row in codes],
        backtests=[_backtest_out(row) for row in backtests],
        orders_total=orders_total,
        codes_total=codes_total,
        backtests_total=backtests_total,
    )


@router.get("/users/{user_id}/orders", response_model=AdminOrderPage, summary="用户订单")
def get_user_orders(
    user_id: int,
    session: Annotated[Session, Depends(get_session)],
    _admin: Annotated[User, Depends(get_current_admin)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
) -> AdminOrderPage:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    conditions = _order_conditions(user)
    total = session.scalar(
        select(func.count()).select_from(PaymentOrder).where(conditions)
    ) or 0
    rows = session.scalars(
        select(PaymentOrder)
        .where(conditions)
        .order_by(PaymentOrder.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    order_ids = [row.id for row in rows]
    codes = (
        dict(
            session.execute(
                select(RedeemCode.order_id, RedeemCode.code).where(
                    RedeemCode.order_id.in_(order_ids)
                )
            ).all()
        )
        if order_ids
        else {}
    )
    return AdminOrderPage(
        items=[_order_out(row, codes.get(row.id)) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/users/{user_id}/codes", response_model=AdminCodePage, summary="用户兑换码")
def get_user_codes(
    user_id: int,
    session: Annotated[Session, Depends(get_session)],
    _admin: Annotated[User, Depends(get_current_admin)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
) -> AdminCodePage:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    conditions = _code_conditions(user)
    total = session.scalar(
        select(func.count()).select_from(RedeemCode).where(conditions)
    ) or 0
    rows = session.scalars(
        select(RedeemCode)
        .where(conditions)
        .order_by(RedeemCode.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return AdminCodePage(
        items=[_code_out(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/users/{user_id}/backtests",
    response_model=AdminBacktestPage,
    summary="用户回测历史",
)
def get_user_backtests(
    user_id: int,
    session: Annotated[Session, Depends(get_session)],
    _admin: Annotated[User, Depends(get_current_admin)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
) -> AdminBacktestPage:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    total = session.scalar(
        select(func.count())
        .select_from(BacktestRun)
        .where(BacktestRun.user_id == user.id)
    ) or 0
    rows = session.scalars(
        select(BacktestRun)
        .where(BacktestRun.user_id == user.id)
        .order_by(BacktestRun.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return AdminBacktestPage(
        items=[_backtest_out(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/users/{user_id}/backtests/{run_id}",
    response_model=AdminBacktestDetail,
    summary="回测详情",
)
def get_user_backtest_detail(
    user_id: int,
    run_id: int,
    session: Annotated[Session, Depends(get_session)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> AdminBacktestDetail:
    row = session.get(BacktestRun, run_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(status_code=404, detail="回测不存在")
    return AdminBacktestDetail(
        id=row.id,
        created_at=row.created_at.isoformat(),
        result=row.result or {},
    )


def _invite_out(row: InviteCode) -> InviteOut:
    return InviteOut(
        code=row.code,
        batch_id=row.batch_id,
        max_uses=row.max_uses,
        used_count=row.used_count,
        status=row.status,
        note=row.note,
        expires_at=row.expires_at.isoformat() if row.expires_at else None,
        created_at=row.created_at.isoformat(),
    )


def _invite_stats(session: Session) -> InviteStats:
    rows = dict(
        session.execute(
            select(InviteCode.status, func.count()).group_by(InviteCode.status)
        ).all()
    )
    return InviteStats(
        total=sum(rows.values()),
        issued=rows.get("issued", 0),
        redeemed=rows.get("redeemed", 0),
        expired=rows.get("expired", 0),
        revoked=rows.get("revoked", 0),
    )


@router.get("/invites", response_model=InviteList, summary="邀请码列表")
def list_invites(
    session: Annotated[Session, Depends(get_session)],
    _admin: Annotated[User, Depends(get_current_admin)],
    status: str | None = Query(default=None),
    batch_id: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> InviteList:
    conditions = []
    if status:
        conditions.append(InviteCode.status == status)
    if batch_id:
        conditions.append(InviteCode.batch_id == batch_id)
    if q:
        conditions.append(InviteCode.code.ilike(f"%{q.strip().upper()}%"))
    total = session.scalar(
        select(func.count()).select_from(InviteCode).where(*conditions)
    ) or 0
    rows = session.scalars(
        select(InviteCode)
        .where(*conditions)
        .order_by(InviteCode.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return InviteList(
        items=[_invite_out(row) for row in rows],
        stats=_invite_stats(session),
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/invites/batches", response_model=list[InviteBatchOut], summary="邀请码批次")
def list_invite_batches(
    session: Annotated[Session, Depends(get_session)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> list[InviteBatchOut]:
    rows = session.execute(
        select(
            InviteCode.batch_id,
            func.count(),
            func.sum(case((InviteCode.status == "issued", 1), else_=0)),
            func.sum(case((InviteCode.status == "redeemed", 1), else_=0)),
            func.min(InviteCode.created_at),
        )
        .where(InviteCode.batch_id.is_not(None))
        .group_by(InviteCode.batch_id)
        .order_by(func.min(InviteCode.created_at).desc())
        .limit(100)
    ).all()
    return [
        InviteBatchOut(
            batch_id=row[0],
            total=row[1],
            issued=int(row[2] or 0),
            redeemed=int(row[3] or 0),
            created_at=row[4].isoformat(),
        )
        for row in rows
    ]


@router.post("/invites", response_model=InviteGenerateResponse, summary="生成邀请码")
def create_invites(
    payload: InviteGenerateRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> InviteGenerateResponse:
    batch_id, rows = generate_invites(
        session,
        count=payload.count,
        max_uses=payload.max_uses,
        valid_days=payload.valid_days,
        note=payload.note,
    )
    _audit(
        session,
        admin,
        request,
        action="generate_invites",
        target_type="invite_batch",
        target_id=batch_id,
        detail={
            "count": len(rows),
            "max_uses": payload.max_uses,
            "valid_days": payload.valid_days,
        },
    )
    return InviteGenerateResponse(
        batch_id=batch_id, codes=[_invite_out(row) for row in rows]
    )


@router.post("/invites/{code}/revoke", response_model=InviteOut, summary="作废邀请码")
def revoke_invite(
    code: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> InviteOut:
    row = session.get(InviteCode, code.strip().upper())
    if row is None:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    if row.status != "issued":
        raise HTTPException(status_code=400, detail="只有未使用的邀请码可以作废")
    row.status = "revoked"
    session.commit()
    _audit(
        session,
        admin,
        request,
        action="revoke_invite",
        target_type="invite_code",
        target_id=row.code,
        detail={"batch_id": row.batch_id},
    )
    return _invite_out(row)


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
    buyer = None
    if payload.buyer_phone:
        buyer = session.scalar(select(User).where(User.phone == payload.buyer_phone))
    if buyer is None and payload.buyer_email:
        buyer = session.scalar(
            select(User).where(User.email == str(payload.buyer_email).strip().lower())
        )
    order = PaymentOrder(
        order_no=_order_no(),
        platform=payload.platform,
        external_order_id=payload.external_order_id,
        buyer_phone=payload.buyer_phone,
        buyer_email=(
            str(payload.buyer_email).strip().lower() if payload.buyer_email else None
        ),
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
            | (PaymentOrder.buyer_email.ilike(like))
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

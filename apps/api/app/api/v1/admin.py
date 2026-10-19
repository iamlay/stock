from __future__ import annotations

import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import RedeemCode, User
from app.security import get_current_admin
from app.services.membership import generate_codes

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


class CodeStats(BaseModel):
    total: int
    issued: int
    redeemed: int
    expired: int
    revoked: int


class CodeList(BaseModel):
    items: list[CodeOut]
    stats: CodeStats


class GenerateRequest(BaseModel):
    count: int = Field(default=10, ge=1, le=500)
    days: int = Field(default=365, ge=1, le=3650)
    valid_days: int = Field(default=90, ge=1, le=3650)
    plan: str = Field(default="member", pattern="^(member|trial)$")
    channel: str = Field(default="manual", min_length=1, max_length=32)


class GenerateResponse(BaseModel):
    batch_id: str
    codes: list[CodeOut]


def _serialize(row: RedeemCode) -> CodeOut:
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


@router.get("/redeem-codes", response_model=CodeList, summary="兑换码列表")
def list_codes(
    session: Annotated[Session, Depends(get_session)],
    _admin: Annotated[User, Depends(get_current_admin)],
    status: str | None = Query(default=None),
) -> CodeList:
    statement = select(RedeemCode).order_by(RedeemCode.created_at.desc()).limit(500)
    if status:
        statement = statement.where(RedeemCode.status == status)
    rows = session.scalars(statement).all()
    return CodeList(items=[_serialize(row) for row in rows], stats=_stats(session))


@router.post("/redeem-codes", response_model=GenerateResponse, summary="批量生成兑换码")
def create_codes(
    payload: GenerateRequest,
    session: Annotated[Session, Depends(get_session)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> GenerateResponse:
    batch_id, rows = generate_codes(
        session,
        count=payload.count,
        days=payload.days,
        plan=payload.plan,
        channel=payload.channel,
        valid_days=payload.valid_days,
    )
    return GenerateResponse(batch_id=batch_id, codes=[_serialize(row) for row in rows])


@router.post("/redeem-codes/{code}/revoke", response_model=CodeOut, summary="作废兑换码")
def revoke_code(
    code: str,
    session: Annotated[Session, Depends(get_session)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> CodeOut:
    row = session.get(RedeemCode, code.strip().upper())
    if row is None:
        raise HTTPException(status_code=404, detail="兑换码不存在")
    if row.status != "issued":
        raise HTTPException(status_code=400, detail="只有未使用的兑换码可以作废")
    row.status = "revoked"
    session.commit()
    return _serialize(row)


@router.get("/redeem-codes/export", summary="导出兑换码 CSV")
def export_codes(
    session: Annotated[Session, Depends(get_session)],
    _admin: Annotated[User, Depends(get_current_admin)],
    status: str | None = Query(default=None),
) -> Response:
    statement = select(RedeemCode).order_by(RedeemCode.created_at.desc())
    if status:
        statement = statement.where(RedeemCode.status == status)
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
                row.status,
                row.used_count,
                row.expires_at.isoformat() if row.expires_at else "",
                row.created_at.isoformat(),
            ]
        )

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="redeem-codes.csv"'},
    )

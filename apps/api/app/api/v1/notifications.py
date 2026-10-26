from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import User, UserNotification
from app.security import get_current_user
from app.services.membership import has_premium_access

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    id: int
    type: str
    code: str
    title: str
    body: str
    link: str | None
    read: bool
    created_at: str


class NotificationList(BaseModel):
    items: list[NotificationOut]
    unread: int


class AlertSettings(BaseModel):
    price_pct: float = Field(ge=1, le=20)
    dividend: bool
    email: bool
    grid: bool
    grid_yield: float = Field(ge=1, le=20)
    resonance: bool


class AlertSettingsUpdate(BaseModel):
    price_pct: float | None = Field(default=None, ge=1, le=20)
    dividend: bool | None = None
    email: bool | None = None
    grid: bool | None = None
    grid_yield: float | None = Field(default=None, ge=1, le=20)
    resonance: bool | None = None


def _out(item: UserNotification) -> NotificationOut:
    return NotificationOut(
        id=item.id,
        type=item.type,
        code=item.code,
        title=item.title,
        body=item.body,
        link=item.link,
        read=item.read_at is not None,
        created_at=item.created_at.isoformat(),
    )


@router.get("", response_model=NotificationList, summary="站内提醒列表")
def list_notifications(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=100),
) -> NotificationList:
    rows = session.scalars(
        select(UserNotification)
        .where(UserNotification.user_id == user.id)
        .order_by(UserNotification.created_at.desc())
        .limit(limit)
    ).all()
    unread_count = len(
        session.scalars(
            select(UserNotification.id).where(
                UserNotification.user_id == user.id,
                UserNotification.read_at.is_(None),
            )
        ).all()
    )
    return NotificationList(
        items=[_out(item) for item in rows],
        unread=unread_count,
    )


@router.get("/unread-count", summary="未读数量")
def unread_count(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    count = len(
        session.scalars(
            select(UserNotification.id).where(
                UserNotification.user_id == user.id,
                UserNotification.read_at.is_(None),
            )
        ).all()
    )
    return {"unread": count}


@router.get("/settings", response_model=AlertSettings, summary="提醒设置")
def get_settings(
    user: Annotated[User, Depends(get_current_user)],
) -> AlertSettings:
    return AlertSettings(
        price_pct=float(user.alert_price_pct),
        dividend=user.alert_dividend,
        email=user.alert_email,
        grid=user.alert_grid and has_premium_access(user),
        grid_yield=float(user.alert_grid_yield),
        resonance=user.alert_resonance and has_premium_access(user),
    )


@router.patch("/settings", response_model=AlertSettings, summary="更新提醒设置")
def update_settings(
    body: AlertSettingsUpdate,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> AlertSettings:
    if body.price_pct is not None:
        user.alert_price_pct = body.price_pct
    if body.dividend is not None:
        user.alert_dividend = body.dividend
    if body.email is not None:
        user.alert_email = body.email
    if body.grid is not None:
        if body.grid and not has_premium_access(user):
            raise HTTPException(status_code=403, detail="网格提醒为会员专享")
        user.alert_grid = body.grid
    if body.grid_yield is not None:
        if not has_premium_access(user):
            raise HTTPException(status_code=403, detail="网格目标为会员专享")
        user.alert_grid_yield = body.grid_yield
    if body.resonance is not None:
        if body.resonance and not has_premium_access(user):
            raise HTTPException(status_code=403, detail="低位共振提醒为会员专享")
        user.alert_resonance = body.resonance
    session.commit()
    session.refresh(user)
    return AlertSettings(
        price_pct=float(user.alert_price_pct),
        dividend=user.alert_dividend,
        email=user.alert_email,
        grid=user.alert_grid and has_premium_access(user),
        grid_yield=float(user.alert_grid_yield),
        resonance=user.alert_resonance and has_premium_access(user),
    )


@router.post("/{notification_id}/read", summary="标记已读")
def mark_read(
    notification_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    row = session.scalar(
        select(UserNotification).where(
            UserNotification.id == notification_id,
            UserNotification.user_id == user.id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="notification not found")
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        session.commit()
    return {"id": row.id, "read": True}


@router.post("/read-all", summary="全部标记已读")
def mark_all_read(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    result = session.execute(
        update(UserNotification)
        .where(
            UserNotification.user_id == user.id,
            UserNotification.read_at.is_(None),
        )
        .values(read_at=datetime.now(UTC))
    )
    session.commit()
    return {"updated": result.rowcount}

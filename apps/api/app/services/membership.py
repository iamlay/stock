from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import BacktestRun, User
from app.settings import settings


def is_member(user: User | None) -> bool:
    if user is None or user.plan != "member":
        return False
    if user.plan_expires_at is None:
        return True
    return user.plan_expires_at > datetime.now(UTC)


def plan_for(user: User | None) -> str:
    if user is None:
        return "guest"
    return "member" if is_member(user) else "free"


def client_key_for(ip: str) -> str:
    return hashlib.sha256(f"{ip}:stocklab".encode()).hexdigest()[:32]


def _start_of_day() -> datetime:
    now = datetime.now(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def daily_usage(session: Session, user: User | None, client_key: str) -> int:
    statement = select(func.count()).select_from(BacktestRun).where(
        BacktestRun.created_at >= _start_of_day()
    )
    if user is not None:
        statement = statement.where(BacktestRun.user_id == user.id)
    else:
        statement = statement.where(BacktestRun.client_key == client_key)
    return session.scalar(statement) or 0


def quota_for(session: Session, user: User | None, client_key: str) -> dict:
    plan = plan_for(user)
    limit = (
        None
        if plan == "member"
        else settings.free_daily_limit
        if plan == "free"
        else settings.guest_daily_limit
    )
    used = daily_usage(session, user, client_key)
    remaining = None if limit is None else max(0, limit - used)
    return {
        "plan": plan,
        "used": used,
        "limit": limit,
        "remaining": remaining,
    }

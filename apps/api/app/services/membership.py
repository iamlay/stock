from __future__ import annotations

import hashlib
import secrets
import string
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import BacktestRun, RedeemCode, User
from app.settings import settings

CODE_ALPHABET = string.ascii_uppercase + string.digits


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def is_member(user: User | None) -> bool:
    if user is None or user.plan != "member":
        return False
    expires = _aware(user.plan_expires_at)
    if expires is None:
        return True
    return expires > datetime.now(UTC)


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


def activate_membership(
    session: Session,
    user: User,
    *,
    plan: str = "member",
    days: int = 365,
    now: datetime | None = None,
) -> datetime:
    current = now or datetime.now(UTC)
    base = current
    existing = _aware(user.plan_expires_at)
    if user.plan == "member" and existing and existing > current:
        base = existing
    user.plan = plan
    user.plan_expires_at = base + timedelta(days=days)
    return user.plan_expires_at


def redeem_code(session: Session, user: User, raw_code: str) -> dict:
    code = raw_code.strip().upper()
    row = session.scalar(
        select(RedeemCode).where(RedeemCode.code == code).with_for_update()
    )
    if row is None:
        raise ValueError("兑换码不存在")
    if row.status != "issued":
        raise ValueError("兑换码已被使用或已失效")
    if row.bound_user_id is not None and row.bound_user_id != user.id:
        raise ValueError("兑换码与当前账号不匹配")
    if row.used_count >= row.max_uses:
        raise ValueError("兑换码使用次数已达上限")

    now = datetime.now(UTC)
    expires = _aware(row.expires_at)
    if expires is not None and expires < now:
        row.status = "expired"
        session.commit()
        raise ValueError("兑换码已过期")

    row.used_count += 1
    row.redeemed_by = user.id
    row.redeemed_at = now
    if row.used_count >= row.max_uses:
        row.status = "redeemed"

    expires_at = activate_membership(
        session,
        user,
        plan=row.plan,
        days=row.duration_days,
        now=now,
    )
    session.commit()
    return {
        "code": code,
        "plan": user.plan,
        "plan_expires_at": expires_at.isoformat(),
        "duration_days": row.duration_days,
    }


def _new_code() -> str:
    return "SL" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(10))


def generate_codes(
    session: Session,
    *,
    count: int,
    days: int,
    plan: str = "member",
    channel: str = "manual",
    valid_days: int = 90,
) -> tuple[str, list[RedeemCode]]:
    batch_id = str(uuid.uuid4())
    expires_at = datetime.now(UTC) + timedelta(days=valid_days)
    rows: list[RedeemCode] = []

    for _ in range(count):
        code = _new_code()
        for _attempt in range(5):
            if session.get(RedeemCode, code) is None:
                break
            code = _new_code()
        else:
            raise RuntimeError("failed to generate a unique code")

        row = RedeemCode(
            code=code,
            plan=plan,
            duration_days=days,
            batch_id=batch_id,
            channel=channel,
            max_uses=1,
            expires_at=expires_at,
        )
        session.add(row)
        rows.append(row)

    session.commit()
    return batch_id, rows

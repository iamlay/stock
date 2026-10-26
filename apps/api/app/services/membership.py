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

TRIAL_DAYS = 7

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
    if is_member(user):
        return "member"
    expires = _aware(user.plan_expires_at)
    if user.plan == "trial" and expires and expires > datetime.now(UTC):
        return "trial"
    return "free"


def has_premium_access(user: User | None) -> bool:
    return plan_for(user) in {"member", "trial"}


def entitlements_for(user: User) -> dict:
    plan = plan_for(user)
    premium = plan in {"member", "trial"}
    expires = _aware(user.plan_expires_at)
    return {
        "state": plan,
        "source": user.entitlement_source or ("legacy" if user.plan != "free" else "free"),
        "expires_at": expires.isoformat() if expires else None,
        "trial_used": user.trial_started_at is not None or user.plan == "trial",
        "trial_eligible": bool(
            user.email and user.email_verified_at and plan == "free"
            and user.trial_started_at is None and user.plan != "trial"
        ),
        "capabilities": {
            "advanced_data": premium,
            "history": premium,
            "advanced_alerts": premium,
            "unlimited_backtests": plan == "member",
            "unlimited_watchlist": premium,
        },
        "daily_backtest_limit": None if plan == "member" else settings.free_daily_limit,
    }


def lock_user(session: Session, user: User) -> User:
    # Refresh an identity already loaded by authentication after waiting for the lock.
    return session.scalars(
        select(User).where(User.id == user.id).with_for_update()
        .execution_options(populate_existing=True)
    ).one()


class TrialUnavailable(ValueError):
    """Authenticated account is not eligible for a trial."""


def start_trial(session: Session, user: User, *, source: str = "trial") -> bool:
    user = lock_user(session, user)
    if not user.email or user.email_verified_at is None:
        raise TrialUnavailable("请先验证邮箱再领取体验")
    if is_member(user):
        raise TrialUnavailable("有效会员无需领取体验")
    if plan_for(user) == "trial":
        if source == "trial":
            return False  # Repeated starts return the original expiry, never extend it.
        raise TrialUnavailable("每个账号仅可领取一次体验")
    if user.trial_started_at is not None or user.plan == "trial":
        raise TrialUnavailable("每个账号仅可领取一次体验")
    now = datetime.now(UTC)
    user.trial_started_at = now
    user.plan = "trial"
    user.plan_expires_at = now + timedelta(days=TRIAL_DAYS)
    user.entitlement_source = source
    return True


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
        if plan in {"free", "trial"}
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
    source: str = "admin",
) -> datetime | None:
    if plan == "trial":
        start_trial(session, user, source="trial_code")
        return user.plan_expires_at
    if plan != "member" or days <= 0:
        raise ValueError("无效的会员方案")
    user = lock_user(session, user)
    current = now or datetime.now(UTC)
    base = current
    existing = _aware(user.plan_expires_at)
    if user.plan == "member" and existing is None:
        return None  # Preserve permanent memberships.
    if user.plan == "member" and existing and existing > current:
        base = existing
    user.entitlement_source = source
    user.plan = plan
    user.plan_expires_at = base + timedelta(days=days)
    return user.plan_expires_at


def redeem_code(session: Session, user: User, raw_code: str) -> dict:
    code = raw_code.strip().upper()
    row = session.scalar(
        select(RedeemCode).where(RedeemCode.code == code).with_for_update()
        .execution_options(populate_existing=True)
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

    expires_at = activate_membership(
        session, user, plan=row.plan, days=row.duration_days, now=now, source="redeem",
    )
    row.used_count += 1
    row.redeemed_by = user.id
    row.redeemed_at = now
    if row.used_count >= row.max_uses:
        row.status = "redeemed"

    session.commit()
    return {
        "code": code,
        "plan": user.plan,
        "plan_expires_at": expires_at.isoformat() if expires_at else None,
        "duration_days": TRIAL_DAYS if row.plan == "trial" else row.duration_days,
    }


def new_code() -> str:
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
        code = new_code()
        for _attempt in range(5):
            if session.get(RedeemCode, code) is None:
                break
            code = new_code()
        else:
            raise RuntimeError("failed to generate a unique code")

        row = RedeemCode(
            code=code,
            plan=plan,
            duration_days=TRIAL_DAYS if plan == "trial" else days,
            batch_id=batch_id,
            channel=channel,
            max_uses=1,
            expires_at=expires_at,
        )
        session.add(row)
        rows.append(row)

    session.commit()
    return batch_id, rows

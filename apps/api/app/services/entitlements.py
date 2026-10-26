from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import StockWatchlist, User, WatchlistItem
from app.services.membership import has_premium_access

FREE_WATCHLIST_LIMIT = 10


def watchlist_count(session: Session, user: User) -> int:
    stocks = session.scalar(
        select(func.count())
        .select_from(StockWatchlist)
        .where(StockWatchlist.user_id == user.id)
    ) or 0
    etfs = session.scalar(
        select(func.count())
        .select_from(WatchlistItem)
        .where(WatchlistItem.user_id == user.id)
    ) or 0
    return stocks + etfs


def ensure_watchlist_slot(session: Session, user: User) -> None:
    if has_premium_access(user):
        return
    if watchlist_count(session, user) >= FREE_WATCHLIST_LIMIT:
        raise HTTPException(
            status_code=403,
            detail=(
                f"免费用户最多 {FREE_WATCHLIST_LIMIT} 个自选，"
                "开通会员可无限添加"
            ),
        )


def require_member(user: User) -> None:
    if not has_premium_access(user):
        raise HTTPException(status_code=403, detail="该功能为会员专享")

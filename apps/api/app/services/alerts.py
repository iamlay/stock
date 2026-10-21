from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    EtfShareDaily,
    Instrument,
    StockDividend,
    StockMetric,
    StockWatchlist,
    User,
    UserNotification,
    WatchlistItem,
)
from app.services.email import EmailNotConfigured, EmailSendError, send_email


def _send_digest(user: User, lines: list[str]) -> bool:
    if not user.alert_email or not user.email or user.email_verified_at is None or not lines:
        return False
    try:
        send_email(
            user.email,
            "StockLab 自选提醒",
            "你关注的标的有新的提醒：\n\n" + "\n".join(f"- {line}" for line in lines),
        )
        return True
    except (EmailNotConfigured, EmailSendError):
        return False


def run_stock_alerts(session: Session, *, as_of: date | None = None) -> dict:
    """Create in-app alerts and optional email digests for watchlists."""
    today = as_of or date.today()
    user_ids = set(session.scalars(select(WatchlistItem.user_id)).all())
    user_ids.update(session.scalars(select(StockWatchlist.user_id)).all())
    if not user_ids:
        return {"users": 0, "notifications": 0, "emails": 0}

    users = session.scalars(
        select(User).where(User.id.in_(user_ids), User.status == "active")
    ).all()
    created_total = 0
    emails = 0

    for user in users:
        stock_codes = list(
            session.scalars(
                select(StockWatchlist.code).where(StockWatchlist.user_id == user.id)
            ).all()
        )
        etf_codes = list(
            session.scalars(
                select(WatchlistItem.code).where(WatchlistItem.user_id == user.id)
            ).all()
        )

        existing = set(
            session.scalars(
                select(UserNotification.dedupe_key).where(
                    UserNotification.user_id == user.id
                )
            ).all()
        )
        lines: list[str] = []
        new_count = 0

        if stock_codes:
            stock_metrics = {
                item.code: item
                for item in session.scalars(
                    select(StockMetric).where(StockMetric.code.in_(stock_codes))
                ).all()
            }
            instruments = {
                item.code: item
                for item in session.scalars(
                    select(Instrument).where(Instrument.code.in_(stock_codes))
                ).all()
            }
            threshold = float(user.alert_price_pct or 5)
            for code in stock_codes:
                metric = stock_metrics.get(code)
                instrument = instruments.get(code)
                if metric is None or instrument is None or metric.change_pct is None:
                    continue
                change = float(metric.change_pct)
                if abs(change) < threshold:
                    continue
                key = f"price:{today.isoformat()}:{code}"
                if key in existing:
                    continue
                direction = "上涨" if change > 0 else "下跌"
                title = f"{instrument.name} 今日{direction} {abs(change):.2f}%"
                session.add(
                    UserNotification(
                        user_id=user.id,
                        type="price",
                        code=code,
                        title=title,
                        body=(
                            f"{code} {instrument.name} 今日涨跌 {change:+.2f}%，"
                            f"触发阈值 {threshold:g}%。"
                        ),
                        link=f"/stocks/{code}",
                        dedupe_key=key,
                    )
                )
                existing.add(key)
                lines.append(title)
                new_count += 1

            if user.alert_dividend:
                upcoming = session.scalars(
                    select(StockDividend).where(
                        StockDividend.code.in_(stock_codes),
                        StockDividend.ex_date > today,
                        StockDividend.ex_date <= today + timedelta(days=3),
                    )
                ).all()
                for dividend in upcoming:
                    key = f"dividend:{dividend.ex_date.isoformat()}:{dividend.code}"
                    if key in existing:
                        continue
                    instrument = instruments.get(dividend.code)
                    name = instrument.name if instrument else dividend.code
                    title = f"{name} 将于 {dividend.ex_date.isoformat()} 除息"
                    session.add(
                        UserNotification(
                            user_id=user.id,
                            type="dividend",
                            code=dividend.code,
                            title=title,
                            body=(
                                f"{dividend.code} {name} 将于 {dividend.ex_date.isoformat()} 除息，"
                                f"每股现金 {float(dividend.cash_per_share):.4f} 元。"
                            ),
                            link=f"/stocks/{dividend.code}",
                            dedupe_key=key,
                        )
                    )
                    existing.add(key)
                    lines.append(title)
                    new_count += 1

        if etf_codes:
            latest_dates = (
                select(
                    EtfShareDaily.code,
                    func.max(EtfShareDaily.trade_date).label("trade_date"),
                )
                .where(EtfShareDaily.code.in_(etf_codes))
                .group_by(EtfShareDaily.code)
                .subquery()
            )
            rows = session.scalars(
                select(EtfShareDaily)
                .join(
                    latest_dates,
                    (EtfShareDaily.code == latest_dates.c.code)
                    & (EtfShareDaily.trade_date == latest_dates.c.trade_date),
                )
                .where(EtfShareDaily.code.in_(etf_codes))
            ).all()
            etf_names = {
                item.code: item.name
                for item in session.scalars(
                    select(Instrument).where(Instrument.code.in_(etf_codes))
                ).all()
            }
            threshold = float(user.alert_price_pct or 5)
            for row in rows:
                change = float(row.change_pct or 0)
                if abs(change) < threshold:
                    continue
                key = f"price:{today.isoformat()}:{row.code}"
                if key in existing:
                    continue
                name = etf_names.get(row.code, row.code)
                direction = "上涨" if change > 0 else "下跌"
                title = f"{name} 今日{direction} {abs(change):.2f}%"
                session.add(
                    UserNotification(
                        user_id=user.id,
                        type="price",
                        code=row.code,
                        title=title,
                        body=(
                            f"{row.code} {name} 今日涨跌 {change:+.2f}%，"
                            f"触发阈值 {threshold:g}%。"
                        ),
                        link=f"/etf/{row.code}",
                        dedupe_key=key,
                    )
                )
                existing.add(key)
                lines.append(title)
                new_count += 1

        if new_count:
            session.flush()
            created_total += new_count
            if _send_digest(user, lines):
                emails += 1

    session.commit()
    return {
        "users": len(users),
        "notifications": created_total,
        "emails": emails,
    }

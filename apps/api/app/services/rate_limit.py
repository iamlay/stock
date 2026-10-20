from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import RateLimitEvent


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit_key(scope: str, value: str) -> str:
    digest = hashlib.sha256(f"{scope}:{value}".encode()).hexdigest()[:32]
    return f"{scope}:{digest}"


def check_rate_limit(
    session: Session,
    *,
    key: str,
    limit: int,
    window_seconds: int,
    message: str = "操作过于频繁，请稍后再试",
) -> None:
    cutoff = datetime.now(UTC) - timedelta(seconds=window_seconds)
    count = session.scalar(
        select(func.count())
        .select_from(RateLimitEvent)
        .where(RateLimitEvent.key == key, RateLimitEvent.created_at >= cutoff)
    )
    if (count or 0) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=message,
        )
    session.add(RateLimitEvent(key=key))
    session.commit()

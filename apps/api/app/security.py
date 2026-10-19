from __future__ import annotations

import hashlib
import hmac
import time
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import User
from app.settings import settings

bearer = HTTPBearer(auto_error=False)


def _slot(timestamp: float) -> int:
    return int(timestamp // 300)


def generate_code(phone: str, timestamp: float | None = None) -> str:
    stamp = timestamp if timestamp is not None else time.time()
    digest = hmac.new(
        settings.otp_secret.encode(),
        f"{phone}:{_slot(stamp)}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{int(digest[:12], 16) % 1_000_000:06d}"


def verify_code(phone: str, code: str) -> bool:
    now = time.time()
    return any(
        hmac.compare_digest(generate_code(phone, now - offset), code) for offset in (0, 300)
    )


def create_access_token(user: User) -> str:
    expires = datetime.now(UTC) + timedelta(minutes=settings.jwt_ttl_minutes)
    payload = {
        "sub": str(user.id),
        "phone": user.phone,
        "role": user.role,
        "exp": expires,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
        ) from exc


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
        )
    payload = decode_token(credentials.credentials)
    user = session.get(User, int(payload["sub"]))
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user unavailable")
    return user

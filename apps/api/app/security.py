from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
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

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    salt_b64 = base64.b64encode(salt).decode()
    digest_b64 = base64.b64encode(digest).decode()
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt_b64}${digest_b64}"


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        scheme, n, r, p, salt_b64, digest_b64 = encoded.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.scrypt(
            password.encode(),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


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
        "ver": user.token_version,
        "exp": expires,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_action_token(user: User, purpose: str, ttl_minutes: int) -> str:
    expires = datetime.now(UTC) + timedelta(minutes=ttl_minutes)
    payload = {
        "sub": str(user.id),
        "purpose": purpose,
        "ver": user.token_version,
        "exp": expires,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_action_token(token: str, purpose: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="链接无效或已过期",
        ) from exc
    if payload.get("purpose") != purpose:
        raise HTTPException(status_code=400, detail="链接无效或已过期")
    return payload


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
    if int(payload.get("ver", 0)) != user.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="session expired")
    return user


def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[Session, Depends(get_session)],
) -> User | None:
    if credentials is None:
        return None
    payload = decode_token(credentials.credentials)
    user = session.get(User, int(payload["sub"]))
    if user is None or user.status != "active":
        return None
    if int(payload.get("ver", 0)) != user.token_version:
        return None
    return user


def get_current_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user

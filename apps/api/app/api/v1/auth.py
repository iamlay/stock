from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import User
from app.security import create_access_token, generate_code, get_current_user, verify_code
from app.settings import settings

router = APIRouter(tags=["auth"])


class SmsRequest(BaseModel):
    phone: str = Field(pattern=r"^1[3-9]\d{9}$")


class SmsResponse(BaseModel):
    sent: bool
    expires_in: int
    dev_code: str | None = None


class LoginRequest(BaseModel):
    phone: str = Field(pattern=r"^1[3-9]\d{9}$")
    code: str = Field(min_length=6, max_length=6)


class UserOut(BaseModel):
    id: int
    phone: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


@router.post("/auth/sms-code", response_model=SmsResponse, summary="发送登录验证码")
def send_sms_code(payload: SmsRequest) -> SmsResponse:
    """Dev mode returns the code; production requires a configured SMS provider."""
    if not settings.auth_dev_mode and settings.sms_provider == "none":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SMS provider is not configured",
        )

    code = generate_code(payload.phone)
    return SmsResponse(
        sent=True,
        expires_in=300,
        dev_code=code if settings.auth_dev_mode else None,
    )


@router.post("/auth/login", response_model=TokenResponse, summary="手机号登录")
def login(
    payload: LoginRequest,
    session: Annotated[Session, Depends(get_session)],
) -> TokenResponse:
    if not verify_code(payload.phone, payload.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid verification code",
        )

    user = session.scalar(select(User).where(User.phone == payload.phone))
    if user is None:
        user = User(phone=payload.phone, role="member")
        session.add(user)
    user.last_login_at = datetime.now(UTC)
    session.commit()
    session.refresh(user)

    return TokenResponse(
        access_token=create_access_token(user),
        user=UserOut(id=user.id, phone=user.phone, role=user.role),
    )


@router.get("/me", response_model=UserOut, summary="当前用户")
def me(user: Annotated[User, Depends(get_current_user)]) -> UserOut:
    return UserOut(id=user.id, phone=user.phone, role=user.role)

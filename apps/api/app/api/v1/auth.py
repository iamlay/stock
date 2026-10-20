from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import User
from app.security import (
    create_access_token,
    generate_code,
    get_current_user,
    hash_password,
    verify_code,
    verify_password,
)
from app.services.membership import is_member, redeem_code
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


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class EmailLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: int
    phone: str | None
    email: str | None
    role: str
    plan: str
    plan_expires_at: str | None
    is_member: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class RedeemRequest(BaseModel):
    code: str = Field(min_length=4, max_length=24)


class RedeemResponse(BaseModel):
    code: str
    plan: str
    plan_expires_at: str
    duration_days: int


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        phone=user.phone,
        email=user.email,
        role=user.role,
        plan=user.plan,
        plan_expires_at=user.plan_expires_at.isoformat() if user.plan_expires_at else None,
        is_member=is_member(user),
    )


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(access_token=create_access_token(user), user=_user_out(user))


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

    return _token_response(user)


@router.post("/auth/register", response_model=TokenResponse, summary="邮箱注册")
def register(
    payload: RegisterRequest,
    session: Annotated[Session, Depends(get_session)],
) -> TokenResponse:
    email = str(payload.email).strip().lower()
    existing = session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="该邮箱已注册")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        role="member",
        plan="free",
        last_login_at=datetime.now(UTC),
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="该邮箱已注册") from exc
    session.refresh(user)
    return _token_response(user)


@router.post("/auth/login/email", response_model=TokenResponse, summary="邮箱密码登录")
def login_email(
    payload: EmailLoginRequest,
    session: Annotated[Session, Depends(get_session)],
) -> TokenResponse:
    email = str(payload.email).strip().lower()
    user = session.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )
    user.last_login_at = datetime.now(UTC)
    session.commit()
    session.refresh(user)
    return _token_response(user)


@router.post("/redeem", response_model=RedeemResponse, summary="兑换码开通会员")
def redeem(
    payload: RedeemRequest,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> RedeemResponse:
    try:
        result = redeem_code(session, user, payload.code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedeemResponse(**result)


@router.get("/me", response_model=UserOut, summary="当前用户")
def me(user: Annotated[User, Depends(get_current_user)]) -> UserOut:
    return _user_out(user)

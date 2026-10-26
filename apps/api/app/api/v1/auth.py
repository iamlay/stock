from __future__ import annotations

import hmac
import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import InviteUsage, User
from app.security import (
    create_access_token,
    create_action_token,
    decode_action_token,
    generate_code,
    get_current_user,
    hash_password,
    set_auth_cookie,
    verify_code,
    verify_password,
)
from app.services.email import (
    EmailNotConfigured,
    EmailSendError,
    send_password_reset_email,
    send_verification_email,
)
from app.services.invites import consume_invite_code
from app.services.membership import (
    TrialUnavailable,
    entitlements_for,
    is_member,
    lock_user,
    redeem_code,
    start_trial,
)
from app.services.rate_limit import check_rate_limit, client_ip, rate_limit_key
from app.settings import settings

router = APIRouter(tags=["auth"])
logger = logging.getLogger(__name__)


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
    invite_code: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, pattern=r"^1[3-9]\d{9}$")
    next_path: str | None = Field(default=None, max_length=2048)


class BindPhoneRequest(BaseModel):
    phone: str = Field(pattern=r"^1[3-9]\d{9}$")
    password: str = Field(min_length=8, max_length=128)


class EmailLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: int
    phone: str | None
    email: str | None
    email_verified: bool
    role: str
    plan: str
    plan_expires_at: str | None
    is_member: bool
    entitlements: dict


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class RegisterResponse(BaseModel):
    email: EmailStr
    verification_sent: bool
    dev_verification_token: str | None = None


class ResendVerificationRequest(BaseModel):
    email: EmailStr
    next_path: str | None = Field(default=None, max_length=2048)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=10)


class VerifyEmailResponse(BaseModel):
    verified: bool
    email: EmailStr


class ResendVerificationResponse(BaseModel):
    sent: bool
    dev_verification_token: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    sent: bool
    dev_reset_token: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10)
    password: str = Field(min_length=8, max_length=128)


class ResetPasswordResponse(BaseModel):
    reset: bool


class RedeemRequest(BaseModel):
    code: str = Field(min_length=4, max_length=24)


class RedeemResponse(BaseModel):
    code: str
    plan: str
    plan_expires_at: str | None
    duration_days: int


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        phone=user.phone,
        email=user.email,
        email_verified=user.email_verified_at is not None,
        role=user.role,
        plan=user.plan,
        plan_expires_at=entitlements_for(user)["expires_at"],
        is_member=is_member(user),
        entitlements=entitlements_for(user),
    )


def _token_response(user: User, response: Response | None = None) -> TokenResponse:
    token = create_access_token(user)
    if response is not None:
        set_auth_cookie(response, token)
    return TokenResponse(access_token=token, user=_user_out(user))


def _send_verification(user: User, next_path: str | None = None) -> tuple[bool, str | None]:
    if not user.email:
        return False, None
    token = create_action_token(user, "verify_email", 60 * 24)
    try:
        send_verification_email(user.email, token, next_path)
    except EmailNotConfigured:
        logger.warning(
            "SMTP not configured; set STOCKLAB_SMTP_HOST and STOCKLAB_SMTP_FROM"
        )
        return False, None
    except EmailSendError:
        logger.exception("verification email delivery failed for %s", user.email)
        return False, None
    return True, token if settings.auth_dev_mode else None


@router.post("/auth/sms-code", response_model=SmsResponse, summary="发送登录验证码")
def send_sms_code(
    payload: SmsRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> SmsResponse:
    """Dev mode returns the code; production requires a configured SMS provider."""
    check_rate_limit(
        session,
        key=rate_limit_key("sms_phone", payload.phone),
        limit=5,
        window_seconds=3600,
        message="验证码发送过于频繁",
    )
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
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
) -> TokenResponse:
    check_rate_limit(
        session,
        key=rate_limit_key("phone_login_ip", client_ip(request)),
        limit=30,
        window_seconds=900,
        message="登录尝试过于频繁，请稍后再试",
    )
    if not verify_code(payload.phone, payload.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid verification code",
        )

    user = session.scalar(select(User).where(User.phone == payload.phone))
    if user is None:
        user = User(phone=payload.phone, role="member")
        session.add(user)
    if user.email is not None and user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="请先验证邮箱后再登录")
    user.last_login_at = datetime.now(UTC)
    session.commit()
    session.refresh(user)

    return _token_response(user, response)


@router.post("/auth/register", response_model=RegisterResponse, summary="邮箱注册")
def register(
    payload: RegisterRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> RegisterResponse:
    email = str(payload.email).strip().lower()
    phone = payload.phone or None
    check_rate_limit(
        session,
        key=rate_limit_key("register_ip", client_ip(request)),
        limit=20,
        window_seconds=3600,
        message="注册过于频繁，请稍后再试",
    )
    check_rate_limit(
        session,
        key=rate_limit_key("register_email", email),
        limit=3,
        window_seconds=3600,
        message="该邮箱注册过于频繁，请稍后再试",
    )
    existing = session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="该邮箱已注册")
    if phone:
        phone_owner = session.scalar(select(User).where(User.phone == phone))
        if phone_owner is not None:
            raise HTTPException(status_code=409, detail="该手机号已绑定其他账号")

    invite_ok = False
    used_invite = None
    if payload.invite_code:
        if settings.registration_invite_code and hmac.compare_digest(
            payload.invite_code, settings.registration_invite_code
        ):
            invite_ok = True
        else:
            try:
                used_invite = consume_invite_code(
                    session,
                    payload.invite_code,
                    email=email,
                    phone=phone,
                )
                invite_ok = True
            except ValueError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
    if settings.registration_invite_required and not invite_ok:
        raise HTTPException(status_code=403, detail="需要邀请码")
    if settings.registration_invite_code and not invite_ok:
        raise HTTPException(status_code=403, detail="邀请码无效")

    user = User(
        email=email,
        phone=phone,
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

    sent, dev_token = _send_verification(user, payload.next_path)
    if not sent:
        session.delete(user)
        session.commit()
        if not settings.email_configured:
            raise HTTPException(
                status_code=503,
                detail="邮箱服务未配置：请设置 STOCKLAB_SMTP_HOST 和 STOCKLAB_SMTP_FROM",
            )
        raise HTTPException(
            status_code=503,
            detail="验证邮件发送失败：请检查 SMTP 授权码、端口和发件人",
        )
    if used_invite is not None:
        session.add(
            InviteUsage(
                code=used_invite.code,
                user_id=user.id,
                email=email,
                phone=phone,
                ip=client_ip(request),
            )
        )
        session.commit()

    return RegisterResponse(
        email=email,
        verification_sent=True,
        dev_verification_token=dev_token,
    )


@router.post("/auth/login/email", response_model=TokenResponse, summary="邮箱密码登录")
def login_email(
    payload: EmailLoginRequest,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
) -> TokenResponse:
    email = str(payload.email).strip().lower()
    check_rate_limit(
        session,
        key=rate_limit_key("email_login_ip", client_ip(request)),
        limit=30,
        window_seconds=900,
        message="登录尝试过于频繁，请稍后再试",
    )
    check_rate_limit(
        session,
        key=rate_limit_key("email_login_account", email),
        limit=10,
        window_seconds=900,
        message="该账号登录尝试过于频繁，请稍后再试",
    )
    user = session.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )
    if user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="请先验证邮箱后再登录")
    user.last_login_at = datetime.now(UTC)
    session.commit()
    session.refresh(user)
    return _token_response(user, response)


@router.post("/auth/bind-phone", response_model=UserOut, summary="绑定手机号")
def bind_phone(
    payload: BindPhoneRequest,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> UserOut:
    if not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="密码错误")
    owner = session.scalar(
        select(User).where(User.phone == payload.phone, User.id != user.id)
    )
    if owner is not None:
        raise HTTPException(status_code=409, detail="该手机号已绑定其他账号")
    user.phone = payload.phone
    session.commit()
    session.refresh(user)
    return _user_out(user)


@router.post("/auth/verify-email", response_model=VerifyEmailResponse, summary="验证邮箱")
def verify_email(
    payload: VerifyEmailRequest,
    session: Annotated[Session, Depends(get_session)],
) -> VerifyEmailResponse:
    data = decode_action_token(payload.token, "verify_email")
    user = session.get(User, int(data["sub"]))
    if user is None or not user.email:
        raise HTTPException(status_code=400, detail="链接无效或已过期")
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC)
        session.commit()
    return VerifyEmailResponse(verified=True, email=user.email)


@router.post(
    "/auth/resend-verification",
    response_model=ResendVerificationResponse,
    summary="重发验证邮件",
)
def resend_verification(
    payload: ResendVerificationRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> ResendVerificationResponse:
    email = str(payload.email).strip().lower()
    check_rate_limit(
        session,
        key=rate_limit_key("resend_ip", client_ip(request)),
        limit=10,
        window_seconds=3600,
        message="验证邮件发送过于频繁，请稍后再试",
    )
    check_rate_limit(
        session,
        key=rate_limit_key("resend_email", email),
        limit=5,
        window_seconds=3600,
        message="该邮箱验证邮件发送过于频繁，请稍后再试",
    )
    user = session.scalar(select(User).where(User.email == email))
    dev_token: str | None = None
    if user is not None and user.email_verified_at is None:
        _sent, dev_token = _send_verification(user, payload.next_path)
    return ResendVerificationResponse(sent=True, dev_verification_token=dev_token)


@router.post(
    "/auth/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="发送密码重置邮件",
)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> ForgotPasswordResponse:
    email = str(payload.email).strip().lower()
    check_rate_limit(
        session,
        key=rate_limit_key("forgot_ip", client_ip(request)),
        limit=20,
        window_seconds=3600,
        message="请求过于频繁，请稍后再试",
    )
    check_rate_limit(
        session,
        key=rate_limit_key("forgot_email", email),
        limit=5,
        window_seconds=3600,
        message="该邮箱请求过于频繁，请稍后再试",
    )
    user = session.scalar(select(User).where(User.email == email))
    dev_token: str | None = None
    if user is not None and user.password_hash:
        token = create_action_token(user, "reset_password", 30)
        try:
            send_password_reset_email(email, token)
        except (EmailNotConfigured, EmailSendError):
            # Do not reveal whether the address exists; the response stays generic.
            pass
        else:
            if settings.auth_dev_mode:
                dev_token = token
    return ForgotPasswordResponse(sent=True, dev_reset_token=dev_token)


@router.post("/auth/reset-password", response_model=ResetPasswordResponse, summary="重置密码")
def reset_password(
    payload: ResetPasswordRequest,
    session: Annotated[Session, Depends(get_session)],
) -> ResetPasswordResponse:
    data = decode_action_token(payload.token, "reset_password")
    user = session.get(User, int(data["sub"]))
    if user is None or int(data.get("ver", 0)) != user.token_version:
        raise HTTPException(status_code=400, detail="链接无效或已过期")
    user.password_hash = hash_password(payload.password)
    user.token_version += 1
    session.commit()
    return ResetPasswordResponse(reset=True)


@router.post("/redeem", response_model=RedeemResponse, summary="兑换码开通会员")
def redeem(
    payload: RedeemRequest,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> RedeemResponse:
    lock_user(session, user)
    check_rate_limit(
        session, key=rate_limit_key("redeem-user", str(user.id)),
        limit=20, window_seconds=60,
    )
    try:
        result = redeem_code(session, user, payload.code)
    except TrialUnavailable as exc:
        session.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedeemResponse(**result)


@router.get("/me", response_model=UserOut, summary="当前用户")
def me(user: Annotated[User, Depends(get_current_user)]) -> UserOut:
    return _user_out(user)


@router.post("/membership/trial", response_model=UserOut, summary="主动开始七天体验")
def claim_trial(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> UserOut:
    lock_user(session, user)
    check_rate_limit(
        session, key=rate_limit_key("trial-user", str(user.id)),
        limit=10, window_seconds=3600,
    )
    check_rate_limit(
        session, key=rate_limit_key("trial-ip", client_ip(request)),
        limit=30, window_seconds=3600,
    )
    try:
        start_trial(session, user)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return _user_out(user)

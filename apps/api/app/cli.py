from __future__ import annotations

import argparse
import secrets
import string
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.db.models import RedeemCode, User
from app.db.session import SessionLocal
from app.services.alerts import run_stock_alerts
from app.services.invites import expire_invites
from app.services.portfolio_income import generate_due_receipts
from app.settings import settings

ALPHABET = string.ascii_uppercase + string.digits


def _new_code() -> str:
    return "SL" + "".join(secrets.choice(ALPHABET) for _ in range(10))


def cmd_gen_codes(args: argparse.Namespace) -> int:
    with SessionLocal() as session:
        rows = []
        for _ in range(args.count):
            rows.append(
                RedeemCode(
                    code=_new_code(),
                    plan=args.plan,
                    duration_days=args.days,
                    channel=args.channel,
                    max_uses=1,
                    expires_at=datetime.now(UTC) + timedelta(days=args.valid_days),
                )
            )
        session.add_all(rows)
        session.commit()

    for row in rows:
        print(f"{row.code}\t{row.plan}\t{row.duration_days}天\t{row.channel}")
    return 0


def cmd_create_admin(args: argparse.Namespace) -> int:
    with SessionLocal() as session:
        if args.email:
            email = args.email.strip().lower()
            user = session.scalar(select(User).where(User.email == email))
            if user is None:
                print(f"user not found: {email}; register on the website first")
                return 1
            user.email_verified_at = user.email_verified_at or datetime.now(UTC)
        else:
            user = session.scalar(select(User).where(User.phone == args.phone))
            if user is None:
                user = User(phone=args.phone, role="admin", plan="member")
                session.add(user)
        user.role = "admin"
        user.plan = "member"
        user.plan_expires_at = datetime.now(UTC) + timedelta(days=3650)
        session.commit()
        session.refresh(user)
    identity = user.email or user.phone
    print(f"admin ready: {identity} id={user.id}")
    return 0


def cmd_expire_invites(args: argparse.Namespace) -> int:
    with SessionLocal() as session:
        expired = expire_invites(session)
    print(f"expired invites: {expired}")
    return 0


def cmd_security_check(_: argparse.Namespace) -> int:
    failures: list[str] = []
    warnings: list[str] = []

    if settings.env != "production":
        warnings.append(f"STOCKLAB_ENV={settings.env!r}，不是 production")
    if settings.auth_dev_mode:
        failures.append("STOCKLAB_AUTH_DEV_MODE=true，生产必须关闭")
    if (
        settings.jwt_secret == "dev-only-change-me-please-32-bytes-min"
        or len(settings.jwt_secret) < 32
    ):
        failures.append("STOCKLAB_JWT_SECRET 仍是默认值或长度不足 32")
    if (
        settings.otp_secret == "dev-only-change-me-please-32-bytes-min"
        or len(settings.otp_secret) < 32
    ):
        failures.append("STOCKLAB_OTP_SECRET 仍是默认值或长度不足 32")
    if any("localhost" in origin or "127.0.0.1" in origin for origin in settings.cors_origin_list):
        warnings.append("CORS 包含 localhost，仅适合本地")
    if not settings.frontend_url.startswith("https://"):
        warnings.append("STOCKLAB_FRONTEND_URL 不是 https")
    if settings.database_url.startswith("postgresql+psycopg://stocklab:stocklab@127.0.0.1"):
        warnings.append("数据库仍指向本地默认地址")
    if not settings.email_configured:
        warnings.append("邮件服务未配置，验证/重置邮件会失败")

    print(f"env={settings.env} auth_dev_mode={settings.auth_dev_mode}")
    print(f"cors={settings.cors_origin_list}")
    print(f"frontend={settings.frontend_url}")
    print(f"email_configured={settings.email_configured}")
    for item in failures:
        print(f"FAIL {item}")
    for item in warnings:
        print(f"WARN {item}")
    if not failures and not warnings:
        print("OK security check passed")
    return 1 if failures else 0


def cmd_rotate_tokens(_: argparse.Namespace) -> int:
    with SessionLocal() as session:
        result = session.execute(
            update(User).values(token_version=User.token_version + 1)
        )
        session.commit()
    print(f"rotated token_version for {result.rowcount} users")
    return 0


def cmd_stock_alerts(_: argparse.Namespace) -> int:
    with SessionLocal() as session:
        result = run_stock_alerts(session)
    print(
        f"stock alerts users={result['users']} notifications={result['notifications']} "
        f"emails={result['emails']}"
    )
    return 0


def cmd_portfolio_receipts(_: argparse.Namespace) -> int:
    with SessionLocal() as session:
        result = generate_due_receipts(session)
    print(
        f"portfolio receipts checked={result['checked']} "
        f"created={result['created']} skipped={result['skipped']}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stocklab-admin", description="StockLab admin CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("gen-codes", help="generate redeem codes")
    gen.add_argument("--count", type=int, default=10)
    gen.add_argument("--days", type=int, default=365)
    gen.add_argument("--plan", default="member")
    gen.add_argument("--channel", default="manual")
    gen.add_argument("--valid-days", type=int, default=90, help="code expiry in days")
    gen.set_defaults(func=cmd_gen_codes)

    admin = sub.add_parser("create-admin", help="promote or create an admin user")
    identity = admin.add_mutually_exclusive_group(required=True)
    identity.add_argument("--phone", help="promote/create by phone")
    identity.add_argument("--email", help="promote an existing email account")
    admin.set_defaults(func=cmd_create_admin)

    expire = sub.add_parser("expire-invites", help="mark expired invite codes")
    expire.set_defaults(func=cmd_expire_invites)

    security = sub.add_parser("security-check", help="check production configuration")
    security.set_defaults(func=cmd_security_check)

    rotate = sub.add_parser("rotate-tokens", help="invalidate all user sessions")
    rotate.set_defaults(func=cmd_rotate_tokens)

    alerts = sub.add_parser("stock-alerts", help="send watchlist price/dividend alerts")
    alerts.set_defaults(func=cmd_stock_alerts)

    receipts = sub.add_parser(
        "portfolio-receipts",
        help="auto-create receipts for implemented events on payment day",
    )
    receipts.set_defaults(func=cmd_portfolio_receipts)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

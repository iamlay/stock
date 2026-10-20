from __future__ import annotations

import argparse
import secrets
import string
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.models import RedeemCode, User
from app.db.session import SessionLocal

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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

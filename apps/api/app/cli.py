from __future__ import annotations

import argparse
import secrets
import string
from datetime import UTC, datetime, timedelta

from app.db.models import RedeemCode
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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

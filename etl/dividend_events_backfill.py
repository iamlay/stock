"""Bounded legacy snapshots. Dry-run by default; never merges or changes legacy dividends."""

import argparse
import json


def main(argv: list[str] | None = None) -> int:
    from app.db.session import SessionLocal
    from app.services.dividend_events import backfill_legacy

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--after-id", type=int, default=0)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    with SessionLocal() as session:
        result = backfill_legacy(
            session, after_id=args.after_id, limit=args.limit, apply=args.apply
        )
        if args.apply:
            session.commit()
        print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

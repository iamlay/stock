from __future__ import annotations

import argparse
import sys
from datetime import date

from app.db.models import DataJob, DataQualityCheck
from app.db.session import SessionLocal
from app.services.status import collect_status
from sqlalchemy import desc, select

from etl.pipeline import seed_universe, sync_all, sync_calendar, sync_code
from etl.universe import ETF_BY_CODE, ETF_UNIVERSE


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def cmd_seed(_: argparse.Namespace) -> int:
    with SessionLocal() as session:
        count = seed_universe(session)
    print(f"seeded {count} ETFs")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    codes = [item.strip() for item in args.codes.split(",") if item.strip()] if args.codes else []
    unknown = [code for code in codes if code not in ETF_BY_CODE]
    if unknown:
        print(f"unknown codes: {', '.join(unknown)}", file=sys.stderr)
        return 2

    with SessionLocal() as session:
        seed_universe(session)
        targets = codes or [seed.code for seed in ETF_UNIVERSE]
        failures = 0
        all_dates: set[date] = set()

        for code in targets:
            try:
                result = sync_code(session, code, args.start, args.end)
                all_dates.update(result.dates)
                marker = "OK " if result.status == "success" else "WARN"
                print(f"{marker} {code} rows={result.rows} status={result.status}")
                for check in result.failures:
                    print(f"     ! {check.name}: {check.detail}")
            except Exception as exc:  # noqa: BLE001 - report and continue
                failures += 1
                print(f"FAIL {code}: {exc}", file=sys.stderr)

        if not args.skip_calendar:
            added = sync_calendar(session, all_dates)
            print(f"calendar: +{added} dates")

    return 1 if failures else 0


def cmd_status(_: argparse.Namespace) -> int:
    with SessionLocal() as session:
        status = collect_status(session)
    for key, value in status.items():
        print(f"{key:24} {value}")
    return 0


def cmd_quality(args: argparse.Namespace) -> int:
    with SessionLocal() as session:
        rows = session.execute(
            select(DataQualityCheck, DataJob)
            .join(DataJob, DataQualityCheck.job_id == DataJob.id, isouter=True)
            .order_by(desc(DataQualityCheck.id))
            .limit(args.limit)
        ).all()

    if not rows:
        print("no quality checks yet")
        return 0

    for check, job in rows:
        code = (job.params or {}).get("code", "?") if job else "?"
        print(f"{check.created_at:%Y-%m-%d %H:%M} {code:8} {check.check_name:22} {check.status:6} {check.detail}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stocklab-etl", description="StockLab data pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    seed = sub.add_parser("seed", help="upsert the frozen 20-ETF universe")
    seed.set_defaults(func=cmd_seed)

    sync = sub.add_parser("sync", help="sync daily bars for selected codes")
    sync.add_argument("--codes", default="", help="comma separated codes; default: all")
    sync.add_argument("--start", type=_parse_date, default=date(2016, 1, 1))
    sync.add_argument("--end", type=_parse_date, default=None)
    sync.add_argument("--skip-calendar", action="store_true")
    sync.set_defaults(func=cmd_sync)

    sync_all_cmd = sub.add_parser("sync-all", help="sync the whole universe")
    sync_all_cmd.add_argument("--start", type=_parse_date, default=date(2016, 1, 1))
    sync_all_cmd.add_argument("--end", type=_parse_date, default=None)
    sync_all_cmd.add_argument("--delay", type=float, default=0.4)
    sync_all_cmd.set_defaults(
        func=lambda args: _run_sync_all(args.start, args.end, args.delay)
    )

    status = sub.add_parser("status", help="show row counts and last job")
    status.set_defaults(func=cmd_status)

    quality = sub.add_parser("quality", help="show recent quality checks")
    quality.add_argument("--limit", type=int, default=20)
    quality.set_defaults(func=cmd_quality)

    return parser


def _run_sync_all(start: date, end: date | None, delay: float) -> int:
    with SessionLocal() as session:
        seed_universe(session)
        results = sync_all(session, start, end, delay_seconds=delay)
    failures = [item for item in results if item.status == "failed"]
    warnings = [item for item in results if item.status == "warning"]
    print(f"synced {len(results)} codes, failures={len(failures)}, warnings={len(warnings)}")
    for item in failures:
        print(f"  FAIL {item.code}: {item.error}", file=sys.stderr)
    for item in warnings:
        print(f"  WARN {item.code}: {', '.join(check.name for check in item.failures)}")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

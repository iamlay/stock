from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

from app.db.models import DataJob, DataQualityCheck
from app.db.session import SessionLocal
from app.services.invites import expire_invites
from app.services.status import collect_status
from sqlalchemy import desc, select

from etl.phase0 import print_report, run_probe
from etl.pipeline import (
    is_trading_session,
    seed_universe,
    sync_all,
    sync_calendar,
    sync_code,
    sync_quotes,
    sync_shares,
    sync_valuation,
)
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


def cmd_sync_shares(args: argparse.Namespace) -> int:
    codes = [item.strip() for item in args.codes.split(",") if item.strip()] if args.codes else None
    with SessionLocal() as session:
        seed_universe(session)
        result = sync_shares(session, codes)

    print(f"shares rows={result['rows']} status={result['status']} latest={result['latest']}")
    for check in result["checks"]:
        if check.status != "pass":
            print(f"  {check.status.upper()} {check.name}: {check.detail}")
    return 0


def cmd_sync_quotes(args: argparse.Namespace) -> int:
    codes = [item.strip() for item in args.codes.split(",") if item.strip()] if args.codes else None
    with SessionLocal() as session:
        seed_universe(session)
        if not args.force and not is_trading_session(session):
            print("skip: outside A-share trading session")
            return 0
        result = sync_quotes(session, codes)
    print(f"quotes rows={result['quotes']} latest={result['latest']}")
    return 0


def cmd_cron(args: argparse.Namespace) -> int:
    with SessionLocal() as session:
        seed_universe(session)
        expired = expire_invites(session)
        quotes = None
        if args.force or is_trading_session(session):
            quotes = sync_quotes(session)

    if quotes is None:
        print(f"cron: quotes skipped, expired_invites={expired}")
    else:
        print(
            f"cron: quotes={quotes['quotes']} latest={quotes['latest']} "
            f"expired_invites={expired}"
        )
    return 0


def cmd_stock_probe(args: argparse.Namespace) -> int:
    out = Path(args.out)
    report = run_probe(
        samples=args.samples,
        bars=args.bars,
        out_path=out,
        max_pages=args.max_pages,
    )
    print_report(report, out)
    return 0


def cmd_sync_valuation(_: argparse.Namespace) -> int:
    with SessionLocal() as session:
        seed_universe(session)
        result = sync_valuation(session)

    print(f"valuation rows={result['rows']} status={result['status']} latest={result['latest']}")
    for check in result["checks"]:
        if check.status != "pass":
            print(f"  {check.status.upper()} {check.name}: {check.detail}")
    for error in result["errors"]:
        print(f"  ERROR {error}", file=sys.stderr)
    return 0


def cmd_daily(args: argparse.Namespace) -> int:
    start = args.start or (date.today() - timedelta(days=30))
    with SessionLocal() as session:
        seed_universe(session)
        bars = sync_all(session, start, None, delay_seconds=args.delay)
        shares = sync_shares(session)
        valuation = sync_valuation(session)

    failed_bars = [item for item in bars if item.status == "failed"]
    print(
        f"daily: bars={len(bars)} failures={len(failed_bars)} "
        f"shares={shares['rows']} valuation={valuation['rows']}"
    )
    return 1 if failed_bars else 0


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

    shares = sub.add_parser("sync-shares", help="snapshot ETF shares/AUM from Tencent")
    shares.add_argument("--codes", default="", help="comma separated codes; default: all")
    shares.set_defaults(func=cmd_sync_shares)

    quotes = sub.add_parser("sync-quotes", help="refresh latest ETF quotes")
    quotes.add_argument("--codes", default="", help="comma separated codes; default: all")
    quotes.add_argument("--force", action="store_true", help="ignore trading session guard")
    quotes.set_defaults(func=cmd_sync_quotes)

    cron = sub.add_parser("cron", help="5-minute maintenance: quotes + invite expiry")
    cron.add_argument("--force", action="store_true", help="ignore trading session guard")
    cron.set_defaults(func=cmd_cron)

    probe = sub.add_parser("stock-probe", help="Phase 0: validate full-market stock sources")
    probe.add_argument("--samples", type=int, default=10)
    probe.add_argument("--bars", type=int, default=3)
    probe.add_argument("--max-pages", type=int, default=None)
    probe.add_argument("--out", default="etl/out/stock_phase0.json")
    probe.set_defaults(func=cmd_stock_probe)

    valuation = sub.add_parser("sync-valuation", help="snapshot index PE/PB percentiles")
    valuation.set_defaults(func=cmd_sync_valuation)

    daily = sub.add_parser("daily", help="incremental daily refresh for all datasets")
    daily.add_argument("--start", type=_parse_date, default=None)
    daily.add_argument("--delay", type=float, default=0.2)
    daily.set_defaults(func=cmd_daily)

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

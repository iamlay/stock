from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

from app.db.models import (
    DataJob,
    DataQualityCheck,
    StockDividend,
    StockMetric,
    StockProfile,
)
from app.db.session import SessionLocal
from app.services.invites import expire_invites
from app.services.status import collect_status
from sqlalchemy import desc, func, select

from etl.industry_phase0 import print_report as print_industry_report
from etl.industry_phase0 import run_probe as run_industry_probe
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
from etl.sources.sina_stock import fetch_stock_universe as fetch_sina_stocks
from etl.stock_quality import (
    run_stock_quality,
    write_quality_checks,
)
from etl.stock_quality import (
    write_report as write_quality_report,
)
from etl.stocks import (
    enrich_stock_industries,
    refresh_stock_metrics,
    sync_stock_daily,
    sync_stock_dividends,
    sync_stock_dividends_bulk,
    sync_stock_pilot,
    sync_stock_quote,
    upsert_stock_universe,
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


def cmd_stock_industry_probe(args: argparse.Namespace) -> int:
    out = Path(args.out)
    report = run_industry_probe(
        samples=args.samples,
        max_nodes=args.max_nodes,
        out_path=out,
    )
    print_industry_report(report, out)
    return 0


def cmd_stock_universe(args: argparse.Namespace) -> int:
    with SessionLocal() as session:
        total, rows = fetch_sina_stocks()
        codes = upsert_stock_universe(session, rows, limit=args.limit)
    print(f"stocks universe={total} stored={len(codes)} limit={args.limit}")
    return 0


def cmd_stock_dividends(args: argparse.Namespace) -> int:
    with SessionLocal() as session:
        query = (
            select(StockProfile.code)
            .join(StockMetric, StockMetric.code == StockProfile.code)
            .where(StockProfile.status == "active")
            .order_by(StockMetric.market_cap.desc())
        )
        if args.limit:
            query = query.limit(args.limit)
        codes = list(session.scalars(query).all())
        result = sync_stock_dividends(session, codes, delay=args.delay)
        refreshed = refresh_stock_metrics(session, codes)
    print(
        f"stock dividends codes={result['codes']} written={result['written']} "
        f"errors={len(result['errors'])} metrics={refreshed}"
    )
    return 1 if result["errors"] and args.strict else 0


def cmd_stock_dividends_bulk(args: argparse.Namespace) -> int:
    with SessionLocal() as session:
        result = sync_stock_dividends_bulk(session, days=args.days)
    print(
        f"stock dividends bulk codes={result['codes']} records={result['records']} "
        f"written={result['written']} metrics={result.get('metrics', 0)}"
    )
    return 0


def cmd_stock_metrics(args: argparse.Namespace) -> int:
    with SessionLocal() as session:
        codes = None
        if args.limit:
            codes = list(
                session.scalars(
                    select(StockMetric.code)
                    .order_by(StockMetric.market_cap.desc())
                    .limit(args.limit)
                ).all()
            )
        refreshed = refresh_stock_metrics(session, codes)
    print(f"stock metrics refreshed={refreshed}")
    return 0


def cmd_stock_sync(args: argparse.Namespace) -> int:
    with SessionLocal() as session:
        result = sync_stock_quote(session, args.code)
    print(f"stock sync {args.code} dividends={result['written']} errors={len(result['errors'])}")
    return 1 if result["errors"] else 0


def cmd_stock_pilot(args: argparse.Namespace) -> int:
    with SessionLocal() as session:
        result = sync_stock_pilot(
            session,
            limit=args.limit,
            dividend_limit=args.dividend_limit,
            delay=args.delay,
        )
    print(
        f"stock pilot universe={result['universe']} stored={result['stored']} "
        f"dividend_codes={result['dividend_codes']} dividends={result['dividends']} "
        f"errors={len(result['errors'])} metrics={result['metrics']}"
    )
    return 0


def cmd_stock_status(_: argparse.Namespace) -> int:
    with SessionLocal() as session:
        profiles = session.scalar(select(func.count()).select_from(StockProfile)) or 0
        metrics = session.scalar(select(func.count()).select_from(StockMetric)) or 0
        dividends = session.scalar(select(func.count()).select_from(StockDividend)) or 0
        with_yield = (
            session.scalar(
                select(func.count())
                .select_from(StockMetric)
                .where(StockMetric.dividend_yield_ttm.is_not(None))
            )
            or 0
        )
        st_count = (
            session.scalar(
                select(func.count()).select_from(StockProfile).where(StockProfile.is_st.is_(True))
            )
            or 0
        )
    print(
        f"stocks profiles={profiles} metrics={metrics} dividends={dividends} "
        f"with_yield={with_yield} st={st_count}"
    )
    return 0


def cmd_stock_quality(args: argparse.Namespace) -> int:
    with SessionLocal() as session:
        report = run_stock_quality(session, limit=args.limit)
        if args.write:
            write_quality_checks(session, report)
    write_quality_report(report, Path(args.out))
    summary = report["summary"]
    print(
        f"stock quality metrics={summary['metrics']} st={summary['st']} "
        f"issues={summary['issues']} fail={summary['fail']} warn={summary['warn']}"
    )
    for name, check in summary["checks"].items():
        print(f"  {check['status'].upper():4} {name:20} count={check['count']}")
    print("top yields:")
    for item in summary["top_yields"][:10]:
        print(
            f"  {item['code']} {item['name']} "
            f"ttm={item['yield_ttm']} fy={item['yield_fy']} price={item['price']}"
        )
    print(f"report: {args.out}")
    if args.fail_on_fail and summary["fail"] > 0:
        return 1
    return 0


def cmd_stock_industry(args: argparse.Namespace) -> int:
    with SessionLocal() as session:
        result = enrich_stock_industries(
            session,
            limit=args.limit,
            include_sina=not args.skip_sina,
            sina_only=args.sina_only,
            sina_prefix=args.sina_prefix,
            overwrite=args.overwrite,
            delay=args.delay,
        )
    print(
        f"stock industry selected={result['selected']} sina={result['sina']} "
        f"eastmoney={result['eastmoney']} errors={len(result['errors'])}"
    )
    return 0


def cmd_stock_daily(args: argparse.Namespace) -> int:
    with SessionLocal() as session:
        result = sync_stock_daily(
            session,
            include_dividends=args.dividends,
            dividend_limit=args.dividend_limit,
            delay=args.delay,
        )
    print(
        f"stock daily universe={result['universe']} matched={result['matched']} "
        f"dividends={result['dividends']} errors={len(result['errors'])} "
        f"metrics={result['metrics']}"
    )
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

    industry = sub.add_parser(
        "stock-industry-probe",
        help="Phase 0: validate industry data sources",
    )
    industry.add_argument("--samples", type=int, default=20)
    industry.add_argument("--max-nodes", type=int, default=None)
    industry.add_argument("--out", default="etl/out/stock_industry_phase0.json")
    industry.set_defaults(func=cmd_stock_industry_probe)

    stock_universe = sub.add_parser("stock-universe", help="sync A-share stock list")
    stock_universe.add_argument("--limit", type=int, default=None)
    stock_universe.set_defaults(func=cmd_stock_universe)

    stock_quality = sub.add_parser("stock-quality", help="check stock data quality")
    stock_quality.add_argument("--limit", type=int, default=None)
    stock_quality.add_argument("--write", action="store_true")
    stock_quality.add_argument("--fail-on-fail", action="store_true")
    stock_quality.add_argument("--out", default="etl/out/stock_quality.json")
    stock_quality.set_defaults(func=cmd_stock_quality)

    stock_daily = sub.add_parser("stock-daily", help="refresh existing stock prices")
    stock_daily.add_argument("--dividends", action="store_true")
    stock_daily.add_argument("--dividend-limit", type=int, default=None)
    stock_daily.add_argument("--delay", type=float, default=0.15)
    stock_daily.set_defaults(func=cmd_stock_daily)

    stock_dividends = sub.add_parser("stock-dividends", help="sync stock dividends")
    stock_dividends.add_argument("--limit", type=int, default=None)
    stock_dividends.add_argument("--delay", type=float, default=0.2)
    stock_dividends.add_argument("--strict", action="store_true")
    stock_dividends.set_defaults(func=cmd_stock_dividends)

    stock_dividends_bulk = sub.add_parser(
        "stock-dividends-bulk",
        help="sync all dividends in bulk",
    )
    stock_dividends_bulk.add_argument("--days", type=int, default=730)
    stock_dividends_bulk.set_defaults(func=cmd_stock_dividends_bulk)

    stock_metrics = sub.add_parser("stock-metrics", help="recompute stock yields")
    stock_metrics.add_argument("--limit", type=int, default=None)
    stock_metrics.set_defaults(func=cmd_stock_metrics)

    stock_industry = sub.add_parser("stock-industry", help="enrich stock industries")
    stock_industry.add_argument("--limit", type=int, default=500)
    stock_industry.add_argument("--delay", type=float, default=0.2)
    stock_industry.add_argument("--skip-sina", action="store_true")
    stock_industry.add_argument("--sina-only", action="store_true")
    stock_industry.add_argument("--sina-prefix", default="sw_")
    stock_industry.add_argument("--overwrite", action="store_true")
    stock_industry.set_defaults(func=cmd_stock_industry)

    stock_sync = sub.add_parser("stock-sync", help="sync one stock on demand")
    stock_sync.add_argument("--code", required=True)
    stock_sync.set_defaults(func=cmd_stock_sync)

    stock_pilot = sub.add_parser("stock-pilot", help="seed and sync a pilot universe")
    stock_pilot.add_argument("--limit", type=int, default=500)
    stock_pilot.add_argument("--dividend-limit", type=int, default=100)
    stock_pilot.add_argument("--delay", type=float, default=0.2)
    stock_pilot.set_defaults(func=cmd_stock_pilot)

    sub.add_parser("stock-status", help="stock module row counts").set_defaults(
        func=cmd_stock_status
    )

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

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from datetime import time as clock_time
from decimal import Decimal
from itertools import groupby
from zoneinfo import ZoneInfo

from app.db.models import (
    DataJob,
    DataQualityCheck,
    EtfProfile,
    EtfShareDaily,
    IndexValuation,
    Instrument,
    MarketDaily,
    PortfolioAccount,
    PortfolioEntry,
    RealtimeQuote,
    StockRealtimeQuote,
    StockWatchlist,
    TradingCalendar,
)
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from etl.quality import (
    CheckResult,
    check_series,
    expected_latest_trading_day,
    has_failures,
)
from etl.sources.danjuan import fetch_valuation
from etl.sources.eastmoney import DailySeries, fetch_daily
from etl.sources.tencent import fetch_daily_tencent
from etl.sources.tencent_quote import fetch_quotes
from etl.universe import ETF_BY_CODE, ETF_UNIVERSE, VALUATION_INDEX


@dataclass
class SyncResult:
    code: str
    rows: int
    status: str
    checks: list[CheckResult]
    dates: tuple[date, ...] = ()
    error: str | None = None

    @property
    def failures(self) -> list[CheckResult]:
        return [check for check in self.checks if check.status == "fail"]


def seed_universe(session: Session) -> int:
    """Upsert the frozen ETF universe and its profile rows."""
    codes = [seed.code for seed in ETF_UNIVERSE]
    instruments = {
        item.code: item
        for item in session.scalars(
            select(Instrument).where(Instrument.code.in_(codes))
        ).all()
    }
    profiles = {
        item.code: item
        for item in session.scalars(
            select(EtfProfile).where(EtfProfile.code.in_(codes))
        ).all()
    }

    for seed in ETF_UNIVERSE:
        instrument = instruments.get(seed.code)
        if instrument is None:
            instrument = Instrument(
                code=seed.code,
                name=seed.name,
                type="etf",
                exchange=seed.exchange,
                lot_size=100,
                is_active=True,
            )
            session.add(instrument)
            instruments[seed.code] = instrument
        else:
            instrument.name = seed.name
            instrument.type = "etf"
            instrument.exchange = seed.exchange
            instrument.is_active = True

        profile = profiles.get(seed.code)
        if profile is None:
            profile = EtfProfile(
                code=seed.code,
                category=seed.category,
                tracked_index=seed.tracked_index,
                valuation_index=VALUATION_INDEX.get(seed.code),
                extra={},
            )
            session.add(profile)
            profiles[seed.code] = profile
        else:
            profile.category = seed.category
            profile.tracked_index = seed.tracked_index
            profile.valuation_index = VALUATION_INDEX.get(seed.code)

    # Retire ETFs removed from the curated universe so /etfs stays at 100.
    session.execute(
        update(Instrument)
        .where(Instrument.type == "etf", Instrument.code.notin_(codes))
        .values(is_active=False)
    )
    session.commit()
    return len(ETF_UNIVERSE)


def _bar_rows(series: DailySeries) -> list[dict]:
    rows: list[dict] = []
    previous_close: float | None = None
    for bar in series.bars:
        rows.append(
            {
                "code": series.code,
                "trade_date": bar.trade_date,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "prev_close": previous_close,
                "volume": bar.volume,
                "amount": bar.amount,
                "amplitude": bar.amplitude,
                "adj_factor": 1,
                "source": series.source,
            }
        )
        previous_close = bar.close
    return rows


def replace_bars(session: Session, series: DailySeries) -> int:
    """Idempotently replace the [first, last] window for one code."""
    if not series.bars:
        return 0

    first, last = series.bars[0].trade_date, series.bars[-1].trade_date
    session.execute(
        delete(MarketDaily).where(
            MarketDaily.code == series.code,
            MarketDaily.trade_date >= first,
            MarketDaily.trade_date <= last,
        )
    )
    rows = _bar_rows(series)
    session.bulk_insert_mappings(MarketDaily, rows)
    return len(rows)


def sync_calendar(session: Session, dates: set[date]) -> int:
    if not dates:
        return 0
    existing = set(
        session.scalars(
            select(TradingCalendar.trade_date).where(
                TradingCalendar.trade_date >= min(dates),
                TradingCalendar.trade_date <= max(dates),
            )
        ).all()
    )
    missing = sorted(dates - existing)
    if missing:
        session.bulk_insert_mappings(
            TradingCalendar,
            [{"trade_date": item, "source": "eastmoney"} for item in missing],
        )
    session.commit()
    return len(missing)


def sync_shares(session: Session, codes: list[str] | None = None) -> dict:
    """Snapshot ETF shares / AUM from Tencent's batched quote endpoint."""
    targets = codes or [seed.code for seed in ETF_UNIVERSE]
    job = DataJob(
        job_name="etf_shares",
        status="running",
        params={"codes": targets},
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    try:
        quotes = fetch_quotes(targets)
        if not quotes:
            raise ValueError("no quotes returned")

        for quote in quotes:
            session.execute(
                delete(EtfShareDaily).where(
                    EtfShareDaily.code == quote.code,
                    EtfShareDaily.trade_date == quote.trade_date,
                )
            )
            session.execute(
                delete(MarketDaily).where(
                    MarketDaily.code == quote.code,
                    MarketDaily.trade_date == quote.trade_date,
                )
            )
            session.add(
                MarketDaily(
                    code=quote.code,
                    trade_date=quote.trade_date,
                    open=quote.open or quote.price,
                    high=quote.high or quote.price,
                    low=quote.low or quote.price,
                    close=quote.price,
                    prev_close=quote.prev_close,
                    volume=quote.volume,
                    amount=quote.amount,
                    amplitude=round(
                        (quote.high - quote.low) / quote.prev_close * 100, 4
                    )
                    if quote.prev_close
                    else 0,
                    adj_factor=1,
                    source="tencent_quote",
                )
            )

        session.bulk_insert_mappings(
            EtfShareDaily,
            [
                {
                    "code": quote.code,
                    "trade_date": quote.trade_date,
                    "shares": quote.shares,
                    "aum": quote.aum,
                    "close": quote.price,
                    "change_pct": quote.change_pct,
                    "source": "tencent",
                }
                for quote in quotes
            ],
        )
        session.flush()

        latest = max(quote.trade_date for quote in quotes)
        lag = (date.today() - latest).days
        checks = [
            CheckResult(
                name="quotes_complete",
                status="pass" if len(quotes) == len(targets) else "warn",
                detail={"expected": len(targets), "received": len(quotes)},
            ),
            CheckResult(
                name="positive_aum",
                status="pass" if all(quote.aum > 0 for quote in quotes) else "fail",
                detail={"violations": sum(1 for quote in quotes if quote.aum <= 0)},
            ),
            CheckResult(
                name="positive_price",
                status="pass" if all(quote.price > 0 for quote in quotes) else "fail",
                detail={"violations": sum(1 for quote in quotes if quote.price <= 0)},
            ),
            CheckResult(
                name="freshness",
                status="pass" if lag <= 7 else "warn",
                detail={"latest": latest.isoformat(), "lag_days": lag},
            ),
        ]

        job.status = "warning" if has_failures(checks) else "success"
        job.rows_written = len(quotes)
        job.finished_at = datetime.now(UTC)
        for check in checks:
            session.add(
                DataQualityCheck(
                    job_id=job.id,
                    check_name=check.name,
                    status=check.status,
                    detail=check.detail,
                )
            )
        session.commit()
        return {
            "rows": len(quotes),
            "status": job.status,
            "latest": latest.isoformat(),
            "checks": checks,
        }
    except Exception as exc:
        session.rollback()
        failed = session.get(DataJob, job.id)
        if failed is not None:
            failed.status = "failed"
            failed.error = str(exc)[:2000]
            failed.finished_at = datetime.now(UTC)
            session.commit()
        raise


def is_trading_session(session: Session, now: datetime | None = None) -> bool:
    """True during A-share sessions on weekdays.

    Deliberately does not require today's trading_calendar row: that row is
    written by the evening ETL, so checking it would skip the whole trading day.
    Holidays may fetch a stale snapshot, which is harmless.
    """
    local = (now or datetime.now(UTC)).astimezone(ZoneInfo("Asia/Shanghai"))
    if local.weekday() >= 5:
        return False
    current = local.time()
    return (clock_time(9, 30) <= current <= clock_time(11, 30)) or (
        clock_time(13, 0) <= current <= clock_time(15, 0)
    )


def sync_stock_watchlist_quotes(
    session: Session, codes: list[str] | None = None
) -> dict:
    """Refresh the deduplicated union of watchlists and open, unarchived holdings."""
    if codes is None:
        codes = list(
            session.scalars(
                select(StockWatchlist.code)
                .join(Instrument, Instrument.code == StockWatchlist.code)
                .where(Instrument.is_active.is_(True))
                .distinct()
            ).all()
        )
        # Replay the same immutable ledger as the holdings page: snapshots/adjustments
        # replace quantity and reversals remove superseded facts, so SQL SUM is unsafe.
        # Only public stock codes go to the quote provider, never account/quantity data.
        from app.services.portfolio_positions import project

        entries = session.scalars(
            select(PortfolioEntry)
            .join(
                PortfolioAccount,
                (PortfolioAccount.id == PortfolioEntry.account_id)
                & (PortfolioAccount.user_id == PortfolioEntry.user_id),
            )
            .join(Instrument, Instrument.code == PortfolioEntry.code)
            .where(
                PortfolioAccount.is_archived.is_(False),
                Instrument.is_active.is_(True),
                Instrument.type == "stock",
            )
            .order_by(PortfolioEntry.account_id)
            .execution_options(yield_per=1000)
        )
        for _, rows in groupby(entries, key=lambda row: row.account_id):
            codes.extend(
                p["code"] for p in project(list(rows)) if Decimal(p["quantity"]) > 0
            )
    codes = sorted(set(codes))
    if not codes:
        return {"codes": 0, "quotes": 0, "latest": None}

    job = DataJob(
        job_name="stock_watchlist_quotes",
        status="running",
        params={"codes": codes},
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    try:
        quotes = []
        for index in range(0, len(codes), 50):
            quotes.extend(fetch_quotes(codes[index : index + 50]))
        if not quotes:
            raise ValueError("no stock quotes returned")

        for quote in quotes:
            quoted_at = quote.quote_time.replace(
                tzinfo=ZoneInfo("Asia/Shanghai")
            ).astimezone(UTC)
            row = session.get(StockRealtimeQuote, quote.code)
            if row is None:
                row = StockRealtimeQuote(code=quote.code)
                session.add(row)
            row.price = quote.price
            row.prev_close = quote.prev_close
            row.change_pct = quote.change_pct
            row.amount = quote.amount
            row.trade_date = quote.trade_date
            row.quote_time = quoted_at
            row.source = "tencent"

        job.status = "success"
        job.rows_written = len(quotes)
        job.finished_at = datetime.now(UTC)
        session.commit()
        return {
            "codes": len(codes),
            "quotes": len(quotes),
            "latest": max(quote.quote_time for quote in quotes).isoformat(),
        }
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)[:1000]
        job.finished_at = datetime.now(UTC)
        session.commit()
        raise


def sync_quotes(session: Session, codes: list[str] | None = None) -> dict:
    """Refresh the latest quote snapshot without touching daily bars."""
    targets = codes or [seed.code for seed in ETF_UNIVERSE]
    job = DataJob(
        job_name="realtime_quotes",
        status="running",
        params={"codes": targets},
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    try:
        quotes = fetch_quotes(targets)
        if not quotes:
            raise ValueError("no quotes returned")

        for quote in quotes:
            quoted_at = quote.quote_time.replace(
                tzinfo=ZoneInfo("Asia/Shanghai")
            ).astimezone(UTC)
            row = session.get(RealtimeQuote, quote.code)
            if row is None:
                row = RealtimeQuote(code=quote.code)
                session.add(row)
            row.price = quote.price
            row.prev_close = quote.prev_close
            row.change_pct = quote.change_pct
            row.amount = quote.amount
            row.trade_date = quote.trade_date
            row.quote_time = quoted_at
            row.source = "tencent"

        job.status = "success"
        job.rows_written = len(quotes)
        job.finished_at = datetime.now(UTC)
        session.commit()
        return {
            "quotes": len(quotes),
            "latest": max(quote.quote_time for quote in quotes).isoformat(),
        }
    except Exception as exc:
        session.rollback()
        job = session.get(DataJob, job.id)
        if job is not None:
            job.status = "failed"
            job.error = str(exc)[:500]
            job.finished_at = datetime.now(UTC)
            session.commit()
        raise


def sync_valuation(session: Session, index_codes: list[str] | None = None) -> dict:
    """Snapshot PE/PB/percentile for the indices mapped to our ETFs."""
    if index_codes is None:
        index_codes = sorted(
            {
                profile.valuation_index
                for profile in session.scalars(select(EtfProfile)).all()
                if profile.valuation_index
            }
        )

    job = DataJob(
        job_name="index_valuation",
        status="running",
        params={"index_codes": index_codes},
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    try:
        snapshots = []
        errors: list[str] = []
        for index_code in index_codes:
            try:
                snapshots.append(fetch_valuation(index_code))
            except Exception as exc:  # noqa: BLE001 - continue with the rest
                errors.append(f"{index_code}: {exc}")
            time.sleep(0.2)

        if not snapshots:
            raise ValueError(f"no valuation snapshots; errors={errors}")

        for snapshot in snapshots:
            session.execute(
                delete(IndexValuation).where(
                    IndexValuation.index_code == snapshot.index_code,
                    IndexValuation.trade_date == snapshot.trade_date,
                )
            )

        session.bulk_insert_mappings(
            IndexValuation,
            [
                {
                    "index_code": item.index_code,
                    "trade_date": item.trade_date,
                    "name": item.name,
                    "pe": item.pe,
                    "pb": item.pb,
                    "pe_percentile": item.pe_percentile,
                    "pb_percentile": item.pb_percentile,
                    "dividend_yield": item.dividend_yield,
                    "bond_yield": item.bond_yield,
                    "source": "danjuan",
                }
                for item in snapshots
            ],
        )
        session.flush()

        latest = max(item.trade_date for item in snapshots)
        lag = (date.today() - latest).days
        checks = [
            CheckResult(
                name="valuation_complete",
                status="pass" if len(snapshots) == len(index_codes) else "warn",
                detail={"expected": len(index_codes), "received": len(snapshots), "errors": errors},
            ),
            CheckResult(
                name="positive_pe",
                status="pass" if all(item.pe > 0 for item in snapshots) else "fail",
                detail={"violations": sum(1 for item in snapshots if item.pe <= 0)},
            ),
            CheckResult(
                name="percentile_range",
                status="pass"
                if all(0 <= item.pe_percentile <= 1 for item in snapshots)
                else "fail",
                detail={
                    "violations": sum(
                        1 for item in snapshots if not 0 <= item.pe_percentile <= 1
                    )
                },
            ),
            CheckResult(
                name="freshness",
                status="pass" if lag <= 7 else "warn",
                detail={"latest": latest.isoformat(), "lag_days": lag},
            ),
        ]

        job.status = "warning" if (errors or has_failures(checks)) else "success"
        job.rows_written = len(snapshots)
        job.finished_at = datetime.now(UTC)
        for check in checks:
            session.add(
                DataQualityCheck(
                    job_id=job.id,
                    check_name=check.name,
                    status=check.status,
                    detail=check.detail,
                )
            )
        session.commit()
        return {
            "rows": len(snapshots),
            "status": job.status,
            "latest": latest.isoformat(),
            "checks": checks,
            "errors": errors,
        }
    except Exception as exc:
        session.rollback()
        failed = session.get(DataJob, job.id)
        if failed is not None:
            failed.status = "failed"
            failed.error = str(exc)[:2000]
            failed.finished_at = datetime.now(UTC)
            session.commit()
        raise


def _fetch_series(code: str, start: date, end: date) -> DailySeries:
    """Eastmoney first, Tencent as fallback. Raises only if both fail."""
    try:
        return fetch_daily(
            code,
            beg=start.strftime("%Y%m%d"),
            end=end.strftime("%Y%m%d"),
            retries=2,
        )
    except Exception as primary_error:  # noqa: BLE001 - fallback is intentional
        try:
            return fetch_daily_tencent(code, start, end)
        except Exception as fallback_error:
            raise RuntimeError(
                f"all sources failed for {code}: {primary_error}; {fallback_error}"
            ) from fallback_error


def sync_code(
    session: Session,
    code: str,
    start: date,
    end: date | None = None,
    *,
    confirm_universe: bool = True,
) -> SyncResult:
    """Fetch, validate and persist one code. Returns a summary even on failure."""
    if confirm_universe and code not in ETF_BY_CODE:
        raise ValueError(f"{code} is not in the frozen ETF universe")

    end = end or date.today()
    job = DataJob(
        job_name="daily_bars",
        status="running",
        params={"code": code, "start": start.isoformat(), "end": end.isoformat()},
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    try:
        series = _fetch_series(code, start, end)
        if not series.bars:
            raise ValueError(f"no bars returned for {code}")

        expected_latest = (
            expected_latest_trading_day() if end >= date.today() - timedelta(days=7) else None
        )
        checks = check_series(series, expected_latest=expected_latest)
        written = replace_bars(session, series)
        session.flush()

        job.status = "warning" if has_failures(checks) else "success"
        job.rows_written = written
        job.finished_at = datetime.now(UTC)
        for check in checks:
            session.add(
                DataQualityCheck(
                    job_id=job.id,
                    check_name=check.name,
                    status=check.status,
                    detail=check.detail,
                )
            )
        session.commit()
        return SyncResult(
            code=code,
            rows=written,
            status=job.status,
            checks=checks,
            dates=tuple(bar.trade_date for bar in series.bars),
        )
    except Exception as exc:
        session.rollback()
        failed = session.get(DataJob, job.id)
        if failed is not None:
            failed.status = "failed"
            failed.error = str(exc)[:2000]
            failed.finished_at = datetime.now(UTC)
            session.commit()
        raise


def sync_all(
    session: Session,
    start: date,
    end: date | None = None,
    *,
    delay_seconds: float = 0.4,
) -> list[SyncResult]:
    """Sync the whole frozen universe, then rebuild the trading calendar."""
    results: list[SyncResult] = []
    calendar_dates: set[date] = set()

    for index, seed in enumerate(ETF_UNIVERSE):
        try:
            result = sync_code(session, seed.code, start, end)
            results.append(result)
            calendar_dates.update(result.dates)
        except Exception as exc:  # noqa: BLE001 - one bad symbol must not stop the batch
            results.append(
                SyncResult(code=seed.code, rows=0, status="failed", checks=[], error=str(exc))
            )
        if index < len(ETF_UNIVERSE) - 1 and delay_seconds > 0:
            time.sleep(delay_seconds)

    sync_calendar(session, calendar_dates)
    return results

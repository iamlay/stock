from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from app.db.models import (
    DataJob,
    DataQualityCheck,
    EtfProfile,
    EtfShareDaily,
    IndexValuation,
    Instrument,
    MarketDaily,
    TradingCalendar,
)
from sqlalchemy import delete, select
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
    """Upsert the frozen 20-ETF universe and its profile rows."""
    for seed in ETF_UNIVERSE:
        session.merge(
            Instrument(
                code=seed.code,
                name=seed.name,
                type="etf",
                exchange=seed.exchange,
                lot_size=100,
                is_active=True,
            )
        )
    session.flush()  # instruments must exist before profiles (FK)

    for seed in ETF_UNIVERSE:
        session.merge(
            EtfProfile(
                code=seed.code,
                category=seed.category,
                tracked_index=seed.tracked_index,
                valuation_index=VALUATION_INDEX.get(seed.code),
                extra={},
            )
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

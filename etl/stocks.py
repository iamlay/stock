from __future__ import annotations

import time
from datetime import UTC, date, datetime

from app.db.models import (
    DataJob,
    Instrument,
    StockDividend,
    StockMetric,
    StockProfile,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from etl.sources.eastmoney_stock import (
    fetch_dividends,
    latest_fiscal_year_yield,
    ttm_dividend_yield,
)
from etl.sources.sina_stock import SinaStockRow, fetch_stock_universe


def upsert_stock_universe(
    session: Session,
    rows: list[SinaStockRow],
    *,
    limit: int | None = None,
) -> list[str]:
    """Persist a stock snapshot; limit selects the largest companies by cap."""
    ordered = sorted(rows, key=lambda row: row.market_cap, reverse=True)
    if limit is not None:
        ordered = ordered[:limit]

    codes: list[str] = []
    for row in ordered:
        instrument = session.get(Instrument, row.code)
        if instrument is None:
            instrument = Instrument(
                code=row.code,
                name=row.name,
                type="stock",
                exchange=row.market,
                lot_size=100,
                is_active=True,
            )
            session.add(instrument)
        else:
            instrument.name = row.name
            instrument.type = "stock"
            instrument.exchange = row.market
            instrument.is_active = True

        profile = session.get(StockProfile, row.code)
        if profile is None:
            profile = StockProfile(
                code=row.code,
                market=row.market,
                is_st=row.is_st,
                status="active",
            )
            session.add(profile)
        else:
            profile.market = row.market
            profile.is_st = row.is_st
            profile.status = "active"

        metric = session.get(StockMetric, row.code)
        if metric is None:
            metric = StockMetric(code=row.code)
            session.add(metric)
        metric.price = row.price
        metric.change_pct = row.change_pct
        metric.market_cap = row.market_cap
        metric.pe_ttm = row.pe_ttm
        metric.pb = row.pb
        codes.append(row.code)

    session.commit()
    return codes


def _existing_dividends(
    session: Session, codes: list[str]
) -> dict[tuple[str, date, str], StockDividend]:
    if not codes:
        return {}
    rows = session.scalars(
        select(StockDividend).where(StockDividend.code.in_(codes))
    ).all()
    return {(row.code, row.ex_date, row.plan): row for row in rows}


def refresh_stock_metrics(
    session: Session,
    codes: list[str] | None = None,
    *,
    as_of: date | None = None,
) -> int:
    today = as_of or date.today()
    query = select(StockMetric)
    if codes:
        query = query.where(StockMetric.code.in_(codes))
    metrics = session.scalars(query).all()
    target_codes = [metric.code for metric in metrics]
    if not target_codes:
        return 0

    dividends: dict[str, list[StockDividend]] = {code: [] for code in target_codes}
    for row in session.scalars(
        select(StockDividend).where(StockDividend.code.in_(target_codes))
    ).all():
        dividends.setdefault(row.code, []).append(row)

    for metric in metrics:
        records = dividends.get(metric.code, [])
        price = float(metric.price or 0)
        ttm, _ = ttm_dividend_yield(records, price, as_of=today)
        fy = latest_fiscal_year_yield(records, price, as_of=today)
        metric.dividend_yield_ttm = ttm
        metric.dividend_yield_fy = fy
        past = [row.ex_date for row in records if row.ex_date <= today]
        metric.last_ex_date = max(past, default=None)

    session.commit()
    return len(metrics)


def sync_stock_dividends(
    session: Session,
    codes: list[str],
    *,
    delay: float = 0.2,
) -> dict:
    job = DataJob(
        job_name="stock_dividends",
        status="running",
        params={"codes": len(codes)},
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    existing = _existing_dividends(session, codes)
    written = 0
    errors: list[str] = []
    for code in codes:
        try:
            records = fetch_dividends(code)
            for record in records:
                key = (record.code, record.ex_date, record.plan)
                row = existing.get(key)
                if row is None:
                    row = StockDividend(
                        code=record.code,
                        ex_date=record.ex_date,
                        fiscal_year=record.fiscal_year,
                        cash_per_share=record.cash_per_share,
                        plan=record.plan,
                        is_special=record.is_special,
                        source="eastmoney",
                    )
                    session.add(row)
                    existing[key] = row
                    written += 1
                else:
                    row.cash_per_share = record.cash_per_share
                    row.fiscal_year = record.fiscal_year
                    row.is_special = record.is_special
        except Exception as exc:  # noqa: BLE001 - continue per stock
            errors.append(f"{code}: {exc}")
        time.sleep(delay)

    job.status = "success"
    job.rows_written = written
    job.error = f"{len(errors)} codes failed" if errors else None
    job.finished_at = datetime.now(UTC)
    session.commit()
    return {"written": written, "errors": errors, "codes": len(codes)}


def sync_stock_quote(session: Session, code: str) -> dict:
    """Add/refresh one stock using the Tencent quote and Eastmoney dividends."""
    from etl.sources.tencent_quote import fetch_quotes

    quotes = fetch_quotes([code])
    if not quotes:
        raise ValueError(f"no quote for {code}")
    quote = quotes[0]
    market = "SH" if code.startswith(("5", "6", "9")) else "SZ"

    instrument = session.get(Instrument, code)
    if instrument is None:
        instrument = Instrument(
            code=code,
            name=quote.name,
            type="stock",
            exchange=market,
            lot_size=100,
            is_active=True,
        )
        session.add(instrument)
    else:
        instrument.name = quote.name
        instrument.type = "stock"
        instrument.exchange = market

    profile = session.get(StockProfile, code)
    if profile is None:
        profile = StockProfile(code=code, market=market, status="active")
        session.add(profile)

    metric = session.get(StockMetric, code)
    if metric is None:
        metric = StockMetric(code=code)
        session.add(metric)
    metric.price = quote.price
    metric.change_pct = quote.change_pct

    session.commit()
    result = sync_stock_dividends(session, [code], delay=0)
    refresh_stock_metrics(session, [code])
    return result


def sync_stock_pilot(
    session: Session,
    *,
    limit: int = 500,
    dividend_limit: int | None = None,
    delay: float = 0.2,
) -> dict:
    total, rows = fetch_stock_universe()
    codes = upsert_stock_universe(session, rows, limit=limit)
    targets = codes[:dividend_limit] if dividend_limit is not None else codes
    dividends = sync_stock_dividends(session, targets, delay=delay)
    refreshed = refresh_stock_metrics(session, codes)
    return {
        "universe": total,
        "stored": len(codes),
        "dividend_codes": len(targets),
        "dividends": dividends["written"],
        "errors": dividends["errors"],
        "metrics": refreshed,
    }

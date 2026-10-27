from __future__ import annotations

import time
from datetime import UTC, date, datetime, timedelta

from app.db.models import (
    DataJob,
    Instrument,
    MarketDaily,
    StockDividend,
    StockFinancial,
    StockMetric,
    StockProfile,
)
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from etl.sources.eastmoney_stock import (
    fetch_dividends,
    fetch_dividends_bulk,
    fetch_stock_financials,
    latest_fiscal_year_yield,
    rly_dividend_yield,
    ttm_dividend_yield,
)
from etl.sources.industry import (
    fetch_eastmoney_industry,
    fetch_sina_industry_map,
)
from etl.sources.sina_stock import SinaStockRow, fetch_stock_universe
from etl.sources.tencent import fetch_daily_tencent


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

    codes = [row.code for row in ordered]
    instruments = {
        item.code: item
        for item in session.scalars(
            select(Instrument).where(Instrument.code.in_(codes))
        ).all()
    }
    profiles = {
        item.code: item
        for item in session.scalars(
            select(StockProfile).where(StockProfile.code.in_(codes))
        ).all()
    }
    metrics = {
        item.code: item
        for item in session.scalars(
            select(StockMetric).where(StockMetric.code.in_(codes))
        ).all()
    }

    for row in ordered:
        instrument = instruments.get(row.code)
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
            instruments[row.code] = instrument
        else:
            instrument.name = row.name
            instrument.type = "stock"
            instrument.exchange = row.market
            instrument.is_active = True

        profile = profiles.get(row.code)
        if profile is None:
            profile = StockProfile(
                code=row.code,
                market=row.market,
                is_st=row.is_st,
                status="active",
            )
            session.add(profile)
            profiles[row.code] = profile
        else:
            profile.market = row.market
            profile.is_st = row.is_st
            profile.status = "active"

        metric = metrics.get(row.code)
        if metric is None:
            metric = StockMetric(code=row.code)
            session.add(metric)
            metrics[row.code] = metric
        metric.price = row.price
        metric.change_pct = row.change_pct
        metric.market_cap = row.market_cap
        metric.pe_ttm = row.pe_ttm
        metric.pb = row.pb

    session.commit()
    return codes


def _existing_dividends(
    session: Session, codes: list[str]
) -> dict[tuple[str, int, str], StockDividend]:
    if not codes:
        return {}
    rows = session.scalars(
        select(StockDividend).where(StockDividend.code.in_(codes))
    ).all()
    return {(row.code, row.fiscal_year, row.plan): row for row in rows}


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
        one_off = 0
        years: set[int] = set()
        for row in records:
            row.is_special = "特别" in row.plan
            contribution = (
                float(row.cash_per_share) / price * 100 if price > 0 else 0.0
            )
            row.is_one_off = row.is_special or contribution >= 8
            if row.is_one_off:
                one_off += 1
            years.add(row.fiscal_year)

        ttm, _ = ttm_dividend_yield(records, price, as_of=today)
        fy = latest_fiscal_year_yield(records, price, as_of=today)
        ly = rly_dividend_yield(records, price, as_of=today)
        metric.dividend_yield_ttm = ttm
        metric.dividend_yield_fy = fy
        metric.dividend_yield_ly = ly
        if not records:
            metric.sustainability = "none"
        elif one_off:
            metric.sustainability = "one_off"
        elif ttm is not None and ttm > 15:
            metric.sustainability = "high_yield"
        elif (ttm is not None and ttm > 10) or (
            ttm is not None and fy is not None and abs(ttm - fy) > 5
        ):
            metric.sustainability = "watch"
        elif ttm is not None and ttm > 0 and len(years) >= 5 and ttm <= 8:
            metric.sustainability = "stable"
        else:
            metric.sustainability = "normal"
        past = [row.ex_date for row in records if row.ex_date <= today]
        metric.last_ex_date = max(past, default=None)

    session.commit()
    return len(metrics)


def sync_stock_dividends_bulk(
    session: Session,
    *,
    codes: list[str] | None = None,
    days: int = 3650,
) -> dict:
    """Sync all dividends in bulk, then recompute yields for selected stocks."""
    targets = codes or list(
        session.scalars(
            select(StockProfile.code).where(StockProfile.status == "active")
        ).all()
    )
    if not targets:
        return {"codes": 0, "records": 0, "written": 0}

    since = date.today() - timedelta(days=days)
    records = fetch_dividends_bulk(since=since)
    target_set = set(targets)
    existing = _existing_dividends(session, targets)

    written = 0
    for record in records:
        if record.code not in target_set:
            continue
        key = (record.code, record.fiscal_year, record.plan)
        row = existing.get(key)
        if row is None:
            row = StockDividend(
                code=record.code,
                ex_date=record.ex_date,
                notice_date=record.notice_date,
                report_date=record.report_date,
                progress=record.progress,
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
            row.ex_date = record.ex_date
            row.notice_date = record.notice_date
            row.report_date = record.report_date
            row.progress = record.progress
            row.cash_per_share = record.cash_per_share
            row.fiscal_year = record.fiscal_year
            row.is_special = record.is_special

    session.commit()
    refreshed = refresh_stock_metrics(session, targets)
    return {
        "codes": len(targets),
        "records": len(records),
        "written": written,
        "metrics": refreshed,
    }


def expected_financial_report_date(today: date | None = None) -> date:
    """Latest report period that should normally be available by today."""
    current = today or date.today()
    if (current.month, current.day) >= (10, 31):
        return date(current.year, 9, 30)
    if (current.month, current.day) >= (8, 31):
        return date(current.year, 6, 30)
    if (current.month, current.day) >= (4, 30):
        return date(current.year, 3, 31)
    return date(current.year - 1, 12, 31)


def sync_stock_financials_batch(
    session: Session,
    *,
    limit: int = 500,
    codes: list[str] | None = None,
    delay: float = 0.2,
    shard_index: int = 0,
    shard_count: int = 1,
    force: bool = False,
) -> dict:
    """Fetch recent financial reports for high-dividend stocks."""
    if shard_count < 1 or shard_index < 0 or shard_index >= shard_count:
        raise ValueError("invalid financials shard")
    if codes:
        targets = codes
    else:
        targets = list(
            session.scalars(
                select(StockMetric.code)
                .join(StockProfile, StockProfile.code == StockMetric.code)
                .where(StockProfile.status == "active")
                .order_by(
                    StockMetric.dividend_yield_ttm.desc().nulls_last(),
                    StockMetric.market_cap.desc(),
                )
                .limit(limit)
            ).all()
        )
    if shard_count > 1:
        targets = targets[shard_index::shard_count]
    if not targets:
        return {
            "selected": 0,
            "skipped": 0,
            "written": 0,
            "updated": 0,
            "errors": [],
        }

    expected = expected_financial_report_date()
    latest_by_code = dict(
        session.execute(
            select(StockFinancial.code, func.max(StockFinancial.report_date))
            .where(StockFinancial.code.in_(targets))
            .group_by(StockFinancial.code)
        ).all()
    )
    if not force:
        before = len(targets)
        targets = [
            code
            for code in targets
            if latest_by_code.get(code) is None or latest_by_code[code] < expected
        ]
        skipped = before - len(targets)
    else:
        skipped = 0
    if not targets:
        return {
            "selected": 0,
            "skipped": skipped,
            "written": 0,
            "updated": 0,
            "errors": [],
        }

    existing = {
        (row.code, row.report_date): row
        for row in session.scalars(
            select(StockFinancial).where(StockFinancial.code.in_(targets))
        ).all()
    }
    written = 0
    updated = 0
    errors: list[dict] = []

    for index, code in enumerate(targets):
        try:
            records = fetch_stock_financials(code)
            for record in records:
                row = existing.get((code, record.report_date))
                if row is None:
                    row = StockFinancial(
                        code=code,
                        report_date=record.report_date,
                        period=record.period,
                        revenue=record.revenue,
                        net_profit=record.net_profit,
                        revenue_yoy=record.revenue_yoy,
                        net_profit_yoy=record.net_profit_yoy,
                        roe=record.roe,
                        operating_cash_flow_per_share=record.operating_cash_flow_per_share,
                        operating_cash_flow=record.operating_cash_flow,
                        gross_margin=record.gross_margin,
                        net_margin=record.net_margin,
                        total_assets=record.total_assets,
                        total_liabilities=record.total_liabilities,
                        debt_asset_ratio=record.debt_asset_ratio,
                        roa=record.roa,
                        disclosure_date=record.disclosure_date,
                        source="eastmoney",
                    )
                    session.add(row)
                    existing[(code, record.report_date)] = row
                    written += 1
                else:
                    row.period = record.period
                    row.revenue = record.revenue
                    row.net_profit = record.net_profit
                    row.revenue_yoy = record.revenue_yoy
                    row.net_profit_yoy = record.net_profit_yoy
                    row.roe = record.roe
                    row.operating_cash_flow_per_share = (
                        record.operating_cash_flow_per_share
                    )
                    row.operating_cash_flow = record.operating_cash_flow
                    row.gross_margin = record.gross_margin
                    row.net_margin = record.net_margin
                    row.total_assets = record.total_assets
                    row.total_liabilities = record.total_liabilities
                    row.debt_asset_ratio = record.debt_asset_ratio
                    row.roa = record.roa
                    row.disclosure_date = record.disclosure_date
                    updated += 1
            if (index + 1) % 25 == 0:
                session.commit()
        except Exception as exc:  # noqa: BLE001 - one stock must not stop the batch
            session.rollback()
            errors.append({"code": code, "error": str(exc)[:300]})
        if index < len(targets) - 1 and delay > 0:
            time.sleep(delay)

    session.commit()
    return {
        "selected": len(targets),
        "skipped": skipped,
        "written": written,
        "updated": updated,
        "errors": errors,
    }


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
                key = (record.code, record.fiscal_year, record.plan)
                row = existing.get(key)
                if row is None:
                    row = StockDividend(
                        code=record.code,
                        ex_date=record.ex_date,
                        notice_date=record.notice_date,
                        report_date=record.report_date,
                        progress=record.progress,
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
                    row.ex_date = record.ex_date
                    row.notice_date = record.notice_date
                    row.report_date = record.report_date
                    row.progress = record.progress
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


def sync_stock_bars(
    session: Session,
    code: str,
    *,
    days: int = 600,
    commit: bool = True,
) -> int:
    """Cache recent daily bars for a stock detail chart."""
    end = date.today()
    start = end - timedelta(days=days * 2)
    series = fetch_daily_tencent(code, start, end)
    bars = series.bars[-days:]
    if not bars:
        if commit:
            session.commit()
        return 0

    session.execute(
        delete(MarketDaily).where(
            MarketDaily.code == code,
            MarketDaily.trade_date >= bars[0].trade_date,
        )
    )
    mappings: list[dict] = []
    previous: float | None = None
    for bar in bars:
        mappings.append(
            {
                "code": code,
                "trade_date": bar.trade_date,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "prev_close": previous,
                "volume": bar.volume,
                "amount": bar.amount,
                "amplitude": bar.amplitude,
                "adj_factor": 1,
                "source": "tencent",
            }
        )
        previous = bar.close
    session.bulk_insert_mappings(MarketDaily, mappings)
    if commit:
        session.commit()
    return len(mappings)


def sync_stock_bars_batch(
    session: Session,
    *,
    limit: int = 2000,
    codes: list[str] | None = None,
    force: bool = False,
    days: int = 600,
    delay: float = 0.2,
) -> dict:
    """Backfill K-line bars for the highest-yield stocks."""
    target_bars = max(420, round(days * 0.66))
    if codes:
        targets = codes
    else:
        targets = list(
            session.scalars(
                select(StockMetric.code)
                .join(StockProfile, StockProfile.code == StockMetric.code)
                .where(StockProfile.status == "active")
                .order_by(
                    StockMetric.dividend_yield_ttm.desc().nulls_last(),
                    StockMetric.market_cap.desc(),
                )
                .limit(limit)
            ).all()
        )
    if not targets:
        return {"selected": 0, "updated": 0, "skipped": 0, "errors": []}

    today = date.today()
    existing = {
        code: (count, latest)
        for code, count, latest in session.execute(
            select(
                MarketDaily.code,
                func.count(),
                func.max(MarketDaily.trade_date),
            )
            .where(MarketDaily.code.in_(targets))
            .group_by(MarketDaily.code)
        ).all()
    }

    updated = 0
    skipped = 0
    errors: list[str] = []
    for index, code in enumerate(targets, start=1):
        count, latest = existing.get(code, (0, None))
        if (
            not force
            and count >= target_bars
            and latest is not None
            and (today - latest).days <= 3
        ):
            skipped += 1
            continue
        try:
            sync_stock_bars(session, code, days=days, commit=False)
            updated += 1
        except Exception as exc:  # noqa: BLE001 - continue per stock
            errors.append(f"{code}: {exc}"[:200])
        time.sleep(delay)
        if index % 25 == 0:
            session.commit()
    session.commit()
    return {
        "selected": len(targets),
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }


def compute_yield_percentile(
    bars: list[tuple[date, float]],
    dividends: list[tuple[date, float]],
    current_yield: float | None,
) -> float | None:
    """Percentile of the current weekly TTM yield over available history."""
    if len(bars) < 52:
        return None
    weekly: dict[tuple[int, int], tuple[date, float]] = {}
    for trade_date, close in bars:
        iso = trade_date.isocalendar()
        weekly[(iso.year, iso.week)] = (trade_date, close)

    series: list[float] = []
    for trade_date, close in sorted(weekly.values()):
        if close <= 0:
            continue
        cutoff = trade_date - timedelta(days=365)
        cash = sum(
            value
            for ex_date, value in dividends
            if cutoff < ex_date <= trade_date and value > 0
        )
        if cash > 0:
            series.append(cash / close * 100)

    series = series[-520:]
    if len(series) < 52:
        return None
    current = (
        float(current_yield)
        if current_yield is not None and current_yield > 0
        else series[-1]
    )
    below = sum(1 for value in series if value <= current)
    return round(below / len(series) * 100, 2)


def refresh_yield_percentiles(
    session: Session,
    *,
    limit: int = 500,
    days: int = 3650,
) -> dict:
    """Compute 10-year weekly TTM yield percentiles for high-yield stocks."""
    today = date.today()
    cutoff = today - timedelta(days=days)
    targets = list(
        session.scalars(
            select(StockMetric.code)
            .join(StockProfile, StockProfile.code == StockMetric.code)
            .where(
                StockProfile.status == "active",
                StockMetric.dividend_yield_ttm.is_not(None),
                StockMetric.dividend_yield_ttm > 0,
            )
            .order_by(StockMetric.dividend_yield_ttm.desc())
            .limit(limit)
        ).all()
    )
    dividends: dict[str, list[tuple[date, float]]] = {}
    for row in session.scalars(
        select(StockDividend).where(StockDividend.code.in_(targets))
    ).all():
        dividends.setdefault(row.code, []).append(
            (row.ex_date, float(row.cash_per_share))
        )

    updated = 0
    insufficient = 0
    for code in targets:
        metric = session.get(StockMetric, code)
        if metric is None:
            continue
        bars = [
            (trade_date, float(close))
            for trade_date, close in session.execute(
                select(MarketDaily.trade_date, MarketDaily.close)
                .where(
                    MarketDaily.code == code,
                    MarketDaily.trade_date >= cutoff,
                )
                .order_by(MarketDaily.trade_date)
            ).all()
        ]
        percentile = compute_yield_percentile(
            bars,
            dividends.get(code, []),
            float(metric.dividend_yield_ttm or 0),
        )
        if percentile is None:
            insufficient += 1
            continue
        metric.yield_percentile = percentile
        updated += 1

    session.commit()
    return {
        "selected": len(targets),
        "updated": updated,
        "insufficient": insufficient,
    }


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
    industry_error: str | None = None
    try:
        company = fetch_eastmoney_industry(code)
        if company.eastmoney_industry:
            profile.industry = company.eastmoney_industry.split("-")[0].strip()
            profile.industry_path = company.eastmoney_industry
            profile.industry_source = "eastmoney"
            if company.listing_date:
                profile.list_date = date.fromisoformat(company.listing_date)
    except Exception as exc:  # noqa: BLE001 - industry is optional
        industry_error = str(exc)[:200]

    metric = session.get(StockMetric, code)
    if metric is None:
        metric = StockMetric(code=code)
        session.add(metric)
    metric.price = quote.price
    metric.change_pct = quote.change_pct

    session.commit()
    bars = 0
    bars_error: str | None = None
    try:
        bars = sync_stock_bars(session, code)
    except Exception as exc:  # noqa: BLE001 - chart is optional
        bars_error = str(exc)[:200]
    result = sync_stock_dividends(session, [code], delay=0)
    refresh_stock_metrics(session, [code])
    result["bars"] = bars
    result["industry_error"] = industry_error
    result["bars_error"] = bars_error
    return result


def enrich_stock_industry_details(
    session: Session,
    *,
    limit: int = 500,
    delay: float = 0.2,
) -> dict:
    """Fill three-level Eastmoney industry paths for high-yield stocks."""
    targets = list(
        session.scalars(
            select(StockProfile.code)
            .join(StockMetric, StockMetric.code == StockProfile.code)
            .where(
                StockProfile.status == "active",
                StockMetric.dividend_yield_ttm.is_not(None),
            )
            .order_by(StockMetric.dividend_yield_ttm.desc().nulls_last())
            .limit(limit)
        ).all()
    )
    if not targets:
        return {"selected": 0, "updated": 0, "errors": []}

    profiles = {
        item.code: item
        for item in session.scalars(
            select(StockProfile).where(StockProfile.code.in_(targets))
        ).all()
    }
    job = DataJob(
        job_name="stock_industry_detail",
        status="running",
        params={"codes": len(targets)},
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    updated = 0
    errors: list[str] = []
    for index, code in enumerate(targets, start=1):
        company = None
        for attempt in range(3):
            try:
                company = fetch_eastmoney_industry(code)
                break
            except Exception:  # noqa: BLE001 - retry then record
                if attempt == 2:
                    errors.append(code)
                time.sleep(0.5 * (attempt + 1))
        profile = profiles.get(code)
        if company and company.eastmoney_industry and profile is not None:
            profile.industry_path = company.eastmoney_industry
            profile.industry_source = "eastmoney"
            if company.listing_date:
                try:
                    profile.list_date = date.fromisoformat(company.listing_date)
                except ValueError:
                    pass
            updated += 1
        time.sleep(delay)
        if index % 50 == 0:
            session.commit()

    job.status = "success"
    job.rows_written = updated
    job.error = f"{len(errors)} codes failed" if errors else None
    job.finished_at = datetime.now(UTC)
    session.commit()
    return {"selected": len(targets), "updated": updated, "errors": errors}


def enrich_stock_industries(
    session: Session,
    codes: list[str] | None = None,
    *,
    limit: int | None = None,
    include_sina: bool = True,
    sina_only: bool = False,
    sina_prefix: str = "sw_",
    overwrite: bool = False,
    delay: float = 0.2,
) -> dict:
    """Fill stock industries from Sina (coarse) and Eastmoney F10 (precise)."""
    query = (
        select(StockProfile.code)
        .join(StockMetric, StockMetric.code == StockProfile.code)
        .where(StockProfile.status == "active")
        .order_by(StockMetric.market_cap.desc())
    )
    if codes:
        query = query.where(StockProfile.code.in_(codes))
    if limit is not None:
        query = query.limit(limit)
    selected = list(session.scalars(query).all())
    if not selected:
        return {"selected": 0, "sina": 0, "eastmoney": 0, "errors": []}
    profiles = {
        item.code: item
        for item in session.scalars(
            select(StockProfile).where(StockProfile.code.in_(selected))
        ).all()
    }

    job = DataJob(
        job_name="stock_industry",
        status="running",
        params={"codes": len(selected), "include_sina": include_sina},
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    sina_count = 0
    if include_sina:
        try:
            _, sina_map = fetch_sina_industry_map(prefix=sina_prefix)
            for code in selected:
                profile = profiles.get(code)
                industry = sina_map.get(code)
                if profile is not None and industry:
                    profile.industry = industry if overwrite else (profile.industry or industry)
                    profile.industry_path = (
                        industry if overwrite else (profile.industry_path or industry)
                    )
                    profile.industry_source = (
                        "sina_sw1" if overwrite else (profile.industry_source or "sina")
                    )
                    sina_count += 1
            session.commit()
        except Exception as exc:  # noqa: BLE001 - F10 can still fill
            job.error = f"sina: {exc}"[:500]

    em_count = 0
    errors: list[str] = []
    if sina_only:
        job.status = "success"
        job.rows_written = sina_count
        job.finished_at = datetime.now(UTC)
        session.commit()
        return {
            "selected": len(selected),
            "sina": sina_count,
            "eastmoney": 0,
            "errors": errors,
        }
    for index, code in enumerate(selected, start=1):
        company = None
        for attempt in range(3):
            try:
                company = fetch_eastmoney_industry(code)
                break
            except Exception:  # noqa: BLE001 - retry then record
                if attempt == 2:
                    errors.append(code)
                time.sleep(0.5 * (attempt + 1))
        if company and company.eastmoney_industry:
            profile = profiles.get(code)
            if profile is not None:
                path = company.eastmoney_industry
                profile.industry = path.split("-")[0].strip()
                profile.industry_path = path
                profile.industry_source = "eastmoney"
                if company.listing_date:
                    try:
                        profile.list_date = date.fromisoformat(company.listing_date)
                    except ValueError:
                        pass
                em_count += 1
        time.sleep(delay)
        if index % 50 == 0:
            session.commit()

    job.status = "success"
    job.rows_written = em_count
    job.error = (
        f"{len(errors)} codes failed" if errors else None
    ) if job.error is None else job.error
    job.finished_at = datetime.now(UTC)
    session.commit()
    return {
        "selected": len(selected),
        "sina": sina_count,
        "eastmoney": em_count,
        "errors": errors,
    }


def sync_stock_daily(
    session: Session,
    *,
    include_dividends: bool = False,
    dividend_limit: int | None = None,
    delay: float = 0.15,
) -> dict:
    """Refresh prices/metrics for stocks already in the database."""
    existing = set(
        session.scalars(
            select(StockProfile.code).where(StockProfile.status == "active")
        ).all()
    )
    if not existing:
        return {
            "universe": 0,
            "matched": 0,
            "dividends": 0,
            "errors": [],
            "metrics": 0,
        }

    total, rows = fetch_stock_universe()
    selected = [row for row in rows if row.code in existing]
    codes = upsert_stock_universe(session, selected)

    dividends = 0
    errors: list[str] = []
    if include_dividends and codes:
        targets = codes[:dividend_limit] if dividend_limit is not None else codes
        result = sync_stock_dividends(session, targets, delay=delay)
        dividends = result["written"]
        errors = result["errors"]

    refreshed = refresh_stock_metrics(session, codes)
    return {
        "universe": total,
        "matched": len(codes),
        "dividends": dividends,
        "errors": errors,
        "metrics": refreshed,
    }


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

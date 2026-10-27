from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

CLIST_API = "https://push2.eastmoney.com/api/qt/clist/get"
DIVIDEND_API = "https://datacenter-web.eastmoney.com/api/data/v1/get"
USER_AGENT = "Mozilla/5.0 (compatible; StockLabETL/0.1)"
A_SHARE_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"


@dataclass(frozen=True)
class StockRow:
    code: str
    name: str
    price: float
    change_pct: float
    market_cap: float  # 亿元
    pe_ttm: float | None
    pb: float | None
    industry: str
    market: str
    is_st: bool


@dataclass(frozen=True)
class DividendRecord:
    code: str
    name: str
    ex_date: date | None
    fiscal_year: int
    cash_per_share: float
    plan: str
    is_special: bool
    notice_date: date | None = None
    report_date: date | None = None
    progress: str = ""


class DividendBatch(list[DividendRecord]):
    """Legacy records remain list-compatible; unfiltered source pages retain all stages."""

    def __init__(self) -> None:
        super().__init__()
        self.source_pages: list[dict] = []

    def capture(self, payload: dict, url: str) -> None:
        result = payload.get("result")
        if payload.get("success") is False or not isinstance(result, dict):
            raise ValueError("dividend source returned an unsuccessful response")
        rows = result.get("data")
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValueError("dividend source returned malformed rows")
        self.source_pages.append({
            "rows": rows,
            "url": url,
            "observed_at": datetime.now(UTC).isoformat(),
        })
        self.extend(parse_dividends(payload))


@dataclass(frozen=True)
class FinancialRecord:
    code: str
    report_date: date
    period: str
    revenue: float | None
    net_profit: float | None
    revenue_yoy: float | None
    net_profit_yoy: float | None
    roe: float | None
    operating_cash_flow_per_share: float | None
    operating_cash_flow: float | None
    gross_margin: float | None
    net_margin: float | None
    total_assets: float | None
    total_liabilities: float | None
    debt_asset_ratio: float | None
    roa: float | None
    disclosure_date: date | None


def _get_json(url: str, referer: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Referer": referer},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def _float(value, default: float | None = 0.0) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def parse_stock_rows(payload: dict) -> list[StockRow]:
    diff = ((payload.get("data") or {}).get("diff") or [])
    if isinstance(diff, dict):
        diff = list(diff.values())
    rows: list[StockRow] = []
    for item in diff:
        code = str(item.get("f12") or "")
        name = str(item.get("f14") or "")
        price = _float(item.get("f2"))
        if not code or price is None or price <= 0:
            continue
        cap = _float(item.get("f20"), 0.0) or 0.0
        rows.append(
            StockRow(
                code=code,
                name=name,
                price=price,
                change_pct=_float(item.get("f3"), 0.0) or 0.0,
                market_cap=round(cap / 100_000_000, 2),
                pe_ttm=_float(item.get("f9")),
                pb=_float(item.get("f23")),
                industry=str(item.get("f100") or "未分类"),
                market="SH" if item.get("f13") == 1 else "SZ",
                is_st="ST" in name.upper(),
            )
        )
    return rows


def fetch_stock_universe(
    *, page_size: int = 100, max_pages: int | None = None
) -> tuple[int, list[StockRow]]:
    rows: list[StockRow] = []
    total = 0
    page = 1
    while True:
        query = urllib.parse.urlencode(
            {
                "pn": page,
                "pz": page_size,
                "po": 1,
                "np": 1,
                "fltt": 2,
                "invt": 2,
                "fid": "f3",
                "fs": A_SHARE_FS,
                "fields": "f12,f14,f2,f3,f13,f20,f9,f23,f100",
            }
        )
        payload = _get_json(f"{CLIST_API}?{query}", "https://quote.eastmoney.com/")
        data = payload.get("data") or {}
        total = int(data.get("total") or total)
        batch = parse_stock_rows(payload)
        rows.extend(batch)
        if not batch or len(rows) >= total:
            break
        if max_pages is not None and page >= max_pages:
            break
        page += 1
    return total, rows


def parse_dividends(payload: dict) -> list[DividendRecord]:
    data = ((payload.get("result") or {}).get("data") or [])
    records: list[DividendRecord] = []
    for item in data:
        progress = str(item.get("ASSIGN_PROGRESS") or "")
        ex_date = _date(item.get("EX_DIVIDEND_DATE"))
        notice_date = _date(item.get("NOTICE_DATE"))
        report_date = _date(item.get("REPORT_DATE"))
        per_ten = _float(item.get("PRETAX_BONUS_RMB"), 0.0) or 0.0
        if report_date is None or per_ten <= 0:
            continue
        plan = str(item.get("IMPL_PLAN_PROFILE") or "")
        records.append(
            DividendRecord(
                code=str(item.get("SECURITY_CODE") or ""),
                name=str(item.get("SECURITY_NAME_ABBR") or ""),
                ex_date=ex_date,
                notice_date=notice_date,
                report_date=report_date,
                progress=progress,
                fiscal_year=report_date.year,
                cash_per_share=round(per_ten / 10, 6),
                plan=plan,
                is_special="特别" in plan,
            )
        )
    return records


def fetch_dividends(code: str) -> list[DividendRecord]:
    records = DividendBatch()
    page = 1
    pages = 1
    while page <= pages:
        query = urllib.parse.urlencode(
            {
                "reportName": "RPT_SHAREBONUS_DET",
                "columns": "ALL",
                "filter": f'(SECURITY_CODE="{code}")',
                "pageNumber": page,
                "pageSize": 100,
                "sortTypes": -1,
                "sortColumns": "NOTICE_DATE",
            }
        )
        payload = _get_json(
            f"{DIVIDEND_API}?{query}",
            "https://data.eastmoney.com/",
        )
        pages = int((payload.get("result") or {}).get("pages") or 1)
        records.capture(payload, f"{DIVIDEND_API}?{query}")
        page += 1
    return records


def fetch_dividends_bulk(
    *,
    since: date | None = None,
    page_size: int = 500,
) -> list[DividendRecord]:
    """Fetch all implemented dividends since a date in ~30 bulk pages."""
    cutoff = since or (date.today().replace(month=1, day=1) - timedelta(days=365))
    records = DividendBatch()
    page = 1
    pages = 1
    while page <= pages:
        query = urllib.parse.urlencode(
            {
                "reportName": "RPT_SHAREBONUS_DET",
                "columns": "ALL",
                "filter": f"(NOTICE_DATE>='{cutoff.isoformat()}')",
                "pageNumber": page,
                "pageSize": page_size,
                "sortTypes": -1,
                "sortColumns": "NOTICE_DATE",
            }
        )
        payload = _get_json(
            f"{DIVIDEND_API}?{query}",
            "https://data.eastmoney.com/",
        )
        result = payload.get("result") or {}
        pages = int(result.get("pages") or 1)
        records.capture(payload, f"{DIVIDEND_API}?{query}")
        page += 1
    return records


def fetch_stock_financials(
    code: str,
    *,
    limit: int = 24,
) -> list[FinancialRecord]:
    """Fetch recent annual/quarterly financials for one stock."""
    query = urllib.parse.urlencode(
        {
            "reportName": "RPT_LICO_FN_CPD",
            "columns": "ALL",
            "filter": f'(SECURITY_CODE="{code}")',
            "pageNumber": 1,
            "pageSize": limit,
            "sortColumns": "REPORTDATE",
            "sortTypes": -1,
        }
    )
    payload = _get_json(f"{DIVIDEND_API}?{query}", "https://data.eastmoney.com/")
    cash_query = urllib.parse.urlencode(
        {
            "reportName": "RPT_DMSK_FN_CASHFLOW",
            "columns": "ALL",
            "filter": f'(SECURITY_CODE="{code}")',
            "pageNumber": 1,
            "pageSize": limit,
            "sortColumns": "REPORT_DATE",
            "sortTypes": -1,
        }
    )
    cash_payload = _get_json(
        f"{DIVIDEND_API}?{cash_query}",
        "https://data.eastmoney.com/",
    )
    cash_by_date = {
        item_date: _float(item.get("NETCASH_OPERATE"), None)
        for item in (cash_payload.get("result") or {}).get("data") or []
        if (item_date := _date(item.get("REPORT_DATE")))
    }
    balance_query = urllib.parse.urlencode(
        {
            "reportName": "RPT_DMSK_FN_BALANCE",
            "columns": "ALL",
            "filter": f'(SECURITY_CODE="{code}")',
            "pageNumber": 1,
            "pageSize": limit,
            "sortColumns": "REPORT_DATE",
            "sortTypes": -1,
        }
    )
    balance_payload = _get_json(
        f"{DIVIDEND_API}?{balance_query}",
        "https://data.eastmoney.com/",
    )
    balance_by_date = {
        item_date: item
        for item in (balance_payload.get("result") or {}).get("data") or []
        if (item_date := _date(item.get("REPORT_DATE")))
    }
    result = payload.get("result") or {}
    rows: list[FinancialRecord] = []
    for item in result.get("data") or []:
        report_date = _date(item.get("REPORTDATE") or item.get("REPORT_DATE"))
        if report_date is None:
            continue
        month = report_date.month
        period = (
            "Q1" if month == 3 else "H1" if month == 6 else "Q3" if month == 9 else "FY"
        )
        revenue = _float(item.get("TOTAL_OPERATE_INCOME"), None)
        net_profit = _float(item.get("PARENT_NETPROFIT"), None)
        net_margin = (
            net_profit / revenue * 100
            if revenue and net_profit is not None and revenue > 0
            else None
        )
        balance = balance_by_date.get(report_date) or {}
        total_assets = _float(balance.get("TOTAL_ASSETS"), None)
        total_liabilities = _float(balance.get("TOTAL_LIABILITIES"), None)
        debt_asset_ratio = _float(balance.get("DEBT_ASSET_RATIO"), None)
        if debt_asset_ratio is None and total_assets and total_liabilities is not None:
            debt_asset_ratio = total_liabilities / total_assets * 100
        roa = (
            net_profit / total_assets * 100
            if net_profit is not None and total_assets and total_assets > 0
            else None
        )
        rows.append(
            FinancialRecord(
                code=code,
                report_date=report_date,
                period=period,
                revenue=revenue,
                net_profit=net_profit,
                revenue_yoy=_float(item.get("YSTZ"), None),
                net_profit_yoy=_float(item.get("SJLTZ"), None),
                roe=_float(item.get("WEIGHTAVG_ROE"), None),
                operating_cash_flow_per_share=_float(item.get("MGJYXJJE"), None),
                operating_cash_flow=cash_by_date.get(report_date),
                gross_margin=_float(item.get("XSMLL"), None),
                net_margin=net_margin,
                total_assets=total_assets,
                total_liabilities=total_liabilities,
                debt_asset_ratio=debt_asset_ratio,
                roa=roa,
                disclosure_date=_date(item.get("NOTICE_DATE")),
            )
        )
    return rows


def ttm_dividend_yield(
    records: list[DividendRecord],
    price: float,
    *,
    as_of: date | None = None,
) -> tuple[float | None, float]:
    if price <= 0:
        return None, 0.0
    today = as_of or date.today()
    cutoff = today - timedelta(days=365)
    cash = sum(
        float(record.cash_per_share)
        for record in records
        if record.ex_date is not None and cutoff < record.ex_date <= today
    )
    if cash <= 0:
        return None, 0.0
    return round(cash / price * 100, 2), round(cash, 6)


def rly_dividend_yield(
    records: list[DividendRecord],
    price: float,
    *,
    as_of: date | None = None,
) -> float | None:
    """Latest annual + current interim announced cash / current price."""
    if price <= 0:
        return None
    today = as_of or date.today()

    def event_date(record: DividendRecord) -> date | None:
        return record.notice_date or record.ex_date

    announced = [
        record
        for record in records
        if record.cash_per_share > 0
        and event_date(record) is not None
        and event_date(record) <= today
    ]
    if not announced:
        return None
    annuals = [
        record
        for record in announced
        if (record.report_date or record.ex_date) is not None
        and (record.report_date or record.ex_date).month == 12
    ]
    interims = [
        record
        for record in announced
        if (record.report_date or record.ex_date) is not None
        and (record.report_date or record.ex_date).month != 12
    ]

    latest_annual = (
        max(annuals, key=lambda item: item.report_date or item.ex_date) if annuals else None
    )
    latest_interim = (
        max(interims, key=lambda item: item.report_date or item.ex_date)
        if interims
        else None
    )
    cash = float(latest_annual.cash_per_share) if latest_annual else 0.0
    annual_date = (latest_annual.report_date or latest_annual.ex_date) if latest_annual else None
    interim_date = (
        (latest_interim.report_date or latest_interim.ex_date) if latest_interim else None
    )
    if latest_interim is not None and (annual_date is None or interim_date > annual_date):
        cash += float(latest_interim.cash_per_share)
    if cash <= 0:
        return None
    return round(cash / price * 100, 2)


def latest_fiscal_year_yield(
    records: list[DividendRecord], price: float, *, as_of: date | None = None
) -> float | None:
    today = as_of or date.today()
    years = [
        record.fiscal_year
        for record in records
        if record.ex_date is not None and record.ex_date <= today
    ]
    if not years or price <= 0:
        return None
    # Prefer the latest completed fiscal year; the current year usually only
    # contains interim dividends and would understate the annual yield.
    completed = [year for year in years if year < today.year]
    year = max(completed) if completed else max(years)
    cash = sum(
        float(record.cash_per_share)
        for record in records
        if record.fiscal_year == year
        and record.ex_date is not None
        and record.ex_date <= today
    )
    return round(cash / price * 100, 2) if cash > 0 else None

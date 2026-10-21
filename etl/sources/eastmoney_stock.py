from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta

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
    ex_date: date
    fiscal_year: int
    cash_per_share: float
    plan: str
    is_special: bool


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
        report_date = _date(item.get("REPORT_DATE"))
        per_ten = _float(item.get("PRETAX_BONUS_RMB"), 0.0) or 0.0
        if ex_date is None or report_date is None or per_ten <= 0:
            continue
        if "实施" not in progress and "分配" not in progress:
            continue
        plan = str(item.get("IMPL_PLAN_PROFILE") or "")
        records.append(
            DividendRecord(
                code=str(item.get("SECURITY_CODE") or ""),
                name=str(item.get("SECURITY_NAME_ABBR") or ""),
                ex_date=ex_date,
                fiscal_year=report_date.year,
                cash_per_share=round(per_ten / 10, 6),
                plan=plan,
                is_special="特别" in plan,
            )
        )
    return records


def fetch_dividends(code: str) -> list[DividendRecord]:
    records: list[DividendRecord] = []
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
                "sortColumns": "EX_DIVIDEND_DATE",
            }
        )
        payload = _get_json(
            f"{DIVIDEND_API}?{query}",
            "https://data.eastmoney.com/",
        )
        pages = int((payload.get("result") or {}).get("pages") or 1)
        records.extend(parse_dividends(payload))
        page += 1
    return records


def fetch_dividends_bulk(
    *,
    since: date | None = None,
    page_size: int = 500,
) -> list[DividendRecord]:
    """Fetch all implemented dividends since a date in ~30 bulk pages."""
    cutoff = since or (date.today().replace(month=1, day=1) - timedelta(days=365))
    records: list[DividendRecord] = []
    page = 1
    pages = 1
    while page <= pages:
        query = urllib.parse.urlencode(
            {
                "reportName": "RPT_SHAREBONUS_DET",
                "columns": "ALL",
                "filter": f"(EX_DIVIDEND_DATE>='{cutoff.isoformat()}')",
                "pageNumber": page,
                "pageSize": page_size,
                "sortTypes": -1,
                "sortColumns": "EX_DIVIDEND_DATE",
            }
        )
        payload = _get_json(
            f"{DIVIDEND_API}?{query}",
            "https://data.eastmoney.com/",
        )
        result = payload.get("result") or {}
        pages = int(result.get("pages") or 1)
        records.extend(parse_dividends(payload))
        page += 1
    return records


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
        if cutoff < record.ex_date <= today
    )
    if cash <= 0:
        return None, 0.0
    return round(cash / price * 100, 2), round(cash, 6)


def latest_fiscal_year_yield(
    records: list[DividendRecord], price: float, *, as_of: date | None = None
) -> float | None:
    today = as_of or date.today()
    years = [record.fiscal_year for record in records if record.ex_date <= today]
    if not years or price <= 0:
        return None
    year = max(years)
    cash = sum(
        float(record.cash_per_share)
        for record in records
        if record.fiscal_year == year and record.ex_date <= today
    )
    return round(cash / price * 100, 2) if cash > 0 else None

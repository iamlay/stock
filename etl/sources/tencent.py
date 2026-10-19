from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date, timedelta

from etl.sources.eastmoney import DailyBar, DailySeries

API = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
USER_AGENT = "Mozilla/5.0 (compatible; StockLabETL/0.1)"


def symbol_for(code: str) -> str:
    prefix = "sh" if code.startswith(("5", "6", "9")) else "sz"
    return f"{prefix}{code}"


def parse_qfqday(code: str, name: str, rows: list[list[str]]) -> DailySeries:
    bars: list[DailyBar] = []
    previous_close: float | None = None
    for row in rows:
        if len(row) < 6:
            continue
        try:
            close = float(row[2])
            high = float(row[3])
            low = float(row[4])
            amplitude = round((high - low) / previous_close * 100, 4) if previous_close else 0.0
            bars.append(
                DailyBar(
                    trade_date=date.fromisoformat(row[0]),
                    open=float(row[1]),
                    close=close,
                    high=high,
                    low=low,
                    volume=int(float(row[5])),
                    amount=0.0,
                    amplitude=amplitude,
                )
            )
            previous_close = close
        except (ValueError, OverflowError):
            continue
    return DailySeries(code=code, name=name, bars=bars, source="tencent")


def _fetch_chunk(code: str, start: date, end: date, timeout: int) -> list[list[str]]:
    params = f"{symbol_for(code)},day,{start.isoformat()},{end.isoformat()},800,qfq"
    query = urllib.parse.urlencode({"param": params})
    request = urllib.request.Request(
        f"{API}?{query}",
        headers={"User-Agent": USER_AGENT, "Referer": "https://gu.qq.com/"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    data = payload.get("data") or {}
    node = data.get(symbol_for(code)) or {}
    return list(node.get("qfqday") or node.get("day") or [])


def fetch_daily_tencent(
    code: str,
    start: date,
    end: date,
    *,
    timeout: int = 30,
) -> DailySeries:
    """Fetch forward-adjusted daily bars from Tencent, chunked by two years.

    Tencent caps a single response near 800 rows, so long histories are paged.
    """
    rows: dict[str, list[str]] = {}
    cursor = start
    while cursor <= end:
        chunk_end = min(date(cursor.year + 1, 12, 31), end)
        for row in _fetch_chunk(code, cursor, chunk_end, timeout):
            rows[row[0]] = row
        cursor = chunk_end + timedelta(days=1)

    series = parse_qfqday(code, code, [rows[key] for key in sorted(rows)])
    return series

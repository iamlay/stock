from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date

API = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
FIELDS1 = "f1,f2,f3,f4,f5,f6"
FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58"
USER_AGENT = "Mozilla/5.0 (compatible; StockLabETL/0.1)"


@dataclass(frozen=True)
class DailyBar:
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float
    amplitude: float


@dataclass(frozen=True)
class DailySeries:
    code: str
    name: str
    bars: list[DailyBar]
    source: str = "eastmoney"


def secid_for(code: str) -> str:
    """Eastmoney secid: 1.<code> for Shanghai, 0.<code> for Shenzhen."""
    if code.startswith(("5", "6", "9")):
        return f"1.{code}"
    return f"0.{code}"


def parse_klines(code: str, name: str, rows: list[str]) -> DailySeries:
    """Parse Eastmoney CSV-like kline rows into a typed series.

    Rows look like: 2024-01-02,3.222,3.173,3.222,3.171,9429306,3269676679.000,1.58
    (date, open, close, high, low, volume, amount, amplitude)
    """
    bars: list[DailyBar] = []
    for row in rows:
        parts = row.split(",")
        if len(parts) < 8:
            continue
        try:
            bars.append(
                DailyBar(
                    trade_date=date.fromisoformat(parts[0]),
                    open=float(parts[1]),
                    close=float(parts[2]),
                    high=float(parts[3]),
                    low=float(parts[4]),
                    volume=int(float(parts[5])),
                    amount=float(parts[6]),
                    amplitude=float(parts[7]),
                )
            )
        except (ValueError, OverflowError):
            continue
    return DailySeries(code=code, name=name, bars=bars)


def fetch_daily(
    code: str,
    beg: str = "20160101",
    end: str = "20500101",
    *,
    timeout: int = 30,
    retries: int = 3,
) -> DailySeries:
    """Fetch daily forward-adjusted bars from Eastmoney.

    Raises RuntimeError after exhausting retries so the job can fail loudly.
    """
    query = urllib.parse.urlencode(
        {
            "secid": secid_for(code),
            "fields1": FIELDS1,
            "fields2": FIELDS2,
            "klt": "101",
            "fqt": "1",
            "beg": beg,
            "end": end,
        }
    )
    url = f"{API}?{query}"
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": USER_AGENT, "Referer": "https://quote.eastmoney.com/"},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
            data = payload.get("data") or {}
            name = str(data.get("name") or code)
            return parse_klines(code, name, list(data.get("klines") or []))
        except Exception as exc:  # noqa: BLE001 - retried and re-raised below
            last_error = exc
            if attempt < retries:
                time.sleep(attempt * 1.5)

    raise RuntimeError(f"eastmoney fetch failed for {code}: {last_error}") from last_error

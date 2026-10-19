from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime

API = "https://danjuanfunds.com/djapi/index_eva/detail"
USER_AGENT = "Mozilla/5.0 (compatible; StockLabETL/0.1)"


@dataclass(frozen=True)
class ValuationSnapshot:
    index_code: str
    name: str
    trade_date: date
    pe: float
    pb: float
    pe_percentile: float  # 0-1
    pb_percentile: float  # 0-1
    dividend_yield: float  # 0-1
    bond_yield: float  # 0-1


def parse_detail(index_code: str, payload: dict) -> ValuationSnapshot:
    data = payload.get("data") or {}
    if not data:
        raise ValueError(f"no valuation data for {index_code}")

    timestamp = int(data.get("ts") or 0)
    trade_date = (
        datetime.fromtimestamp(timestamp / 1000, tz=UTC).date() if timestamp else date.today()
    )
    return ValuationSnapshot(
        index_code=index_code,
        name=str(data.get("name") or index_code),
        trade_date=trade_date,
        pe=float(data.get("pe") or 0),
        pb=float(data.get("pb") or 0),
        pe_percentile=float(data.get("pe_percentile") or 0),
        pb_percentile=float(data.get("pb_percentile") or 0),
        dividend_yield=float(data.get("yeild") or 0),
        bond_yield=float(data.get("bond_yeild") or 0),
    )


def fetch_valuation(index_code: str, *, timeout: int = 20, retries: int = 2) -> ValuationSnapshot:
    url = f"{API}/{index_code}"
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": USER_AGENT, "Referer": "https://danjuanfunds.com/"},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
            return parse_detail(index_code, payload)
        except Exception as exc:  # noqa: BLE001 - retried and re-raised below
            last_error = exc
            if attempt < retries:
                time.sleep(attempt)

    raise RuntimeError(f"danjuan valuation failed for {index_code}: {last_error}") from last_error

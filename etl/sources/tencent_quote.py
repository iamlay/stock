from __future__ import annotations

import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime

API = "https://qt.gtimg.cn/q="
USER_AGENT = "Mozilla/5.0 (compatible; StockLabETL/0.1)"


@dataclass(frozen=True)
class EtfQuote:
    code: str
    name: str
    trade_date: date
    quote_time: datetime
    price: float
    prev_close: float
    open: float
    change_pct: float
    high: float
    low: float
    volume: int
    amount: float
    aum: float  # 亿元
    shares: float  # 亿份


def symbol_for(code: str) -> str:
    prefix = "sh" if code.startswith(("5", "6", "9")) else "sz"
    return f"{prefix}{code}"


def _to_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_quote_line(code: str, body: str) -> EtfQuote | None:
    fields = body.split("~")
    if len(fields) < 45:
        return None

    price = _to_float(fields[3])
    if price <= 0:
        return None

    stamp = fields[30] if len(fields) > 30 else ""
    try:
        trade_date = date(int(stamp[0:4]), int(stamp[4:6]), int(stamp[6:8]))
        quote_time = datetime(
            int(stamp[0:4]),
            int(stamp[4:6]),
            int(stamp[6:8]),
            int(stamp[8:10]),
            int(stamp[10:12]),
            int(stamp[12:14]),
        )
    except (ValueError, IndexError):
        trade_date = date.today()
        quote_time = datetime.now()

    aum = _to_float(fields[44])
    return EtfQuote(
        code=code,
        name=fields[1] or code,
        trade_date=trade_date,
        quote_time=quote_time,
        price=price,
        prev_close=_to_float(fields[4]),
        open=_to_float(fields[5]),
        change_pct=_to_float(fields[32]),
        high=_to_float(fields[33]),
        low=_to_float(fields[34]),
        volume=int(_to_float(fields[6])),
        amount=_to_float(fields[37]) * 10_000,
        aum=aum,
        shares=round(aum / price, 4) if aum > 0 else 0.0,
    )


def fetch_quotes(codes: list[str], *, timeout: int = 30) -> list[EtfQuote]:
    """Fetch one batched snapshot for up to ~50 ETF codes from Tencent."""
    if not codes:
        return []

    symbols = ",".join(symbol_for(code) for code in codes)
    request = urllib.request.Request(
        f"{API}{urllib.parse.quote(symbols, safe=',')}",
        headers={"User-Agent": USER_AGENT, "Referer": "https://gu.qq.com/"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read().decode("gbk", errors="replace")

    quotes: list[EtfQuote] = []
    for line in text.replace(";", "\n").splitlines():
        line = line.strip()
        if not line.startswith("v_") or '="' not in line:
            continue
        symbol, body = line.split('="', 1)
        code = symbol[2:][-6:]
        quote = parse_quote_line(code, body.rstrip('"'))
        if quote is not None:
            quotes.append(quote)
    return quotes

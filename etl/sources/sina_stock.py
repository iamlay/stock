from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

API = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"


@dataclass(frozen=True)
class SinaStockRow:
    code: str
    name: str
    price: float
    change_pct: float
    market_cap: float
    pe_ttm: float | None
    pb: float | None
    industry: str
    market: str
    is_st: bool


def _float(value, default: float | None = 0.0) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_rows(items: list[dict]) -> list[SinaStockRow]:
    rows: list[SinaStockRow] = []
    for item in items:
        symbol = str(item.get("symbol") or "")
        if not symbol.startswith(("sh", "sz")):
            continue
        code = str(item.get("code") or symbol[2:])
        name = str(item.get("name") or "")
        price = _float(item.get("trade"))
        if price is None or price <= 0:
            continue
        cap = _float(item.get("mktcap"), 0.0) or 0.0
        rows.append(
            SinaStockRow(
                code=code,
                name=name,
                price=price,
                change_pct=_float(item.get("changepercent"), 0.0) or 0.0,
                market_cap=round(cap / 10_000, 2),
                pe_ttm=_float(item.get("per")),
                pb=_float(item.get("pb")),
                industry="未分类",
                market="SH" if symbol.startswith("sh") else "SZ",
                is_st="ST" in name.upper(),
            )
        )
    return rows


def fetch_stock_universe(
    *, page_size: int = 100, max_pages: int | None = None
) -> tuple[int, list[SinaStockRow]]:
    rows: list[SinaStockRow] = []
    page = 1
    while True:
        query = urllib.parse.urlencode(
            {
                "page": page,
                "num": page_size,
                "sort": "symbol",
                "asc": 1,
                "node": "hs_a",
                "symbol": "",
                "_s_r_a": "page",
            }
        )
        request = urllib.request.Request(
            f"{API}?{query}",
            headers={"User-Agent": USER_AGENT, "Referer": "https://finance.sina.com.cn/"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            items = json.load(response)
        if not items:
            break
        rows.extend(parse_rows(items))
        if max_pages is not None and page >= max_pages:
            break
        page += 1
    return len(rows), rows

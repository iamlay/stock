from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import date
from pathlib import Path

from etl.sources.eastmoney_stock import (
    fetch_dividends,
    fetch_stock_universe,
    latest_fiscal_year_yield,
    ttm_dividend_yield,
)
from etl.sources.sina_stock import fetch_stock_universe as fetch_sina_universe
from etl.sources.tencent import fetch_daily_tencent

SAMPLE_CODES = [
    "600519",
    "601398",
    "600036",
    "601088",
    "600028",
    "601857",
    "600900",
    "601318",
    "000651",
    "000333",
    "600690",
    "601166",
    "601288",
    "601988",
    "600030",
    "600887",
    "000858",
    "600309",
    "601668",
    "600048",
]


def run_probe(
    *,
    samples: int = 10,
    bars: int = 3,
    out_path: Path = Path("etl/out/stock_phase0.json"),
    max_pages: int | None = None,
) -> dict:
    today = date.today()
    source = "eastmoney"
    try:
        total, universe = fetch_stock_universe(max_pages=max_pages)
    except Exception as exc:  # noqa: BLE001 - fallback source
        source = f"sina (eastmoney fallback: {exc})"
        total, universe = fetch_sina_universe(max_pages=max_pages)
    by_code = {row.code: row for row in universe}
    selected = [code for code in SAMPLE_CODES if code in by_code][:samples]

    stocks: list[dict] = []
    for code in selected:
        row = by_code[code]
        try:
            dividends = fetch_dividends(code)
            ttm, cash = ttm_dividend_yield(dividends, row.price, as_of=today)
            fy = latest_fiscal_year_yield(dividends, row.price, as_of=today)
            last_ex = max(
                (item.ex_date for item in dividends if item.ex_date <= today),
                default=None,
            )
            stocks.append(
                {
                    **asdict(row),
                    "ttm_yield": ttm,
                    "ttm_cash": cash,
                    "fy_yield": fy,
                    "dividend_count": len(dividends),
                    "last_ex_date": last_ex.isoformat() if last_ex else None,
                    "sample_dividends": [
                        asdict(item) | {"ex_date": item.ex_date.isoformat()}
                        for item in dividends[:3]
                    ],
                }
            )
        except Exception as exc:  # noqa: BLE001 - report and continue
            stocks.append({**asdict(row), "error": str(exc)})
        time.sleep(0.3)

    bar_samples: list[dict] = []
    for item in stocks[:bars]:
        code = item["code"]
        try:
            series = fetch_daily_tencent(
                code,
                date(today.year - 1, 1, 1),
                today,
            )
            bar_samples.append(
                {
                    "code": code,
                    "rows": len(series.bars),
                    "first": series.bars[0].trade_date.isoformat() if series.bars else None,
                    "last": series.bars[-1].trade_date.isoformat() if series.bars else None,
                    "last_close": series.bars[-1].close if series.bars else None,
                }
            )
        except Exception as exc:  # noqa: BLE001
            bar_samples.append({"code": code, "error": str(exc)})

    report = {
        "generated_at": today.isoformat(),
        "universe": {
            "source": source,
            "total_reported": total,
            "fetched": len(universe),
            "st_count": sum(1 for row in universe if row.is_st),
            "industries": len({row.industry for row in universe}),
            "sample_available": len(selected),
        },
        "stocks": stocks,
        "bars": bar_samples,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def print_report(report: dict, out_path: Path) -> None:
    universe = report["universe"]
    print(f"source: {universe.get('source', 'eastmoney')}")
    print(
        f"universe: total={universe['total_reported']} fetched={universe['fetched']} "
        f"st={universe['st_count']} industries={universe['industries']}"
    )
    print(f"{'code':8} {'name':10} {'price':>8} {'TTM%':>7} {'FY%':>7} {'divs':>5} {'last_ex':>10}")
    for item in report["stocks"]:
        print(
            f"{item['code']:8} {item.get('name', ''):10} "
            f"{item.get('price', 0):8.2f} "
            f"{item.get('ttm_yield') if item.get('ttm_yield') is not None else '-':>7} "
            f"{item.get('fy_yield') if item.get('fy_yield') is not None else '-':>7} "
            f"{item.get('dividend_count', 0):5d} "
            f"{item.get('last_ex_date') or '-':>10}"
        )
    for item in report["bars"]:
        if "error" in item:
            print(f"bars {item['code']}: ERROR {item['error']}")
        else:
            print(
                f"bars {item['code']}: rows={item['rows']} "
                f"{item['first']} -> {item['last']} close={item['last_close']}"
            )
    print(f"report: {out_path}")

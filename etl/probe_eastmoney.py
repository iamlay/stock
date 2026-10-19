#!/usr/bin/env python3
"""Probe Eastmoney's public daily K-line endpoint.

Sprint 0 uses this to prove the data path works before the real ETL lands in W2.
It writes a CSV under etl/out/ and validates basic OHLC invariants.

Usage:
    python etl/probe_eastmoney.py --code 510300
    python etl/probe_eastmoney.py --code 159941 --beg 20200101
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path

API = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
FIELDS1 = "f1,f2,f3,f4,f5,f6"
FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58"


@dataclass
class Bar:
    trade_date: str
    open: float
    close: float
    high: float
    low: float
    volume: int
    amount: float
    amplitude: float


def secid_for(code: str) -> str:
    """Eastmoney secid: 1.<code> for Shanghai, 0.<code> for Shenzhen."""
    if code.startswith(("5", "6", "9")):
        return f"1.{code}"
    return f"0.{code}"


def fetch(code: str, beg: str, end: str) -> tuple[str, list[Bar]]:
    query = urllib.parse.urlencode(
        {
            "secid": secid_for(code),
            "fields1": FIELDS1,
            "fields2": FIELDS2,
            "klt": "101",  # daily
            "fqt": "1",  # forward adjusted
            "beg": beg,
            "end": end,
        }
    )
    request = urllib.request.Request(
        f"{API}?{query}",
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; StockLabProbe/0.1)",
            "Referer": "https://quote.eastmoney.com/",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)

    data = payload.get("data") or {}
    name = str(data.get("name") or code)
    bars: list[Bar] = []
    for row in data.get("klines") or []:
        parts = row.split(",")
        if len(parts) < 8:
            continue
        bars.append(
            Bar(
                trade_date=parts[0],
                open=float(parts[1]),
                close=float(parts[2]),
                high=float(parts[3]),
                low=float(parts[4]),
                volume=int(parts[5]),
                amount=float(parts[6]),
                amplitude=float(parts[7]),
            )
        )
    return name, bars


def validate(bars: list[Bar]) -> list[str]:
    errors: list[str] = []
    if not bars:
        return ["no rows returned"]

    seen: set[str] = set()
    previous = ""
    for bar in bars:
        if bar.trade_date in seen:
            errors.append(f"duplicate date {bar.trade_date}")
        seen.add(bar.trade_date)
        if bar.trade_date <= previous:
            errors.append(f"date not ascending at {bar.trade_date}")
        previous = bar.trade_date
        if bar.high < bar.low:
            errors.append(f"high < low on {bar.trade_date}")
        if not (bar.low <= bar.close <= bar.high):
            errors.append(f"close outside low/high on {bar.trade_date}")
        if bar.open <= 0 or bar.close <= 0:
            errors.append(f"non-positive price on {bar.trade_date}")
    return errors


def write_csv(path: Path, bars: list[Bar]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["trade_date", "open", "close", "high", "low", "volume", "amount", "amplitude"])
        for bar in bars:
            writer.writerow(
                [
                    bar.trade_date,
                    bar.open,
                    bar.close,
                    bar.high,
                    bar.low,
                    bar.volume,
                    bar.amount,
                    bar.amplitude,
                ]
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Eastmoney daily K-line data")
    parser.add_argument("--code", default="510300", help="ETF/stock code, e.g. 510300")
    parser.add_argument("--beg", default="20160101", help="start date YYYYMMDD")
    parser.add_argument("--end", default="20500101", help="end date YYYYMMDD")
    parser.add_argument("--out", default="etl/out", help="output directory")
    args = parser.parse_args()

    name, bars = fetch(args.code, args.beg, args.end)
    errors = validate(bars)
    output = Path(args.out) / f"{args.code}_daily.csv"
    write_csv(output, bars)

    print(f"code    : {args.code}")
    print(f"name    : {name}")
    print(f"rows    : {len(bars)}")
    if bars:
        print(f"range   : {bars[0].trade_date} -> {bars[-1].trade_date}")
        print(f"last    : close={bars[-1].close} volume={bars[-1].volume}")
    print(f"csv     : {output}")
    print(f"checked : {date.today().isoformat()}")

    if errors:
        print(f"INVALID : {len(errors)} issue(s)", file=sys.stderr)
        for error in errors[:5]:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("status  : OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

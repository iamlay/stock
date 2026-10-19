"""External data source adapters."""

from etl.sources.eastmoney import DailyBar, DailySeries, fetch_daily, parse_klines
from etl.sources.tencent import fetch_daily_tencent

__all__ = [
    "DailyBar",
    "DailySeries",
    "fetch_daily",
    "fetch_daily_tencent",
    "parse_klines",
]

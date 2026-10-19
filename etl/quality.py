from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from etl.sources.eastmoney import DailySeries


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str  # pass | warn | fail
    detail: dict


def _status(count: int, *, warn: bool = False) -> str:
    if count == 0:
        return "pass"
    return "warn" if warn else "fail"


def check_series(
    series: DailySeries,
    *,
    min_rows: int = 250,
    expected_latest: date | None = None,
) -> list[CheckResult]:
    """Run deterministic quality checks over one series.

    Pure function: no database, no network. Used by the pipeline and tests.
    """
    bars = series.bars
    results: list[CheckResult] = []

    results.append(
        CheckResult(
            name="non_empty",
            status="pass" if bars else "fail",
            detail={"rows": len(bars), "code": series.code},
        )
    )

    results.append(
        CheckResult(
            name="row_count",
            status="pass" if len(bars) >= min_rows else "warn",
            detail={"rows": len(bars), "min_rows": min_rows},
        )
    )

    duplicates = 0
    unordered = 0
    ohlc_violations = 0
    non_positive = 0
    negative_volume = 0
    previous: date | None = None
    seen: set[date] = set()

    for bar in bars:
        if bar.trade_date in seen:
            duplicates += 1
        seen.add(bar.trade_date)
        if previous is not None and bar.trade_date <= previous:
            unordered += 1
        previous = bar.trade_date

        if bar.high < bar.low or not (bar.low <= bar.close <= bar.high):
            ohlc_violations += 1
        if min(bar.open, bar.high, bar.low, bar.close) <= 0:
            non_positive += 1
        if bar.volume < 0:
            negative_volume += 1

    results.append(
        CheckResult(
            name="unique_dates",
            status=_status(duplicates),
            detail={"duplicates": duplicates},
        )
    )
    results.append(
        CheckResult(
            name="date_order",
            status=_status(unordered),
            detail={"unordered": unordered},
        )
    )
    results.append(
        CheckResult(
            name="ohlc_bounds",
            status=_status(ohlc_violations),
            detail={"violations": ohlc_violations},
        )
    )
    results.append(
        CheckResult(
            name="price_positive",
            status=_status(non_positive),
            detail={"violations": non_positive},
        )
    )
    results.append(
        CheckResult(
            name="volume_non_negative",
            status=_status(negative_volume),
            detail={"violations": negative_volume},
        )
    )

    if expected_latest is not None and bars:
        latest = bars[-1].trade_date
        lag = (expected_latest - latest).days
        results.append(
            CheckResult(
                name="freshness",
                status="pass" if lag <= 7 else "warn",
                detail={"latest": latest.isoformat(), "lag_days": lag},
            )
        )

    return results


def has_failures(results: list[CheckResult]) -> bool:
    return any(result.status == "fail" for result in results)


def expected_latest_trading_day(today: date | None = None) -> date:
    """Approximate last expected trading day: today or the previous weekday."""
    current = today or date.today()
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current

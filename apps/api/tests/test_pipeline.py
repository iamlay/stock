from datetime import date

from etl import pipeline
from etl.sources.eastmoney import DailyBar, DailySeries
from sqlalchemy import func, select

from app.db.models import DataJob, DataQualityCheck, MarketDaily, TradingCalendar


def make_series(code: str = "510300") -> DailySeries:
    bars = [
        DailyBar(date(2024, 1, 2), 1.0, 1.0, 1.0, 1.0, 100, 100.0, 0.0),
        DailyBar(date(2024, 1, 3), 1.0, 1.1, 1.0, 1.1, 110, 110.0, 0.0),
        DailyBar(date(2024, 1, 4), 1.0, 1.2, 1.0, 1.2, 120, 120.0, 0.0),
    ]
    return DailySeries(code=code, name="沪深300ETF", bars=bars, source="test")


def test_seed_universe(session) -> None:
    count = pipeline.seed_universe(session)
    assert count == 20
    assert session.scalar(select(func.count()).select_from(MarketDaily)) == 0

    # Idempotent
    assert pipeline.seed_universe(session) == 20


def test_sync_code_is_idempotent(session, monkeypatch) -> None:
    pipeline.seed_universe(session)
    monkeypatch.setattr(pipeline, "_fetch_series", lambda code, start, end: make_series(code))

    result = pipeline.sync_code(session, "510300", date(2024, 1, 1), date(2024, 1, 5))
    assert result.rows == 3
    assert result.status == "success"
    assert session.scalar(select(func.count()).select_from(MarketDaily)) == 3

    # Second run replaces the window instead of duplicating it.
    pipeline.sync_code(session, "510300", date(2024, 1, 1), date(2024, 1, 5))
    assert session.scalar(select(func.count()).select_from(MarketDaily)) == 3

    jobs = session.scalars(select(DataJob)).all()
    assert len(jobs) == 2
    assert all(job.status == "success" for job in jobs)
    checks = session.scalars(select(DataQualityCheck)).all()
    assert len(checks) == 14  # 7 checks per historical run (no freshness check)


def test_sync_calendar_is_idempotent(session) -> None:
    dates = {date(2024, 1, 2), date(2024, 1, 3)}
    assert pipeline.sync_calendar(session, dates) == 2
    assert pipeline.sync_calendar(session, dates) == 0
    assert session.scalar(select(func.count()).select_from(TradingCalendar)) == 2


def test_sync_all_collects_calendar(session, monkeypatch) -> None:
    pipeline.seed_universe(session)
    monkeypatch.setattr(pipeline, "_fetch_series", lambda code, start, end: make_series(code))

    results = pipeline.sync_all(session, date(2024, 1, 1), date(2024, 1, 5), delay_seconds=0)
    assert len(results) == 20
    assert all(item.status == "success" for item in results)
    assert session.scalar(select(func.count()).select_from(TradingCalendar)) == 3

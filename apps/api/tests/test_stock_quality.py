from datetime import UTC, date, datetime, timedelta

from etl.stock_quality import run_stock_quality, write_quality_checks
from etl.stocks import upsert_stock_universe

from app.db.models import DataJob, StockMetric
from tests.test_stock_etl import make_row


def test_stock_quality_flags_high_yield_and_missing_industry(session) -> None:
    upsert_stock_universe(
        session,
        [make_row("600519", "贵州茅台", 18800), make_row("000001", "平安银行", 2000)],
    )
    high = session.get(StockMetric, "600519")
    high.price = 10
    high.dividend_yield_ttm = 16
    high.dividend_yield_fy = 4
    high.updated_at = datetime.now(UTC) - timedelta(days=10)
    session.commit()

    report = run_stock_quality(session, as_of=date(2026, 10, 21))
    checks = report["summary"]["checks"]
    assert checks["yield_high"]["count"] == 1
    assert checks["ttm_fy_divergence"]["count"] == 1
    assert checks["industry_missing"]["count"] == 2
    assert checks["stale_metrics"]["count"] == 1

    write_quality_checks(session, report)
    assert session.query(DataJob).filter_by(job_name="stock_quality").count() == 1

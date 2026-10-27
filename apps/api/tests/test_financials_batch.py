from datetime import date

from etl.stocks import (
    expected_financial_report_date,
    sync_stock_financials_batch,
)

from app.db.models import (
    Instrument,
    StockFinancial,
    StockMetric,
    StockProfile,
)


def _stock(session, code: str, index: int) -> None:
    session.add(
        Instrument(
            code=code,
            name=f"测试{code}",
            type="stock",
            exchange="SH",
            lot_size=100,
            is_active=True,
        )
    )
    session.add(StockProfile(code=code, status="active"))
    session.add(StockMetric(code=code, dividend_yield_ttm=10 - index))


def test_financials_shard_and_incremental_skip(session, monkeypatch) -> None:
    codes = [f"60000{index}" for index in range(6)]
    for index, code in enumerate(codes):
        _stock(session, code, index)
    session.commit()

    called: list[str] = []
    monkeypatch.setattr(
        "etl.stocks.fetch_stock_financials",
        lambda code: called.append(code) or [],
    )

    shard = sync_stock_financials_batch(
        session, limit=6, delay=0, shard_index=0, shard_count=5
    )
    assert shard["selected"] == 2
    assert called == [codes[0], codes[5]]

    session.add(
        StockFinancial(
            code=codes[0],
            report_date=expected_financial_report_date(date.today()),
            period="Q3",
        )
    )
    session.commit()

    called.clear()
    incremental = sync_stock_financials_batch(
        session, limit=6, delay=0, shard_index=0, shard_count=1
    )
    assert incremental["skipped"] == 1
    assert codes[0] not in called
    assert called == codes[1:]

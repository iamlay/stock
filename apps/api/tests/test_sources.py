from datetime import date

from etl.sources.danjuan import parse_detail
from etl.sources.eastmoney import parse_klines
from etl.sources.tencent import parse_qfqday


def test_parse_eastmoney_rows() -> None:
    rows = [
        "2024-01-02,3.222,3.173,3.222,3.171,9429306,3269676679.000,1.58",
        "bad-row",
        "2024-01-03,3.166,3.163,3.180,3.148,10617503,3654757871.000,1.01",
    ]
    series = parse_klines("510300", "沪深300ETF", rows)
    assert len(series.bars) == 2
    assert series.bars[0].trade_date == date(2024, 1, 2)
    assert series.bars[1].close == 3.163
    assert series.source == "eastmoney"


def test_parse_tencent_rows() -> None:
    rows = [
        ["2024-01-02", "3.222", "3.173", "3.222", "3.171", "9429306.000"],
        ["2024-01-03", "3.166", "3.163", "3.180", "3.148", "10617503.000"],
    ]
    series = parse_qfqday("510300", "510300", rows)
    assert len(series.bars) == 2
    assert series.bars[0].volume == 9429306
    assert series.source == "tencent"


def test_parse_danjuan_valuation() -> None:
    payload = {
        "data": {
            "name": "沪深300",
            "pe": 12.9964,
            "pb": 1.3781,
            "pe_percentile": 0.5548,
            "pb_percentile": 0.2972,
            "yeild": 0.0282,
            "bond_yeild": 0.05,
            "ts": 1792080000000,
        }
    }
    snapshot = parse_detail("SH000300", payload)
    assert snapshot.name == "沪深300"
    assert snapshot.pe == 12.9964
    assert snapshot.pe_percentile == 0.5548
    assert snapshot.dividend_yield == 0.0282
    assert snapshot.trade_date.year == 2026

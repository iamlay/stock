from datetime import date

from etl.sources.eastmoney_stock import (
    DividendRecord,
    latest_fiscal_year_yield,
    parse_dividends,
    parse_stock_rows,
    ttm_dividend_yield,
)
from etl.sources.industry import parse_eastmoney_company, parse_sina_nodes
from etl.sources.sina_stock import parse_rows as parse_sina_rows


def test_parse_stock_rows() -> None:
    payload = {
        "data": {
            "total": 2,
            "diff": [
                {
                    "f12": "600519",
                    "f14": "贵州茅台",
                    "f2": 1500.0,
                    "f3": 1.2,
                    "f13": 1,
                    "f20": 1880000000000,
                    "f9": 22.1,
                    "f23": 8.2,
                    "f100": "食品饮料",
                },
                {
                    "f12": "000001",
                    "f14": "ST平安",
                    "f2": 10.0,
                    "f3": -1.0,
                    "f13": 0,
                    "f20": 10000000000,
                    "f9": 5.0,
                    "f23": 0.8,
                    "f100": "银行",
                },
            ],
        }
    }
    rows = parse_stock_rows(payload)
    assert len(rows) == 2
    assert rows[0].code == "600519"
    assert rows[0].market == "SH"
    assert rows[0].market_cap == 18800.0
    assert rows[1].is_st is True


def test_parse_dividends_converts_per_ten_shares() -> None:
    payload = {
        "result": {
            "data": [
                {
                    "SECURITY_CODE": "600519",
                    "SECURITY_NAME_ABBR": "贵州茅台",
                    "PRETAX_BONUS_RMB": 280.2423,
                    "REPORT_DATE": "2025-12-31 00:00:00",
                    "EX_DIVIDEND_DATE": "2026-06-26 00:00:00",
                    "ASSIGN_PROGRESS": "实施分配",
                    "IMPL_PLAN_PROFILE": "10派280.2423元(含税)",
                },
                {
                    "SECURITY_CODE": "600519",
                    "SECURITY_NAME_ABBR": "贵州茅台",
                    "PRETAX_BONUS_RMB": 100.0,
                    "REPORT_DATE": "2024-12-31 00:00:00",
                    "EX_DIVIDEND_DATE": None,
                    "ASSIGN_PROGRESS": "股东大会通过",
                    "IMPL_PLAN_PROFILE": "10派100元",
                },
            ]
        }
    }
    records = parse_dividends(payload)
    assert len(records) == 1
    assert records[0].cash_per_share == 28.02423
    assert records[0].fiscal_year == 2025


def test_ttm_and_fiscal_year_yield() -> None:
    records = [
        DividendRecord("600519", "贵州茅台", date(2026, 6, 26), 2025, 28.02423, "", False),
        DividendRecord("600519", "贵州茅台", date(2025, 12, 19), 2025, 23.957, "", False),
        DividendRecord("600519", "贵州茅台", date(2025, 6, 26), 2024, 27.673, "", False),
    ]
    ttm, cash = ttm_dividend_yield(records, 1325.0, as_of=date(2026, 10, 20))
    assert cash == 51.98123
    assert ttm == 3.92

    fy = latest_fiscal_year_yield(records, 1325.0, as_of=date(2026, 10, 20))
    assert fy == 3.92


def test_fiscal_year_ignores_current_partial_year() -> None:
    records = [
        DividendRecord("603165", "荣晟环保", date(2026, 9, 8), 2026, 0.6, "", False),
        DividendRecord("603165", "荣晟环保", date(2026, 6, 9), 2025, 1.1, "", False),
        DividendRecord("603165", "荣晟环保", date(2026, 2, 9), 2025, 0.38, "", False),
    ]
    fy = latest_fiscal_year_yield(records, 12.96, as_of=date(2026, 10, 20))
    assert fy == 11.42


def test_no_dividend_returns_none() -> None:
    ttm, cash = ttm_dividend_yield([], 10.0, as_of=date(2026, 10, 20))
    assert ttm is None
    assert cash == 0.0


def test_parse_sina_rows_filters_bj() -> None:
    rows = parse_sina_rows(
        [
            {
                "symbol": "sh600519",
                "code": "600519",
                "name": "贵州茅台",
                "trade": "1500.00",
                "changepercent": 1.2,
                "per": 22.1,
                "pb": 8.2,
                "mktcap": 188000000,
            },
            {
                "symbol": "bj920000",
                "code": "920000",
                "name": "北交所",
                "trade": "13.47",
            },
        ]
    )
    assert len(rows) == 1
    assert rows[0].code == "600519"
    assert rows[0].market == "SH"
    assert rows[0].market_cap == 18800.0


def test_parse_sina_industry_nodes() -> None:
    payload = [
        "行情中心",
        [
            [
                "A股",
                [
                    [
                        "新浪行业",
                        [
                            ["玻璃行业", "", "new_blhy"],
                            ["传媒娱乐", "", "new_cmyl"],
                        ],
                    ]
                ],
            ]
        ],
    ]
    nodes = parse_sina_nodes(payload)
    assert len(nodes) == 2
    assert nodes[0].code == "new_blhy"


def test_parse_eastmoney_company_survey() -> None:
    payload = {
        "jbzl": [
            {
                "SECURITY_NAME_ABBR": "贵州茅台",
                "EM2016": "食品饮料-饮料-白酒",
                "INDUSTRYCSRC1": "制造业-酒、饮料和精制茶制造业",
                "SECURITY_TYPE": "上交所主板A股",
            }
        ],
        "fxxg": [{"LISTING_DATE": "2001-08-27 00:00:00"}],
    }
    company = parse_eastmoney_company(payload, "600519")
    assert company.name == "贵州茅台"
    assert company.eastmoney_industry == "食品饮料-饮料-白酒"
    assert company.listing_date == "2001-08-27"

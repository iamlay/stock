from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from test_portfolio import clients as clients
from test_portfolio_ledger import ledger as ledger
from test_portfolio_positions import call, input_data, save

from app.db.models import DividendEvent, DividendEventVersion, StockDividend, StockMetric
from app.services.portfolio_dividend_reference import reference

DAY = date(2026, 10, 28)


def legacy(session, day=date(2026, 7, 13), cash="1.03", report=date(2025, 12, 31), **changes):
    row = StockDividend(
        code="600036",
        ex_date=day,
        cash_per_share=Decimal(cash),
        report_date=report,
        fiscal_year=(report or DAY).year,
        progress="实施分配",
        plan=f"10派{Decimal(cash) * 10}元(含税)",
        source="eastmoney",
    )
    for k, v in changes.items():
        setattr(row, k, v)
    session.add(row)
    session.flush()
    return row


def event(session, row=None, *, cash="2", stage="implemented", reviewed=True):
    e = DividendEvent(
        id=str(uuid4()),
        code="600036",
        current_revision=1,
        origin="manual_review",
        legacy_dividend_id=row.id if row else None,
    )
    session.add(e)
    session.flush()
    v = DividendEventVersion(
        event_id=e.id,
        revision=1,
        source="eastmoney",
        report_date=date(2025, 12, 31),
        ex_date=date(2026, 7, 13),
        cash_per_share=Decimal(cash),
        plan="10派20元",
        progress="实施分配",
        stage=stage,
        evidence_status="reviewed" if reviewed else "legacy_unverified",
        review_reasons=[],
        rule_version="v2-49.1",
        raw_payload={},
        review_note="sample",
        observed_at=datetime.now(UTC),
    )
    session.add(v)
    session.flush()
    return e, v


def ref(session, window="12", **kwargs):
    return reference(
        session,
        "600036",
        dict(forecast=window, custom=kwargs.get("custom")),
        Decimal("1000"),
        as_of=kwargs.get("as_of", DAY),
    )


def test_existing_detail_records_compute_cash_and_price_yield(ledger, session, monkeypatch):
    monkeypatch.setattr("app.services.portfolio_positions.today", lambda: DAY)
    legacy(session)
    legacy(session, date(2026, 10, 26), "0.98", date(2026, 6, 30))
    session.add(
        StockMetric(
            code="600036", price=Decimal("49.38"), updated_at=datetime(2026, 10, 27, tzinfo=UTC)
        )
    )
    session.commit()
    data = input_data(quantity="1000", preferences=dict(forecast="12"))
    preview = call(ledger, "position-preview", data)
    assert preview["summary"]["forecast"]["annual_per_share"] == "2.010000"
    result = save(ledger, data)
    p = result["positions"][0]
    assert p["forecast"]["annual_amount"] == "2010.000000"
    assert p["forecast"]["status"] == "historical_reference"
    assert p["price_yield"] == "4.070474"
    assert p["price_yield_status"] == "available"
    assert p["quote"]["source"] == "stock_metrics"
    assert p["quote"]["time_label"] == "行情快照更新时间"
    assert p["forecast"]["coverage_verified"] is False


def test_fixed_three_year_denominator_and_empty_year_not_claimed_zero(ledger, session):
    legacy(session, date(2026, 7, 13), "2")
    legacy(session, date(2024, 7, 13), "4", date(2023, 12, 31))
    r = ref(session, "36")
    assert r["annual_per_share"] == "2.000000"
    assert r["divisor_years"] == 3
    assert r["periods"][1]["recorded_cash"] is None
    assert "不等于已确认零分红" in r["note"]


@pytest.mark.parametrize("months,years", [("12", 1), ("36", 3), ("60", 5)])
def test_exact_ex_date_window_boundaries(ledger, session, months, years):
    legacy(session, date(2026 - years, 10, 28), "100")  # left boundary excluded
    legacy(session, date(2026 - years, 10, 29), "5", date(2026 - years, 6, 30))
    legacy(session, DAY, "10", date(2026, 6, 30))
    legacy(session, date(2026, 10, 29), "100", date(2026, 9, 30))
    assert Decimal(ref(session, months)["annual_per_share"]) == Decimal(15) / years


def test_leap_day_window(ledger, session):
    r = ref(session, as_of=date(2024, 2, 29))
    assert r["from_date"] == date(2023, 2, 28)


def test_previews_special_zero_and_proposals_not_counted_as_income(ledger, session):
    legacy(session)
    legacy(session, date(2026, 9, 1), "99", date(2026, 6, 30), is_special=True)
    legacy(session, None, "88", date(2026, 9, 30), progress="董事会预案")
    legacy(session, date(2026, 8, 1), "77", date(2026, 3, 31), progress="取消分配")
    r = ref(session)
    assert r["annual_per_share"] == "1.030000"
    assert sum(d["included"] for d in r["details"]) == 1
    assert len(r["details"]) == 4


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"ex_date": None}, "missing_date"),
        ({"plan": "10转增2派10.3"}, "corporate_action"),
        ({"progress": "未知状态"}, "unknown_stage"),
    ],
)
def test_bad_records_have_specific_reason(ledger, session, changes, reason):
    legacy(session, **changes)
    r = ref(session)
    assert r["annual_per_share"] is None
    assert r["reason"] == reason
    assert r["reason_label"] != "资料不足"


def test_zero_share_distribution_does_not_block_cash(ledger, session):
    legacy(session, plan="10送0转0派10.3")
    assert ref(session)["annual_per_share"] == "1.030000"


def test_reviewed_revision_overrides_legacy_without_double_count(ledger, session):
    row = legacy(session)
    e, v = event(session, row, cash="2")
    # Only the current revision is used, even when old versions still exist.
    v2 = DividendEventVersion(
        **{c.name: getattr(v, c.name) for c in v.__table__.columns if c.name != "created_at"}
    )
    v2.revision = 2
    v2.cash_per_share = Decimal("3")
    session.add(v2)
    e.current_revision = 2
    session.flush()
    r = ref(session)
    assert r["annual_per_share"] == "3.000000" and len(r["details"]) == 1


def test_unreviewed_backfill_does_not_override_updated_legacy(ledger, session):
    row = legacy(session)
    event(session, row, cash="9", reviewed=False)
    assert ref(session)["annual_per_share"] == "1.030000"


def test_unlinked_reviewed_event_replaces_matching_legacy(ledger, session):
    legacy(session)
    event(session, cash="2")
    assert ref(session)["annual_per_share"] == "2.000000"


def test_cancellation_suppresses_linked_legacy(ledger, session):
    row = legacy(session)
    event(session, row, stage="cancelled")
    assert ref(session)["annual_per_share"] is None


def test_duplicate_plans_not_double_counted_and_conflicts_not_guessed(ledger, session):
    legacy(session)
    legacy(session, plan="每10股派10.30元")
    assert ref(session)["annual_per_share"] == "1.030000"
    legacy(session, cash="2", plan="10派20元")
    r = ref(session)
    assert r["annual_per_share"] is None and r["reason"] == "conflicting_records"


def test_same_report_multiple_dates_remain_separate(ledger, session):
    legacy(session)
    legacy(session, day=date(2026, 10, 26), cash="2")
    assert ref(session)["annual_per_share"] == "3.030000"


def test_missing_quote_is_separate_from_missing_reference(ledger, session, monkeypatch):
    monkeypatch.setattr("app.services.portfolio_positions.today", lambda: DAY)
    legacy(session)
    session.commit()
    p = save(ledger, input_data(preferences=dict(forecast="12")))["positions"][0]
    assert p["forecast"]["annual_per_share"] == "1.030000"
    assert p["price_yield"] is None and p["price_yield_status"] == "missing_quote"
    client, users, _, account = ledger
    p = save(
        ledger, input_data(expected_version=2, kind="preference", preferences=dict(forecast="skip"))
    )["positions"][0]
    assert p["price_yield_status"] == "not_set"
    assert p["price_yield_issues"] == ["未设置分红参考", "暂无有效报价"]


def test_empty_window_not_zero_but_custom_zero_is_valid(ledger, session):
    assert ref(session)["reason"] == "no_records"
    assert ref(session)["annual_per_share"] is None
    r = ref(session, "custom", custom="0")
    assert r["annual_per_share"] == "0.000000"
    assert r["status"] == "user_estimate"


def test_preview_requires_review_if_reference_changes(ledger, session, monkeypatch):
    monkeypatch.setattr("app.services.portfolio_positions.today", lambda: DAY)
    row = legacy(session)
    session.commit()
    data = input_data(preferences=dict(forecast="12"))
    before = call(ledger, "position-preview", data)
    row.cash_per_share = Decimal("2")
    session.commit()
    call(ledger, "position-confirm", dict(entry=data, preview_token=before["preview_token"]), 409)

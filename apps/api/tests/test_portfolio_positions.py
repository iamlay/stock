from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_portfolio import clients as clients
from test_portfolio_ledger import ledger as ledger
from test_portfolio_ledger import payload, post

from app.db.models import PortfolioAccount, PortfolioEntry, PortfolioReviewRange, StockRealtimeQuote


def input_data(**changes):
    return (
        dict(
            expected_version=1,
            request_id=str(uuid4()),
            code="600036",
            kind="snapshot",
            event_date="2025-01-01",
            quantity="500",
            cost="1",
            basis="dividend",
        )
        | changes
    )


def call(ledger, action, data, status=200, owner=0):
    client, _, headers, account = ledger
    result = client.post(
        f"/api/v1/portfolio/accounts/{account['id']}/{action}", headers=headers[owner], json=data
    )
    assert result.status_code == status, result.text
    assert result.headers["cache-control"] == "private, no-store"
    return result.json()


def save(ledger, data):
    preview = call(ledger, "position-preview", data)
    return call(
        ledger, "position-confirm", dict(entry=data, preview_token=preview["preview_token"]), 201
    )


def test_preview_has_no_writes_and_unknown_costs_stay_unknown(ledger, session):
    data = input_data()
    before = call(ledger, "position-preview", data)
    assert session.scalar(select(func.count()).select_from(PortfolioEntry)) == 0
    assert session.get(PortfolioAccount, ledger[3]["id"]).version == 1
    result = call(
        ledger, "position-confirm", dict(entry=data, preview_token=before["preview_token"]), 201
    )
    p = result["positions"][0]
    assert p["costs"]["dividend"]["total"] == "500.000000"
    assert p["costs"]["weighted"]["total"] is p["costs"]["net"]["total"] is None
    assert p["dividends_received"] is None
    assert result["entries"][0]["total_cost"] == "0.000000"
    call(ledger, "position-confirm", dict(entry=data, preview_token=before["preview_token"]), 201)
    assert session.scalar(select(func.count()).select_from(PortfolioEntry)) == 1


@pytest.mark.parametrize(
    "basis,cost,expected",
    [
        ("dividend", "-2", "-1000.000000"),
        ("net", "0", "0.000000"),
        ("weighted", "5", "2500.000000"),
    ],
)
def test_signed_and_zero_balances(ledger, basis, cost, expected):
    p = save(ledger, input_data(basis=basis, cost=cost))["positions"][0]
    assert p["costs"][basis]["total"] == expected


@pytest.mark.parametrize(
    "changes",
    [
        dict(basis="weighted", cost="-1"),
        dict(quantity="0"),
        dict(quantity="1.1"),
        dict(cost="NaN"),
        dict(cost="1e3"),
        dict(fees="5"),
        dict(event_date="2999-01-01"),
        dict(code="510300"),
        dict(cost="999999999999", quantity="999999999999"),
    ],
)
def test_invalid_snapshot(ledger, changes):
    call(ledger, "position-preview", input_data(**changes), 422)


def test_day_end_no_duplicate_or_backfill_and_correction_atomic(ledger):
    result = save(ledger, input_data())
    first = result["entries"][0]
    for day in ["2024-12-31", "2025-01-01"]:
        call(
            ledger,
            "position-preview",
            input_data(expected_version=2, kind="buy", event_date=day, cost="5"),
            422,
        )
    result = save(
        ledger,
        input_data(
            expected_version=2,
            kind="sell",
            event_date="2025-01-02",
            quantity="400",
            cost="5",
            fees="0",
        ),
    )
    p = result["positions"][0]
    assert p["quantity"] == "100.000000" and p["realized_pnl"] is None
    assert p["costs"]["dividend"]["total"] == "-1500.000000"
    call(
        ledger,
        "position-preview",
        input_data(expected_version=3, reverses_id=first["id"], note="改正", quantity="200"),
        422,
    )
    corrected = save(
        ledger, input_data(expected_version=3, reverses_id=first["id"], note="改正", quantity="600")
    )
    assert corrected["positions"][0]["quantity"] == "200.000000"
    assert len(corrected["entries"]) == 3


def test_total_input_precision_fees_unknown_and_cycles(ledger):
    result = save(ledger, input_data(basis="weighted", quantity="3", cost="1", input_mode="total"))
    assert result["positions"][0]["costs"]["weighted"]["total"] == "1.000000"
    result = save(
        ledger,
        input_data(
            expected_version=2, kind="sell", quantity="3", cost="2", event_date="2025-01-02"
        ),
    )
    assert result["positions"][0]["estimated"] is True
    assert result["positions"][0]["costs"]["weighted"]["per_share"] is None
    result = save(
        ledger,
        input_data(
            expected_version=3,
            kind="buy",
            quantity="10",
            cost="5",
            fees="0",
            event_date="2025-01-03",
        ),
    )
    p = result["positions"][0]
    assert p["costs"]["net"]["total"] == "50.000000"
    assert p["realized_pnl"] == "0.000000" and p["estimated"] is False
    assert p["closed_cycles"][0]["realized_pnl"] == "5.000000"


def test_complete_trade_cost_example_and_auto_order(ledger):
    result = save(ledger, input_data(kind="buy", quantity="1000", cost="5", fees="0"))
    result = save(
        ledger, input_data(expected_version=2, kind="sell", quantity="500", cost="8", fees="0")
    )
    p = result["positions"][0]
    assert p["costs"]["weighted"]["per_share"] == "5.000000"
    assert p["costs"]["net"]["per_share"] == "2.000000"
    assert p["realized_pnl"] == "1500.000000"
    # No receipt ledger yet: do not pretend the teaching example's dividend was received.
    assert p["costs"]["dividend"]["total"] is None
    assert [e["day_order"] for e in result["entries"]] == [1, 2]


def test_preview_tampering_stale_and_ownership(ledger):
    data = input_data()
    before = call(ledger, "position-preview", data)
    call(ledger, "position-preview", data, 404, owner=1)
    call(
        ledger,
        "position-confirm",
        dict(entry=data | {"cost": "99"}, preview_token=before["preview_token"]),
        409,
    )
    save(ledger, input_data(code="000001"))
    call(ledger, "position-confirm", dict(entry=data, preview_token=before["preview_token"]), 409)


def test_search_all_stocks_without_quotes_and_wildcards(ledger):
    assert call(ledger, "stock-search", {"query": "招商"})["items"][0]["code"] == "600036"
    assert call(ledger, "stock-search", {"query": "510300"})["items"] == []
    assert call(ledger, "stock-search", {"query": "%"})["items"] == []


def test_preferences_forecast_missing_is_not_zero_and_quote_time(ledger, session):
    session.add(
        StockRealtimeQuote(
            code="600036",
            price=20,
            prev_close=20,
            change_pct=0,
            amount=0,
            trade_date=datetime.now().date(),
            quote_time=datetime.now(UTC),
        )
    )
    session.commit()
    p = save(ledger, input_data(preferences=dict(forecast="36")))["positions"][0]
    assert p["forecast"]["annual_per_share"] is None and p["forecast"]["status"] == "insufficient"
    assert p["market_value"] == "10000.000000" and p["quote"]["at"]
    before = session.scalar(select(func.count()).select_from(PortfolioReviewRange))
    p = save(
        ledger,
        input_data(
            expected_version=2,
            kind="preference",
            preferences=dict(basis="dividend", group="收息", forecast="custom", custom="2.01"),
        ),
    )["positions"][0]
    assert p["quantity"] == "500.000000" and p["forecast"]["annual_amount"] == "1005.000000"
    assert p["price_yield"] == "10.050000"
    assert session.scalar(select(func.count()).select_from(PortfolioReviewRange)) == before


def test_legacy_precision_preserved_export_and_delete(ledger, session):
    old = post(ledger, payload(quantity="2.5", total_cost="3.123456"))
    result = save(ledger, input_data(expected_version=2, kind="preference"))
    assert result["positions"][0]["quantity"] == "2.500000"
    assert result["positions"][0]["total_cost"] == "3.123456"
    assert result["entries"][0]["id"] == old["entries"][0]["id"]
    client, _, headers, account = ledger
    exported = client.get("/api/v1/portfolio/export", headers=headers[0]).json()
    assert exported["ledgers"][0]["entries"][1]["details"]["rule_version"]
    removed = client.request(
        "DELETE",
        f"/api/v1/portfolio/accounts/{account['id']}",
        headers=headers[0],
        json=dict(expected_version=3, confirmation="DELETE"),
    )
    assert removed.status_code == 200
    assert session.scalar(select(func.count()).select_from(PortfolioEntry)) == 0


def test_current_position_rebase_replaces_balance_without_double_count(ledger):
    save(ledger, input_data())
    save(
        ledger,
        input_data(
            expected_version=2,
            kind="buy",
            event_date="2025-01-02",
            quantity="100",
            cost="5",
            fees="0",
        ),
    )
    data = input_data(
        expected_version=3,
        kind="rebase",
        event_date="2025-01-03",
        quantity="1000",
        cost="-2",
        note="核对当前数量",
        evidence="脱敏持仓数字",
    )
    p = save(ledger, data)["positions"][0]
    assert p["quantity"] == "1000.000000"
    assert p["costs"]["dividend"]["total"] == "-2000.000000"
    assert p["known_since"] == "2025-01-03"
    assert p["costs"]["weighted"]["total"] is None
    assert p["closed_cycles"][0]["reason"] == "baseline_reset"
    call(
        ledger,
        "position-preview",
        input_data(expected_version=4, kind="buy", event_date="2025-01-03"),
        422,
    )


def test_zero_custom_and_large_exact_forecast(ledger):
    p = save(
        ledger,
        input_data(
            quantity="999999999999",
            cost="0",
            preferences=dict(forecast="custom", custom="999999999999.999999"),
        ),
    )["positions"][0]
    assert p["forecast"]["annual_amount"] == "999999999998999999000000.000001"


def test_new_details_replayed_deletion_manifest(ledger, session):
    from etl.portfolio_privacy import replay_deletions

    save(ledger, input_data())
    _, users, _, account = ledger
    manifest = dict(
        schema_version="portfolio-deletion-manifest-v1",
        deletions=[
            dict(
                account_id=account["id"],
                user_id=users[0].id,
                deleted_at=datetime.now(UTC).isoformat(),
            )
        ],
    )
    replay_deletions(session, manifest, apply=True)
    session.commit()
    assert session.scalar(select(func.count()).select_from(PortfolioEntry)) == 0
    assert session.scalar(select(func.count()).select_from(PortfolioReviewRange)) == 0


@pytest.mark.parametrize("field", ["basis", "cost", "quantity"])
def test_baseline_must_not_silently_default_financial_input(ledger, field):
    data = input_data()
    data.pop(field)
    call(ledger, "position-preview", data, 422)

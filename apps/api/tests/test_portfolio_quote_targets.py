from decimal import Decimal

from etl.pipeline import sync_stock_watchlist_quotes
from test_portfolio import clients as clients
from test_portfolio_ledger import ledger as ledger
from test_portfolio_ledger import payload, post
from test_portfolio_positions import input_data, save

from app.db.models import Instrument, PortfolioAccount, StockWatchlist


def targets(session, monkeypatch, codes=None):
    requested = []

    def fetch(codes):
        requested.extend(codes)
        # Stop at the provider boundary: no private quantities or identities go out.
        raise RuntimeError("test provider boundary")

    monkeypatch.setattr("etl.pipeline.fetch_quotes", fetch)
    try:
        sync_stock_watchlist_quotes(session, codes)
    except RuntimeError as exc:
        assert str(exc) == "test provider boundary"
    return requested


def test_holdings_only_added_and_closed_position_removed(ledger, session, monkeypatch):
    save(ledger, input_data())
    assert targets(session, monkeypatch) == ["600036"]
    save(
        ledger,
        input_data(
            expected_version=2,
            kind="sell",
            event_date="2025-01-02",
            quantity="500",
            cost="5",
            fees="0",
        ),
    )
    assert targets(session, monkeypatch) == []
    save(
        ledger,
        input_data(
            expected_version=3,
            kind="buy",
            event_date="2025-01-03",
            quantity="100",
            cost="5",
            fees="0",
        ),
    )
    assert targets(session, monkeypatch) == ["600036"]


def test_watchlist_union_deduplicated_archive_and_inactive(ledger, session, monkeypatch):
    save(ledger, input_data())
    user = ledger[1][0]
    session.add_all(
        [
            StockWatchlist(user_id=user.id, code="600036"),
            StockWatchlist(user_id=user.id, code="000001"),
        ]
    )
    session.commit()
    assert targets(session, monkeypatch) == ["000001", "600036"]
    account = session.get(PortfolioAccount, ledger[3]["id"])
    account.is_archived = True
    session.query(StockWatchlist).filter(StockWatchlist.code == "600036").delete()
    session.commit()
    assert targets(session, monkeypatch) == ["000001"]
    account.is_archived = False
    session.get(Instrument, "600036").is_active = False
    session.commit()
    assert targets(session, monkeypatch) == ["000001"]


def test_reversal_and_rebase_use_replayed_quantity(ledger, session, monkeypatch):
    first = save(ledger, input_data())["entries"][0]
    save(
        ledger,
        input_data(
            expected_version=2,
            kind="sell",
            event_date="2025-01-02",
            quantity="500",
            cost="5",
            fees="0",
        ),
    )
    assert targets(session, monkeypatch) == []
    # Correct the original snapshot to 600: only its replacement counts (100 remain).
    save(
        ledger,
        input_data(expected_version=3, reverses_id=first["id"], quantity="600", note="核对数量"),
    )
    assert targets(session, monkeypatch) == ["600036"]
    result = save(
        ledger,
        input_data(
            expected_version=4,
            kind="rebase",
            event_date="2025-01-03",
            quantity="200",
            cost="1",
            note="核对",
            evidence="测试依据",
        ),
    )
    assert Decimal(result["positions"][0]["quantity"]) == 200
    save(
        ledger,
        input_data(
            expected_version=5,
            kind="sell",
            event_date="2025-01-04",
            quantity="200",
            cost="5",
            fees="0",
        ),
    )
    assert targets(session, monkeypatch) == []


def test_legacy_holdings_and_explicit_code_override(ledger, session, monkeypatch):
    post(ledger, payload())
    assert targets(session, monkeypatch) == ["600036"]
    assert targets(session, monkeypatch, ["000001"]) == ["000001"]
    post(
        ledger,
        payload(
            expected_version=2,
            kind="adjustment",
            event_date="2025-01-02",
            quantity="0",
            total_cost="0",
            note="清仓",
            evidence="测试",
        ),
    )
    assert targets(session, monkeypatch) == []


def test_holdings_only_quotes_update_market_value_and_yield(ledger, session, monkeypatch):
    from datetime import date, datetime
    from types import SimpleNamespace

    save(ledger, input_data(preferences={"forecast": "custom", "custom": "2"}))
    quote = SimpleNamespace(
        code="600036",
        price=Decimal("10"),
        prev_close=Decimal("9"),
        change_pct=Decimal("11.11"),
        amount=Decimal("100"),
        trade_date=date(2026, 10, 28),
        quote_time=datetime(2026, 10, 28, 10, 0),
    )
    requested = []

    def fetch(codes):
        requested.append(codes)
        return [quote]

    monkeypatch.setattr("etl.pipeline.fetch_quotes", fetch)
    client, _, headers, account = ledger
    for price, expected_value, expected_yield in [
        ("10", "5000.000000", "20.000000"),
        ("20", "10000.000000", "10.000000"),
    ]:
        quote.price = Decimal(price)
        assert sync_stock_watchlist_quotes(session)["quotes"] == 1
        response = client.get(
            f"/api/v1/portfolio/accounts/{account['id']}/holdings", headers=headers[0]
        )
        assert response.status_code == 200
        body = response.json()
        assert body["known_market_value"] == expected_value
        assert body["positions"][0]["market_value"] == expected_value
        assert body["positions"][0]["price_yield"] == expected_yield
        assert body["positions"][0]["quote"]["source"] == "stock_realtime_quotes"
    assert requested == [["600036"], ["600036"]]

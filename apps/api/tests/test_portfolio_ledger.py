from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from etl.portfolio_privacy import replay_deletions
from sqlalchemy import func, select
from test_portfolio import body, create
from test_portfolio import clients as clients

from app.db.models import (
    Instrument,
    PortfolioAccount,
    PortfolioEntry,
    PortfolioPrivacyAcceptance,
    PortfolioReviewRange,
)
from app.settings import settings

BASE = "/api/v1/portfolio/accounts"


@pytest.fixture
def ledger(clients, session):
    client, users, headers = clients
    session.add_all(
        [
            Instrument(code="600036", name="招商银行", type="stock", exchange="SH"),
            Instrument(code="000001", name="平安银行", type="stock", exchange="SZ"),
            Instrument(code="510300", name="ETF", type="etf", exchange="SH"),
        ]
    )
    session.commit()
    account = create(client, headers[0])
    return client, users, headers, account


def payload(**changes):
    return (
        dict(
            expected_version=1,
            request_id=str(uuid4()),
            code="600036",
            kind="opening",
            event_date="2025-01-01",
            day_order=10,
            quantity="100",
            price="0",
            fees="0",
            total_cost="1000",
            history_status="since_date",
            note="",
            evidence="",
            reverses_id=None,
        )
        | changes
    )


def post(ledger, data, status=201):
    client, _, headers, account = ledger
    result = client.post(f"{BASE}/{account['id']}/entries", headers=headers[0], json=data)
    assert result.status_code == status, result.text
    assert result.headers["cache-control"] == "private, no-store"
    return result.json()


def snapshot(ledger):
    client, _, headers, account = ledger
    return client.get(f"{BASE}/{account['id']}/ledger", headers=headers[0]).json()


def test_moving_average_fees_full_close_and_no_fake_income(ledger):
    post(ledger, payload())
    post(
        ledger,
        payload(
            expected_version=2,
            kind="buy",
            event_date="2025-01-02",
            quantity="100",
            price="20",
            fees="10",
            total_cost="0",
        ),
    )
    result = post(
        ledger,
        payload(
            expected_version=3,
            kind="sell",
            event_date="2025-01-03",
            quantity="50",
            price="18",
            fees="5",
            total_cost="0",
        ),
    )
    p = result["positions"][0]
    assert Decimal(p["quantity"]) == 150 and Decimal(p["total_cost"]) == Decimal("2257.5")
    assert Decimal(p["realized_pnl"]) == Decimal("142.5")
    assert Decimal(p["average_cost"]) == Decimal("15.05")
    assert p["unrealized_pnl"] is p["dividends_received"] is None
    assert p["known_since"] == "2025-01-01" and p["history_before_known_since"] == "unknown"
    result = post(
        ledger,
        payload(
            expected_version=4,
            kind="sell",
            event_date="2025-01-04",
            quantity="150",
            price="16",
            fees="5",
            total_cost="0",
        ),
    )
    assert Decimal(result["positions"][0]["total_cost"]) == 0
    assert result["positions"][0]["average_cost"] is None
    assert Decimal(result["positions"][0]["realized_pnl"]) == 280
    assert result["automatic_dividends"] is False


def test_historical_oversell_even_when_current_balance_positive(ledger):
    post(ledger, payload())
    post(
        ledger,
        payload(
            expected_version=2,
            kind="sell",
            event_date="2025-02-01",
            quantity="100",
            price="12",
            total_cost="0",
        ),
    )
    post(
        ledger,
        payload(
            expected_version=3,
            kind="buy",
            event_date="2025-03-01",
            quantity="200",
            price="10",
            total_cost="0",
        ),
    )
    response = post(
        ledger,
        payload(
            expected_version=4,
            kind="sell",
            event_date="2025-01-15",
            quantity="1",
            price="10",
            total_cost="0",
        ),
        422,
    )
    assert response["detail"]["code"] == "historical_oversell"
    assert len(snapshot(ledger)["entries"]) == 3
    assert snapshot(ledger)["account_version"] == 4


def test_atomic_correction_preserves_original_and_invalidates_earliest_date(ledger):
    first = post(ledger, payload())["entries"][0]
    result = post(
        ledger,
        payload(
            expected_version=2,
            event_date="2024-12-31",
            quantity="200",
            total_cost="1800",
            reverses_id=first["id"],
            note="核对期初数量",
        ),
    )
    assert len(result["entries"]) == 2
    old = next(e for e in result["entries"] if e["id"] == first["id"])
    assert Decimal(old["quantity"]) == 100 and not old["active"]
    assert Decimal(result["positions"][0]["quantity"]) == 200
    assert result["review_ranges"][-1]["from_date"] == "2024-12-31"
    new = next(e for e in result["entries"] if e["active"])
    post(
        ledger, payload(expected_version=3, reverses_id=new["id"], quantity="300", note="再次更正")
    )
    assert Decimal(snapshot(ledger)["positions"][0]["quantity"]) == 300


def test_reversal_checks_later_sales_and_retains_trace(ledger):
    first = post(ledger, payload())["entries"][0]
    sold = post(
        ledger,
        payload(
            expected_version=2,
            kind="sell",
            event_date="2025-02-01",
            quantity="50",
            price="12",
            total_cost="0",
        ),
    )["entries"][-1]
    reverse = payload(
        expected_version=3,
        kind="reversal",
        quantity="0",
        total_cost="0",
        reverses_id=first["id"],
        note="撤销误录",
    )
    post(ledger, reverse, 422)
    result = post(ledger, reverse | {"event_date": sold["event_date"], "reverses_id": sold["id"]})
    assert Decimal(result["positions"][0]["quantity"]) == 100
    post(ledger, reverse | {"expected_version": 4, "request_id": str(uuid4())})
    assert snapshot(ledger)["positions"] == []
    post(ledger, reverse | {"expected_version": 5, "request_id": str(uuid4())}, 422)


def test_same_day_order_and_opening_must_be_first(ledger):
    post(ledger, payload())
    post(ledger, payload(expected_version=2, kind="buy", total_cost="0", price="10"), 422)
    post(
        ledger,
        payload(expected_version=2, kind="sell", total_cost="0", price="10", day_order=5),
        422,
    )
    post(
        ledger,
        payload(
            expected_version=2, kind="buy", total_cost="0", price="10", event_date="2024-12-31"
        ),
        422,
    )
    result = post(
        ledger, payload(expected_version=2, kind="sell", total_cost="0", price="10", day_order=20)
    )
    assert Decimal(result["positions"][0]["quantity"]) == 0


def test_adjustment_requires_evidence_and_marks_incomplete(ledger):
    post(ledger, payload())
    adj = payload(
        expected_version=2,
        kind="adjustment",
        event_date="2025-02-01",
        quantity="120",
        total_cost="900",
    )
    post(ledger, adj, 422)
    result = post(ledger, adj | {"note": "送转后核对", "evidence": "根据券商持仓页面人工核对"})
    p = result["positions"][0]
    assert p["has_adjustment"] is True and p["history_status"] == "incomplete"
    assert Decimal(p["quantity"]) == 120 and Decimal(p["realized_pnl"]) == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"quantity": "-1"},
        {"quantity": 1},
        {"quantity": True},
        {"quantity": "NaN"},
        {"quantity": "1e2"},
        {"quantity": "0.0000001"},
        {"fees": "-1"},
        {"quantity": "1000000000000"},
        {"day_order": True},
        {"day_order": 0},
        {"event_date": "2999-01-01"},
        {"event_date": 1000},
        {"event_date": "2025-01-01T00:00:00"},
        {"code": "510300"},
        {"code": "999999"},
        {"quantity": "0"},
        {"history_status": "full_history"},
        {"note": "private\x00secret"},
    ],
)
def test_invalid_values_are_rejected_atomically_without_echo(ledger, changes):
    result = post(ledger, payload(**changes), 422)
    assert "input" not in result and "private" not in str(result)
    assert snapshot(ledger)["entries"] == []


def test_idempotency_does_not_duplicate_and_changed_payload_rejected(ledger):
    data = payload()
    first = post(ledger, data)
    assert post(ledger, data) == first
    post(ledger, data | {"quantity": "200"}, 409)
    assert len(snapshot(ledger)["entries"]) == 1
    post(ledger, payload(), 409)


def test_old_consent_must_reconfirm_before_first_financial_write(ledger, session):
    client, users, headers, account = ledger
    old = PortfolioPrivacyAcceptance(
        id=str(uuid4()),
        user_id=users[0].id,
        policy_version="portfolio-account-2026-10-27.v1",
        policy_sha256="a" * 64,
        policy_snapshot={"scope": "private_account_metadata"},
        accepted_at=datetime.now(UTC),
    )
    session.add(old)
    session.flush()
    session.get(PortfolioAccount, account["id"]).privacy_acceptance_id = old.id
    session.commit()
    assert snapshot(ledger)["consent_required"] is True
    post(ledger, payload(), 403)
    consent_path = f"{BASE}/{account['id']}/consent"
    consent = body()["consent"]
    bad = client.post(
        consent_path,
        headers=headers[0],
        json={"expected_version": 1, "consent": consent | {"version": "old"}},
    )
    assert bad.status_code == 409
    good = client.post(
        consent_path, headers=headers[0], json={"expected_version": 1, "consent": consent}
    )
    assert good.status_code == 200 and good.json()["version"] == 2
    assert session.get(PortfolioPrivacyAcceptance, old.id).policy_snapshot == {
        "scope": "private_account_metadata"
    }
    post(ledger, payload(expected_version=2))


def test_owner_isolation_including_admin_and_cross_account_reversal(ledger, session):
    client, _, headers, account = ledger
    first = post(ledger, payload())["entries"][0]
    for auth in headers[1:]:
        for method, path, data in [
            ("GET", "ledger", None),
            ("POST", "entries", payload()),
            ("POST", "consent", {"expected_version": 2, "consent": body()["consent"]}),
        ]:
            response = client.request(
                method, f"{BASE}/{account['id']}/{path}", headers=auth, json=data
            )
            assert response.status_code == 404 and "no-store" in response.headers["cache-control"]
    other = create(client, headers[1])
    response = client.post(
        f"{BASE}/{other['id']}/entries",
        headers=headers[1],
        json=payload(reverses_id=first["id"], note="foreign"),
    )
    assert response.status_code == 422
    exported = client.get("/api/v1/portfolio/export", headers=headers[1]).json()
    assert exported["ledgers"][0]["entries"] == []


def test_archived_read_only_but_expired_and_flag_off_still_editable(ledger, session, monkeypatch):
    client, users, headers, account = ledger
    users[0].plan_expires_at = datetime.now(UTC) - timedelta(days=3)
    session.commit()
    monkeypatch.setattr(settings, "portfolio_enabled", False)
    post(ledger, payload())
    response = client.patch(
        f"{BASE}/{account['id']}",
        headers=headers[0],
        json={"expected_version": 2, "is_archived": True},
    )
    assert response.status_code == 200
    post(ledger, payload(expected_version=3, day_order=20), 409)
    assert len(snapshot(ledger)["entries"]) == 1
    assert client.get("/api/v1/portfolio/export", headers=headers[0]).status_code == 200


@pytest.mark.parametrize("via_manifest", [False, True])
def test_export_and_deletion_cover_all_private_ledger_data(ledger, session, via_manifest):
    client, users, headers, account = ledger
    post(ledger, payload(note="私人备注"))
    export = client.get("/api/v1/portfolio/export", headers=headers[0]).json()
    assert export["ledgers"][0]["entries"][0]["note"] == "私人备注"
    assert isinstance(export["ledgers"][0]["entries"][0]["quantity"], str)
    if via_manifest:
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
        replay_deletions(session, manifest)
        assert session.scalar(select(func.count()).select_from(PortfolioEntry)) == 1
        replay_deletions(session, manifest, apply=True)
        session.commit()
    else:
        response = client.request(
            "DELETE",
            f"{BASE}/{account['id']}",
            headers=headers[0],
            json={"expected_version": 2, "confirmation": "DELETE"},
        )
        assert response.status_code == 200
    for model in (PortfolioEntry, PortfolioReviewRange):
        assert session.scalar(select(func.count()).select_from(model)) == 0


def test_fractional_decimal_replay_is_stable_across_reads(ledger):
    post(ledger, payload(quantity="3", total_cost="1"))
    for version in (2, 3, 4):
        result = post(
            ledger,
            payload(
                expected_version=version,
                kind="sell",
                day_order=version * 10,
                quantity="1",
                price="0.5",
                total_cost="0",
            ),
        )
    p = result["positions"][0]
    assert Decimal(p["total_cost"]) == 0 and Decimal(p["realized_pnl"]) == Decimal("0.5")
    assert snapshot(ledger)["positions"] == result["positions"]


def test_opening_requires_explicit_cost_instead_of_default_zero(ledger):
    data = payload()
    data.pop("total_cost")
    post(ledger, data, 422)
    assert snapshot(ledger)["entries"] == []

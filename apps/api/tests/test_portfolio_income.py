from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from app.db.models import (
    DividendEvent,
    DividendEventVersion,
    Instrument,
    PortfolioEntry,
    User,
)
from app.services.portfolio import POLICY, POLICY_SHA256, create_account
from app.services.portfolio_income import (
    create_receipt,
    income_home,
    income_snapshot,
    reverse_receipt,
    sync_entitlements,
    update_receipt,
)
from app.settings import settings


def _account(session):
    user = User(phone="13800005555", role="member", plan="free")
    session.add(user)
    session.commit()
    session.refresh(user)
    account = create_account(
        session,
        user.id,
        "收息账本",
        {
            "accepted": True,
            "version": POLICY["version"],
            "sha256": POLICY_SHA256,
        },
    )
    session.commit()
    return user, account


def _event(session, code: str = "600519") -> DividendEvent:
    session.add(
        Instrument(
            code=code,
            name="贵州茅台",
            type="stock",
            exchange="SH",
            lot_size=100,
            is_active=True,
        )
    )
    event = DividendEvent(
        id=str(uuid4()),
        code=code,
        current_revision=1,
        origin="reviewed_observation",
    )
    session.add(event)
    session.flush()
    session.add(
        DividendEventVersion(
            event_id=event.id,
            revision=1,
            source="eastmoney",
            report_date=date(2025, 12, 31),
            notice_date=date(2026, 6, 1),
            record_date=date(2026, 6, 20),
            ex_date=date(2026, 6, 21),
            payment_date=date(2026, 6, 30),
            cash_per_share=Decimal("0.50"),
            plan="10派5.00元(含税)",
            progress="实施分配",
            stage="implemented",
            evidence_status="reviewed",
            review_reasons=[],
            rule_version="v2-49.1",
            raw_payload={},
            review_note="reviewed fixture",
            observed_at=datetime.now(UTC),
            source_url="https://example.com/announcement",
        )
    )
    session.flush()
    return event


def test_entitlement_and_receipts(session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "portfolio_enabled", True)
    user, account = _account(session)
    _event(session)
    session.add(
        PortfolioEntry(
            id=str(uuid4()),
            account_id=account.id,
            user_id=user.id,
            request_id=str(uuid4()),
            request_hash="hash",
            code="600519",
            kind="opening",
            event_date=date(2026, 1, 1),
            day_order=1,
            quantity=Decimal("100"),
            price=Decimal("0"),
            fees=Decimal("0"),
            total_cost=Decimal("1000"),
            history_status="since_date",
            source="manual",
            note="",
            evidence="",
            account_version=1,
            created_at=datetime.now(UTC),
        )
    )
    session.commit()

    result = sync_entitlements(session, user.id, account.id)
    session.commit()
    assert result["created"] == 1
    snapshot = income_snapshot(session, user.id, account.id)
    assert snapshot["summary"]["gross_amount"] == "50.00"
    entitlement = snapshot["entitlements"][0]
    assert entitlement["eligible_quantity"] == "100.000000"
    assert entitlement["status"] == "pending"

    first = create_receipt(
        session,
        user.id,
        account.id,
        expected_version=account.version,
        request_id=str(uuid4()),
        entitlement_id=entitlement["id"],
        code="600519",
        received_date=date(2026, 6, 30),
        net_amount="20.00",
        gross_amount="20.00",
        tax_amount="0",
        quantity="40",
        cash_per_share="0.50",
    )
    session.commit()
    assert first["status"] == "active"
    assert first["quantity"] == "40.000000"
    assert first["cash_per_share"] == "0.50000000"
    snapshot = income_snapshot(session, user.id, account.id)
    assert snapshot["entitlements"][0]["status"] == "partial"
    assert snapshot["entitlements"][0]["remaining_amount"] == "30.00"

    updated = update_receipt(
        session,
        user.id,
        account.id,
        first["id"],
        expected_version=account.version,
        received_date=date(2026, 6, 30),
        net_amount="25.00",
        gross_amount="25.00",
        tax_amount="0",
        quantity="50",
        cash_per_share="0.50",
    )
    session.commit()
    assert updated["net_amount"] == "25.00"
    assert updated["quantity"] == "50.000000"
    snapshot = income_snapshot(session, user.id, account.id)
    assert snapshot["entitlements"][0]["remaining_amount"] == "25.00"

    create_receipt(
        session,
        user.id,
        account.id,
        expected_version=account.version,
        request_id=str(uuid4()),
        entitlement_id=entitlement["id"],
        code="600519",
        received_date=date(2026, 7, 1),
        net_amount="25.00",
        gross_amount="25.00",
        tax_amount="0",
    )
    session.commit()
    snapshot = income_snapshot(session, user.id, account.id)
    assert snapshot["entitlements"][0]["status"] == "settled"

    reverse_receipt(
        session,
        user.id,
        account.id,
        first["id"],
        expected_version=account.version,
    )
    session.commit()
    snapshot = income_snapshot(session, user.id, account.id)
    assert snapshot["entitlements"][0]["status"] == "partial"
    assert len(snapshot["receipts"]) == 2
    assert any(row["status"] == "reversed" for row in snapshot["receipts"])

    home = income_home(session, user.id, account.id, 2026)
    assert home["summary"]["received"] == "25.00"
    assert home["summary"]["pending"] == "25.00"
    assert home["calendar"]
    assert any(
        item["date_type"] == "payment"
        for day in home["calendar"]
        for item in day["items"]
    )

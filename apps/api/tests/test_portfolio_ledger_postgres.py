import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_dividend_events_postgres import pg_engine as pg_engine
from test_dividend_events_postgres import run_parallel
from test_portfolio_ledger import payload
from test_portfolio_postgres import consent

from app.db.models import Instrument, PortfolioAccount, PortfolioEntry, PortfolioReviewRange, User
from app.services.portfolio import PortfolioError, create_account, delete_account
from app.services.portfolio_ledger import add_entry, ledger_snapshot
from app.settings import settings


@pytest.fixture
def account(pg_engine, monkeypatch):
    monkeypatch.setattr(settings, "portfolio_enabled", True)
    with Session(pg_engine) as session:
        owner = User(email="ledger-pg@example.com")
        other = User(email="ledger-other@example.com")
        session.add_all(
            [owner, other, Instrument(code="600036", name="test", type="stock", exchange="SH")]
        )
        session.flush()
        account = create_account(session, owner.id, "test", consent())
        session.commit()
        return owner.id, account.id, other.id


def test_concurrent_entries_cannot_double_spend_or_overwrite(pg_engine, account):
    owner, identifier, _ = account
    with Session(pg_engine) as session:
        add_entry(session, owner, identifier, payload())
        session.commit()

    def sell(session):
        try:
            add_entry(
                session,
                owner,
                identifier,
                payload(
                    expected_version=2,
                    kind="sell",
                    quantity="80",
                    price="10",
                    total_cost="0",
                    day_order=20,
                ),
            )
            return "success"
        except PortfolioError:
            session.rollback()
            return "conflict"

    assert sorted(run_parallel(pg_engine, [sell] * 3)) == ["conflict", "conflict", "success"]
    with Session(pg_engine) as session:
        assert (
            ledger_snapshot(session, owner, identifier)["positions"][0]["quantity"] == "20.000000"
        )


def test_parallel_same_request_is_one_financial_fact(pg_engine, account):
    owner, identifier, _ = account
    data = payload()

    def add(session):
        return add_entry(session, owner, identifier, data)["entries"][0]["id"]

    assert len(set(run_parallel(pg_engine, [add] * 4))) == 1
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(PortfolioEntry)) == 1
        assert session.scalar(select(func.count()).select_from(PortfolioReviewRange)) == 1
        assert session.get(PortfolioAccount, identifier).version == 2


def test_real_numeric_replay_and_account_delete_cascade(pg_engine, account):
    owner, identifier, _ = account
    with Session(pg_engine) as session:
        first = add_entry(session, owner, identifier, payload(quantity="3", total_cost="1"))[
            "entries"
        ][0]
        session.commit()
        add_entry(
            session,
            owner,
            identifier,
            payload(
                expected_version=2,
                reverses_id=first["id"],
                quantity="6",
                total_cost="2",
                note="更正",
            ),
        )
        session.commit()
        result = add_entry(
            session,
            owner,
            identifier,
            payload(
                expected_version=3,
                kind="sell",
                quantity="1",
                price="1",
                fees="0.000001",
                total_cost="0",
                day_order=20,
            ),
        )
        session.commit()
        assert result["positions"][0]["realized_pnl"] == "0.666666"
        # Direct database cascade, not just application cleanup.
        session.delete(session.get(PortfolioAccount, identifier))
        session.commit()
        for model in (PortfolioEntry, PortfolioReviewRange):
            assert session.scalar(select(func.count()).select_from(model)) == 0


def test_db_rejects_cross_owner_and_cross_account_reversal(pg_engine, account):
    owner, identifier, other = account
    with Session(pg_engine) as session:
        first = add_entry(session, owner, identifier, payload())["entries"][0]
        second = create_account(session, other, "other", consent())
        session.commit()
        original = session.get(PortfolioEntry, first["id"])
        values = {c.name: getattr(original, c.name) for c in PortfolioEntry.__table__.columns}
        for changes in [
            dict(user_id=other),
            dict(user_id=other, account_id=second.id, reverses_id=original.id),
        ]:
            session.add(
                PortfolioEntry(
                    **(values | dict(id=str(uuid4()), request_id=str(uuid4())) | changes)
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
        assert session.scalar(select(func.count()).select_from(PortfolioEntry)) == 1


def test_entry_delete_race_never_leaves_orphan(pg_engine, account):
    owner, identifier, _ = account

    def add(session):
        try:
            add_entry(session, owner, identifier, payload())
            return "entry"
        except PortfolioError:
            session.rollback()
            return "conflict"

    def remove(session):
        try:
            delete_account(session, owner, identifier, 1)
            return "deleted"
        except PortfolioError:
            session.rollback()
            return "conflict"

    results = run_parallel(pg_engine, [add, remove])
    assert results.count("conflict") == 1
    with Session(pg_engine) as session:
        if session.get(PortfolioAccount, identifier) is None:
            assert session.scalar(select(func.count()).select_from(PortfolioEntry)) == 0
        else:
            assert session.scalar(select(func.count()).select_from(PortfolioEntry)) == 1


def test_ledger_migration_keeps_old_account_consent(pg_engine, account):
    owner, identifier, _ = account
    path = Path(__file__).parents[1] / "alembic/versions/e0f6a8b41235_portfolio_ledger.py"
    spec = importlib.util.spec_from_file_location("ledger_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with Session(pg_engine) as session:
        before = session.get(PortfolioAccount, identifier).privacy_acceptance_id
    with pg_engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
        module.downgrade()
        module.upgrade()
        # Bring the rebuilt V2-51 tables to the current application schema.
        next_path = path.with_name("f1a7b9c52346_portfolio_positions.py")
        next_spec = importlib.util.spec_from_file_location("positions_migration", next_path)
        next_module = importlib.util.module_from_spec(next_spec)
        next_spec.loader.exec_module(next_module)
        next_module.upgrade()
    with Session(pg_engine) as session:
        assert session.get(PortfolioAccount, identifier).privacy_acceptance_id == before
        add_entry(session, owner, identifier, payload())
        session.commit()

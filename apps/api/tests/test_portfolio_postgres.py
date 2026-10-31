import importlib.util
from datetime import UTC, datetime
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

from app.db.models import PortfolioAccount, PortfolioAuditEvent, PortfolioPrivacyAcceptance, User
from app.services.portfolio import (
    POLICY,
    POLICY_SHA256,
    PortfolioError,
    create_account,
    delete_account,
    update_account,
)
from app.settings import settings


@pytest.fixture(autouse=True)
def feature(monkeypatch):
    monkeypatch.setattr(settings, "portfolio_enabled", True)


def seed(engine):
    with Session(engine) as session:
        users = [User(email=f"pg-private-{i}@example.com") for i in range(2)]
        session.add_all(users)
        session.commit()
        return [user.id for user in users]


def consent():
    return {"accepted": True, "version": POLICY["version"], "sha256": POLICY_SHA256}


def test_parallel_create_is_single_account_with_atomic_consent(pg_engine):
    owner, _ = seed(pg_engine)

    def action(session):
        try:
            return create_account(session, owner, "private", consent()).id
        except PortfolioError:
            session.rollback()
            return "conflict"

    results = run_parallel(pg_engine, [action] * 4)
    assert results.count("conflict") == 3
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(PortfolioAccount)) == 1
        assert session.scalar(select(func.count()).select_from(PortfolioPrivacyAcceptance)) == 1
        assert session.scalar(select(func.count()).select_from(PortfolioAuditEvent)) == 1


def test_parallel_revision_updates_do_not_overwrite(pg_engine):
    owner, _ = seed(pg_engine)
    with Session(pg_engine) as session:
        identifier = create_account(session, owner, "initial", consent()).id
        session.commit()

    def action(session):
        try:
            update_account(session, owner, identifier, 1, {"name": "edited"})
            return "updated"
        except PortfolioError:
            session.rollback()
            return "conflict"

    assert sorted(run_parallel(pg_engine, [action] * 3)) == ["conflict", "conflict", "updated"]
    with Session(pg_engine) as session:
        assert session.get(PortfolioAccount, identifier).version == 2


def test_database_rejects_cross_owner_audit_and_consent_link(pg_engine):
    owner, other = seed(pg_engine)
    with Session(pg_engine) as session:
        account = create_account(session, owner, "private", consent())
        session.commit()
        session.add(
            PortfolioAuditEvent(
                id=str(uuid4()),
                account_id=account.id,
                user_id=other,
                action="update",
                account_version=1,
                created_at=datetime.now(UTC),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.add(
            PortfolioAccount(
                id=str(uuid4()),
                user_id=other,
                name="foreign consent",
                currency="CNY",
                is_archived=False,
                version=1,
                privacy_acceptance_id=account.privacy_acceptance_id,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        assert session.scalar(select(func.count()).select_from(PortfolioAccount)) == 1


def test_delete_clears_audit_but_retains_minimal_consent(pg_engine):
    owner, _ = seed(pg_engine)
    with Session(pg_engine) as session:
        account = create_account(session, owner, "erase name", consent())
        identifier = account.id
        session.commit()
        delete_account(session, owner, identifier, 1)
        session.commit()
        assert session.scalar(select(func.count()).select_from(PortfolioAuditEvent)) == 0
        assert session.scalar(select(func.count()).select_from(PortfolioPrivacyAcceptance)) == 1
        assert session.get(PortfolioAccount, identifier) is None


def test_private_migration_roundtrip_keeps_existing_users(pg_engine):
    seed(pg_engine)
    path = Path(__file__).parents[1] / "alembic/versions/d9e5f7a30124_private_portfolio.py"
    spec = importlib.util.spec_from_file_location("private_portfolio_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ledger_path = path.with_name("e0f6a8b41235_portfolio_ledger.py")
    ledger_spec = importlib.util.spec_from_file_location("ledger_migration", ledger_path)
    ledger_module = importlib.util.module_from_spec(ledger_spec)
    ledger_spec.loader.exec_module(ledger_module)
    income_path = path.with_name("b2d5e7f1a034_portfolio_income.py")
    income_spec = importlib.util.spec_from_file_location(
        "portfolio_income_migration", income_path
    )
    income_module = importlib.util.module_from_spec(income_spec)
    income_spec.loader.exec_module(income_module)
    with pg_engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
        income_module.downgrade()
        ledger_module.downgrade()
        module.downgrade()
        assert conn.scalar(select(func.count()).select_from(User)) == 2
        module.upgrade()
        ledger_module.upgrade()
        income_module.upgrade()
        assert conn.scalar(select(func.count()).select_from(User)) == 2
    with Session(pg_engine) as session:
        owner = session.scalar(select(User.id).order_by(User.id))
        create_account(session, owner, "after migration", consent())
        session.commit()
        assert session.scalar(select(func.count()).select_from(PortfolioAccount)) == 1

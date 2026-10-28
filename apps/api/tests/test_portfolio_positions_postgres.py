"""Real PostgreSQL serialization and additive migration checks for V2-51R."""

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from test_dividend_events_postgres import pg_engine as pg_engine
from test_dividend_events_postgres import run_parallel
from test_portfolio_ledger_postgres import account as account
from test_portfolio_positions import input_data

from app.api.v1.portfolio import PositionInput
from app.db.models import PortfolioEntry
from app.services.portfolio import PortfolioError
from app.services.portfolio_positions import confirm, holdings, preview


def normalized(**kwargs):
    return PositionInput(**input_data(**kwargs)).model_dump(mode="json")


def test_same_preview_concurrent_confirm_is_one_fact(pg_engine, account):
    owner, identifier, _ = account
    data = normalized()
    with Session(pg_engine) as session:
        token = preview(session, owner, identifier, data)["preview_token"]
        session.commit()

    def save(session):
        return confirm(session, owner, identifier, data, token)["entries"][0]["id"]

    assert len(set(run_parallel(pg_engine, [save] * 3))) == 1
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(PortfolioEntry)) == 1
        assert holdings(session, owner, identifier)["account_version"] == 2


def test_different_previews_concurrent_only_one_commits(pg_engine, account):
    owner, identifier, _ = account
    data = [normalized(kind="buy", cost="5", fees="0") for _ in range(2)]
    tokens = []
    for d in data:
        with Session(pg_engine) as session:
            tokens.append(preview(session, owner, identifier, d)["preview_token"])
            session.commit()

    def save(index):
        def run(session):
            try:
                confirm(session, owner, identifier, data[index], tokens[index])
                return "saved"
            except PortfolioError:
                session.rollback()
                return "conflict"

        return run

    assert sorted(run_parallel(pg_engine, [save(0), save(1)])) == ["conflict", "saved"]


def test_additive_migration_preserves_old_rows_and_blocks_lossy_downgrade(pg_engine, account):
    owner, identifier, _ = account
    migration = Path(__file__).parents[1] / "alembic/versions/f1a7b9c52346_portfolio_positions.py"
    spec = importlib.util.spec_from_file_location("position_migration", migration)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pg_engine.begin() as conn:
        module.op = Operations(MigrationContext.configure(conn))
        module.downgrade()
        conn.execute(
            text("""INSERT INTO portfolio_entries
          (id, account_id, user_id, request_id, request_hash, code, kind, event_date,
           day_order, quantity, price, fees, total_cost, history_status, source, note, evidence,
           account_version, created_at)
          VALUES (:id,:account,:owner,:request,:hash,'600036','opening','2025-01-01',10,
            2.5,0,0,3.123456,'since_date','manual','','',2,now())"""),
            dict(
                id=str(uuid4()),
                account=identifier,
                owner=owner,
                request=str(uuid4()),
                hash="a" * 64,
            ),
        )
        before = dict(conn.execute(text("select * from portfolio_entries")).mappings().one())
        module.upgrade()
        after = dict(conn.execute(text("select * from portfolio_entries")).mappings().one())
        assert after.pop("details") is None
        assert before == after
    with Session(pg_engine) as session:
        data = normalized(kind="preference")
        token = preview(session, owner, identifier, data)["preview_token"]
        confirm(session, owner, identifier, data, token)
        session.commit()
    with pg_engine.begin() as conn:
        module.op = Operations(MigrationContext.configure(conn))
        with pytest.raises(RuntimeError, match="New position records"):
            module.downgrade()

"""Real PostgreSQL serialization/constraint tests, isolated schema per test."""

import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    AdminAuditLog,
    DividendEvent,
    DividendEventVersion,
    DividendSourceObservation,
    Instrument,
    StockDividend,
    User,
)
from app.services.dividend_events import (
    ReviewConflict,
    backfill_legacy,
    record_source_pages,
    review_observation,
)


@pytest.fixture
def pg_engine():
    url = os.getenv("STOCKLAB_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("disposable STOCKLAB_TEST_POSTGRES_URL required")
    admin = create_engine(url)
    schema = "dividend_test_" + uuid4().hex
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def page(amount="5", notice="2026-07-01"):
    return [
        {
            "url": "https://data.eastmoney.com/test",
            "observed_at": datetime.now(UTC).isoformat(),
            "rows": [
                {
                    "SECURITY_CODE": "600036",
                    "PRETAX_BONUS_RMB": amount,
                    "REPORT_DATE": "2025-12-31",
                    "NOTICE_DATE": notice,
                    "EQUITY_RECORD_DATE": "2026-07-09",
                    "EX_DIVIDEND_DATE": "2026-07-10",
                    "ASSIGN_PROGRESS": "实施分配",
                    "IMPL_PLAN_PROFILE": "test plan",
                }
            ],
        }
    ]


def seed(engine):
    with Session(engine) as session:
        session.add(Instrument(code="600036", name="test", type="stock", exchange="SH"))
        user = User(email="review@example.com", role="admin")
        session.add(user)
        session.commit()
        return user.id


def run_parallel(engine, actions):
    barrier = Barrier(len(actions))

    def work(action):
        with Session(engine, autoflush=False, expire_on_commit=False) as session:
            barrier.wait(timeout=10)
            try:
                result = action(session)
                session.commit()
                return result
            except ReviewConflict:
                session.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=len(actions)) as pool:
        return list(pool.map(work, actions))


def decision(**updates):
    return {
        "action": "create",
        "event_id": None,
        "expected_revision": 0,
        "patch": {},
        "note": "Evidence manually reconciled by test reviewer",
        "allow_older_evidence": False,
    } | updates


def test_parallel_capture_inserts_one_observation(pg_engine):
    seed(pg_engine)
    captured = run_parallel(
        pg_engine,
        [
            lambda session: record_source_pages(session, page(), ["600036"]),
        ]
        * 4,
    )
    assert sorted(captured) == [0, 0, 0, 1]
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(DividendSourceObservation)) == 1


def test_parallel_review_retry_creates_one_event_revision_and_audit(pg_engine):
    user_id = seed(pg_engine)
    with Session(pg_engine) as session:
        record_source_pages(session, page(), ["600036"])
        session.commit()
        observation_id = session.scalar(select(DividendSourceObservation.id))

    def review(session):
        # Keep a stale identity map before row locks, as real concurrent API callers may do.
        session.get(DividendSourceObservation, observation_id)
        row, version = review_observation(
            session, observation_id, reviewer_id=user_id, decision=decision()
        )
        return row.event_id, version.revision

    results = run_parallel(pg_engine, [review] * 4)
    assert len(set(results)) == 1
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(DividendEvent)) == 1
        assert session.scalar(select(func.count()).select_from(DividendEventVersion)) == 1
        assert session.scalar(select(func.count()).select_from(AdminAuditLog)) == 1


def test_competing_revision_review_does_not_lose_history(pg_engine):
    user_id = seed(pg_engine)
    with Session(pg_engine) as session:
        record_source_pages(session, page(), ["600036"])
        session.commit()
        first = session.scalar(select(DividendSourceObservation.id))
        row, _ = review_observation(session, first, reviewer_id=user_id, decision=decision())
        event_id = row.event_id
        session.commit()
        record_source_pages(session, page("6", "2026-07-02") + page("7", "2026-07-03"), ["600036"])
        session.commit()
        ids = session.scalars(
            select(DividendSourceObservation.id).where(DividendSourceObservation.state == "pending")
        ).all()

    def review(identifier):
        def action(session):
            _, version = review_observation(
                session,
                identifier,
                reviewer_id=user_id,
                decision=decision(action="revise", event_id=event_id, expected_revision=1),
            )
            return version.revision

        return action

    assert sorted(
        map(str, run_parallel(pg_engine, [review(identifier) for identifier in ids]))
    ) == [
        "2",
        "conflict",
    ]
    with Session(pg_engine) as session:
        assert session.get(DividendEvent, event_id).current_revision == 2
        assert session.scalar(select(func.count()).select_from(DividendEventVersion)) == 2
        assert session.scalar(select(func.count()).select_from(AdminAuditLog)) == 2


def test_parallel_legacy_backfill_is_idempotent(pg_engine):
    seed(pg_engine)
    with Session(pg_engine) as session:
        session.add(
            StockDividend(
                code="600036",
                fiscal_year=2025,
                cash_per_share="0.5",
                plan="same legacy",
                progress="实施分配",
            )
        )
        session.commit()
    results = run_parallel(pg_engine, [lambda session: backfill_legacy(session, apply=True)] * 3)
    assert sum(item["created"] for item in results) == 1
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(DividendEventVersion)) == 1
        assert session.scalar(select(func.count()).select_from(StockDividend)) == 1


def test_new_migration_downgrade_upgrade_preserves_legacy_data(pg_engine):
    seed(pg_engine)
    with Session(pg_engine) as session:
        session.add(
            StockDividend(
                code="600036",
                fiscal_year=2025,
                cash_per_share="0.5",
                plan="legacy unchanged",
                progress="实施分配",
            )
        )
        session.commit()
    path = Path(__file__).parents[1] / "alembic/versions/c8d4e6f29013_dividend_events.py"
    spec = importlib.util.spec_from_file_location("dividend_event_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    income_path = path.with_name("b2d5e7f1a034_portfolio_income.py")
    income_spec = importlib.util.spec_from_file_location(
        "portfolio_income_migration", income_path
    )
    income_migration = importlib.util.module_from_spec(income_spec)
    income_spec.loader.exec_module(income_migration)
    with pg_engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
        income_migration.downgrade()
        migration.downgrade()
        assert conn.scalar(text("SELECT count(*) FROM stock_dividends")) == 1
        migration.upgrade()
        income_migration.upgrade()
        assert conn.scalar(text("SELECT count(*) FROM stock_dividends")) == 1
        assert conn.scalar(text("SELECT count(*) FROM dividend_events")) == 0
    with Session(pg_engine) as session:
        assert backfill_legacy(session, apply=True)["created"] == 1
        session.commit()
        assert session.scalar(select(func.count()).select_from(DividendEventVersion)) == 1

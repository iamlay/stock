"""Real row-lock regression tests.

Set STOCKLAB_TEST_POSTGRES_URL to a disposable PostgreSQL database. Each test
uses a unique schema and removes only that schema on completion.
"""
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from urllib.parse import urlencode
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api.v1.billing import notify, sign_params
from app.db.base import Base
from app.db.models import PaymentOrder, RedeemCode, User
from app.services.membership import redeem_code, start_trial
from app.settings import settings


@pytest.fixture
def pg_engine():
    url = os.getenv("STOCKLAB_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("STOCKLAB_TEST_POSTGRES_URL is required for real row-lock tests")
    admin = create_engine(url)
    schema = "trial_test_" + uuid4().hex
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


def seed(engine):
    with Session(engine) as session:
        user = User(email="concurrent@example.com", email_verified_at=datetime.now(UTC))
        session.add(user)
        session.flush()
        user_id = user.id
        session.add_all([
            RedeemCode(code="SLPAID", plan="member", duration_days=30),
            RedeemCode(code="SLTRIALA", plan="trial", duration_days=7),
            RedeemCode(code="SLTRIALB", plan="trial", duration_days=7),
        ])
        for number in ("PAY1", "PAY2"):
            session.add(PaymentOrder(order_no=number, user_id=user_id, platform="ezfpy",
                                     product="standard-monthly", amount=9.99, status="pending"))
        session.commit()
        return user_id


def parallel(engine, user_id, actions):
    barrier = Barrier(len(actions))

    def work(action):
        with Session(engine, autoflush=False, expire_on_commit=False) as session:
            user = session.get(User, user_id)  # Deliberately stale identities before locking.
            barrier.wait(timeout=10)
            try:
                result = action(session, user)
                session.commit()
                return result
            except ValueError:
                session.rollback()
                return "rejected"

    with ThreadPoolExecutor(max_workers=len(actions)) as pool:
        return list(pool.map(work, actions))


def test_concurrent_trial_claim_is_idempotent(pg_engine):
    user_id = seed(pg_engine)
    results = parallel(pg_engine, user_id, [start_trial] * 4)
    assert results.count(True) == 1
    assert results.count(False) == 3
    with Session(pg_engine) as session:
        user = session.get(User, user_id)
        assert user.plan_expires_at - user.trial_started_at == timedelta(days=7)


def test_concurrent_distinct_trial_codes_only_consume_one(pg_engine):
    user_id = seed(pg_engine)
    results = parallel(pg_engine, user_id, [
        lambda s, u: redeem_code(s, u, "SLTRIALA"),
        lambda s, u: redeem_code(s, u, "SLTRIALB"),
    ])
    assert results.count("rejected") == 1
    with Session(pg_engine) as session:
        assert sum(session.get(RedeemCode, code).used_count
                   for code in ("SLTRIALA", "SLTRIALB")) == 1


def test_payment_retries_renewals_redemption_and_trial_do_not_lose_days(pg_engine, monkeypatch):
    monkeypatch.setattr(settings, "ezfpy_pid", "test")
    monkeypatch.setattr(settings, "ezfpy_key", "secret")
    user_id = seed(pg_engine)

    def pay(number):
        def action(session, _user):
            params = {"pid": "test", "out_trade_no": number,
                      "money": "9.99", "trade_status": "TRADE_SUCCESS"}
            params["sign"] = sign_params(params, "secret")
            request = Request({"type": "http", "method": "GET",
                               "query_string": urlencode(params).encode(), "headers": []})
            response = asyncio.run(notify(request, session))
            assert response.status_code == 200
        return action

    before = datetime.now(UTC)
    parallel(pg_engine, user_id, [pay("PAY1"), pay("PAY1"), pay("PAY2"),
                                 lambda s, u: redeem_code(s, u, "SLPAID"), start_trial])
    with Session(pg_engine) as session:
        user = session.get(User, user_id)
        assert user.plan == "member"
        assert before + timedelta(days=90) <= user.plan_expires_at
        assert user.plan_expires_at <= datetime.now(UTC) + timedelta(days=90)
        assert session.get(RedeemCode, "SLPAID").used_count == 1


def test_legacy_trial_migration_preserves_expiry_and_consumption(pg_engine):
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = Path(__file__).parents[1] / "alembic/versions/e6a2c9f08314_membership_entitlements.py"
    spec = importlib.util.spec_from_file_location("trial_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    user_id = seed(pg_engine)
    expiry = datetime.now(UTC) + timedelta(days=12)
    with pg_engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            migration.downgrade()
            conn.execute(text("UPDATE users SET plan='trial', plan_expires_at=:expiry"),
                         {"expiry": expiry})
            migration.upgrade()
        row = conn.execute(
            text("SELECT * FROM users WHERE id=:id"), {"id": user_id}
        ).mappings().one()
        assert row["trial_started_at"] is not None
        assert row["plan_expires_at"] == expiry
        assert row["entitlement_source"] == "legacy_trial"
        # A previously redeemed trial must remain used even after upgrading to paid.
        conn.execute(text("UPDATE users SET plan='member'"))
        conn.execute(text("UPDATE redeem_codes SET redeemed_by=:id, redeemed_at=NOW(), "
                          "status='redeemed', used_count=1 WHERE code='SLTRIALA'"), {"id": user_id})
        with Operations.context(MigrationContext.configure(conn)):
            migration.downgrade()
            migration.upgrade()
        assert conn.execute(text("SELECT trial_started_at FROM users")).scalar() is not None


def test_failed_delivery_rolls_back_and_retry_delivers_once(pg_engine, monkeypatch):
    from app.api.v1 import billing

    monkeypatch.setattr(settings, "ezfpy_pid", "test")
    monkeypatch.setattr(settings, "ezfpy_key", "secret")
    user_id = seed(pg_engine)
    params = {"pid": "test", "out_trade_no": "PAY1", "money": "9.99",
              "trade_status": "TRADE_SUCCESS"}
    params["sign"] = sign_params(params, "secret")
    real_activate = billing.activate_membership

    def failed_activate(*args, **kwargs):
        real_activate(*args, **kwargs)
        args[0].flush()  # Fail after a real write but before the transaction commits.
        raise RuntimeError("simulated delivery failure")

    def deliver():
        request = Request({"type": "http", "method": "GET", "headers": [],
                           "query_string": urlencode(params).encode()})
        with Session(pg_engine) as session:
            return asyncio.run(notify(request, session))

    monkeypatch.setattr(billing, "activate_membership", failed_activate)
    with pytest.raises(RuntimeError, match="simulated"):
        deliver()
    with Session(pg_engine) as session:
        assert session.get(User, user_id).plan == "free"
        assert session.query(PaymentOrder).filter_by(order_no="PAY1").one().status == "pending"
    monkeypatch.setattr(billing, "activate_membership", real_activate)
    assert deliver().status_code == 200
    with Session(pg_engine) as session:
        expiry = session.get(User, user_id).plan_expires_at
    assert deliver().status_code == 200
    with Session(pg_engine) as session:
        assert session.get(User, user_id).plan_expires_at == expiry


def test_concurrent_preview_bindings_cannot_unlock_two_stocks(pg_engine, monkeypatch):
    from fastapi import HTTPException

    from app.api.v1.previews import Selection, select_personal
    from app.db.models import StockWatchlist
    from tests.test_stocks_api import _stock

    monkeypatch.setattr(settings, "stock_preview_enabled", True)
    monkeypatch.setattr(settings, "stock_preview_percent", 100)
    user_id = seed(pg_engine)
    with Session(pg_engine) as session:
        for code in ("601398", "600519"):
            _stock(session, code, "测试", "测试", 1000, 5)
            session.add(StockWatchlist(user_id=user_id, code=code))
        session.commit()

    def bind(code):
        def action(session, user):
            try:
                return select_personal(Selection(code=code), session, user).selected_code
            except HTTPException as exc:
                assert exc.status_code == 409
                raise ValueError("different binding") from exc
        return action

    results = parallel(pg_engine, user_id, [bind("601398"), bind("600519")])
    assert results.count("rejected") == 1
    selected = next(result for result in results if result != "rejected")
    assert parallel(pg_engine, user_id, [bind(selected)] * 3) == [selected] * 3
    with Session(pg_engine) as session:
        assert session.get(User, user_id).advanced_preview_code == selected

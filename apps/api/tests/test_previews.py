from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.api.v1.previews import eligible
from app.db import get_session
from app.db.models import MarketDaily, StockFinancial, StockWatchlist, User
from app.main import app
from app.security import create_access_token
from app.settings import settings
from tests.test_stocks_api import _stock


@pytest.fixture
def preview_client(session, monkeypatch):
    monkeypatch.setattr(settings, "stock_preview_enabled", True)
    monkeypatch.setattr(settings, "stock_preview_percent", 100)
    monkeypatch.setattr(settings, "stock_preview_user_ids", "")
    monkeypatch.setattr(settings, "advanced_samples_enabled", True)
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def seed(session):
    user = User(email="preview@example.com", email_verified_at=datetime.now(UTC))
    other = User(email="other@example.com", email_verified_at=datetime.now(UTC))
    session.add_all([user, other])
    session.flush()
    for code in ("601398", "600519", "000001"):
        _stock(session, code, "测试公司", "测试", 1000, 5)
    session.add_all(
        [
            StockWatchlist(user_id=user.id, code="601398"),
            StockWatchlist(user_id=user.id, code="600519"),
            StockWatchlist(user_id=other.id, code="000001"),
        ]
    )
    for i in range(30):
        session.add(
            MarketDaily(
                code="601398",
                trade_date=date(2026, 9, 1) + timedelta(days=i),
                open=10,
                high=12,
                low=9,
                close=10 + i / 100,
                volume=100,
            )
        )
    for year in (2024, 2025):
        session.add(
            StockFinancial(
                code="601398",
                report_date=date(year, 12, 31),
                period="FY",
                net_profit_yoy=8,
                roe=6,
                revenue=99999,
            )
        )
    session.commit()
    return user, other


def headers(user):
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def test_samples_are_public_fixed_and_can_be_disabled(preview_client, monkeypatch):
    result = preview_client.get("/api/v1/previews/samples")
    assert result.status_code == 200
    body = result.json()
    assert body["kind"] == "sample" and body["code"] == "DEMO"
    assert len(body["cards"]) == 3
    assert all(card["as_of"] and card["purpose"] and card["metrics"] for card in body["cards"])
    assert "no-store" in result.headers["cache-control"]
    monkeypatch.setattr(settings, "advanced_samples_enabled", False)
    assert preview_client.get("/api/v1/previews/samples").json() is None


def test_preview_requires_auth_and_verified_account(preview_client, session):
    assert preview_client.get("/api/v1/previews/personal").status_code == 401
    assert (
        preview_client.post("/api/v1/previews/personal", json={"code": "601398"}).status_code == 401
    )
    user, _ = seed(session)
    user.email_verified_at = None
    session.commit()
    assert (
        preview_client.post(
            "/api/v1/previews/personal", headers=headers(user), json={"code": "601398"}
        ).status_code
        == 403
    )
    assert user.advanced_preview_code is None


def test_one_binding_bounded_fields_and_full_endpoints_stay_locked(preview_client, session):
    user, _ = seed(session)
    auth = headers(user)
    state = preview_client.get("/api/v1/previews/personal", headers=auth).json()
    assert {x["code"] for x in state["choices"]} == {"601398", "600519"}
    result = preview_client.post("/api/v1/previews/personal", headers=auth, json={"code": "601398"})
    assert result.status_code == 200
    assert result.headers["cache-control"] == "private, no-store"
    body = result.json()
    assert body["selected_code"] == "601398" and body["choices"] == []
    grid, band, financial = body["preview"]["cards"]
    assert len(grid["metrics"]) == 3
    assert grid["metrics"]["5% 对应价格"] == "10.00 元"
    assert len(band["metrics"]) == 5 and band["as_of"] == "2026-09-30"
    assert financial["as_of"] == "2025-12-31" and len(financial["metrics"]) == 4
    assert "99999" not in result.text
    assert user.plan == "free" and user.trial_started_at is None
    assert (
        preview_client.post(
            "/api/v1/previews/personal", headers=auth, json={"code": "601398"}
        ).json()
        == body
    )
    assert (
        preview_client.post(
            "/api/v1/previews/personal", headers=auth, json={"code": "600519"}
        ).status_code
        == 409
    )
    for path in ("grid", "bollinger", "financials"):
        assert preview_client.get(f"/api/v1/stocks/{path}", headers=auth).status_code == 403
    assert preview_client.get("/api/v1/stocks/601398", headers=auth).json()["financials"] == []


def test_cannot_select_others_stock_or_change_scope(preview_client, session):
    user, other = seed(session)
    auth = headers(user)
    for code in ("000001", "999999"):
        assert (
            preview_client.post(
                "/api/v1/previews/personal", headers=auth, json={"code": code}
            ).status_code
            == 403
        )
    for query in ("code=000001", "page_size=100", "user_id=2", "start=2020-01-01"):
        assert (
            preview_client.get(f"/api/v1/previews/personal?{query}", headers=auth).status_code
            == 422
        )
        assert (
            preview_client.post(
                f"/api/v1/previews/personal?{query}", headers=auth, json={"code": "601398"}
            ).status_code
            == 422
        )
    for body in (
        {"code": "601398", "user_id": other.id},
        {"code": "601398,600519"},
        {"code": "601398", "range": "all"},
    ):
        assert (
            preview_client.post("/api/v1/previews/personal", headers=auth, json=body).status_code
            == 422
        )
    assert user.advanced_preview_code is None
    preview_client.post("/api/v1/previews/personal", headers=auth, json={"code": "601398"})
    assert (
        preview_client.get("/api/v1/previews/personal", headers=headers(other)).json()[
            "selected_code"
        ]
        is None
    )


def test_delete_watchlist_does_not_reset_binding(preview_client, session):
    user, _ = seed(session)
    auth = headers(user)
    preview_client.post("/api/v1/previews/personal", headers=auth, json={"code": "601398"})
    session.execute(
        delete(StockWatchlist).where(
            StockWatchlist.user_id == user.id, StockWatchlist.code == "601398"
        )
    )
    session.commit()
    body = preview_client.get("/api/v1/previews/personal", headers=auth).json()
    assert body["selected_code"] == "601398" and body["preview"] is None and body["message"]
    assert (
        preview_client.post(
            "/api/v1/previews/personal", headers=auth, json={"code": "600519"}
        ).status_code
        == 409
    )
    session.add(StockWatchlist(user_id=user.id, code="601398"))
    session.commit()
    assert (
        preview_client.get("/api/v1/previews/personal", headers=auth).json()["preview"]["code"]
        == "601398"
    )


def test_missing_data_is_not_replaced_with_sample(preview_client, session):
    user, _ = seed(session)
    body = preview_client.post(
        "/api/v1/previews/personal", headers=headers(user), json={"code": "600519"}
    ).json()
    assert body["preview"]["kind"] == "personal"
    assert body["preview"]["cards"][1]["metrics"] == {}
    assert body["preview"]["cards"][2]["as_of"] is None


def test_rollout_and_shutdown_keep_binding(preview_client, session, monkeypatch):
    user, _ = seed(session)
    auth = headers(user)
    monkeypatch.setattr(settings, "stock_preview_percent", 0)
    assert not eligible(user)
    monkeypatch.setattr(settings, "stock_preview_user_ids", str(user.id))
    assert eligible(user)
    preview_client.post("/api/v1/previews/personal", headers=auth, json={"code": "601398"})
    monkeypatch.setattr(settings, "stock_preview_enabled", False)
    assert not preview_client.get("/api/v1/previews/personal", headers=auth).json()["enabled"]
    assert (
        preview_client.post(
            "/api/v1/previews/personal", headers=auth, json={"code": "601398"}
        ).status_code
        == 403
    )
    assert user.advanced_preview_code == "601398"
    monkeypatch.setattr(settings, "stock_preview_enabled", True)
    for plan in ("member", "trial"):
        user.plan = plan
        user.plan_expires_at = datetime.now(UTC) + timedelta(days=1)
        session.commit()
        assert not eligible(user)
    user.plan_expires_at = datetime.now(UTC) - timedelta(days=1)
    session.commit()
    assert eligible(user) and user.advanced_preview_code == "601398"

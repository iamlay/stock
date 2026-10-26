from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.v1.billing import sign_params
from app.api.v1.plans import PLANS
from app.db.models import PaymentOrder, User
from app.db.session import get_session
from app.main import app
from app.security import create_access_token
from app.settings import settings


def test_catalogue_only_advertises_delivered_products_and_features():
    with TestClient(app) as client:
        response = client.get("/api/v1/plans")
    assert response.status_code == 200
    free, member = response.json()
    assert [free["id"], member["id"]] == ["free", "standard-monthly"]
    assert free["purchasable"] is False
    assert free["duration_days"] == 0
    assert member["price_cny"] == 9.99
    assert member["duration_days"] == 30
    assert member["billing_note"] == "一次购买 30 天，不自动扣费"
    assert "试用" not in response.text
    assert "导出" not in response.text
    assert "回测不限次数，可查看回测历史" in member["features"]
    assert any("ETF + 股票自选合计最多 10 个" == value for value in free["features"])


def test_catalogue_uses_deployed_quota_limits(monkeypatch):
    monkeypatch.setattr(settings, "free_daily_limit", 35)
    monkeypatch.setattr(settings, "guest_daily_limit", 12)
    with TestClient(app) as client:
        free = client.get("/api/v1/plans").json()[0]
    assert "登录后回测 35 次/日" in free["features"]
    assert "游客回测 12 次/日" in free["features"]


def test_changed_product_matches_catalogue_checkout_notice_and_delivery(session, monkeypatch):
    # Changing the one product definition must update both selling and fulfilling it.
    monkeypatch.setattr(PLANS[0], "price_cny", 12.34)
    monkeypatch.setattr(PLANS[0], "duration_days", 45)
    monkeypatch.setattr(settings, "ezfpy_pid", "test-merchant")
    monkeypatch.setattr(settings, "ezfpy_key", "test-key")
    user = User(
        email="catalogue@example.com", role="member", plan="free",
        email_verified_at=datetime.now(UTC),
    )
    session.add(user)
    session.commit()

    headers = {"Authorization": f"Bearer {create_access_token(user)}"}
    app.dependency_overrides[get_session] = lambda: session
    try:
        with TestClient(app) as client:
            member = client.get("/api/v1/plans").json()[1]
            assert member["price_cny"] == 12.34
            assert member["billing_note"] == "一次购买 45 天，不自动扣费"
            assert "¥12.34/45 天" in client.get("/api/v1/plans/notice").json()["notice"]
            result = client.post(
                "/api/v1/billing/checkout",
                json={"plan_id": member["id"], "payment_type": "alipay"},
                headers=headers,
            )
            assert result.status_code == 200
            order_data = result.json()
            assert order_data["amount"] == member["price_cny"]
            assert order_data["fields"]["money"] == "12.34"
            params = {
                "pid": "test-merchant",
                "trade_no": "test-transaction",
                "out_trade_no": order_data["order_no"],
                "money": "12.34",
                "trade_status": "TRADE_SUCCESS",
            }
            params["sign"] = sign_params(params, "test-key")
            assert client.get("/api/v1/billing/notify", params=params).text == "success"
            order = session.query(PaymentOrder).filter_by(order_no=order_data["order_no"]).one()
            session.refresh(user)
            assert order.amount == Decimal("12.34")
            assert user.plan_expires_at.replace(tzinfo=UTC) == (
                order.paid_at.replace(tzinfo=UTC) + timedelta(days=45)
            )
    finally:
        app.dependency_overrides.clear()


def test_free_trial_and_legacy_products_cannot_be_purchased(session):

    user = User(
        email="no-checkout@example.com", role="member", plan="free",
        email_verified_at=datetime.now(UTC),
    )
    session.add(user)
    session.commit()
    app.dependency_overrides[get_session] = lambda: session
    try:
        with TestClient(app) as client:
            for product in ["free", "trial", "standard-yearly"]:
                response = client.post(
                    "/api/v1/billing/checkout",
                    json={"plan_id": product},
                    headers={"Authorization": f"Bearer {create_access_token(user)}"},
                )
                assert response.status_code == 400
            assert session.query(PaymentOrder).count() == 0
    finally:
        app.dependency_overrides.clear()

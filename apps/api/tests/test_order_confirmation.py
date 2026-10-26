from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.v1.billing import sign_params
from app.db.models import PaymentOrder, User
from app.db.session import get_session
from app.main import app
from app.security import create_access_token
from app.settings import settings


@pytest.fixture
def orders(session, monkeypatch):
    monkeypatch.setattr(settings, "ezfpy_pid", "test")
    monkeypatch.setattr(settings, "ezfpy_key", "secret")
    expiry = datetime.now(UTC) + timedelta(days=90)
    owner = User(email="owner@example.com", email_verified_at=datetime.now(UTC),
                 plan="member", plan_expires_at=expiry)
    other = User(email="other@example.com", email_verified_at=datetime.now(UTC))
    session.add_all([owner, other])
    session.flush()
    order = PaymentOrder(order_no="ONLINE1", platform="ezfpy", user_id=owner.id,
                         product="standard-monthly", amount=9.99, status="pending")
    session.add(order)
    session.commit()
    app.dependency_overrides[get_session] = lambda: session
    try:
        with TestClient(app) as client:
            yield client, owner, other, order
    finally:
        app.dependency_overrides.clear()


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def callback(**changes):
    fields = {"pid": "test", "out_trade_no": "ONLINE1", "money": "9.99",
              "trade_status": "TRADE_SUCCESS", "trade_no": "GATEWAY1", **changes}
    fields["sign"] = sign_params(fields, "secret")
    return fields


def test_pending_order_is_not_paid_even_for_existing_member(orders):
    client, owner, other, _ = orders
    path = "/api/v1/billing/order/ONLINE1"
    assert client.get(path).status_code == 401
    hidden = client.get(path, headers=auth(other))
    missing = client.get("/api/v1/billing/order/MISSING", headers=auth(other))
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json()
    response = client.get(path, headers=auth(owner))
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["status"] == "pending"
    assert response.json()["paid_at"] is None
    assert response.json()["delivered_at"] is None


def test_post_callback_is_idempotent_and_query_confirms_delivery(orders, session):
    client, owner, _, order = orders
    before = owner.plan_expires_at
    for _ in range(2):
        response = client.post("/api/v1/billing/notify", data=callback())
        assert response.status_code == 200 and response.text == "success"
    session.refresh(owner)
    assert owner.plan_expires_at.replace(tzinfo=UTC) == before + timedelta(days=30)
    result = client.get("/api/v1/billing/order/ONLINE1", headers=auth(owner)).json()
    assert result["status"] == "delivered" and result["paid_at"] and result["delivered_at"]
    assert order.external_order_id == "GATEWAY1"
    # Even an already delivered order must reject a mismatching signed amount.
    assert client.get("/api/v1/billing/notify", params=callback(money="1")).status_code == 400


@pytest.mark.parametrize("changes", [
    {"money": "NaN"}, {"money": "sNaN"}, {"money": "Infinity"},
    {"money": "-9.99"}, {"money": "0"}, {"money": "invalid"}, {"money": "19.99"},
    {"pid": "other"}, {"trade_status": "WAIT_BUYER_PAY"},
])
def test_invalid_callbacks_never_deliver(orders, changes):
    client, owner, _, order = orders
    before = owner.plan_expires_at
    response = client.get("/api/v1/billing/notify", params=callback(**changes))
    assert response.status_code == 400
    assert order.status == "pending" and owner.plan_expires_at == before


def test_invalid_signature_and_nonpayable_order_do_not_deliver(orders, session):
    client, _, _, order = orders
    fields = callback()
    fields["sign"] = "forged"
    assert client.get("/api/v1/billing/notify", params=fields).status_code == 400
    order.status = "refunded"
    session.commit()
    assert client.get("/api/v1/billing/notify", params=callback()).status_code == 409
    order.platform = "manual"
    session.commit()
    assert client.get("/api/v1/billing/notify", params=callback()).status_code == 400

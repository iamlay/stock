from datetime import UTC, date, datetime

from fastapi.testclient import TestClient

from app.api.v1.billing import sign_params
from app.db.models import PaymentOrder, User
from app.db.session import get_session
from app.main import app
from app.security import create_access_token
from app.settings import settings


def _client(session) -> TestClient:
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def test_sign_params_is_ascii_sorted_and_skips_sign() -> None:
    params = {
        "pid": "1000",
        "type": "alipay",
        "out_trade_no": "SL1",
        "money": "199.00",
        "sign": "ignored",
        "sign_type": "MD5",
    }
    expected_source = "money=199.00&out_trade_no=SL1&pid=1000&type=alipaysecret"
    import hashlib

    assert sign_params(params, "secret") == hashlib.md5(
        expected_source.encode()
    ).hexdigest()


def test_checkout_and_notify_activate_membership(session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ezfpy_pid", "1000")
    monkeypatch.setattr(settings, "ezfpy_key", "secret")
    user = User(
        phone="13800007777",
        email="pay@example.com",
        role="member",
        plan="free",
        email_verified_at=datetime.now(UTC),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    headers = {"Authorization": f"Bearer {create_access_token(user)}"}
    client = _client(session)
    try:
        checkout = client.post(
            "/api/v1/billing/checkout",
            json={"plan_id": "standard-yearly", "payment_type": "alipay"},
            headers=headers,
        )
        assert checkout.status_code == 200
        body = checkout.json()
        assert body["amount"] == 199.0
        assert body["fields"]["sign"] == sign_params(body["fields"], "secret")

        notify_params = {
            "pid": "1000",
            "trade_no": "EZF123",
            "out_trade_no": body["order_no"],
            "type": "alipay",
            "name": "StockLab 标准年付",
            "money": "199.00",
            "trade_status": "TRADE_SUCCESS",
            "sign_type": "MD5",
        }
        notify_params["sign"] = sign_params(notify_params, "secret")
        notify = client.get("/api/v1/billing/notify", params=notify_params)
        assert notify.status_code == 200
        assert notify.text == "success"

        order = session.query(PaymentOrder).filter_by(order_no=body["order_no"]).one()
        assert order.status == "delivered"
        session.refresh(user)
        assert user.plan == "member"
        assert user.plan_expires_at is not None
        assert user.plan_expires_at.date() >= date.today()

        repeat = client.get("/api/v1/billing/notify", params=notify_params)
        assert repeat.status_code == 200
        assert repeat.text == "success"
    finally:
        app.dependency_overrides.clear()

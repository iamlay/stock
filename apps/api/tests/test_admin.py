from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.db.models import BacktestRun, PaymentOrder, User
from app.db.session import get_session
from app.main import app
from app.security import create_access_token


def _client(session) -> TestClient:
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def _headers(session, role: str = "admin") -> dict[str, str]:
    user = User(phone=f"135{role[:4]:0<8}"[:11], role=role, plan="free")
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def test_admin_generates_and_lists_codes(session) -> None:
    client = _client(session)
    try:
        headers = _headers(session)
        created = client.post(
            "/api/v1/admin/redeem-codes",
            json={"count": 2, "days": 30, "channel": "test", "plan": "member"},
            headers=headers,
        )
        assert created.status_code == 200
        body = created.json()
        assert len(body["codes"]) == 2
        assert len({item["code"] for item in body["codes"]}) == 2

        listed = client.get("/api/v1/admin/redeem-codes", headers=headers)
        assert listed.status_code == 200
        data = listed.json()
        assert data["stats"]["total"] == 2
        assert data["stats"]["issued"] == 2

        code = body["codes"][0]["code"]
        revoked = client.post(
            f"/api/v1/admin/redeem-codes/{code}/revoke", headers=headers
        )
        assert revoked.status_code == 200
        assert revoked.json()["status"] == "revoked"
    finally:
        app.dependency_overrides.clear()


def test_admin_requires_admin_role(session) -> None:
    client = _client(session)
    try:
        headers = _headers(session, role="member")
        response = client.get("/api/v1/admin/redeem-codes", headers=headers)
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_admin_export_csv(session) -> None:
    client = _client(session)
    try:
        headers = _headers(session)
        client.post(
            "/api/v1/admin/redeem-codes",
            json={"count": 1, "days": 7, "channel": "test"},
            headers=headers,
        )
        response = client.get("/api/v1/admin/redeem-codes/export", headers=headers)
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert "SL" in response.text
    finally:
        app.dependency_overrides.clear()


def test_admin_pagination_and_batch_filter(session) -> None:
    client = _client(session)
    try:
        headers = _headers(session)
        created = client.post(
            "/api/v1/admin/redeem-codes",
            json={"count": 3, "days": 30, "channel": "batch-test"},
            headers=headers,
        ).json()
        batch_id = created["batch_id"]

        first = client.get(
            "/api/v1/admin/redeem-codes?page=1&page_size=2", headers=headers
        ).json()
        assert first["total"] == 3
        assert len(first["items"]) == 2

        second = client.get(
            "/api/v1/admin/redeem-codes?page=2&page_size=2", headers=headers
        ).json()
        assert len(second["items"]) == 1

        filtered = client.get(
            f"/api/v1/admin/redeem-codes?batch_id={batch_id}", headers=headers
        ).json()
        assert filtered["total"] == 3

        batches = client.get("/api/v1/admin/redeem-codes/batches", headers=headers).json()
        assert any(item["batch_id"] == batch_id for item in batches)
    finally:
        app.dependency_overrides.clear()


def test_admin_audit_log_records_generate(session) -> None:
    client = _client(session)
    try:
        headers = _headers(session)
        client.post(
            "/api/v1/admin/redeem-codes",
            json={"count": 1, "days": 7, "channel": "audit"},
            headers=headers,
        )
        logs = client.get("/api/v1/admin/audit-logs", headers=headers).json()
        assert logs["total"] >= 1
        assert logs["items"][0]["action"] == "generate_codes"
    finally:
        app.dependency_overrides.clear()


def test_order_creates_code_and_refund_revokes(session) -> None:
    client = _client(session)
    try:
        headers = _headers(session)
        created = client.post(
            "/api/v1/admin/orders",
            json={
                "platform": "zhishixingqiu",
                "external_order_id": "EXT-001",
                "buyer_phone": "13800138000",
                "amount": 199,
                "days": 365,
                "product": "member-365",
            },
            headers=headers,
        )
        assert created.status_code == 200
        order = created.json()
        assert order["amount"] == 199
        assert order["code"].startswith("SL")
        assert order["status"] == "delivered"

        listed = client.get("/api/v1/admin/orders", headers=headers).json()
        assert listed["total"] == 1
        assert listed["revenue"] == 199
        assert listed["items"][0]["external_order_id"] == "EXT-001"

        refunded = client.post(
            f"/api/v1/admin/orders/{order['order_no']}/refund", headers=headers
        )
        assert refunded.status_code == 200
        assert refunded.json()["status"] == "refunded"

        codes = client.get(
            f"/api/v1/admin/redeem-codes?batch_id={order['order_no']}", headers=headers
        ).json()
        assert codes["items"][0]["status"] == "revoked"
    finally:
        app.dependency_overrides.clear()


def test_admin_can_search_ban_and_grant_membership(session) -> None:
    client = _client(session)
    try:
        headers = _headers(session)
        target = User(
            phone="13700000000",
            email="member@example.com",
            role="member",
            plan="free",
            email_verified_at=datetime.now(UTC),
        )
        session.add(target)
        session.commit()
        session.refresh(target)
        target_token = create_access_token(target)

        listed = client.get(
            "/api/v1/admin/users?q=member", headers=headers
        )
        assert listed.status_code == 200
        assert listed.json()["total"] == 1

        granted = client.patch(
            f"/api/v1/admin/users/{target.id}",
            json={"plan": "member", "days": 30},
            headers=headers,
        )
        assert granted.status_code == 200
        assert granted.json()["plan"] == "member"
        assert granted.json()["plan_expires_at"]

        banned = client.patch(
            f"/api/v1/admin/users/{target.id}",
            json={"status": "banned"},
            headers=headers,
        )
        assert banned.status_code == 200
        assert banned.json()["status"] == "banned"

        blocked = client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {target_token}"},
        )
        assert blocked.status_code == 401

        unbanned = client.patch(
            f"/api/v1/admin/users/{target.id}",
            json={"status": "active"},
            headers=headers,
        )
        assert unbanned.json()["status"] == "active"

        revoked = client.patch(
            f"/api/v1/admin/users/{target.id}",
            json={"plan": "free"},
            headers=headers,
        )
        assert revoked.json()["plan"] == "free"
        assert revoked.json()["plan_expires_at"] is None
    finally:
        app.dependency_overrides.clear()


def test_admin_user_detail_aggregates(session) -> None:
    client = _client(session)
    try:
        headers = _headers(session)
        target = User(
            phone="13600000000",
            email="detail@example.com",
            role="member",
            plan="free",
            email_verified_at=datetime.now(UTC),
        )
        session.add(target)
        session.commit()
        session.refresh(target)

        order = client.post(
            "/api/v1/admin/orders",
            json={
                "platform": "manual",
                "buyer_phone": target.phone,
                "amount": 99,
                "days": 365,
                "product": "member-365",
            },
            headers=headers,
        ).json()

        backtest = BacktestRun(
            user_id=target.id,
            code="510300",
            strategy="dual-ma",
            params={},
            initial_cash=100000,
            status="success",
            metrics={"total_return": 12.5},
            result={
                "code": "510300",
                "strategy": "dual-ma",
                "equity": [],
                "trades": [{"side": "buy"}, {"side": "sell"}],
            },
        )
        session.add(backtest)
        session.commit()
        session.refresh(backtest)
        detail = client.get(f"/api/v1/admin/users/{target.id}", headers=headers)
        assert detail.status_code == 200
        body = detail.json()
        assert body["user"]["email"] == "detail@example.com"
        assert len(body["orders"]) == 1
        assert body["orders"][0]["order_no"] == order["order_no"]
        assert len(body["codes"]) == 1
        assert body["codes"][0]["code"] == order["code"]
        assert len(body["backtests"]) == 1
        assert body["backtests"][0]["total_return"] == 12.5
        assert body["backtests"][0]["trades"] == 2
        assert body["orders_total"] == 1
        assert body["codes_total"] == 1
        assert body["backtests_total"] == 1

        run = client.get(
            f"/api/v1/admin/users/{target.id}/backtests/{backtest.id}",
            headers=headers,
        )
        assert run.status_code == 200
        assert run.json()["result"]["code"] == "510300"
    finally:
        app.dependency_overrides.clear()


def test_admin_order_links_by_email(session) -> None:
    client = _client(session)
    try:
        headers = _headers(session)
        target = User(
            email="buyer@example.com",
            role="member",
            plan="free",
            email_verified_at=datetime.now(UTC),
        )
        session.add(target)
        session.commit()
        session.refresh(target)

        order = client.post(
            "/api/v1/admin/orders",
            json={
                "platform": "manual",
                "buyer_email": "buyer@example.com",
                "amount": 88,
                "days": 30,
                "product": "member-30",
            },
            headers=headers,
        )
        assert order.status_code == 200
        body = order.json()
        assert body["buyer_email"] == "buyer@example.com"
        assert body["user_id"] == target.id

        detail = client.get(f"/api/v1/admin/users/{target.id}", headers=headers)
        assert detail.json()["orders_total"] == 1
    finally:
        app.dependency_overrides.clear()


def test_admin_user_orders_paginate(session) -> None:
    client = _client(session)
    try:
        headers = _headers(session)
        target = User(
            phone="13500000000",
            email="paging@example.com",
            role="member",
            plan="free",
            email_verified_at=datetime.now(UTC),
        )
        session.add(target)
        session.commit()
        session.refresh(target)
        for index in range(3):
            session.add(
                PaymentOrder(
                    order_no=f"SO-PAGE-{index}",
                    platform="manual",
                    buyer_phone=target.phone,
                    user_id=target.id,
                    product="member-365",
                    amount=99,
                    status="delivered",
                )
            )
        session.commit()

        first = client.get(
            f"/api/v1/admin/users/{target.id}/orders?page=1&page_size=2",
            headers=headers,
        ).json()
        assert first["total"] == 3
        assert len(first["items"]) == 2

        second = client.get(
            f"/api/v1/admin/users/{target.id}/orders?page=2&page_size=2",
            headers=headers,
        ).json()
        assert len(second["items"]) == 1
    finally:
        app.dependency_overrides.clear()

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.db.models import User
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

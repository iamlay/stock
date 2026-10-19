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

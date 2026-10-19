from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import app


def _client(session) -> TestClient:
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def test_phone_login_flow(session) -> None:
    client = _client(session)
    try:
        sent = client.post("/api/v1/auth/sms-code", json={"phone": "13800138000"})
        assert sent.status_code == 200
        code = sent.json()["dev_code"]
        assert code is not None and len(code) == 6

        login = client.post(
            "/api/v1/auth/login",
            json={"phone": "13800138000", "code": code},
        )
        assert login.status_code == 200
        body = login.json()
        assert body["token_type"] == "bearer"
        assert body["user"]["phone"] == "13800138000"

        me = client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {body['access_token']}"},
        )
        assert me.status_code == 200
        assert me.json()["phone"] == "13800138000"
    finally:
        app.dependency_overrides.clear()


def test_wrong_code_is_rejected(session) -> None:
    client = _client(session)
    try:
        sent = client.post("/api/v1/auth/sms-code", json={"phone": "13900139000"})
        code = sent.json()["dev_code"]
        wrong = "000001" if code != "000001" else "000002"
        response = client.post(
            "/api/v1/auth/login",
            json={"phone": "13900139000", "code": wrong},
        )
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_invalid_phone_is_rejected(session) -> None:
    client = _client(session)
    try:
        response = client.post("/api/v1/auth/sms-code", json={"phone": "12345"})
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_me_requires_token(session) -> None:
    client = _client(session)
    try:
        assert client.get("/api/v1/me").status_code == 401
        assert (
            client.get("/api/v1/me", headers={"Authorization": "Bearer broken"}).status_code
            == 401
        )
    finally:
        app.dependency_overrides.clear()

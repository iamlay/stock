from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import app


def _client(session) -> TestClient:
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def test_email_register_and_login(session) -> None:
    client = _client(session)
    try:
        registered = client.post(
            "/api/v1/auth/register",
            json={"email": "User@Example.com", "password": "correct-horse-1"},
        )
        assert registered.status_code == 200
        body = registered.json()
        assert body["email"] == "user@example.com"
        assert body["verification_sent"] is True
        assert body["dev_verification_token"]

        blocked = client.post(
            "/api/v1/auth/login/email",
            json={"email": "user@example.com", "password": "correct-horse-1"},
        )
        assert blocked.status_code == 403

        verified = client.post(
            "/api/v1/auth/verify-email",
            json={"token": body["dev_verification_token"]},
        )
        assert verified.status_code == 200

        login = client.post(
            "/api/v1/auth/login/email",
            json={"email": "user@example.com", "password": "correct-horse-1"},
        )
        assert login.status_code == 200
        login_body = login.json()
        assert login_body["user"]["email"] == "user@example.com"
        assert login_body["user"]["email_verified"] is True

        me = client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {login_body['access_token']}"},
        )
        assert me.status_code == 200
        assert me.json()["email"] == "user@example.com"
    finally:
        app.dependency_overrides.clear()


def test_email_register_rejects_duplicate(session) -> None:
    client = _client(session)
    try:
        payload = {"email": "dup@example.com", "password": "correct-horse-1"}
        assert client.post("/api/v1/auth/register", json=payload).status_code == 200
        assert client.post("/api/v1/auth/register", json=payload).status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_email_login_rejects_wrong_password(session) -> None:
    client = _client(session)
    try:
        client.post(
            "/api/v1/auth/register",
            json={"email": "wrong@example.com", "password": "correct-horse-1"},
        )
        response = client.post(
            "/api/v1/auth/login/email",
            json={"email": "wrong@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_email_register_validates_input(session) -> None:
    client = _client(session)
    try:
        assert (
            client.post(
                "/api/v1/auth/register",
                json={"email": "not-an-email", "password": "correct-horse-1"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/auth/register",
                json={"email": "short@example.com", "password": "short"},
            ).status_code
            == 422
        )
    finally:
        app.dependency_overrides.clear()

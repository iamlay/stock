from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import app


def _client(session) -> TestClient:
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def test_register_sends_verification_and_verifies(session) -> None:
    client = _client(session)
    try:
        registered = client.post(
            "/api/v1/auth/register",
            json={"email": "verify@example.com", "password": "correct-horse-1"},
        )
        assert registered.status_code == 200
        body = registered.json()
        assert body["verification_sent"] is True
        token = body["dev_verification_token"]
        assert token

        verified = client.post("/api/v1/auth/verify-email", json={"token": token})
        assert verified.status_code == 200
        assert verified.json()["verified"] is True

        login = client.post(
            "/api/v1/auth/login/email",
            json={"email": "verify@example.com", "password": "correct-horse-1"},
        )
        assert login.status_code == 200
        me = client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )
        assert me.json()["email_verified"] is True
    finally:
        app.dependency_overrides.clear()


def test_reset_password_invalidates_old_password_and_sessions(session) -> None:
    client = _client(session)
    try:
        registered = client.post(
            "/api/v1/auth/register",
            json={"email": "reset@example.com", "password": "correct-horse-1"},
        ).json()
        client.post(
            "/api/v1/auth/verify-email",
            json={"token": registered["dev_verification_token"]},
        )
        old_access = client.post(
            "/api/v1/auth/login/email",
            json={"email": "reset@example.com", "password": "correct-horse-1"},
        ).json()["access_token"]

        forgot = client.post(
            "/api/v1/auth/forgot-password", json={"email": "reset@example.com"}
        )
        assert forgot.status_code == 200
        reset_token = forgot.json()["dev_reset_token"]
        assert reset_token

        reset = client.post(
            "/api/v1/auth/reset-password",
            json={"token": reset_token, "password": "new-password-2"},
        )
        assert reset.status_code == 200
        assert reset.json()["reset"] is True

        old_login = client.post(
            "/api/v1/auth/login/email",
            json={"email": "reset@example.com", "password": "correct-horse-1"},
        )
        assert old_login.status_code == 401

        new_login = client.post(
            "/api/v1/auth/login/email",
            json={"email": "reset@example.com", "password": "new-password-2"},
        )
        assert new_login.status_code == 200

        stale = client.get(
            "/api/v1/me", headers={"Authorization": f"Bearer {old_access}"}
        )
        assert stale.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_forgot_password_is_generic_for_unknown_email(session) -> None:
    client = _client(session)
    try:
        response = client.post(
            "/api/v1/auth/forgot-password", json={"email": "missing@example.com"}
        )
        assert response.status_code == 200
        assert response.json()["sent"] is True
        assert response.json()["dev_reset_token"] is None
    finally:
        app.dependency_overrides.clear()


def test_resend_ignores_verified_email(session) -> None:
    client = _client(session)
    try:
        registered = client.post(
            "/api/v1/auth/register",
            json={"email": "resend@example.com", "password": "correct-horse-1"},
        ).json()
        client.post(
            "/api/v1/auth/verify-email",
            json={"token": registered["dev_verification_token"]},
        )
        response = client.post(
            "/api/v1/auth/resend-verification",
            json={"email": "resend@example.com"},
        )
        assert response.status_code == 200
        assert response.json()["sent"] is True
        assert response.json()["dev_verification_token"] is None
    finally:
        app.dependency_overrides.clear()

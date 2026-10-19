from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.db.models import RedeemCode, User
from app.db.session import get_session
from app.main import app
from app.security import create_access_token


def _client(session) -> TestClient:
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def _user(session) -> tuple[User, dict[str, str]]:
    user = User(phone="13600136000", plan="free")
    session.add(user)
    session.commit()
    session.refresh(user)
    token = create_access_token(user)
    return user, {"Authorization": f"Bearer {token}"}


def test_redeem_activates_membership(session) -> None:
    client = _client(session)
    try:
        user, headers = _user(session)
        code = RedeemCode(
            code="SLTEST0001",
            plan="member",
            duration_days=365,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        session.add(code)
        session.commit()

        response = client.post("/api/v1/redeem", json={"code": "sltest0001"}, headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["plan"] == "member"
        assert body["duration_days"] == 365

        me = client.get("/api/v1/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["is_member"] is True
        assert me.json()["plan"] == "member"

        session.refresh(user)
        assert user.plan == "member"
        assert user.plan_expires_at is not None

        again = client.post("/api/v1/redeem", json={"code": "SLTEST0001"}, headers=headers)
        assert again.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_expired_code_is_rejected(session) -> None:
    client = _client(session)
    try:
        _, headers = _user(session)
        session.add(
            RedeemCode(
                code="SLEXPIRED1",
                plan="member",
                duration_days=365,
                expires_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
        session.commit()

        response = client.post("/api/v1/redeem", json={"code": "SLEXPIRED1"}, headers=headers)
        assert response.status_code == 400
        assert "过期" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_redeem_requires_login(session) -> None:
    client = _client(session)
    try:
        response = client.post("/api/v1/redeem", json={"code": "SLTEST0001"})
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()

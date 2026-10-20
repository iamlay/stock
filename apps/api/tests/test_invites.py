from fastapi.testclient import TestClient

from app.db.models import InviteCode, User
from app.db.session import get_session
from app.main import app
from app.security import create_access_token
from app.settings import settings


def _client(session) -> TestClient:
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def _admin_headers(session) -> dict[str, str]:
    admin = User(phone="13911112222", role="admin", plan="member")
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return {"Authorization": f"Bearer {create_access_token(admin)}"}


def test_admin_generates_and_revokes_invites(session) -> None:
    client = _client(session)
    try:
        headers = _admin_headers(session)
        created = client.post(
            "/api/v1/admin/invites",
            json={"count": 2, "max_uses": 2, "valid_days": 30, "note": "test"},
            headers=headers,
        )
        assert created.status_code == 200
        body = created.json()
        assert len(body["codes"]) == 2

        listed = client.get("/api/v1/admin/invites", headers=headers).json()
        assert listed["total"] == 2
        assert listed["stats"]["issued"] == 2

        code = body["codes"][0]["code"]
        revoked = client.post(
            f"/api/v1/admin/invites/{code}/revoke", headers=headers
        )
        assert revoked.status_code == 200
        assert revoked.json()["status"] == "revoked"
    finally:
        app.dependency_overrides.clear()


def test_registration_consumes_invite_code(session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "registration_invite_required", True)
    client = _client(session)
    try:
        admin_headers = _admin_headers(session)
        created = client.post(
            "/api/v1/admin/invites",
            json={"count": 1, "max_uses": 1, "valid_days": 30},
            headers=admin_headers,
        ).json()
        code = created["codes"][0]["code"]

        missing = client.post(
            "/api/v1/auth/register",
            json={"email": "invite-a@example.com", "password": "correct-horse-1"},
        )
        assert missing.status_code == 403

        ok = client.post(
            "/api/v1/auth/register",
            json={
                "email": "invite-a@example.com",
                "password": "correct-horse-1",
                "invite_code": code,
            },
        )
        assert ok.status_code == 200

        row = session.get(InviteCode, code)
        assert row is not None
        assert row.used_count == 1
        assert row.status == "redeemed"

        reused = client.post(
            "/api/v1/auth/register",
            json={
                "email": "invite-b@example.com",
                "password": "correct-horse-1",
                "invite_code": code,
            },
        )
        assert reused.status_code == 403
    finally:
        app.dependency_overrides.clear()

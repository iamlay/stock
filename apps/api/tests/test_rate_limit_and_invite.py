import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import app
from app.services.rate_limit import check_rate_limit
from app.settings import settings


def test_rate_limit_blocks_after_limit(session) -> None:
    for _ in range(2):
        check_rate_limit(session, key="test:limit", limit=2, window_seconds=60)
    with pytest.raises(HTTPException) as exc:
        check_rate_limit(session, key="test:limit", limit=2, window_seconds=60)
    assert exc.value.status_code == 429


def test_registration_requires_configured_invite(session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "registration_invite_code", "INVITE-2026")
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    try:
        missing = client.post(
            "/api/v1/auth/register",
            json={"email": "invite-missing@example.com", "password": "correct-horse-1"},
        )
        assert missing.status_code == 403

        wrong = client.post(
            "/api/v1/auth/register",
            json={
                "email": "invite-wrong@example.com",
                "password": "correct-horse-1",
                "invite_code": "WRONG",
            },
        )
        assert wrong.status_code == 403

        ok = client.post(
            "/api/v1/auth/register",
            json={
                "email": "invite-ok@example.com",
                "password": "correct-horse-1",
                "invite_code": "INVITE-2026",
            },
        )
        assert ok.status_code == 200
    finally:
        app.dependency_overrides.clear()

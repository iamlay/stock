from fastapi.testclient import TestClient

from app.db.models import Instrument, User
from app.db.session import get_session
from app.main import app
from app.security import create_access_token


def _client(session) -> TestClient:
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def _headers(session) -> dict[str, str]:
    user = User(phone="13800009999", role="member", plan="free")
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def test_watchlist_add_list_remove(session) -> None:
    client = _client(session)
    try:
        headers = _headers(session)
        session.add(
            Instrument(
                code="510300",
                name="沪深300ETF",
                type="etf",
                exchange="SH",
                lot_size=100,
                is_active=True,
            )
        )
        session.commit()

        unknown = client.post(
            "/api/v1/watchlist", json={"code": "999999"}, headers=headers
        )
        assert unknown.status_code == 404

        added = client.post(
            "/api/v1/watchlist", json={"code": "510300"}, headers=headers
        )
        assert added.status_code == 200
        assert added.json()["saved"] is True

        duplicate = client.post(
            "/api/v1/watchlist", json={"code": "510300"}, headers=headers
        )
        assert duplicate.status_code == 200

        listed = client.get("/api/v1/watchlist", headers=headers)
        assert listed.status_code == 200
        assert isinstance(listed.json(), list)

        removed = client.delete("/api/v1/watchlist/510300", headers=headers)
        assert removed.status_code == 200
        assert removed.json()["removed"] is True
    finally:
        app.dependency_overrides.clear()

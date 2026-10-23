from fastapi.testclient import TestClient

from app.db.models import Instrument, User, WatchlistItem
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


def test_watchlist_free_limit(session) -> None:
    user = User(phone="13800008888", role="member", plan="free")
    session.add(user)
    codes = [f"5100{index:02d}" for index in range(1, 11)]
    for code in codes:
        session.add(
            Instrument(
                code=code,
                name=f"测试ETF{code}",
                type="etf",
                exchange="SH",
                lot_size=100,
                is_active=True,
            )
        )
    session.commit()
    session.refresh(user)
    for code in codes:
        session.add(WatchlistItem(user_id=user.id, code=code))
    session.add(
        Instrument(
            code="510099",
            name="测试ETF510099",
            type="etf",
            exchange="SH",
            lot_size=100,
            is_active=True,
        )
    )
    session.commit()

    client = _client(session)
    headers = {"Authorization": f"Bearer {create_access_token(user)}"}
    try:
        response = client.post(
            "/api/v1/watchlist",
            json={"code": "510099"},
            headers=headers,
        )
        assert response.status_code == 403
        assert "10" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()

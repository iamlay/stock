from datetime import UTC, date, datetime

from fastapi.testclient import TestClient

from app.db.models import (
    Instrument,
    StockMetric,
    StockProfile,
    StockWatchlist,
    User,
    UserNotification,
)
from app.db.session import get_session
from app.main import app
from app.security import create_access_token
from app.services.alerts import run_stock_alerts


def _seed(session) -> User:
    user = User(
        email="alerts@example.com",
        email_verified_at=datetime.now(UTC),
        role="user",
        plan="free",
    )
    session.add(user)
    session.add(
        Instrument(
            code="600519",
            name="贵州茅台",
            type="stock",
            exchange="SH",
            lot_size=100,
            is_active=True,
        )
    )
    session.add(StockProfile(code="600519", industry="食品饮料", status="active"))
    session.add(
        StockMetric(
            code="600519",
            price=100,
            change_pct=6.0,
            market_cap=1000,
            dividend_yield_ttm=3,
        )
    )
    session.commit()
    session.refresh(user)
    session.add(StockWatchlist(user_id=user.id, code="600519"))
    session.commit()
    return user


def test_run_alerts_creates_daily_notification(session) -> None:
    user = _seed(session)
    result = run_stock_alerts(session, as_of=date(2026, 10, 21))
    assert result["notifications"] == 1
    row = session.query(UserNotification).filter_by(user_id=user.id).one()
    assert row.type == "price"
    assert "6.00%" in row.title

    again = run_stock_alerts(session, as_of=date(2026, 10, 21))
    assert again["notifications"] == 0


def test_notification_api_settings_and_read(session) -> None:
    user = _seed(session)
    run_stock_alerts(session, as_of=date(2026, 10, 21))
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {create_access_token(user)}"}
    try:
        listed = client.get("/api/v1/notifications", headers=headers)
        assert listed.status_code == 200
        body = listed.json()
        assert body["unread"] == 1
        notification_id = body["items"][0]["id"]

        settings = client.patch(
            "/api/v1/notifications/settings",
            json={"price_pct": 8, "dividend": False, "email": False},
            headers=headers,
        )
        assert settings.status_code == 200
        assert settings.json()["price_pct"] == 8

        read = client.post(
            f"/api/v1/notifications/{notification_id}/read",
            headers=headers,
        )
        assert read.status_code == 200
        assert client.get("/api/v1/notifications", headers=headers).json()["unread"] == 0
    finally:
        app.dependency_overrides.clear()

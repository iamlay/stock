from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import app

client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "stocklab-api"


def test_market_overview_demo_without_data(session) -> None:
    app.dependency_overrides[get_session] = lambda: session
    try:
        response = client.get("/api/v1/market/overview")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["demo"] is True
    assert body["etf_count"] == 0
    assert body["turnover_billion"] is None


def test_plans_use_ezfpy_checkout() -> None:
    response = client.get("/api/v1/plans")
    assert response.status_code == 200
    plans = response.json()
    assert plans, "plans should not be empty"
    standard = next(plan for plan in plans if plan["id"] == "standard-monthly")
    assert standard["purchasable"] is True
    assert standard["price_cny"] == 9.99
    assert standard["duration_days"] == 30
    assert standard["purchase_channel"] == "ezfpy"
    assert all(plan["id"] != "standard-yearly" for plan in plans)
    assert all(plan["purchase_channel"] != "wechat" for plan in plans)


def test_openapi_is_served() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "/api/v1/market/overview" in schema["paths"]

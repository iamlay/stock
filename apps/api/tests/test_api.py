from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "stocklab-api"


def test_market_overview_is_demo() -> None:
    response = client.get("/api/v1/market/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["demo"] is True
    assert len(body["indices"]) == 3
    assert body["advancing"] > body["declining"]


def test_plans_have_no_in_app_checkout() -> None:
    response = client.get("/api/v1/plans")
    assert response.status_code == 200
    plans = response.json()
    assert plans, "plans should not be empty"
    assert all(plan["purchasable"] is False for plan in plans)
    assert all(plan["purchase_channel"] != "wechat" for plan in plans)


def test_openapi_is_served() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "/api/v1/market/overview" in schema["paths"]

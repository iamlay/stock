from datetime import date

from fastapi.testclient import TestClient

from app.db.models import (
    Instrument,
    StockDividend,
    StockMetric,
    StockProfile,
    User,
)
from app.db.session import get_session
from app.main import app
from app.security import create_access_token


def _stock(
    session,
    code: str,
    name: str,
    industry: str,
    cap: float,
    yield_ttm: float,
    *,
    is_st: bool = False,
) -> None:
    session.add(
        Instrument(
            code=code,
            name=name,
            type="stock",
            exchange="SH" if code.startswith("6") else "SZ",
            lot_size=100,
            is_active=True,
        )
    )
    session.add(
        StockProfile(
            code=code,
            industry=industry,
            industry_path=f"{industry}-测试",
            industry_source="eastmoney",
            market="SH" if code.startswith("6") else "SZ",
            is_st=is_st,
            status="active",
        )
    )
    session.add(
        StockMetric(
            code=code,
            price=10.0,
            change_pct=1.0,
            market_cap=cap,
            pe_ttm=10.0,
            pb=1.0,
            dividend_yield_ttm=yield_ttm,
            dividend_yield_fy=yield_ttm,
            last_ex_date=date(2026, 6, 26),
        )
    )


def _client(session) -> TestClient:
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def _headers(session, role: str = "admin") -> dict[str, str]:
    user = User(phone=f"136{role[:4]:0<8}"[:11], role=role, plan="free")
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def _seed(session) -> None:
    _stock(session, "601398", "工商银行", "金融", 20000, 5.2)
    _stock(session, "600519", "贵州茅台", "食品饮料", 18800, 3.9)
    _stock(session, "000001", "ST平安", "金融", 2000, 7.0, is_st=True)
    session.add(
        StockDividend(
            code="600519",
            ex_date=date(2026, 6, 26),
            fiscal_year=2025,
            cash_per_share=28.02423,
            plan="10派280.2423元",
            is_special=False,
        )
    )
    session.commit()


def test_stock_list_sorts_by_yield_and_excludes_st(session) -> None:
    _seed(session)
    client = _client(session)
    try:
        response = client.get("/api/v1/stocks")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert [item["code"] for item in body["items"]] == ["601398", "600519"]

        with_st = client.get("/api/v1/stocks?include_st=true")
        assert with_st.json()["total"] == 3
        assert with_st.json()["items"][0]["code"] == "000001"
    finally:
        app.dependency_overrides.clear()


def test_stock_filters_and_detail(session) -> None:
    _seed(session)
    client = _client(session)
    try:
        filtered = client.get("/api/v1/stocks?industry=金融&min_yield=4")
        assert filtered.status_code == 200
        assert [item["code"] for item in filtered.json()["items"]] == ["601398"]

        detail = client.get("/api/v1/stocks/600519")
        assert detail.status_code == 200
        body = detail.json()
        assert body["name"] == "贵州茅台"
        assert body["dividend_yield_ttm"] == 3.9
        assert len(body["dividends"]) == 1
    finally:
        app.dependency_overrides.clear()


def test_admin_can_exclude_stock(session) -> None:
    _seed(session)
    client = _client(session)
    try:
        user_headers = _headers(session, role="user")
        denied = client.patch(
            "/api/v1/admin/stocks/601398",
            json={"status": "excluded"},
            headers=user_headers,
        )
        assert denied.status_code == 403

        headers = _headers(session)
        updated = client.patch(
            "/api/v1/admin/stocks/601398",
            json={"status": "excluded"},
            headers=headers,
        )
        assert updated.status_code == 200
        assert updated.json()["status"] == "excluded"

        listed = client.get("/api/v1/stocks")
        assert listed.json()["total"] == 1
    finally:
        app.dependency_overrides.clear()

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.db.models import (
    Instrument,
    MarketDaily,
    StockDividend,
    StockFinancial,
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


def _headers(session, role: str = "admin", plan: str = "free") -> dict[str, str]:
    user = User(phone=f"136{role[:4]:0<8}"[:11], role=role, plan=plan)
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

        search = client.get("/api/v1/stocks/search?q=茅台")
        assert search.status_code == 200
        assert [item["code"] for item in search.json()] == ["600519"]
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


def test_stock_watchlist_roundtrip(session) -> None:
    _seed(session)
    client = _client(session)
    try:
        headers = _headers(session, role="user")
        added = client.post(
            "/api/v1/stock-watchlist",
            json={"code": "600519"},
            headers=headers,
        )
        assert added.status_code == 200
        assert added.json()["saved"] is True

        duplicate = client.post(
            "/api/v1/stock-watchlist",
            json={"code": "600519"},
            headers=headers,
        )
        assert duplicate.json()["saved"] is False

        listed = client.get("/api/v1/stock-watchlist", headers=headers)
        assert listed.status_code == 200
        assert [item["code"] for item in listed.json()] == ["600519"]

        enriched = client.get("/api/v1/stock-watchlist/enriched", headers=headers)
        assert enriched.status_code == 200
        assert enriched.json()[0]["code"] == "600519"
        assert "bollinger_daily" in enriched.json()[0]

        missing = client.post(
            "/api/v1/stock-watchlist",
            json={"code": "ABC"},
            headers=headers,
        )
        assert missing.status_code == 400

        removed = client.delete("/api/v1/stock-watchlist/600519", headers=headers)
        assert removed.json()["removed"] is True
        assert client.get("/api/v1/stock-watchlist", headers=headers).json() == []
    finally:
        app.dependency_overrides.clear()


def test_market_industries_aggregate_equal_weight(session) -> None:
    _seed(session)
    bank = session.get(StockMetric, "601398")
    bank.change_pct = 2
    food = session.get(StockMetric, "600519")
    food.change_pct = -1
    st = session.get(StockMetric, "000001")
    st.change_pct = 5
    session.commit()

    client = _client(session)
    try:
        response = client.get("/api/v1/market/industries")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        by_name = {item["name"]: item for item in body["items"]}
        assert by_name["金融"]["change_pct"] == 2
        assert by_name["食品饮料"]["change_pct"] == -1
        assert by_name["金融"]["count"] == 1

        with_st = client.get("/api/v1/market/industries?include_st=true")
        by_name = {item["name"]: item for item in with_st.json()["items"]}
        assert by_name["金融"]["count"] == 2
        assert by_name["金融"]["change_pct"] == 3.5
    finally:
        app.dependency_overrides.clear()


def test_stock_bollinger_requires_bars(session) -> None:
    _seed(session)
    for index in range(30):
        close = 10 + index * 0.02
        session.add(
            MarketDaily(
                code="600519",
                trade_date=date(2026, 6, 1) + timedelta(days=index),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1000,
                amount=close * 1000,
                source="test",
            )
        )
    session.commit()

    client = _client(session)
    try:
        headers = _headers(session, role="member", plan="member")
        response = client.get("/api/v1/stocks/bollinger", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["code"] == "600519"
        assert body["items"][0]["daily"] is not None
        assert body["items"][0]["daily"]["periods"] == 20
    finally:
        app.dependency_overrides.clear()


def test_stock_grid_member_only(session) -> None:
    _seed(session)
    client = _client(session)
    try:
        free_headers = _headers(session, role="free", plan="free")
        denied = client.get("/api/v1/stocks/grid", headers=free_headers)
        assert denied.status_code == 403

        headers = _headers(session, role="member", plan="member")
        response = client.get("/api/v1/stocks/grid", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        first = body["items"][0]
        assert first["code"] == "601398"
        assert len(first["grid_targets"]) == 5
        assert first["grid_targets"][0]["target_yield"] == 4
        assert first["grid_targets"][0]["target_price"] == 13.0
    finally:
        app.dependency_overrides.clear()


def test_stock_financials_cookie_auth(session) -> None:
    _seed(session)
    user = User(phone="13600007777", role="member", plan="member")
    session.add(user)
    session.commit()
    session.refresh(user)

    client = _client(session)
    try:
        client.cookies.set("stocklab_token", create_access_token(user))
        response = client.get("/api/v1/stocks/financials")
        assert response.status_code == 200
        assert response.json()["total"] == 0

        user.plan = "free"
        session.commit()
        free = client.get("/api/v1/stocks/financials")
        assert free.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_stock_financials_list_and_detail(session) -> None:
    _seed(session)
    session.add_all(
        [
            StockFinancial(
                code="600519",
                report_date=date(2025, 12, 31),
                period="FY",
                revenue=100,
                net_profit=50,
                revenue_yoy=10,
                net_profit_yoy=12,
                disclosure_date=date(2026, 4, 17),
            ),
            StockFinancial(
                code="600519",
                report_date=date(2024, 12, 31),
                period="FY",
                revenue=90,
                net_profit=44,
                revenue_yoy=8,
                net_profit_yoy=9,
                disclosure_date=date(2025, 4, 1),
            ),
            StockFinancial(
                code="600519",
                report_date=date(2026, 3, 31),
                period="Q1",
                revenue=30,
                net_profit=16,
                revenue_yoy=6,
                net_profit_yoy=7,
                roe=15.5,
                operating_cash_flow_per_share=2.5,
                total_assets=200,
                total_liabilities=80,
                debt_asset_ratio=40,
                roa=8.5,
                disclosure_date=date(2026, 4, 25),
            ),
        ]
    )
    session.commit()

    client = _client(session)
    try:
        free_headers = _headers(session, role="free", plan="free")
        denied = client.get("/api/v1/stocks/financials", headers=free_headers)
        assert denied.status_code == 403

        headers = _headers(session, role="member", plan="member")
        response = client.get("/api/v1/stocks/financials", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["code"] == "600519"
        assert item["latest_period"] == "Q1"
        assert item["latest_revenue_yoy"] == 6
        assert item["latest_roe"] == 15.5
        assert item["latest_roa"] == 8.5
        assert item["latest_debt_asset_ratio"] == 40
        assert item["latest_operating_cash_flow_per_share"] == 2.5
        assert len(item["annuals"]) == 2
        assert item["annuals"][0]["year"] == 2025
        assert item["annuals"][0]["net_profit"] == 50

        detail = client.get("/api/v1/stocks/600519", headers=headers)
        assert detail.status_code == 200
        assert len(detail.json()["financials"]) == 3
    finally:
        app.dependency_overrides.clear()

import pytest

from app.services.return_paths import safe_return_path


@pytest.mark.parametrize("path", [
    None, "", "pricing", "https://evil.example", "//evil.example", "/\\evil.example",
    "/%2fevil.example", "/%252fevil.example", "/pricing%5cevil.example",
    "/pricing%0a", "/pricing\n", "/pricing\t", "/pricing%", "/pricing%252f",
    "/api/session", "/login?next=/pricing", "/verify-email?token=x", "/admin/orders",
    "/pricing/../../api/session", "/pricing?" + "x" * 2048,
])
def test_reject_unsafe_return_paths(path):
    assert safe_return_path(path) == "/account"


@pytest.mark.parametrize("path", [
    "/", "/pricing?plan=standard-monthly#checkout", "/stocks/600036?tab=grid#yield",
    "/strategies/dual-ma?code=510300&start=2020-01-01", "/stocks?q=%E9%93%B6%E8%A1%8C",
])
def test_keep_research_inputs(path):
    assert safe_return_path(path) == path


def test_strategy_return_never_replays_a_calculation():
    assert safe_return_path("/strategies/dual-ma?code=510300&run=1&fast=10&run=1#result") == (
        "/strategies/dual-ma?code=510300&fast=10#result"
    )
    assert safe_return_path("/strategies/dual-ma?%72un=1") == "/strategies/dual-ma"

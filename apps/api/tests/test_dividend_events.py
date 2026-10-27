import copy
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from etl.sources.dividend_events import content_fingerprint, normalize_observation
from etl.sources.eastmoney_stock import DividendBatch, fetch_dividends, fetch_dividends_bulk
from etl.stocks import sync_stock_dividends, sync_stock_dividends_bulk
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.models import (
    AdminAuditLog,
    DividendEvent,
    DividendEventVersion,
    DividendSourceObservation,
    Instrument,
    StockDividend,
    StockMetric,
    StockProfile,
    User,
)
from app.db.session import get_session
from app.main import app
from app.security import create_access_token
from app.services.dividend_events import (
    ReviewConflict,
    backfill_legacy,
    record_source_pages,
    review_observation,
)


def raw_row(**updates):
    return {
        "SECURITY_CODE": "600036",
        "REPORT_DATE": "2025-12-31",
        "PLAN_NOTICE_DATE": "2026-03-28",
        "NOTICE_DATE": "2026-07-04",
        "EQUITY_RECORD_DATE": "2026-07-09",
        "EX_DIVIDEND_DATE": "2026-07-10",
        "PRETAX_BONUS_RMB": "10.03",
        "ASSIGN_PROGRESS": "实施分配",
        "IMPL_PLAN_PROFILE": "10派10.03元(含税)",
    } | updates


def source_pages(*rows):
    return [
        {
            "rows": list(rows),
            "url": "https://data.eastmoney.com/source",
            "observed_at": "2026-10-27T00:00:00+00:00",
        }
    ]


def seed(session, code="600036"):
    session.add(Instrument(code=code, name="test", type="stock", exchange="SH"))
    session.flush()
    session.add_all([StockProfile(code=code), StockMetric(code=code, price=10)])
    session.commit()


def admin(session):
    user = User(email="reviewer@example.com", role="admin", email_verified_at=datetime.now(UTC))
    session.add(user)
    session.commit()
    return user


def observe(session, raw=None):
    record_source_pages(session, source_pages(raw or raw_row()), ["600036"])
    session.commit()
    normalized = normalize_observation(raw or raw_row())
    return session.scalar(
        select(DividendSourceObservation).where(
            DividendSourceObservation.fingerprint == content_fingerprint(normalized)
        )
    )


def decision(**updates):
    return {
        "action": "create",
        "expected_revision": 0,
        "event_id": None,
        "patch": {},
        "allow_older_evidence": False,
        "note": "Manually reconciled with announcement evidence",
    } | updates


def test_lossless_capture_retains_unknown_zero_cancelled_and_raw_evidence(session):
    seed(session)
    rows = [
        raw_row(),
        raw_row(PRETAX_BONUS_RMB=None, ASSIGN_PROGRESS="预披露"),
        raw_row(PRETAX_BONUS_RMB=0, ASSIGN_PROGRESS="取消分配"),
    ]
    original = copy.deepcopy(rows)
    assert record_source_pages(session, source_pages(*rows), ["600036"]) == 3
    session.commit()
    stored = session.scalars(select(DividendSourceObservation)).all()
    assert len(stored) == 3
    assert {row.normalized["stage"] for row in stored} == {"implemented", "unknown", "cancelled"}
    assert all(row.state == "pending" and row.event_id is None for row in stored)
    assert session.scalar(select(func.count()).select_from(DividendEvent)) == 0
    assert rows == original


def test_semantic_repeat_ignores_volatile_fields_and_numeric_format(session):
    seed(session)
    first = raw_row(PRETAX_BONUS_RMB="10.0300", EX_DIVIDEND_DAYS=1)
    second = raw_row(PRETAX_BONUS_RMB=10.03, EX_DIVIDEND_DAYS=20, DIVIDENT_RATIO=0.1)
    assert record_source_pages(session, source_pages(first, second), ["600036"]) == 1
    session.commit()
    assert record_source_pages(session, source_pages(second), ["600036"]) == 0


@pytest.mark.parametrize("amount", [None, "NaN", "Infinity", "-1", True, "0.000000001"])
def test_invalid_amount_stays_unknown(amount):
    data = normalize_observation(raw_row(PRETAX_BONUS_RMB=amount))
    assert data["cash_per_share"] is None
    assert "unknown_cash_amount" in data["review_reasons"]


@pytest.mark.parametrize(
    ("progress", "stage"),
    [
        ("实施分配", "implemented"),
        ("董事会预案", "proposed"),
        ("股东大会通过", "approved"),
        ("取消分配", "cancelled"),
        ("终止分配", "cancelled"),
        ("不分配", "no_distribution"),
        ("预披露", "unknown"),
        ("实施分配后已取消", "unknown"),
    ],
)
def test_exact_stage_mapping_and_no_inferred_payment(progress, stage):
    data = normalize_observation(raw_row(ASSIGN_PROGRESS=progress))
    assert data["stage"] == stage
    assert data["payment_date"] is None
    assert data["source_event_id"] is None
    assert data["announcement_url"] is None


def test_backfill_is_bounded_idempotent_and_never_merges_same_report(session):
    seed(session)
    for when in [date(2026, 1, 10), date(2026, 7, 10)]:
        session.add(
            StockDividend(
                code="600036",
                ex_date=when,
                report_date=date(2025, 12, 31),
                fiscal_year=2025,
                cash_per_share=Decimal("1.003"),
                plan="same plan",
                progress="实施分配",
            )
        )
    session.commit()
    assert backfill_legacy(session)["candidates"] == 2
    assert session.scalar(select(func.count()).select_from(DividendEvent)) == 0
    first = backfill_legacy(session, limit=1, apply=True)
    second = backfill_legacy(session, after_id=first["last_id"], apply=True)
    session.commit()
    ids = session.scalars(select(DividendEvent.id)).all()
    assert len(ids) == 2
    assert first["created"] == second["created"] == 1
    assert backfill_legacy(session, apply=True)["created"] == 0
    assert session.scalar(select(func.count()).select_from(DividendEventVersion)) == 2
    versions = session.scalars(select(DividendEventVersion)).all()
    assert all(v.record_date is None and v.payment_date is None for v in versions)
    assert all(v.evidence_status == "legacy_unverified" for v in versions)
    assert {v.cash_per_share for v in versions} == {Decimal("1.00300000")}
    assert session.scalar(select(func.count()).select_from(StockDividend)) == 2


def test_explicit_create_revise_replay_and_no_silent_overwrite(session):
    seed(session)
    user = admin(session)
    observation = observe(session)
    create = decision(
        patch={
            "payment_date": "2026-07-10",
            "announcement_url": "https://example.com/announcement.pdf",
        }
    )
    row, original = review_observation(
        session, observation.id, reviewer_id=user.id, decision=create
    )
    session.commit()
    event_id = row.event_id
    assert original.record_date == date(2026, 7, 9)
    assert original.payment_date == date(2026, 7, 10)
    assert original.revision == 1
    assert row.raw_payload.get("payment_date") is None
    replay, version = review_observation(
        session, observation.id, reviewer_id=user.id, decision=create
    )
    assert replay.event_id == event_id and version.revision == 1
    session.commit()
    changed = observe(session, raw_row(PRETAX_BONUS_RMB="12", NOTICE_DATE="2026-07-05"))
    assert session.get(DividendEvent, event_id).current_revision == 1
    update = decision(action="revise", event_id=event_id, expected_revision=1)
    _, updated = review_observation(session, changed.id, reviewer_id=user.id, decision=update)
    session.commit()
    assert updated.revision == 2 and updated.cash_per_share == Decimal("1.2")
    assert session.get(DividendEventVersion, (event_id, 1)).cash_per_share == Decimal("1.003")
    assert (
        updated.payment_date is None
    )  # Does not carry a possibly invalidated manual date forward.
    with pytest.raises(ReviewConflict):
        review_observation(
            session, changed.id, reviewer_id=user.id, decision=decision(action="ignore")
        )
    session.rollback()


def test_same_report_two_rounds_stay_separate_after_explicit_review(session):
    seed(session)
    user = admin(session)
    first = observe(session)
    second = observe(
        session,
        raw_row(
            EQUITY_RECORD_DATE="2026-12-09", EX_DIVIDEND_DATE="2026-12-10", NOTICE_DATE="2026-12-01"
        ),
    )
    for row in [first, second]:
        review_observation(session, row.id, reviewer_id=user.id, decision=decision())
        session.commit()
    assert session.scalar(select(func.count()).select_from(DividendEvent)) == 2


def test_revision_and_stock_mismatch_are_rejected(session):
    seed(session)
    user = admin(session)
    row = observe(session)
    _, version = review_observation(session, row.id, reviewer_id=user.id, decision=decision())
    session.commit()
    next_row = observe(session, raw_row(PRETAX_BONUS_RMB="11"))
    with pytest.raises(ReviewConflict):
        review_observation(
            session,
            next_row.id,
            reviewer_id=user.id,
            decision=decision(action="revise", event_id=version.event_id, expected_revision=0),
        )
    session.rollback()
    seed(session, "600519")
    other = DividendEvent(id="other-stock-event", code="600519", origin="test", current_revision=1)
    session.add(other)
    session.commit()
    with pytest.raises(ValueError, match="same stock"):
        review_observation(
            session,
            next_row.id,
            reviewer_id=user.id,
            decision=decision(action="revise", event_id=other.id, expected_revision=1),
        )
    session.rollback()


def test_older_evidence_requires_explicit_override_and_appends_history(session):
    seed(session)
    user = admin(session)
    current = observe(session)
    _, version = review_observation(session, current.id, reviewer_id=user.id, decision=decision())
    session.commit()
    older = observe(session, raw_row(NOTICE_DATE="2026-06-01", PRETAX_BONUS_RMB="9"))
    review = decision(action="revise", event_id=version.event_id, expected_revision=1)
    with pytest.raises(ReviewConflict, match="older"):
        review_observation(session, older.id, reviewer_id=user.id, decision=review)
    session.rollback()
    _, revised = review_observation(
        session, older.id, reviewer_id=user.id, decision=review | {"allow_older_evidence": True}
    )
    session.commit()
    assert revised.revision == 2


@pytest.mark.parametrize(
    "patch",
    [
        {"payment_date": "2026-07-10"},
        {"announcement_url": "javascript:alert(1)"},
        {"announcement_url": "https://user:password@example.com/file.pdf"},
        {"cash_per_share": "NaN"},
        {"cash_per_share": "-1"},
        {"record_date": "2026-07-11"},
        {"code": "600519"},
        {"stage": "paid"},
    ],
)
def test_review_rejects_unsupported_or_unsubstantiated_changes(session, patch):
    seed(session)
    user = admin(session)
    row = observe(session)
    with pytest.raises(ValueError):
        review_observation(session, row.id, reviewer_id=user.id, decision=decision(patch=patch))
    session.rollback()
    assert session.scalar(select(func.count()).select_from(DividendEvent)) == 0


def test_ignored_observation_is_idempotent_and_creates_no_event(session):
    seed(session)
    user = admin(session)
    row = observe(session)
    ignore = decision(action="ignore")
    review_observation(session, row.id, reviewer_id=user.id, decision=ignore)
    session.commit()
    reviewed, version = review_observation(session, row.id, reviewer_id=user.id, decision=ignore)
    assert reviewed.state == "ignored" and version is None
    assert session.scalar(select(func.count()).select_from(DividendEvent)) == 0


@pytest.mark.parametrize("bulk", [False, True])
def test_source_fetch_captures_unfiltered_pages_without_changing_legacy_list(monkeypatch, bulk):
    payload = {
        "success": True,
        "result": {
            "pages": 1,
            "data": [
                raw_row(),
                raw_row(PRETAX_BONUS_RMB=None, ASSIGN_PROGRESS="预披露"),
                raw_row(PRETAX_BONUS_RMB=0, ASSIGN_PROGRESS="取消分配"),
            ],
        },
    }
    monkeypatch.setattr("etl.sources.eastmoney_stock._get_json", lambda *_: payload)
    batch = fetch_dividends_bulk() if bulk else fetch_dividends("600036")
    assert isinstance(batch, list) and isinstance(batch, DividendBatch)
    assert len(batch) == 1  # Existing yield parser semantics retained.
    assert len(batch.source_pages[0]["rows"]) == 3


@pytest.mark.parametrize("bulk", [False, True])
def test_both_etl_paths_write_observations_and_preserve_research_contract(
    session, monkeypatch, bulk
):
    seed(session)
    payload = {
        "result": {
            "pages": 1,
            "data": [
                raw_row(),
                raw_row(PRETAX_BONUS_RMB=0, ASSIGN_PROGRESS="取消分配", IMPL_PLAN_PROFILE="取消"),
            ],
        }
    }
    batch = DividendBatch()
    batch.capture(payload, "https://data.eastmoney.com/source")
    monkeypatch.setattr("etl.stocks.fetch_dividends", lambda _: batch)
    monkeypatch.setattr("etl.stocks.fetch_dividends_bulk", lambda **_: batch)
    run = (
        (lambda: sync_stock_dividends_bulk(session, codes=["600036"]))
        if bulk
        else (lambda: sync_stock_dividends(session, ["600036"], delay=0))
    )
    first = run()
    assert first["written"] == 1 and first["observations_written"] == 2
    assert run()["observations_written"] == 0
    assert session.scalar(select(func.count()).select_from(StockDividend)) == 1
    assert session.scalar(select(func.count()).select_from(DividendEvent)) == 0


def test_real_saved_v248_rows_are_losslessly_ingested_offline(session):
    path = Path(__file__).parents[3] / "docs/evidence/v2-48/live-2026-10-27/snapshot.json"
    snapshot = json.loads(path.read_text())
    codes = []
    for item in snapshot["requests"]:
        seed(session, item["code"])
        codes.append(item["code"])
    pages = [
        {
            "url": item["url"],
            "observed_at": item["observed_at"],
            "rows": item["payload"]["result"]["data"],
        }
        for item in snapshot["requests"]
    ]
    assert record_source_pages(session, pages, codes) == 40
    session.commit()
    assert record_source_pages(session, pages, codes) == 0
    assert session.scalar(select(func.count()).select_from(DividendEvent)) == 0


def test_api_permissions_review_history_and_old_detail(session):
    seed(session)
    user = admin(session)
    row = observe(session)
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {create_access_token(user)}"}
    try:
        assert client.get("/api/v1/admin/stocks/dividend-observations").status_code == 401
        user.role = "user"
        session.commit()
        assert (
            client.get("/api/v1/admin/stocks/dividend-observations", headers=headers).status_code
            == 403
        )
        user.role = "admin"
        session.commit()
        queue = client.get("/api/v1/admin/stocks/dividend-observations", headers=headers)
        assert queue.status_code == 200 and queue.json()["total"] == 1
        assert "no-store" in queue.headers["cache-control"]
        reviewed = client.post(
            f"/api/v1/admin/stocks/dividend-observations/{row.id}/review",
            headers=headers,
            json=decision(),
        )
        assert reviewed.status_code == 200, reviewed.text
        event_id = reviewed.json()["version"]["event_id"]
        public = client.get("/api/v1/stocks/600036/dividend-events")
        assert public.status_code == 200 and public.json()["total"] == 1
        version = public.json()["items"][0]
        assert version["payment_date"] is None
        assert version["automatic_entitlement_allowed"] is False
        assert "raw_payload" not in version and "reviewed_by" not in version
        history = client.get(f"/api/v1/stocks/600036/dividend-events/{event_id}/versions")
        assert history.status_code == 200 and history.json()["total"] == 1
        assert (
            client.get(f"/api/v1/stocks/600519/dividend-events/{event_id}/versions").status_code
            == 404
        )
        assert client.get("/api/v1/stocks/600036").status_code == 200
        assert session.scalar(select(func.count()).select_from(AdminAuditLog)) == 1
        assert (
            client.post(
                f"/api/v1/admin/stocks/dividend-observations/{row.id}/review",
                headers=headers,
                json=decision(),
            ).status_code
            == 200
        )
        assert session.scalar(select(func.count()).select_from(AdminAuditLog)) == 1
        assert client.get("/api/v1/stocks/600036/dividend-events?page_size=101").status_code == 422
        assert (
            client.post(
                f"/api/v1/admin/stocks/dividend-observations/{row.id}/review",
                headers=headers,
                json=decision(unexpected="bad"),
            ).status_code
            == 422
        )
        profile = session.get(StockProfile, "600036")
        profile.status = "excluded"
        session.commit()
        assert client.get("/api/v1/stocks/600036/dividend-events").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_source_failure_is_not_treated_as_an_empty_success(monkeypatch):
    monkeypatch.setattr(
        "etl.sources.eastmoney_stock._get_json", lambda *_: {"success": False, "result": None}
    )
    with pytest.raises(ValueError, match="unsuccessful"):
        fetch_dividends("600036")


def test_bulk_keeps_undated_approved_observation_without_crashing_legacy_metrics(
    session, monkeypatch
):
    seed(session)
    batch = DividendBatch()
    batch.capture(
        {
            "result": {
                "data": [
                    raw_row(
                        EX_DIVIDEND_DATE=None,
                        EQUITY_RECORD_DATE=None,
                        ASSIGN_PROGRESS="股东大会通过",
                    )
                ]
            }
        },
        "https://data.eastmoney.com/source",
    )
    monkeypatch.setattr("etl.stocks.fetch_dividends_bulk", lambda **_: batch)
    result = sync_stock_dividends_bulk(session, codes=["600036"])
    assert result["observations_written"] == 1
    assert session.get(StockMetric, "600036").last_ex_date is None


def test_single_stock_savepoint_rolls_back_capture_if_legacy_write_fails(session, monkeypatch):
    from etl.sources.eastmoney_stock import DividendRecord

    seed(session)
    batch = DividendBatch()
    batch.capture({"result": {"data": [raw_row()]}}, "https://data.eastmoney.com/source")
    batch.clear()
    batch.append(DividendRecord("600036", "test", date(2026, 7, 10), None, 1, "invalid", False))
    monkeypatch.setattr("etl.stocks.fetch_dividends", lambda _: batch)
    result = sync_stock_dividends(session, ["600036"], delay=0)
    assert result["errors"] and result["written"] == result["observations_written"] == 0
    assert session.scalar(select(func.count()).select_from(DividendSourceObservation)) == 0
    assert session.scalar(select(func.count()).select_from(StockDividend)) == 0

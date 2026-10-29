"""V2-48 audit regression: evidence gaps must never become automatic accounting."""

import copy
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from etl.dividend_probe import (
    build_report,
    collect_snapshot,
    inspect_record,
    main,
)


def source_row(**updates):
    row = {
        "SECURITY_CODE": "600036",
        "REPORT_DATE": "2025-12-31 00:00:00",
        "NOTICE_DATE": "2026-07-04 00:00:00",
        "PLAN_NOTICE_DATE": "2026-03-28 00:00:00",
        "EQUITY_RECORD_DATE": "2026-07-09 00:00:00",
        "EX_DIVIDEND_DATE": "2026-07-10 00:00:00",
        "PRETAX_BONUS_RMB": "10.03",
        "ASSIGN_PROGRESS": "实施分配",
        "IMPL_PLAN_PROFILE": "10派10.03元(含税)",
        "BONUS_RATIO": 0,
        "IT_RATIO": 0,
    }
    return row | updates


def snapshot(rows, **request_updates):
    request = {
        "code": "600036",
        "url": "https://example.invalid/public-source",
        "observed_at": "2026-10-27T00:00:00+00:00",
        "payload": {"success": True, "result": {"data": rows}},
    } | request_updates
    return {
        "kind": "live_source_observation",
        "created_at": request["observed_at"],
        "requests": [request],
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("10.03", "1.003"),
        ("5", "0.5"),
        (0, "0"),
        ("0.000001", "0.0000001"),
    ],
)
def test_per_ten_decimal_conversion(raw, expected):
    row = inspect_record(source_row(PRETAX_BONUS_RMB=raw))
    assert Decimal(row["cash_per_share"]) == Decimal(expected)
    assert row["automatic_entitlement_allowed"] is False


@pytest.mark.parametrize("bad", [None, "--", "", "NaN", "Infinity", "-Infinity", -1, True])
def test_invalid_amount_is_not_zero_or_eligible(bad):
    row = inspect_record(source_row(PRETAX_BONUS_RMB=bad))
    assert row["cash_per_share"] is None
    assert "invalid_cash_per_ten" in row["issues"]
    assert row["automatic_entitlement_allowed"] is False


@pytest.mark.parametrize(
    ("field", "issue"),
    [
        ("REPORT_DATE", "missing_or_invalid_report_date"),
        ("NOTICE_DATE", "missing_or_invalid_notice_date"),
        ("PLAN_NOTICE_DATE", "missing_or_invalid_plan_notice_date"),
        ("EQUITY_RECORD_DATE", "missing_or_invalid_record_date"),
        ("EX_DIVIDEND_DATE", "missing_or_invalid_ex_date"),
    ],
)
def test_unknown_dates_remain_unknown(field, issue):
    row = inspect_record(source_row(**{field: "2026-02-30"}))
    assert issue in row["issues"]
    assert row["automatic_entitlement_allowed"] is False


@pytest.mark.parametrize(
    ("progress", "expected"),
    [
        ("董事会预案", "proposed"),
        ("股东大会通过", "approved"),
        ("实施分配", "implemented"),
        ("取消分配", "cancelled"),
        ("终止分配", "cancelled"),
        ("不分配", "no_distribution"),
        ("实施分配已取消", "unknown"),
        ("", "unknown"),
        ("未来新状态", "unknown"),
    ],
)
def test_stage_mapping_is_explicit_and_never_enables_accounting(progress, expected):
    row = inspect_record(source_row(ASSIGN_PROGRESS=progress))
    assert row["stage_candidate"] == expected
    assert ("unmapped_stage" in row["issues"]) == (expected == "unknown")
    assert row["automatic_entitlement_allowed"] is False


@pytest.mark.parametrize("value", [None, "--", -1, "1", "NaN"])
def test_corporate_actions_are_not_assumed_absent(value):
    row = inspect_record(source_row(BONUS_RATIO=value))
    assert "corporate_action_unverified" in row["issues"]


def test_date_order_identity_and_payment_are_not_inferred():
    row = inspect_record(source_row(EQUITY_RECORD_DATE="2026-07-11"))
    assert "invalid_record_ex_order" in row["issues"]
    assert row["payment_date"] is None
    assert row["source_event_id"] is None
    assert row["announcement_url"] is None
    assert "event_identity_unverified" in row["issues"]


def test_revisions_and_second_payment_are_retained_without_guessing_identity():
    rows = [
        source_row(),
        source_row(PRETAX_BONUS_RMB="11"),
        source_row(EX_DIVIDEND_DATE="2026-12-01", IMPL_PLAN_PROFILE="10派5元"),
    ]
    original = copy.deepcopy(rows)
    report = build_report(snapshot(rows))
    assert report["observed_rows"] == report["distinct_raw_rows"] == 3
    assert report["multiple_rows_in_same_stock_year"] == [
        {"code": "600036", "year": "2025", "rows": 3},
    ]
    assert rows == original
    assert report["automatic_entitlement_allowed"] is False
    assert report["automatic_receipt_allowed"] is False


def test_30_duplicate_rows_do_not_satisfy_sample_size():
    report = build_report(snapshot([source_row()] * 30))
    assert report["duplicate_raw_rows"] == 29
    assert report["at_least_30_distinct_raw_rows"] is False


def test_failed_request_does_not_count_as_verified_source():
    report = build_report(snapshot([], error="TimeoutError: sample"))
    assert report["observed_rows"] == 0
    assert report["source_failures"][0]["code"] == "600036"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {"success": False},
        {"success": True, "result": {"data": "broken"}},
        {"success": True, "result": {"data": [None]}},
    ],
)
def test_malformed_saved_response_is_rejected(payload):
    with pytest.raises(ValueError):
        build_report(snapshot([], payload=payload))


def test_cross_stock_response_is_rejected():
    with pytest.raises(ValueError, match="stock codes differ"):
        build_report(snapshot([source_row(SECURITY_CODE="600519")]))


def test_collection_captures_network_failure_without_database():
    with patch("etl.dividend_probe.urllib.request.urlopen", side_effect=TimeoutError("test")):
        result = collect_snapshot(["600036"])
    assert "TimeoutError" in result["requests"][0]["error"]
    assert "payload" not in result["requests"][0]


@pytest.mark.parametrize("codes", [["600036", "600036"], [], ['600036")'], ["123"]])
def test_collection_rejects_ambiguous_or_invalid_requests(codes):
    with pytest.raises(ValueError):
        collect_snapshot(codes)


def test_saved_live_evidence_is_reproducible_and_remains_blocked(tmp_path):
    root = Path(__file__).resolve().parents[3]
    evidence = root / "docs/evidence/v2-48/live-2026-10-27"
    saved = json.loads((evidence / "snapshot.json").read_text(encoding="utf-8"))
    expected = json.loads((evidence / "report.json").read_text(encoding="utf-8"))
    assert build_report(saved) == expected
    assert expected["at_least_30_distinct_raw_rows"] is True
    assert expected["assessment"] == "blocked_for_automatic_accounting"
    with patch("etl.dividend_probe.urllib.request.urlopen", side_effect=AssertionError("offline")):
        assert main(["--snapshot", str(evidence / "snapshot.json"), "--output", str(tmp_path)]) == 0
    assert json.loads((tmp_path / "report.json").read_text(encoding="utf-8")) == expected


def test_insufficient_evidence_cli_returns_failure(tmp_path):
    source = tmp_path / "input.json"
    source.write_text(json.dumps(snapshot([source_row()])))
    assert main(["--snapshot", str(source), "--output", str(tmp_path / "out")]) == 1

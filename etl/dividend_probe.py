"""Read-only V2-48 dividend source audit. Never connects to the application database.

Live observations are not announcement verification, licensing approval or an SLA.
The report deliberately never enables automatic personal dividend accounting.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from etl.sources.eastmoney_stock import DIVIDEND_API, USER_AGENT

SCHEMA_VERSION = "v2-48.1"
DATE_FIELDS = {
    "report_date": "REPORT_DATE",
    "notice_date": "NOTICE_DATE",
    "plan_notice_date": "PLAN_NOTICE_DATE",
    "record_date": "EQUITY_RECORD_DATE",
    "ex_date": "EX_DIVIDEND_DATE",
}
# This endpoint has no verified payment-date, event-ID or announcement-URL mapping.
STAGES = {
    "董事会预案": "proposed",
    "股东大会通过": "approved",
    "实施分配": "implemented",
    "不分配": "no_distribution",
    "取消分配": "cancelled",
    "终止分配": "cancelled",
}


def _date(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        return None


def _decimal(value: object) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def inspect_record(raw: dict) -> dict:
    """Inspect a raw row without inferring unknown fields or production identities."""
    issues: list[str] = []
    code = str(raw.get("SECURITY_CODE") or "")
    if not re.fullmatch(r"\d{6}", code):
        issues.append("invalid_security_code")
    dates = {name: _date(raw.get(field)) for name, field in DATE_FIELDS.items()}
    for name, parsed in dates.items():
        if parsed is None:
            issues.append(f"missing_or_invalid_{name}")
    per_ten = _decimal(raw.get("PRETAX_BONUS_RMB"))
    cash = per_ten / Decimal(10) if per_ten is not None and per_ten >= 0 else None
    if cash is None:
        issues.append("invalid_cash_per_ten")
    progress = str(raw.get("ASSIGN_PROGRESS") or "")
    stage = STAGES.get(progress, "unknown")
    if stage == "unknown":
        issues.append("unmapped_stage")
    plan = str(raw.get("IMPL_PLAN_PROFILE") or "")
    if not plan:
        issues.append("missing_plan")
    # Unknown/negative corporate-action fields are unsafe, too; zero is known no-action.
    action_values = [_decimal(raw.get(key)) for key in ("BONUS_RATIO", "IT_RATIO")]
    if any(value is None or value != 0 for value in action_values):
        issues.append("corporate_action_unverified")
    if (
        dates["record_date"]
        and dates["ex_date"]
        and dates["record_date"] >= dates["ex_date"]
    ):
        issues.append("invalid_record_ex_order")
    issues.extend(
        [
            "payment_date_unverified",
            "event_identity_unverified",
            "announcement_link_unverified",
        ]
    )
    return {
        "code": code,
        **dates,
        "cash_per_share": str(cash) if cash is not None else None,
        "source_progress": progress,
        "stage_candidate": stage,
        "plan": plan,
        "special_candidate": "特别" in plan,
        "payment_date": None,
        "source_event_id": None,
        "announcement_url": None,
        "raw_sha256": hashlib.sha256(
            json.dumps(raw, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest(),
        "issues": issues,
        "automatic_entitlement_allowed": False,
    }


def collect_snapshot(
    codes: list[str], *, page_size: int = 10, timeout: int = 15
) -> dict:
    """Bounded one-page queries per code; persist failures instead of faking coverage."""
    if not codes or len(codes) > 20 or len(set(codes)) != len(codes):
        raise ValueError("provide 1–20 unique stock codes")
    if not all(re.fullmatch(r"\d{6}", code) for code in codes):
        raise ValueError("stock codes must contain six digits")
    if not 1 <= page_size <= 100 or not 1 <= timeout <= 30:
        raise ValueError("page_size must be 1–100 and timeout 1–30 seconds")
    requests = []
    for code in codes:
        params = {
            "reportName": "RPT_SHAREBONUS_DET",
            "columns": "ALL",
            "filter": f'(SECURITY_CODE="{code}")',
            "pageNumber": 1,
            "pageSize": page_size,
            "sortTypes": -1,
            "sortColumns": "NOTICE_DATE",
        }
        url = f"{DIVIDEND_API}?{urllib.parse.urlencode(params)}"
        item = {
            "code": code,
            "url": url,
            "params": params,
            "observed_at": datetime.now(UTC).isoformat(),
        }
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Referer": "https://data.eastmoney.com/",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read(5_000_001)
                if len(body) > 5_000_000:
                    raise ValueError("response exceeds 5 MB")
                payload = json.loads(body)
            result = payload.get("result") if isinstance(payload, dict) else None
            if not isinstance(result, dict) or payload.get("success") is not True:
                raise ValueError("source did not return a successful result")
            if not isinstance(result.get("data"), list):
                raise TypeError("source result.data is not a list")
            if not all(isinstance(row, dict) for row in result["data"]):
                raise ValueError("source contains a non-object row")
            if any(str(row.get("SECURITY_CODE")) != code for row in result["data"]):
                raise ValueError("source returned another stock's rows")
            item["payload"] = payload
        except Exception as exc:  # noqa: BLE001 - retain probe failure, no database writes
            item["error"] = f"{type(exc).__name__}: {exc}"[:300]
        requests.append(item)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "live_source_observation",
        "created_at": datetime.now(UTC).isoformat(),
        "requests": requests,
    }


def build_report(snapshot: dict) -> dict:
    if snapshot.get("kind") != "live_source_observation":
        raise ValueError("expected a live_source_observation snapshot")
    rows = []
    failures = []
    fields: Counter = Counter()
    stages: Counter = Counter()
    source_counts: Counter = Counter()
    dates = []
    for request in snapshot.get("requests", []):
        if request.get("error"):
            failures.append({"code": request.get("code"), "error": request["error"]})
            continue
        payload = request.get("payload")
        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict) or payload.get("success") is not True:
            raise ValueError("snapshot contains a failed or malformed source response")
        data = result.get("data")
        if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
            raise ValueError("snapshot result.data must contain objects")
        for raw in data:
            if str(raw.get("SECURITY_CODE")) != request.get("code"):
                raise ValueError("snapshot request and row stock codes differ")
            row = inspect_record(raw)
            row["source_url"] = request["url"]
            row["observed_at"] = request["observed_at"]
            rows.append(row)
            source_counts[row["code"]] += 1
            stages[row["source_progress"]] += 1
            fields.update(key for key, value in raw.items() if value is not None)
            if row["report_date"]:
                dates.append(row["report_date"])
    counts = Counter(issue for row in rows for issue in row["issues"])
    stock_year: Counter = Counter(
        (row["code"], row["report_date"][:4]) for row in rows if row["report_date"]
    )
    hashes = Counter(row["raw_sha256"] for row in rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "snapshot_created_at": snapshot.get("created_at"),
        "assessment": "blocked_for_automatic_accounting",
        "automatic_entitlement_allowed": False,
        "automatic_receipt_allowed": False,
        "observed_rows": len(rows),
        "distinct_raw_rows": len(hashes),
        "duplicate_raw_rows": sum(count - 1 for count in hashes.values()),
        "at_least_30_distinct_raw_rows": len(hashes) >= 30,
        "counts_by_code": dict(source_counts),
        "source_progress_values": dict(stages),
        "non_null_field_counts": dict(sorted(fields.items())),
        "issue_counts": dict(counts),
        "observed_report_date_range": [min(dates), max(dates)] if dates else None,
        "multiple_rows_in_same_stock_year": [
            {"code": code, "year": year, "rows": count}
            for (code, year), count in sorted(stock_year.items())
            if count > 1
        ],
        "source_failures": failures,
        "unverified": [
            "announcement_by_announcement_reconciliation",
            "payment_date_mapping",
            "stable_event_identity",
            "historical_revision_and_cancellation_coverage",
            "source_update_latency_and_history_completeness",
            "commercial_data_permission",
            "target_user_interviews",
        ],
        "records": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true")
    mode.add_argument(
        "--snapshot", type=Path, help="replay a saved raw source snapshot"
    )
    parser.add_argument(
        "--codes", nargs="+", default=["600036", "600519", "601088", "600028"]
    )
    parser.add_argument("--page-size", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    snapshot = (
        collect_snapshot(args.codes, page_size=args.page_size, timeout=args.timeout)
        if args.live
        else json.loads(args.snapshot.read_text())
    )
    report = build_report(snapshot)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, content in [("snapshot.json", snapshot), ("report.json", report)]:
        (args.output / name).write_text(
            json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "assessment",
                    "observed_rows",
                    "distinct_raw_rows",
                    "counts_by_code",
                    "source_failures",
                )
            },
            ensure_ascii=False,
        )
    )
    # A successful probe is NOT product acceptance. Source failure or inadequate sample is nonzero.
    return (
        1
        if report["source_failures"] or not report["at_least_30_distinct_raw_rows"]
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())

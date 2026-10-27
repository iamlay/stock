"""Conservative, lossless event observations; separate from legacy yield parsing."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation

STAGES = {
    "董事会预案": "proposed",
    "股东大会通过": "approved",
    "实施分配": "implemented",
    "不分配": "no_distribution",
    "取消分配": "cancelled",
    "终止分配": "cancelled",
}
DATE_FIELDS = {
    "report_date": "REPORT_DATE",
    "notice_date": "NOTICE_DATE",
    "plan_notice_date": "PLAN_NOTICE_DATE",
    "record_date": "EQUITY_RECORD_DATE",
    "ex_date": "EX_DIVIDEND_DATE",
}
RULE_VERSION = "v2-49.1"


def parse_date(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        return None


def normalize_observation(raw: dict) -> dict:
    code = str(raw.get("SECURITY_CODE") or "")
    if not re.fullmatch(r"\d{6}", code):
        raise ValueError("invalid dividend stock code")
    issues = []
    dates = {key: parse_date(raw.get(field)) for key, field in DATE_FIELDS.items()}
    for key, value in dates.items():
        if value is None:
            issues.append(f"unknown_{key}")
    cash = None
    try:
        value = raw.get("PRETAX_BONUS_RMB")
        amount = Decimal(str(value))
        if not isinstance(value, bool) and amount.is_finite() and 0 <= amount < Decimal("1e12"):
            converted = amount / 10
            if converted == converted.quantize(Decimal("0.00000001")):
                cash = format(converted.normalize(), "f")
    except (InvalidOperation, ValueError):
        pass
    if cash is None:
        issues.append("unknown_cash_amount")
    progress = str(raw.get("ASSIGN_PROGRESS") or "")
    stage = STAGES.get(progress, "unknown")
    if stage == "unknown":
        issues.append("unknown_stage")
    issues.extend(["identity_unverified", "payment_date_unverified", "corporate_action_unverified"])
    if dates["record_date"] and dates["ex_date"] and dates["record_date"] >= dates["ex_date"]:
        issues.append("invalid_record_ex_order")
    return {
        "code": code,
        **dates,
        "cash_per_share": cash,
        "plan": str(raw.get("IMPL_PLAN_PROFILE") or ""),
        "progress": progress,
        "stage": stage,
        "payment_date": None,
        "announcement_url": None,
        "source_event_id": None,
        "review_reasons": issues,
        "rule_version": RULE_VERSION,
    }


def content_fingerprint(data: dict) -> str:
    # Ignore market prices, distance-in-days, acquisition time and other volatile raw fields.
    core = {
        key: value for key, value in data.items() if key not in {"review_reasons", "rule_version"}
    }
    return hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

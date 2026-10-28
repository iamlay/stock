"""Historical reference from existing stock data, never a receivable or coverage attestation.

Reviewed event revisions override linked legacy snapshots; otherwise the live legacy
stock-dividend table (also used by stock detail) is authoritative over stale backfills.
"""

from __future__ import annotations

import calendar
import re
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext

from etl.sources.dividend_events import STAGES
from sqlalchemy import select

from app.db.models import DividendEvent, DividendEventVersion, Instrument, StockDividend

REASONS = {
    "not_set": "未设置分红参考",
    "no_records": "所选期间暂无可用分红记录",
    "missing_date": "分红记录缺少除息日期",
    "missing_amount": "分红记录缺少有效金额",
    "unknown_stage": "分红实施状态待核对",
    "conflicting_records": "分红记录存在冲突，待核对",
    "corporate_action": "存在送转记录，每股口径待核对",
    "short_history": "上市时间未覆盖所选期间",
    "only_special": "期间仅有特别或一次性分红，未纳入普通分红参考",
    "historical_reference": "按已收录普通现金分红计算",
    "user_estimate": "自定义年度分红参考",
}


def decimal_text(value):
    return (
        None
        if value is None
        else format(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP), ".6f")
    )


def year_before(day, years):
    year = day.year - years
    return day.replace(year=year, day=min(day.day, calendar.monthrange(year, day.month)[1]))


def _legacy(row):
    return dict(
        event_id=f"legacy:{row.id}",
        revision=0,
        report_date=row.report_date,
        notice_date=row.notice_date,
        ex_date=row.ex_date,
        cash_per_share=Decimal(row.cash_per_share),
        stage=STAGES.get(row.progress, "historical" if not row.progress else "unknown"),
        evidence_status="legacy_reference",
        source=row.source,
        source_url=None,
        plan=row.plan,
        special=row.is_special or row.is_one_off or "特别" in row.plan or "一次性" in row.plan,
        reviewed=False,
    )


def _version(event, version, legacy):
    return dict(
        event_id=event.id,
        revision=version.revision,
        report_date=version.report_date,
        notice_date=version.notice_date,
        ex_date=version.ex_date,
        cash_per_share=Decimal(version.cash_per_share)
        if version.cash_per_share is not None
        else None,
        stage=version.stage,
        evidence_status=version.evidence_status,
        source=version.source,
        source_url=version.announcement_url or version.source_url,
        plan=version.plan,
        special=bool(legacy and (legacy.is_special or legacy.is_one_off))
        or "特别" in version.plan
        or "一次性" in version.plan,
        reviewed=version.evidence_status == "reviewed",
    )


def _records(session, code):
    legacy = {
        r.id: r for r in session.scalars(select(StockDividend).where(StockDividend.code == code))
    }
    candidates = []
    suppressed = set()
    reviewed = []
    versions = session.execute(
        select(DividendEvent, DividendEventVersion)
        .join(
            DividendEventVersion,
            (DividendEvent.id == DividendEventVersion.event_id)
            & (DividendEvent.current_revision == DividendEventVersion.revision),
        )
        .where(DividendEvent.code == code)
    ).all()
    for event, version in versions:
        linked = legacy.get(event.legacy_dividend_id)
        # Unreviewed backfills are frozen copies; do not override newer ETL values.
        if linked and version.evidence_status != "reviewed":
            continue
        if linked:
            suppressed.add(linked.id)
        item = _version(event, version, linked)
        candidates.append(item)
        if item["reviewed"]:
            reviewed.append(item)
    for identifier, row in legacy.items():
        if identifier in suppressed:
            continue
        item = _legacy(row)
        # Match unlinked reviewed events conservatively by report + ex-date (not year).
        # A cancellation without an ex-date may match only the identical report and plan.
        matched = any(
            r["report_date"] is not None
            and r["report_date"] == row.report_date
            and (r["ex_date"] == row.ex_date or (r["ex_date"] is None and r["plan"] == row.plan))
            for r in reviewed
        )
        if not matched:
            candidates.append(item)
    return candidates


def reference(session, code, preferences, quantity, *, as_of):
    with localcontext() as ctx:
        ctx.prec = 50
        return _reference(session, code, preferences, quantity, as_of=as_of)


def _reference(session, code, preferences, quantity, *, as_of):
    window = preferences.get("forecast", "skip")
    years = int(window) // 12 if window in {"12", "36", "60"} else 1
    start = year_before(as_of, years)
    candidates = _records(session, code)
    rows, problems = [], set()
    for item in candidates:
        ex = item["ex_date"]
        # Unknown dates far outside the window should not disable every later window.
        anchors = [d for d in (item["notice_date"], item["report_date"]) if d]
        if ex and not start < ex <= as_of:
            continue
        if ex is None and anchors and max(anchors) < year_before(start, 1):
            continue
        if ex is None and anchors and min(anchors) > as_of:
            continue
        item.update(included=False, exclusion_reason=None)
        stage = item["stage"]
        if stage in {"proposed", "approved", "cancelled", "no_distribution"}:
            item["exclusion_reason"] = "预案/未实施/取消或不分配，不纳入已实施现金分红"
        elif not ex:
            problems.add("missing_date")
            item["exclusion_reason"] = REASONS["missing_date"]
        elif stage not in {"implemented", "historical"}:
            problems.add("unknown_stage")
            item["exclusion_reason"] = REASONS["unknown_stage"]
        elif (
            item["cash_per_share"] is None
            or not item["cash_per_share"].is_finite()
            or item["cash_per_share"] < 0
        ):
            problems.add("missing_amount")
            item["exclusion_reason"] = REASONS["missing_amount"]
        else:
            # Detect positive share distributions even when cash is zero or special.
            ratios = re.findall(r"(?:送|转增|转)(?:股)?\s*(\d+(?:\.\d+)?)", item["plan"])
            if any(Decimal(r) > 0 for r in ratios):
                problems.add("corporate_action")
                item["exclusion_reason"] = REASONS["corporate_action"]
            elif item["special"]:
                item["exclusion_reason"] = "特别或一次性分红，单列不计入普通分红参考"
            else:
                item["included"] = True
        rows.append(item)
    # ETL can retain multiple plan strings for the same date/report after a revision.
    # Equal amounts are duplicates; conflicting amounts are not silently summed/chosen.
    groups = defaultdict(list)
    for item in rows:
        if item["included"]:
            groups[(item["report_date"], item["ex_date"])].append(item)
    for group in groups.values():
        if len(group) < 2:
            continue
        reviewed_count = sum(r["reviewed"] for r in group)
        if len({r["cash_per_share"] for r in group}) > 1 or reviewed_count > 1:
            problems.add("conflicting_records")
            for item in group:
                item.update(included=False, exclusion_reason=REASONS["conflicting_records"])
        else:
            group.sort(key=lambda r: (not r["reviewed"], r["event_id"]))
            for item in group[1:]:
                item.update(
                    included=False, exclusion_reason="同报告期同除息日相同金额，重复记录不计入"
                )
    stock = session.get(Instrument, code)
    if stock and stock.listed_on and stock.listed_on > start:
        problems.add("short_history")
    included = [r for r in rows if r["included"]]
    total = sum((r["cash_per_share"] for r in included), Decimal(0))
    yearly = []
    for n in range(years):
        left, right = year_before(as_of, n + 1), year_before(as_of, n)
        period = [r for r in included if left < r["ex_date"] <= right]
        yearly.append(
            dict(
                from_date=left,
                to_date=right,
                count=len(period),
                recorded_cash=decimal_text(sum((r["cash_per_share"] for r in period), Decimal(0)))
                if period
                else None,
            )
        )
    value = None
    if window == "custom" and preferences.get("custom") is not None:
        reason = "user_estimate"
        value = Decimal(preferences["custom"])
        status = "user_estimate"
    elif window == "skip":
        reason = status = "not_set"
    elif problems:
        reason = next(
            p
            for p in (
                "conflicting_records",
                "corporate_action",
                "missing_date",
                "missing_amount",
                "unknown_stage",
                "short_history",
            )
            if p in problems
        )
        status = "insufficient"
    elif total > 0:
        reason = status = "historical_reference"
        value = total / years  # Fixed 1/3/5 denominator, never divide by dividend-bearing years.
    else:
        reason = "only_special" if any(r["special"] for r in rows) else "no_records"
        status = "insufficient"
    note = REASONS[reason]
    if status == "historical_reference":
        note += (
            f"；窗口内每股合计 {decimal_text(total)} 元 ÷ {years} 年。"
            "仅为已收录记录参考，未证明全量覆盖，不代表未来派息或个人已收。"
        )
        if any(not y["count"] for y in yearly):
            note += " 部分年度区间未收录记录，不等于已确认零分红。"
    elif status == "user_estimate":
        note += "（税前），不是已确认应收或到账。"
    elif status != "not_set":
        note += "；不会当作0，可补齐数据或设置自定义参考。"
    rows.sort(key=lambda r: (r["ex_date"] or date.min, r["event_id"]), reverse=True)
    details = [
        {
            k: decimal_text(v) if isinstance(v, Decimal) else v
            for k, v in r.items()
            if k not in {"reviewed", "special"}
        }
        for r in rows
    ]
    return dict(
        window=window,
        as_of=as_of,
        from_date=start,
        to_date=as_of,
        status=status,
        reason=reason,
        reason_label=REASONS[reason],
        issues=sorted(problems),
        annual_per_share=decimal_text(value),
        annual_amount=decimal_text(quantity * value) if value is not None else None,
        recorded_total=decimal_text(total),
        divisor_years=years,
        periods=yearly,
        note=note,
        details=details,
        coverage_verified=False,
    )

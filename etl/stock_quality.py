from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from app.db.models import (
    DataJob,
    DataQualityCheck,
    Instrument,
    StockDividend,
    StockMetric,
    StockProfile,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class Issue:
    level: str
    check: str
    code: str
    name: str
    value: float | int | str | None
    detail: str


def _issue(
    level: str,
    check: str,
    code: str,
    name: str,
    value: float | str | None,
    detail: str,
) -> Issue:
    return Issue(level=level, check=check, code=code, name=name, value=value, detail=detail)


def run_stock_quality(
    session: Session,
    *,
    as_of: date | None = None,
    limit: int | None = None,
) -> dict:
    today = as_of or date.today()
    rows = session.execute(
        select(Instrument, StockProfile, StockMetric)
        .join(StockProfile, StockProfile.code == Instrument.code)
        .join(StockMetric, StockMetric.code == Instrument.code)
        .where(Instrument.type == "stock")
        .order_by(StockMetric.dividend_yield_ttm.desc().nulls_last())
    ).all()
    if limit is not None:
        rows = rows[:limit]

    issues: list[Issue] = []
    top_yields: list[dict] = []
    st_count = 0
    for instrument, profile, metric in rows:
        if profile.is_st:
            st_count += 1
        price = float(metric.price) if metric.price is not None else None
        ttm = float(metric.dividend_yield_ttm) if metric.dividend_yield_ttm is not None else None
        fy = float(metric.dividend_yield_fy) if metric.dividend_yield_fy is not None else None
        if ttm is not None:
            top_yields.append(
                {
                    "code": instrument.code,
                    "name": instrument.name,
                    "yield_ttm": ttm,
                    "yield_fy": fy,
                    "price": price,
                }
            )
        if price is None or price <= 0:
            issues.append(
                _issue("fail", "price_missing", instrument.code, instrument.name, price, "价格缺失")
            )
        if ttm is not None and ttm > 30:
            issues.append(
                _issue("fail", "yield_extreme", instrument.code, instrument.name, ttm, "TTM 股息率 > 30%")
            )
        elif ttm is not None and ttm > 15:
            issues.append(
                _issue("warn", "yield_high", instrument.code, instrument.name, ttm, "TTM 股息率 > 15%")
            )
        if ttm is not None and fy is not None and abs(ttm - fy) > 5:
            issues.append(
                _issue(
                    "warn",
                    "ttm_fy_divergence",
                    instrument.code,
                    instrument.name,
                    round(ttm - fy, 2),
                    f"TTM {ttm:.2f}% / 年度 {fy:.2f}%",
                )
            )
        if not profile.industry:
            issues.append(
                _issue("warn", "industry_missing", instrument.code, instrument.name, None, "行业为空")
            )
        updated = metric.updated_at
        if updated is not None:
            updated_date = updated.date() if hasattr(updated, "date") else updated
            if (today - updated_date).days > 3:
                issues.append(
                    _issue(
                        "warn",
                        "stale_metrics",
                        instrument.code,
                        instrument.name,
                        updated_date.isoformat(),
                        "指标超过 3 天未更新",
                    )
                )

    future = (
        session.scalar(
            select(func.count())
            .select_from(StockDividend)
            .where(StockDividend.ex_date > today)
        )
        or 0
    )
    if future:
        issues.append(
            _issue("warn", "future_dividends", "-", "-", future, "存在未来除息日记录")
        )

    duplicates = session.execute(
        select(
            StockDividend.code,
            StockDividend.ex_date,
            StockDividend.plan,
            func.count(),
        )
        .group_by(StockDividend.code, StockDividend.ex_date, StockDividend.plan)
        .having(func.count() > 1)
        .limit(20)
    ).all()
    for code, ex_date, plan, count in duplicates:
        issues.append(
            _issue("fail", "duplicate_dividends", code, code, count, f"{ex_date} {plan}")
        )

    order = {"fail": 0, "warn": 1, "pass": 2}
    issues.sort(key=lambda item: (order.get(item.level, 3), item.check, item.code))
    checks: dict[str, dict] = {}
    for issue in issues:
        entry = checks.setdefault(
            issue.check,
            {"status": "pass", "count": 0, "samples": []},
        )
        entry["count"] += 1
        entry["status"] = (
            "fail" if issue.level == "fail" or entry["status"] == "fail" else "warn"
        )
        if len(entry["samples"]) < 20:
            entry["samples"].append(asdict(issue))

    summary = {
        "metrics": len(rows),
        "st": st_count,
        "issues": len(issues),
        "fail": sum(1 for item in issues if item.level == "fail"),
        "warn": sum(1 for item in issues if item.level == "warn"),
        "checks": checks,
        "top_yields": top_yields[:20],
    }
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "as_of": today.isoformat(),
        "summary": summary,
        "issues": [asdict(item) for item in issues],
    }


def write_quality_checks(session: Session, report: dict) -> None:
    job = DataJob(
        job_name="stock_quality",
        status="success",
        params={"as_of": report["as_of"]},
        rows_written=report["summary"]["metrics"],
        finished_at=datetime.now(UTC),
    )
    session.add(job)
    session.flush()
    for name, check in report["summary"]["checks"].items():
        session.add(
            DataQualityCheck(
                job_id=job.id,
                check_name=name,
                status=check["status"],
                detail={"count": check["count"], "samples": check["samples"]},
            )
        )
    session.commit()


def write_report(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

"""Deterministic private ledger replay. No inferred pre-opening holdings or dividends."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal, localcontext
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    DividendEntitlement,
    DividendReceipt,
    Instrument,
    PortfolioEntry,
    PortfolioPrivacyAcceptance,
    PortfolioReviewRange,
)
from app.services import portfolio as accounts

RULE_VERSION = "moving-average-cny-v1"
UNIT = Decimal("0.000001")
ZERO = Decimal(0)
FIELDS = (
    "id",
    "code",
    "kind",
    "event_date",
    "day_order",
    "quantity",
    "price",
    "fees",
    "total_cost",
    "history_status",
    "source",
    "note",
    "evidence",
    "reverses_id",
    "account_version",
    "created_at",
    "request_id",
)


def fail(code, message):
    raise accounts.PortfolioError(code, message, 422)


def decimal_input(value) -> Decimal:
    # JSON strings only: no binary float loss, exponent, NaN, implicit bool or silent rounding.
    if not isinstance(value, str) or not re.fullmatch(
        r"(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?", value
    ):
        fail("invalid_decimal", "数量和金额请填写非负十进制数，最多12位整数、6位小数")
    return Decimal(value)


def text_input(value: str) -> str:
    import unicodedata

    value = value.strip()
    if len(value) > 500 or any(unicodedata.category(c).startswith("C") for c in value):
        fail("invalid_note", "备注和依据最多500个字符，不能含控制字符")
    return value


def current_consent(session: Session, account) -> bool:
    ack = session.get(PortfolioPrivacyAcceptance, account.privacy_acceptance_id)
    return bool(
        ack
        and ack.user_id == account.user_id
        and ack.policy_version == accounts.POLICY["version"]
        and ack.policy_sha256 == accounts.POLICY_SHA256
    )


def accept_ledger(session, user_id, account_id, expected_version, consent):
    accounts.lock_owner(session, user_id)
    account = accounts.own_account(session, user_id, account_id, lock=True)
    if account.version != expected_version:
        raise accounts.PortfolioError("account_changed", "账本已变化，请刷新后重试")
    ack = accounts._acceptance(session, user_id, consent)
    if account.privacy_acceptance_id != ack.id:
        account.privacy_acceptance_id = ack.id
        account.version += 1
        account.updated_at = datetime.now(UTC)
        accounts._audit(session, account, "ledger_consent")
        session.flush()
    return accounts.account_out(account)


def entries_for(session, user_id, account_id):
    return list(
        session.scalars(
            select(PortfolioEntry)
            .where(PortfolioEntry.user_id == user_id, PortfolioEntry.account_id == account_id)
            .order_by(
                PortfolioEntry.event_date,
                PortfolioEntry.day_order,
                PortfolioEntry.created_at,
                PortfolioEntry.id,
            )
        )
    )


def entry_out(row, cancelled):
    result = {key: getattr(row, key) for key in FIELDS}
    for key in ("quantity", "price", "fees", "total_cost"):
        result[key] = format(Decimal(result[key]), ".6f")
    stamp = row.created_at
    result["created_at"] = stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)
    result["details"] = getattr(row, "details", None)
    result["active"] = row.id not in cancelled and row.kind != "reversal"
    return result


def replay(rows) -> list[dict]:
    if any(getattr(r, "details", None) for r in rows):
        from app.services.portfolio_positions import project

        return project(rows)
    cancelled = {row.reverses_id for row in rows if row.reverses_id}
    active = sorted(
        (r for r in rows if r.id not in cancelled and r.kind != "reversal"),
        key=lambda r: (r.event_date, r.day_order, r.id),
    )
    positions = {}
    orders = set()
    with localcontext() as ctx:
        ctx.prec = 50
        for row in active:
            key = (row.code, row.event_date, row.day_order)
            if key in orders:
                fail("duplicate_order", "同一股票同一天的有效流水顺序不能重复，请调整同日顺序")
            orders.add(key)
            state = positions.setdefault(
                row.code,
                dict(
                    code=row.code,
                    quantity=ZERO,
                    total_cost=ZERO,
                    realized_pnl=ZERO,
                    fees=ZERO,
                    known_since=row.event_date,
                    history_status=row.history_status,
                    has_adjustment=False,
                    count=0,
                ),
            )
            q, price, fees, cost = (
                Decimal(getattr(row, key)) for key in ("quantity", "price", "fees", "total_cost")
            )
            if row.kind == "opening":
                if state["count"]:
                    fail(
                        "opening_not_first",
                        "期初持仓必须是该股票第一笔有效流水；补录更早历史需先更正期初",
                    )
                state["quantity"], state["total_cost"] = q, cost
            elif row.kind == "adjustment":
                state["quantity"], state["total_cost"] = q, cost
                state["has_adjustment"] = True
                state["history_status"] = "incomplete"
            elif row.kind == "buy":
                state["quantity"] += q
                state["total_cost"] += (q * price + fees).quantize(UNIT, rounding=ROUND_HALF_UP)
            elif row.kind in {"bonus", "reinvest"}:
                state["quantity"] += q
            elif row.kind == "sell":
                if q > state["quantity"]:
                    fail("historical_oversell", "重算后存在超额卖出，请检查该笔及后续所有历史流水")
                removed = (
                    state["total_cost"]
                    if q == state["quantity"]
                    else (state["total_cost"] * q / state["quantity"]).quantize(
                        UNIT, rounding=ROUND_HALF_UP
                    )
                )
                state["realized_pnl"] += (q * price - fees - removed).quantize(
                    UNIT, rounding=ROUND_HALF_UP
                )
                state["total_cost"] -= removed
                state["quantity"] -= q
            state["fees"] += fees
            if row.history_status == "incomplete":
                state["history_status"] = "incomplete"
            state["count"] += 1
        output = []
        for state in positions.values():
            state["average_cost"] = (
                (state["total_cost"] / state["quantity"]).quantize(UNIT, rounding=ROUND_HALF_UP)
                if state["quantity"]
                else None
            )
            state["unrealized_pnl"] = None  # No invented market price or quote timestamp.
            state["dividends_received"] = None
            state["history_before_known_since"] = "unknown"
            state.pop("count")
            output.append(
                {k: format(v, ".6f") if isinstance(v, Decimal) else v for k, v in state.items()}
            )
        return sorted(output, key=lambda p: p["code"])


def ledger_snapshot(session, user_id, account_id):
    accounts.lock_owner(session, user_id)
    account = accounts.own_account(session, user_id, account_id)
    rows = entries_for(session, user_id, account_id)
    cancelled = {r.reverses_id for r in rows if r.reverses_id}
    reviews = session.scalars(
        select(PortfolioReviewRange)
        .where(
            PortfolioReviewRange.user_id == user_id, PortfolioReviewRange.account_id == account_id
        )
        .order_by(PortfolioReviewRange.account_version)
    ).all()
    return dict(
        account_version=account.version,
        consent_required=not current_consent(session, account),
        rule_version="positions-cny-v3" if any(r.details for r in rows) else RULE_VERSION,
        entries=[entry_out(r, cancelled) for r in rows],
        positions=replay(rows),
        review_ranges=[
            dict(
                code=r.code,
                from_date=r.from_date,
                account_version=r.account_version,
                reason=r.reason,
                status="pending_dividend_review",
            )
            for r in reviews
        ],
        automatic_dividends=False,
    )


def add_entry(session, user_id, account_id, payload):
    accounts.lock_owner(session, user_id)
    account = accounts.own_account(session, user_id, account_id, lock=True)
    request_id = str(UUID(payload["request_id"]))
    digest = hashlib.sha256(
        json.dumps(
            {k: v for k, v in payload.items() if k != "expected_version"},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    rows = entries_for(session, user_id, account_id)
    prior = next((r for r in rows if r.request_id == request_id), None)
    if prior:
        if prior.request_hash != digest:
            raise accounts.PortfolioError("request_reused", "请求编号已用于其他内容，请刷新后重试")
        return ledger_snapshot(session, user_id, account_id)
    if account.version != payload["expected_version"]:
        raise accounts.PortfolioError("account_changed", "账本已变化，请刷新后重试")
    if account.is_archived:
        raise accounts.PortfolioError("account_archived", "请先恢复账本再录入或冲正流水")
    if not current_consent(session, account):
        raise accounts.PortfolioError("privacy_ack_required", "请先确认持仓与交易数据说明", 403)
    if any(r.details for r in rows):
        fail("new_entry_required", "账本已启用新版持仓，请使用新版预览和保存入口")
    kind = payload["kind"]
    code = payload["code"]
    instrument = session.get(Instrument, code)
    if (
        not instrument
        or instrument.type != "stock"
        or instrument.exchange.upper() not in {"SH", "SZ", "BJ", "SSE", "SZSE", "BSE"}
    ):
        fail("unsupported_stock", "请选择系统中已有的A股股票代码，暂不支持ETF及其他市场")
    day = date.fromisoformat(payload["event_date"])
    if day > datetime.now(ZoneInfo("Asia/Shanghai")).date():
        fail("future_trade", "不能录入未来日期的成交或持仓")
    if instrument.listed_on and day < instrument.listed_on:
        fail("before_listing", "生效日期不能早于该股票上市日期")
    q, price, fees, cost = (
        decimal_input(payload[k]) for k in ("quantity", "price", "fees", "total_cost")
    )
    note, evidence = text_input(payload["note"]), text_input(payload["evidence"])
    target_id = payload["reverses_id"]
    target = next((r for r in rows if r.id == target_id), None) if target_id else None
    if target_id:
        cancelled = {r.reverses_id for r in rows if r.reverses_id}
        if not target or target.kind == "reversal" or target.id in cancelled or target.code != code:
            fail("invalid_reversal", "只能冲正本账本同一股票尚未被冲正的有效流水")
        if not note:
            fail("reason_required", "更正或冲正需填写原因")
    if kind == "reversal":
        if (
            not target
            or any((q, price, fees, cost))
            or day != target.event_date
            or payload["day_order"] != target.day_order
        ):
            fail("invalid_reversal", "冲正必须关联原流水，沿用原生效日及顺序，数量和金额为零")
    elif kind in {"opening", "adjustment"}:
        if price or fees or (not q and cost) or (kind == "opening" and not q):
            fail("invalid_balance", "期初/调整填写数量和总成本；零持仓成本必须为零，价格及费用留零")
        if kind == "adjustment" and (not note or not evidence):
            fail("reason_required", "持仓调整必须填写原因及核对依据")
    elif not q or not price or cost:
        fail("invalid_trade", "买卖数量及成交价必须大于零；总成本由系统计算，请留零")
    now = datetime.now(UTC)
    row = PortfolioEntry(
        id=str(uuid4()),
        account_id=account_id,
        user_id=user_id,
        request_id=request_id,
        request_hash=digest,
        code=code,
        kind=kind,
        event_date=day,
        day_order=payload["day_order"],
        quantity=q,
        price=price,
        fees=fees,
        total_cost=cost,
        history_status=payload["history_status"],
        source="manual",
        note=note,
        evidence=evidence,
        reverses_id=target_id,
        account_version=account.version + 1,
        created_at=now,
    )
    replay([*rows, row])  # Validate ALL subsequent time points before persisting anything.
    account.version += 1
    account.updated_at = now
    session.add(row)
    session.add(
        PortfolioReviewRange(
            id=str(uuid4()),
            user_id=user_id,
            account_id=account_id,
            code=code,
            from_date=min(day, target.event_date) if target else day,
            account_version=account.version,
            reason="ledger_changed",
            created_at=now,
        )
    )
    accounts._audit(session, account, "ledger_entry")
    session.flush()
    return ledger_snapshot(session, user_id, account_id)


def clear_ledger(session, user_id, account_id):
    # Explicit cleanup also works in SQLite test environments without FK enforcement.
    for model in (PortfolioReviewRange, PortfolioEntry):
        session.execute(
            delete(model).where(model.user_id == user_id, model.account_id == account_id)
        )


def delete_holding(
    session, user_id, account_id, code, *, expected_version
) -> dict:
    if not re.fullmatch(r"\d{6}", code):
        fail("invalid_code", "股票代码格式不正确")
    accounts.lock_owner(session, user_id)
    account = accounts.own_account(session, user_id, account_id, lock=True)
    if account.version != expected_version:
        raise accounts.PortfolioError("account_changed", "账本已变化，请刷新后重试")
    if account.is_archived:
        raise accounts.PortfolioError("account_archived", "账本已归档，请先恢复")
    entry_count = session.scalar(
        select(PortfolioEntry.id)
        .where(
            PortfolioEntry.user_id == user_id,
            PortfolioEntry.account_id == account_id,
            PortfolioEntry.code == code,
        )
        .limit(1)
    )
    if entry_count is None:
        raise accounts.PortfolioError("position_missing", "该股票没有持仓记录", 404)

    receipt_count = session.execute(
        delete(DividendReceipt).where(
            DividendReceipt.user_id == user_id,
            DividendReceipt.account_id == account_id,
            DividendReceipt.code == code,
        )
    ).rowcount
    entitlement_count = session.execute(
        delete(DividendEntitlement).where(
            DividendEntitlement.user_id == user_id,
            DividendEntitlement.account_id == account_id,
            DividendEntitlement.code == code,
        )
    ).rowcount
    session.execute(
        delete(PortfolioReviewRange).where(
            PortfolioReviewRange.user_id == user_id,
            PortfolioReviewRange.account_id == account_id,
            PortfolioReviewRange.code == code,
        )
    )
    deleted_entries = session.execute(
        delete(PortfolioEntry).where(
            PortfolioEntry.user_id == user_id,
            PortfolioEntry.account_id == account_id,
            PortfolioEntry.code == code,
        )
    ).rowcount
    account.version += 1
    account.updated_at = datetime.now(UTC)
    accounts._audit(session, account, "holding_delete")
    session.flush()
    return {
        "deleted": True,
        "code": code,
        "entries": deleted_entries,
        "receipts": receipt_count,
        "entitlements": entitlement_count,
    }

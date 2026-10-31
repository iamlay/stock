"""V2-51R: explicit baselines, independent costs, server previews and private preferences.

Facts remain append-only in the existing owner-scoped ledger. New signed balances live
in versioned details, NEVER in legacy total_cost. No inferred dividend receipts.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext
from uuid import uuid4
from zoneinfo import ZoneInfo

import jwt
from sqlalchemy import func, or_, select

from app.db.models import (
    Instrument,
    PortfolioEntry,
    PortfolioReviewRange,
    StockMetric,
    StockRealtimeQuote,
)
from app.services import portfolio as accounts
from app.services.portfolio_ledger import (
    UNIT,
    ZERO,
    current_consent,
    decimal_input,
    entries_for,
    entry_out,
    fail,
    text_input,
)
from app.settings import settings

RULE = "positions-cny-v3"
BASES = ("weighted", "net", "dividend")
DEFAULT_PREFS = dict(basis="weighted", group="", forecast="skip", custom=None)


def today():
    return datetime.now(ZoneInfo("Asia/Shanghai")).date()


def money(value):
    return value.quantize(UNIT, rounding=ROUND_HALF_UP)


def string(value):
    return None if value is None else format(money(value), ".6f")


def digest(data):
    return hashlib.sha256(
        json.dumps(
            data, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
        ).encode()
    ).hexdigest()


def active_rows(rows):
    cancelled = {r.reverses_id for r in rows if r.reverses_id}
    return sorted(
        (r for r in rows if r.id not in cancelled and r.kind != "reversal"),
        key=lambda r: (r.event_date, r.day_order, r.id),
    )


def project(rows):
    """Pure deterministic replay; unknown values propagate, clear/rebuy starts a cycle."""
    states, orders = {}, set()
    with localcontext() as ctx:
        ctx.prec = 50
        for r in active_rows(rows):
            if r.kind == "preference":
                continue
            key = (r.code, r.event_date, r.day_order)
            if key in orders:
                fail("duplicate_order", "同股同日顺序重复，请调整当天先后顺序")
            orders.add(key)
            s = states.get(r.code)
            meta = getattr(r, "details", None) or {}
            if s is None:
                s = states[r.code] = dict(
                    code=r.code,
                    quantity=ZERO,
                    weighted=ZERO,
                    net=ZERO,
                    dividend=None,
                    realized_pnl=ZERO,
                    fees=ZERO,
                    estimated=False,
                    known_since=r.event_date,
                    history_status=r.history_status,
                    has_adjustment=False,
                    count=0,
                    snapshot_date=None,
                    cycle_id=r.id,
                    closed_cycles=[],
                    reference=None,
                )
            if s["snapshot_date"] and r.event_date <= s["snapshot_date"]:
                fail("snapshot_day_overlap", "日终快照已含当日交易，请更正快照；新流水须晚于截至日")
            q, price, fees, cost = (
                Decimal(getattr(r, k)) for k in ("quantity", "price", "fees", "total_cost")
            )
            if r.kind in {"snapshot", "opening", "rebase"}:
                if s["count"] and r.kind != "rebase":
                    fail(
                        "opening_not_first",
                        "已有持仓记录，请记录买入或更正原持仓；不能重复添加快照",
                    )
                if r.kind == "rebase":
                    if not s["count"]:
                        fail("position_missing", "修正当前持仓必须有原持仓记录")
                    s["closed_cycles"].append(
                        dict(
                            cycle_id=s["cycle_id"] + ":" + r.id,
                            net=string(s["net"]),
                            dividend=string(s["dividend"]),
                            realized_pnl=string(s["realized_pnl"]),
                            reason="baseline_reset",
                        )
                    )
                    s.update(
                        known_since=r.event_date,
                        realized_pnl=ZERO,
                        fees=ZERO,
                        estimated=False,
                        has_adjustment=True,
                        reference=None,
                    )
                s["quantity"] = q
                s["net"] = s["dividend"] = None
                s["weighted"] = cost if r.kind == "opening" else None
                if r.kind in {"snapshot", "rebase"}:
                    basis = meta["basis"]
                    if basis in BASES:
                        s[basis] = Decimal(meta["amount"])
                    else:
                        s["reference"] = meta["amount"]
                    s["snapshot_date"] = r.event_date
                # Realized P&L here covers only new trades after this baseline.
            elif r.kind == "adjustment":
                s.update(
                    quantity=q,
                    weighted=cost,
                    net=None,
                    dividend=None,
                    has_adjustment=True,
                    history_status="incomplete",
                )
            elif r.kind == "buy":
                if s["count"] and not s["quantity"]:
                    s["closed_cycles"].append(
                        dict(
                            cycle_id=s["cycle_id"],
                            net=string(s["net"]),
                            dividend=string(s["dividend"]),
                            realized_pnl=string(s["realized_pnl"]),
                        )
                    )
                    s.update(
                        weighted=ZERO,
                        net=ZERO,
                        dividend=None,
                        reference=None,
                        cycle_id=r.id,
                        realized_pnl=ZERO,
                        fees=ZERO,
                        estimated=False,
                        known_since=r.event_date,
                        snapshot_date=None,
                    )
                outlay = money(q * price + fees)
                for basis in BASES:
                    if s[basis] is not None:
                        s[basis] += outlay
                s["quantity"] += q
            elif r.kind in {"bonus", "reinvest"}:
                s["quantity"] += q
            elif r.kind == "sell":
                if q > s["quantity"]:
                    fail("historical_oversell", "重算后存在历史超卖，请检查该笔及后续流水")
                proceeds = money(q * price - fees)
                if s["weighted"] is not None:
                    removed = (
                        s["weighted"]
                        if q == s["quantity"]
                        else money(s["weighted"] * q / s["quantity"])
                    )
                    s["weighted"] -= removed
                    if s["realized_pnl"] is not None:
                        s["realized_pnl"] += proceeds - removed
                else:
                    s["realized_pnl"] = None
                for basis in ("net", "dividend"):
                    if s[basis] is not None:
                        s[basis] -= proceeds
                s["quantity"] -= q
            s["fees"] += fees
            s["estimated"] |= meta.get("fees_known") is False
            if r.history_status == "incomplete":
                s["history_status"] = "incomplete"
            s["count"] += 1
        output = []
        for s in states.values():
            out = {
                k: string(s[k]) if isinstance(s[k], Decimal) else s[k]
                for k in (
                    "code",
                    "quantity",
                    "realized_pnl",
                    "fees",
                    "known_since",
                    "history_status",
                    "has_adjustment",
                    "cycle_id",
                    "closed_cycles",
                    "reference",
                    "estimated",
                )
            }
            out["costs"] = {
                basis: dict(
                    total=string(s[basis]),
                    per_share=string(s[basis] / s["quantity"])
                    if s[basis] is not None and s["quantity"]
                    else None,
                    status="unknown"
                    if s[basis] is None
                    else "estimated"
                    if s["estimated"]
                    else "known",
                )
                for basis in BASES
            }
            out.update(
                total_cost=string(s["weighted"]),
                average_cost=out["costs"]["weighted"]["per_share"],
                unrealized_pnl=None,
                dividends_received=None,
                history_before_known_since="unknown",
                date_semantics="end_of_day" if s["snapshot_date"] else "legacy_or_trade",
                rule_version=RULE,
            )
            output.append(out)
        return sorted(output, key=lambda s: s["code"])


def stock_out(stock):
    return dict(
        code=stock.code,
        name=stock.name,
        exchange=stock.exchange,
        currency="CNY",
        is_active=stock.is_active,
        listed_on=stock.listed_on,
    )


def search(session, user_id, account_id, term):
    accounts.own_account(session, user_id, account_id)
    term = text_input(term).strip()
    if not term or len(term) > 64:
        return {"items": []}
    # Escape wildcards; don't filter on quote availability or research watchlists.
    term = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = session.scalars(
        select(Instrument)
        .where(
            Instrument.type == "stock",
            func.upper(Instrument.exchange).in_(["SH", "SZ", "BJ", "SSE", "SZSE", "BSE"]),
            or_(
                Instrument.code.ilike(f"%{term}%", escape="\\"),
                Instrument.name.ilike(f"%{term}%", escape="\\"),
            ),
        )
        .order_by(Instrument.code)
        .limit(20)
    ).all()
    return {"items": [stock_out(s) for s in rows]}


def history_reference(session, code, preferences, quantity=ZERO):
    from app.services.portfolio_dividend_reference import reference

    return reference(session, code, preferences, quantity, as_of=today())


def quote_reference(session, code):
    quote = session.get(StockRealtimeQuote, code)
    if quote and quote.price > 0:
        stamp = quote.quote_time
        return dict(
            price=string(Decimal(quote.price)),
            at=stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC),
            source="stock_realtime_quotes",
            time_label="报价时间",
        )
    metric = session.get(StockMetric, code)
    if metric and metric.price is not None and metric.price > 0:
        stamp = metric.updated_at
        return dict(
            price=string(Decimal(metric.price)),
            at=stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC),
            source="stock_metrics",
            time_label="行情快照更新时间",
        )
    return None


def position_preferences(rows):
    prefs = {}
    for r in sorted(active_rows(rows), key=lambda r: r.account_version):
        meta = getattr(r, "details", None) or {}
        if "preferences" in meta:
            prefs[r.code] = meta["preferences"]
    return prefs


def holdings(session, user_id, account_id):
    with localcontext() as ctx:
        ctx.prec = 50
        return _holdings(session, user_id, account_id)


def _holdings(session, user_id, account_id):
    accounts.lock_owner(session, user_id)
    account = accounts.own_account(session, user_id, account_id)
    rows = entries_for(session, user_id, account_id)
    prefs = position_preferences(rows)
    positions = project(rows)
    known_value = ZERO
    missing = 0
    for p in positions:
        stock = session.get(Instrument, p["code"])
        p.update(
            name=stock.name if stock else p["code"], preferences=prefs.get(p["code"], DEFAULT_PREFS)
        )
        quote = quote_reference(session, p["code"])
        q = Decimal(p["quantity"])
        price = Decimal(quote["price"]) if quote else None
        p["quote"] = quote
        p["market_value"] = string(q * price) if price is not None else None
        if q:
            if price is None:
                missing += 1
            else:
                known_value += q * price
        p["forecast"] = history_reference(session, p["code"], p["preferences"], q)
        annual = p["forecast"]["annual_per_share"]
        p["price_yield"] = (
            string(Decimal(annual) / price * 100) if annual is not None and price else None
        )
        p["price_yield_status"] = (
            p["forecast"]["reason"]
            if annual is None
            else "missing_quote"
            if price is None
            else "available"
        )
        p["price_yield_reason"] = (
            p["forecast"]["reason_label"]
            if annual is None
            else "暂无有效报价"
            if price is None
            else None
        )
        p["price_yield_issues"] = ([p["forecast"]["reason_label"]] if annual is None else []) + (
            ["暂无有效报价"] if price is None else []
        )
        weighted = p["costs"]["weighted"]["per_share"]
        p["cost_yield"] = (
            string(Decimal(annual) / Decimal(weighted) * 100)
            if annual is not None and weighted and Decimal(weighted) > 0
            else None
        )
    cancelled = {r.reverses_id for r in rows if r.reverses_id}
    return dict(
        account_version=account.version,
        consent_required=not current_consent(session, account),
        positions=positions,
        entries=[entry_out(r, cancelled) for r in rows],
        known_market_value=(
            None
            if missing and missing == sum(Decimal(p["quantity"]) > 0 for p in positions)
            else string(known_value)
        ),
        missing_quotes=missing,
        rule_version=RULE,
        automatic_dividends=False,
    )


def writable(session, user_id, account_id, version):
    accounts.lock_owner(session, user_id)
    account = accounts.own_account(session, user_id, account_id, lock=True)
    if account.version != version:
        raise accounts.PortfolioError("account_changed", "账本已变化，请刷新后重新预览")
    if account.is_archived:
        raise accounts.PortfolioError("account_archived", "账本已归档，请先恢复")
    if not current_consent(session, account):
        raise accounts.PortfolioError("privacy_ack_required", "请先确认新版持仓数据说明", 403)
    return account


def prepare(session, user_id, account_id, data, rows):
    """Build/validate a candidate without flushing; used identically by preview and confirm."""
    kind, code = data["kind"], data["code"]
    stock = session.get(Instrument, code)
    if (
        not stock
        or stock.type != "stock"
        or stock.exchange.upper() not in {"SH", "SZ", "BJ", "SSE", "SZSE", "BSE"}
    ):
        fail("unsupported_stock", "请选择系统收录的A股股票")
    day = date.fromisoformat(data["event_date"])
    if day > today() or (stock.listed_on and day < stock.listed_on):
        fail("invalid_date", "日期不能晚于今天或早于上市日")
    active = active_rows(rows)
    target = next((r for r in active if r.id == data.get("reverses_id")), None)
    if data.get("reverses_id") and (
        not target or target.code != code or target.kind == "preference"
    ):
        fail("invalid_reversal", "只能更正本账本同股票的有效持仓或交易")
    note, evidence = text_input(data["note"]), text_input(data["evidence"])
    if target and not note:
        fail("reason_required", "更正或撤销必须填写原因")
    if kind == "reversal" and not target:
        fail("invalid_reversal", "撤销必须关联原记录")
    if target and kind != "reversal" and target.kind != kind:
        fail("invalid_reversal", "更正须保留原记录类型与日期语义")
    if kind in {"opening", "adjustment"} and not target:
        fail("legacy_only", "旧版记录类型仅支持更正，新建请使用持仓快照")
    if kind in {"bonus", "reinvest"} and not target:
        if not any(r.code == code for r in active if r.kind != "preference"):
            fail("position_missing", "请先添加该股票的持仓，再记录送股或分红复投")
    q = ZERO if kind in {"reversal", "preference"} else decimal_input(data["quantity"])
    if kind not in {"reversal", "preference", "adjustment"} and not q:
        fail("invalid_quantity", "股数必须大于0")
    if q != q.to_integral_value() and not (target and target.details is None):
        fail("invalid_quantity", "A股请输入整数股数，可录入零股，不要求100股整数倍")
    price = fees = cost = ZERO
    meta = dict(
        rule_version=RULE,
        input_mode=data["input_mode"],
        input_value=data["cost"],
        fees_known=data["fees"] is not None,
    )
    basis = data["basis"]
    if kind in {"snapshot", "opening", "adjustment", "rebase"}:
        raw = data["cost"]
        if not isinstance(raw, str) or not re.fullmatch(
            r"-?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?", raw
        ):
            fail("invalid_decimal", "成本最多12位整数、6位小数，可按口径输入负数")
        value = Decimal(raw)
        if kind not in {"snapshot", "rebase"} and basis != "weighted":
            fail("legacy_basis", "旧记录使用加权口径，不能通过更正更换其历史含义")
        if basis == "weighted" and value < 0:
            fail("negative_weighted", "加权平均成本不能为负；请核实券商成本口径")
        if data["fees"] is not None:
            fail("snapshot_fees", "已有持仓不再重复添加历史手续费")
        amount = money(q * value if data["input_mode"] == "per_share" else value)
        if abs(amount) >= Decimal("100000000000000"):
            fail("amount_overflow", "对应总额超过允许范围")
        if not q and amount:
            fail("invalid_balance", "零持仓的加权成本必须为零")
        meta.update(
            basis=basis,
            amount=string(amount),
            fees_known=True,
            date_semantics="end_of_day" if kind in {"snapshot", "rebase"} else "legacy",
        )
        if kind not in {"snapshot", "rebase"}:
            cost = amount
        if kind in {"adjustment", "rebase"} and (not note or not evidence):
            fail("reason_required", "调整必须填写原因和核对依据")
    elif kind in {"buy", "sell"}:
        price = decimal_input(data["cost"])
        fees = decimal_input(data["fees"]) if data["fees"] is not None else ZERO
        if not price:
            fail("invalid_price", "成交价必须大于0")
        if q * price + fees >= Decimal("100000000000000"):
            fail("amount_overflow", "交易总额超过允许范围")
    elif kind in {"bonus", "reinvest"}:
        if data["cost"] not in {"", "0", "0.0"}:
            fail("invalid_cost", "送股和分红复投不填写成交价")
        if data["fees"] is not None and decimal_input(data["fees"]) != ZERO:
            fail("invalid_fees", "送股和分红复投不产生交易费用")
        price = fees = cost = ZERO
        meta.update(
            basis="weighted",
            amount="0",
            fees_known=True,
            date_semantics="trade",
        )
    prefs = data["preferences"].copy()
    if kind in {"snapshot", "rebase"}:
        prefs["basis"] = basis
    prefs["group"] = text_input(prefs["group"])
    if prefs["forecast"] == "custom":
        prefs["custom"] = string(decimal_input(prefs["custom"]))
    else:
        prefs["custom"] = None
    if kind != "reversal":
        meta["preferences"] = prefs
    if kind == "preference" and not any(r.code == code for r in active if r.kind != "preference"):
        fail("position_missing", "请先添加持仓")
    day_order = data.get("day_order")
    if kind == "reversal":
        day, day_order = target.event_date, target.day_order
    elif day_order is None:
        day_order = (
            target.day_order
            if target and day == target.event_date
            else 1
            + max(
                (r.day_order for r in active if r.code == code and r.event_date == day), default=0
            )
        )
    row = PortfolioEntry(
        id=data["request_id"],
        user_id=user_id,
        account_id=account_id,
        request_id=data["request_id"],
        request_hash=digest(data),
        code=code,
        kind=kind,
        event_date=day,
        day_order=day_order,
        quantity=q,
        price=price,
        fees=fees,
        total_cost=cost,
        history_status="incomplete" if kind == "adjustment" else "since_date",
        source="manual",
        note=note,
        evidence=evidence,
        reverses_id=data.get("reverses_id"),
        details=meta,
        account_version=data["expected_version"] + 1,
        created_at=datetime.now(UTC),
    )
    positions = project([*rows, row])
    position = next((p for p in positions if p["code"] == code), None)
    summary = dict(
        stock=stock_out(stock),
        kind=kind,
        event_date=day.isoformat(),
        day_order=day_order,
        quantity=string(q),
        input_value=data["cost"],
        input_mode=data["input_mode"],
        basis=basis,
        amount=meta.get("amount")
        if kind in {"snapshot", "opening", "adjustment", "rebase", "bonus", "reinvest"}
        else string(q * price + fees if kind == "buy" else q * price - fees),
        fees=string(fees) if kind in {"buy", "sell"} else None,
        fees_known=meta["fees_known"],
        resulting_position=position,
        preferences=prefs,
        forecast=history_reference(
            session, code, prefs, Decimal(position["quantity"]) if position else ZERO
        ),
        date_semantics=meta.get("date_semantics", "trade"),
        warning="起点以前的盈亏和分红未知；历史参考不生成应收或到账。日终快照已含截至日交易。",
    )
    return row, summary


def preview(session, user_id, account_id, data):
    writable(session, user_id, account_id, data["expected_version"])
    rows = entries_for(session, user_id, account_id)
    with localcontext() as ctx:
        ctx.prec = 50
        _, summary = prepare(session, user_id, account_id, data, rows)
    # Token contains hashes only, never private holdings. Body remains in UI memory.
    token = jwt.encode(
        dict(
            sub=str(user_id),
            account=account_id,
            payload_hash=digest(data),
            summary_hash=digest(summary),
            rule=RULE,
            policy=accounts.POLICY_SHA256,
            aud="portfolio-preview",
            exp=datetime.now(UTC) + timedelta(minutes=15),
        ),
        settings.jwt_secret,
        algorithm="HS256",
    )
    return dict(preview_token=token, summary=summary, expires_in=900)


def confirm(session, user_id, account_id, data, token):
    accounts.lock_owner(session, user_id)
    account = accounts.own_account(session, user_id, account_id, lock=True)
    rows = entries_for(session, user_id, account_id)
    prior = next((r for r in rows if r.request_id == data["request_id"]), None)
    if prior:
        if prior.request_hash != digest(data):
            raise accounts.PortfolioError("request_reused", "请求编号已用于其他内容")
        return holdings(session, user_id, account_id)
    try:
        claims = jwt.decode(
            token, settings.jwt_secret, algorithms=["HS256"], audience="portfolio-preview"
        )
        if (
            claims["sub"],
            claims["account"],
            claims["payload_hash"],
            claims["rule"],
            claims["policy"],
        ) != (str(user_id), account_id, digest(data), RULE, accounts.POLICY_SHA256):
            raise ValueError("preview mismatch")
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise accounts.PortfolioError("preview_expired", "预览已失效，请重新核对后保存") from exc
    writable(session, user_id, account_id, data["expected_version"])
    with localcontext() as ctx:
        ctx.prec = 50
        row, summary = prepare(session, user_id, account_id, data, rows)
    if digest(summary) != claims["summary_hash"]:
        raise accounts.PortfolioError("preview_changed", "预览结果已变化，请重新核对")
    account.version += 1
    account.updated_at = datetime.now(UTC)
    session.add(row)
    if row.kind != "preference":
        target = next((r for r in rows if r.id == row.reverses_id), None)
        session.add(
            PortfolioReviewRange(
                id=str(uuid4()),
                user_id=user_id,
                account_id=account_id,
                code=row.code,
                from_date=min(row.event_date, target.event_date) if target else row.event_date,
                account_version=account.version,
                reason="position_changed",
                created_at=datetime.now(UTC),
            )
        )
    accounts._audit(session, account, "position_entry")
    session.flush()
    return holdings(session, user_id, account_id)

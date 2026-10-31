"""V2-52/53: evidence-backed entitlements and confirmed dividend receipts.

Entitlements are derived, versioned projections. Receipts are user-confirmed facts.
No entitlement is generated from a proposal, an incomplete position history or an
unreviewed legacy dividend row.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.db.models import (
    DividendEntitlement,
    DividendEvent,
    DividendEventVersion,
    DividendReceipt,
    PortfolioEntry,
)
from app.services import portfolio as accounts
from app.services.portfolio_ledger import (
    current_consent,
    decimal_input,
    entries_for,
    text_input,
)
from app.services.portfolio_positions import active_rows

CALC_VERSION = "entitlement-cny-v1"
ZERO = Decimal(0)
CENT = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, ".2f")


def _parse_money(value: str | None, field: str, *, required: bool = False) -> Decimal | None:
    if value is None:
        if required:
            raise accounts.PortfolioError("invalid_amount", f"{field}不能为空", 422)
        return None
    try:
        amount = decimal_input(value)
    except accounts.PortfolioError as exc:
        raise accounts.PortfolioError(
            "invalid_amount", f"{field}请填写非负金额，最多12位整数、6位小数", 422
        ) from exc
    if amount > Decimal("999999999999.99"):
        raise accounts.PortfolioError("amount_overflow", f"{field}超出允许范围", 422)
    return _money(amount)


def quantity_at(
    rows: list[PortfolioEntry], code: str, at: date
) -> tuple[Decimal | None, date | None, str | None]:
    """Quantity at end of ``at``; None when history starts later or is unreliable."""
    relevant = [
        row
        for row in active_rows(rows)
        if row.code == code and row.kind != "preference"
    ]
    if not relevant:
        return ZERO, None, "no_position_history"
    known_since = relevant[0].event_date
    if known_since > at:
        return None, known_since, "record_date_before_history"
    quantity = ZERO
    incomplete = False
    for row in relevant:
        if row.event_date > at:
            break
        qty = Decimal(row.quantity)
        if row.kind in {"opening", "snapshot", "rebase", "adjustment"}:
            quantity = qty
        elif row.kind == "buy":
            quantity += qty
        elif row.kind in {"bonus", "reinvest"}:
            quantity += qty
        elif row.kind == "sell":
            if qty > quantity:
                return None, known_since, "historical_oversell"
            quantity -= qty
        if row.history_status == "incomplete":
            incomplete = True
    if quantity < 0:
        return None, known_since, "negative_position"
    if incomplete:
        return quantity, known_since, "incomplete_history"
    return quantity, known_since, None


def _current_events(session: Session, codes: list[str]):
    if not codes:
        return []
    return session.execute(
        select(DividendEvent, DividendEventVersion)
        .join(
            DividendEventVersion,
            and_(
                DividendEventVersion.event_id == DividendEvent.id,
                DividendEventVersion.revision == DividendEvent.current_revision,
            ),
        )
        .where(DividendEvent.code.in_(codes))
    ).all()


def _has_corporate_action(plan: str) -> bool:
    return bool(re.search(r"送|转增|转股|拆股|并股", plan))


def _status_for(gross: Decimal, received: Decimal) -> str:
    if received <= 0:
        return "pending"
    if received < gross:
        return "partial"
    return "settled"


def _active_received(session: Session, entitlement_id: str) -> Decimal:
    values = session.scalars(
        select(DividendReceipt.net_amount).where(
            DividendReceipt.entitlement_id == entitlement_id,
            DividendReceipt.status == "active",
        )
    ).all()
    return sum((Decimal(value) for value in values), ZERO)


def _received_map(session: Session, ids: list[str]) -> dict[str, Decimal]:
    if not ids:
        return {}
    rows = session.execute(
        select(
            DividendReceipt.entitlement_id,
            DividendReceipt.net_amount,
            DividendReceipt.gross_amount,
        ).where(
            DividendReceipt.entitlement_id.in_(ids),
            DividendReceipt.status == "active",
        )
    ).all()
    result: dict[str, Decimal] = {}
    for entitlement_id, net, gross in rows:
        if entitlement_id is None:
            continue
        # Gross is the entitlement basis; tax may be withheld. Net-only receipts
        # are treated as gross-known-equals-net and are flagged by the absence of tax.
        amount = Decimal(gross) if gross is not None else Decimal(net)
        result[entitlement_id] = result.get(entitlement_id, ZERO) + amount
    return result


def _net_received_map(session: Session, ids: list[str]) -> dict[str, Decimal]:
    if not ids:
        return {}
    rows = session.execute(
        select(DividendReceipt.entitlement_id, DividendReceipt.net_amount).where(
            DividendReceipt.entitlement_id.in_(ids),
            DividendReceipt.status == "active",
        )
    ).all()
    result: dict[str, Decimal] = {}
    for entitlement_id, net in rows:
        if entitlement_id is None:
            continue
        result[entitlement_id] = result.get(entitlement_id, ZERO) + Decimal(net)
    return result


def sync_entitlements(session: Session, user_id: int, account_id: str) -> dict:
    """Recalculate pending entitlements from reviewed events and the ledger."""
    accounts.lock_owner(session, user_id)
    account = accounts.own_account(session, user_id, account_id, lock=True)
    rows = entries_for(session, user_id, account_id)
    codes = {
        row.code
        for row in active_rows(rows)
        if row.kind not in {"preference"} and row.code
    }
    events = _current_events(session, sorted(codes))
    now = datetime.now(UTC)
    created = updated = voided = 0
    skipped: list[dict] = []

    active_rows_db = session.scalars(
        select(DividendEntitlement).where(
            DividendEntitlement.account_id == account.id,
            DividendEntitlement.user_id == user_id,
            DividendEntitlement.is_active.is_(True),
        )
    ).all()
    active_by_event = {row.event_id: row for row in active_rows_db}
    valid_events: set[str] = set()

    for event, version in events:
        if (
            version.stage != "implemented"
            or version.evidence_status != "reviewed"
            or version.record_date is None
            or version.cash_per_share is None
            or Decimal(version.cash_per_share) <= 0
        ):
            continue
        if _has_corporate_action(version.plan):
            skipped.append(
                {"code": event.code, "event_id": event.id, "reason": "corporate_action"}
            )
            continue
        quantity, known_since, reason = quantity_at(rows, event.code, version.record_date)
        if quantity is None or quantity <= 0:
            skipped.append(
                {
                    "code": event.code,
                    "event_id": event.id,
                    "reason": reason or "no_eligible_quantity",
                    "known_since": known_since.isoformat() if known_since else None,
                }
            )
            continue
        if reason:
            skipped.append(
                {
                    "code": event.code,
                    "event_id": event.id,
                    "reason": reason,
                    "known_since": known_since.isoformat() if known_since else None,
                }
            )
            continue
        gross = _money(quantity * Decimal(version.cash_per_share))
        if gross <= 0:
            continue
        valid_events.add(event.id)
        existing = active_by_event.get(event.id)
        if existing is not None:
            if (
                Decimal(existing.eligible_quantity) == quantity
                and Decimal(existing.cash_per_share) == Decimal(version.cash_per_share)
                and existing.event_revision == event.current_revision
                and existing.record_date == version.record_date
                and existing.payment_date == version.payment_date
            ):
                continue
            received = _active_received(session, existing.id)
            if received > 0:
                existing.status = "review"
                existing.review_reasons = ["event_or_position_changed"]
                existing.updated_at = now
                updated += 1
                continue
            existing.is_active = False
            existing.updated_at = now
            revision = existing.revision + 1
        else:
            revision = 1
        session.add(
            DividendEntitlement(
                id=str(uuid4()),
                account_id=account.id,
                user_id=user_id,
                event_id=event.id,
                event_revision=event.current_revision,
                account_version=account.version,
                revision=revision,
                code=event.code,
                record_date=version.record_date,
                payment_date=version.payment_date,
                eligible_quantity=quantity,
                cash_per_share=Decimal(version.cash_per_share),
                gross_amount=gross,
                status="pending",
                is_active=True,
                calculation_version=CALC_VERSION,
                review_reasons=[],
                created_at=now,
                updated_at=now,
            )
        )
        if existing is None:
            created += 1
        else:
            updated += 1

    for event_id, row in active_by_event.items():
        if event_id not in valid_events and row.is_active:
            received = _active_received(session, row.id)
            row.is_active = False
            row.status = "review" if received > 0 else "void"
            row.review_reasons = ["event_no_longer_eligible"]
            row.updated_at = now
            voided += 1

    session.flush()
    return {
        "created": created,
        "updated": updated,
        "voided": voided,
        "skipped": skipped[:100],
    }


def _entitlement_out(
    row: DividendEntitlement, received: Decimal, net_received: Decimal
) -> dict:
    remaining = max(Decimal(row.gross_amount) - received, ZERO)
    status = (
        row.status
        if row.status in {"review", "void"}
        else _status_for(Decimal(row.gross_amount), received)
    )
    return {
        "id": row.id,
        "code": row.code,
        "event_id": row.event_id,
        "event_revision": row.event_revision,
        "account_version": row.account_version,
        "revision": row.revision,
        "record_date": row.record_date.isoformat(),
        "payment_date": row.payment_date.isoformat() if row.payment_date else None,
        "eligible_quantity": format(Decimal(row.eligible_quantity), ".6f"),
        "cash_per_share": format(Decimal(row.cash_per_share), ".8f"),
        "gross_amount": _text(Decimal(row.gross_amount)),
        "received_amount": _text(net_received),
        "remaining_amount": _text(remaining),
        "status": status,
        "calculation_version": row.calculation_version,
        "review_reasons": row.review_reasons,
    }


def _receipt_out(row: DividendReceipt) -> dict:
    return {
        "id": row.id,
        "entitlement_id": row.entitlement_id,
        "code": row.code,
        "quantity": format(Decimal(row.quantity), ".6f") if row.quantity is not None else None,
        "cash_per_share": (
            format(Decimal(row.cash_per_share), ".8f")
            if row.cash_per_share is not None
            else None
        ),
        "received_date": row.received_date.isoformat(),
        "gross_amount": _text(Decimal(row.gross_amount)) if row.gross_amount is not None else None,
        "tax_amount": _text(Decimal(row.tax_amount)) if row.tax_amount is not None else None,
        "net_amount": _text(Decimal(row.net_amount)),
        "status": row.status,
        "note": row.note,
        "created_at": row.created_at.isoformat(),
        "reversed_at": row.reversed_at.isoformat() if row.reversed_at else None,
    }


def income_snapshot(session: Session, user_id: int, account_id: str) -> dict:
    accounts.own_account(session, user_id, account_id)
    entitlements = session.scalars(
        select(DividendEntitlement)
        .where(
            DividendEntitlement.account_id == account_id,
            DividendEntitlement.user_id == user_id,
            DividendEntitlement.is_active.is_(True),
        )
        .order_by(DividendEntitlement.record_date.desc(), DividendEntitlement.code)
    ).all()
    received = _received_map(session, [row.id for row in entitlements])
    net_received = _net_received_map(session, [row.id for row in entitlements])
    receipts = session.scalars(
        select(DividendReceipt)
        .where(
            DividendReceipt.account_id == account_id,
            DividendReceipt.user_id == user_id,
        )
        .order_by(DividendReceipt.received_date.desc(), DividendReceipt.created_at.desc())
    ).all()
    gross_total = sum((Decimal(row.gross_amount) for row in entitlements), ZERO)
    recognized_total = sum((received.get(row.id, ZERO) for row in entitlements), ZERO)
    net_total = sum((net_received.get(row.id, ZERO) for row in entitlements), ZERO)
    unlinked = sum(
        (
            Decimal(row.net_amount)
            for row in receipts
            if row.entitlement_id is None and row.status == "active"
        ),
        ZERO,
    )
    return {
        "summary": {
            "gross_amount": _text(gross_total),
            "received_amount": _text(net_total),
            "recognized_amount": _text(recognized_total),
            "remaining_amount": _text(max(gross_total - recognized_total, ZERO)),
            "unlinked_received_amount": _text(unlinked),
            "entitlement_count": len(entitlements),
            "pending_count": sum(
                1
                for row in entitlements
                if _status_for(Decimal(row.gross_amount), received.get(row.id, ZERO)) == "pending"
            ),
            "calculation_version": CALC_VERSION,
        },
        "entitlements": [
            _entitlement_out(
                row,
                received.get(row.id, ZERO),
                net_received.get(row.id, ZERO),
            )
            for row in entitlements
        ],
        "receipts": [_receipt_out(row) for row in receipts],
    }


def _write_account(session: Session, user_id: int, account_id: str, version: int):
    accounts.lock_owner(session, user_id)
    account = accounts.own_account(session, user_id, account_id, lock=True)
    if account.version != version:
        raise accounts.PortfolioError("account_changed", "账本已变化，请刷新后重试")
    if account.is_archived:
        raise accounts.PortfolioError("account_archived", "账本已归档，请先恢复")
    if not current_consent(session, account):
        raise accounts.PortfolioError(
            "privacy_ack_required", "请先确认新版持仓数据说明", 403
        )
    return account


def create_receipt(
    session: Session,
    user_id: int,
    account_id: str,
    *,
    expected_version: int,
    request_id: str,
    entitlement_id: str | None,
    code: str,
    received_date: date,
    net_amount: str,
    gross_amount: str | None,
    tax_amount: str | None,
    note: str = "",
    quantity: str | None = None,
    cash_per_share: str | None = None,
) -> dict:
    account = _write_account(session, user_id, account_id, expected_version)
    net = _parse_money(net_amount, "净额", required=True)
    if net is None or net <= 0:
        raise accounts.PortfolioError("invalid_amount", "净额必须大于0", 422)
    gross = _parse_money(gross_amount, "税前金额")
    tax = _parse_money(tax_amount, "税额")
    parsed_quantity = None
    parsed_cash = None
    if quantity is not None or cash_per_share is not None:
        if quantity is None or cash_per_share is None:
            raise accounts.PortfolioError("invalid_amount", "数量和每股派息必须同时填写", 422)
        try:
            parsed_quantity = decimal_input(quantity)
            parsed_cash = decimal_input(cash_per_share)
        except accounts.PortfolioError as exc:
            raise accounts.PortfolioError(
                "invalid_amount", "数量和每股派息必须是非负十进制数", 422
            ) from exc
        if parsed_quantity <= 0 or parsed_cash <= 0:
            raise accounts.PortfolioError("invalid_amount", "数量和每股派息必须大于0", 422)
        calculated_gross = _money(parsed_quantity * parsed_cash)
        if gross is not None and gross != calculated_gross:
            raise accounts.PortfolioError(
                "invalid_amount", "税前金额与数量×每股派息不一致", 422
            )
        gross = calculated_gross
    if gross is not None and tax is not None and gross != net + tax:
        raise accounts.PortfolioError(
            "invalid_amount", "税前金额必须等于净额加税额", 422
        )
    if gross is None and tax is not None:
        raise accounts.PortfolioError("invalid_amount", "填写税额时必须填写税前金额", 422)
    if gross is not None and tax is None:
        tax = gross - net
    if tax is not None and tax < 0:
        raise accounts.PortfolioError("invalid_amount", "税额不能为负", 422)
    if not re.fullmatch(r"\d{6}", code):
        raise accounts.PortfolioError("invalid_code", "股票代码格式不正确", 422)
    if received_date > datetime.now(UTC).date():
        raise accounts.PortfolioError("future_date", "到账日期不能晚于今天", 422)
    entitlement = None
    if entitlement_id:
        entitlement = session.scalar(
            select(DividendEntitlement).where(
                DividendEntitlement.id == entitlement_id,
                DividendEntitlement.account_id == account.id,
                DividendEntitlement.user_id == user_id,
                DividendEntitlement.is_active.is_(True),
            )
        )
        if entitlement is None:
            raise accounts.PortfolioError("entitlement_not_found", "应收记录不存在", 404)
        code = entitlement.code

    existing = session.scalar(
        select(DividendReceipt).where(
            DividendReceipt.account_id == account.id,
            DividendReceipt.request_id == request_id,
        )
    )
    values = {
        "entitlement_id": entitlement_id,
        "code": code,
        "quantity": quantity,
        "cash_per_share": cash_per_share,
        "received_date": received_date.isoformat(),
        "gross_amount": gross_amount,
        "tax_amount": tax_amount,
        "net_amount": net_amount,
        "note": note,
    }
    request_hash = hashlib.sha256(
        json.dumps(values, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    if existing is not None:
        if existing.request_hash != request_hash:
            raise accounts.PortfolioError(
                "request_conflict", "同一请求编号提交了不同内容", 409
            )
        return _receipt_out(existing)

    row = DividendReceipt(
        id=str(uuid4()),
        account_id=account.id,
        user_id=user_id,
        entitlement_id=entitlement_id,
        code=code,
        quantity=parsed_quantity,
        cash_per_share=parsed_cash,
        received_date=received_date,
        gross_amount=gross,
        tax_amount=tax,
        net_amount=net,
        status="active",
        note=text_input(note),
        request_id=request_id,
        request_hash=request_hash,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    account.version += 1
    account.updated_at = datetime.now(UTC)
    accounts._audit(session, account, "dividend_receipt")
    session.flush()
    if entitlement is not None:
        received = _active_received(session, entitlement.id)
        entitlement.status = _status_for(Decimal(entitlement.gross_amount), received)
        entitlement.updated_at = datetime.now(UTC)
    return _receipt_out(row)


def reverse_receipt(
    session: Session,
    user_id: int,
    account_id: str,
    receipt_id: str,
    *,
    expected_version: int,
) -> dict:
    account = _write_account(session, user_id, account_id, expected_version)
    row = session.scalar(
        select(DividendReceipt).where(
            DividendReceipt.id == receipt_id,
            DividendReceipt.account_id == account.id,
            DividendReceipt.user_id == user_id,
        )
    )
    if row is None:
        raise accounts.PortfolioError("receipt_not_found", "到账记录不存在", 404)
    if row.status == "active":
        row.status = "reversed"
        row.reversed_at = datetime.now(UTC)
        account.version += 1
        account.updated_at = datetime.now(UTC)
        accounts._audit(session, account, "dividend_receipt_reversal")
        if row.entitlement_id:
            entitlement = session.get(DividendEntitlement, row.entitlement_id)
            if entitlement is not None:
                received = _active_received(session, entitlement.id)
                entitlement.status = _status_for(
                    Decimal(entitlement.gross_amount), received
                )
                entitlement.updated_at = datetime.now(UTC)
        session.flush()
    return _receipt_out(row)


def _month_key(value: date) -> str:
    return value.strftime("%Y-%m")


def _event_amount(
    rows: list[PortfolioEntry], event, version
) -> tuple[str | None, str | None, str | None]:
    if version.record_date is None or version.cash_per_share is None:
        return None, None, "missing_record_date_or_cash"
    quantity, known_since, reason = quantity_at(rows, event.code, version.record_date)
    if quantity is None or quantity <= 0 or reason:
        return None, None, reason or "no_eligible_quantity"
    amount = _money(quantity * Decimal(version.cash_per_share))
    return format(quantity, ".6f"), format(amount, ".2f"), None


def income_home(session: Session, user_id: int, account_id: str, year: int) -> dict:
    """Calendar + annual cash-flow projection for the next income action."""
    if year < 2000 or year > 2100:
        raise accounts.PortfolioError("invalid_year", "年份超出范围", 422)
    accounts.own_account(session, user_id, account_id)
    rows = entries_for(session, user_id, account_id)
    codes = sorted({row.code for row in active_rows(rows) if row.kind != "preference"})
    events = _current_events(session, codes)
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    entitlements = session.scalars(
        select(DividendEntitlement).where(
            DividendEntitlement.account_id == account_id,
            DividendEntitlement.user_id == user_id,
            DividendEntitlement.is_active.is_(True),
        )
    ).all()
    entitlement_by_event = {row.event_id: row for row in entitlements}
    received_by_entitlement = _received_map(session, [row.id for row in entitlements])
    net_by_entitlement = _net_received_map(session, [row.id for row in entitlements])
    receipts = session.scalars(
        select(DividendReceipt).where(
            DividendReceipt.account_id == account_id,
            DividendReceipt.user_id == user_id,
            DividendReceipt.status == "active",
        )
    ).all()

    months = {
        f"{year}-{month:02d}": {
            "month": f"{year}-{month:02d}",
            "received": ZERO,
            "pending": ZERO,
            "proposal": ZERO,
        }
        for month in range(1, 13)
    }
    calendar: dict[str, list[dict]] = {}
    unknown: list[dict] = []
    proposals: list[dict] = []
    event_rows: list[dict] = []

    for event, version in events:
        if version.stage not in {"implemented", "approved", "proposed"}:
            continue
        quantity, amount, reason = _event_amount(rows, event, version)
        entitlement = entitlement_by_event.get(event.id)
        remaining = (
            max(
                Decimal(entitlement.gross_amount)
                - received_by_entitlement.get(entitlement.id, ZERO),
                ZERO,
            )
            if entitlement
            else ZERO
        )
        item = {
            "event_id": event.id,
            "code": event.code,
            "stage": version.stage,
            "plan": version.plan,
            "record_date": version.record_date.isoformat() if version.record_date else None,
            "ex_date": version.ex_date.isoformat() if version.ex_date else None,
            "payment_date": (
                version.payment_date.isoformat() if version.payment_date else None
            ),
            "cash_per_share": _text(Decimal(version.cash_per_share))
            if version.cash_per_share is not None
            else None,
            "eligible_quantity": quantity,
            "amount": amount,
            "entitlement_id": entitlement.id if entitlement else None,
            "received_amount": _text(net_by_entitlement.get(entitlement.id, ZERO))
            if entitlement
            else None,
            "remaining_amount": _text(remaining) if entitlement else None,
            "reason": reason,
        }
        event_rows.append(item)

        if version.stage in {"approved", "proposed"} and version.payment_date:
            if version.payment_date.year == year:
                month = months.get(_month_key(version.payment_date))
                if month and amount:
                    month["proposal"] += Decimal(amount)
                proposals.append(item)
        elif version.stage == "implemented" and entitlement:
            if entitlement.payment_date and entitlement.payment_date.year == year:
                month = months.get(_month_key(entitlement.payment_date))
                if month:
                    month["pending"] += remaining
            if entitlement.payment_date is None:
                unknown.append(item)

        dates = [
            ("record", version.record_date),
            ("ex", version.ex_date),
            ("payment", version.payment_date),
        ]
        for kind, event_date in dates:
            if event_date is None or event_date.year != year:
                continue
            calendar.setdefault(event_date.isoformat(), []).append(
                {
                    **item,
                    "date_type": kind,
                    "date_type_label": {
                        "record": "登记日",
                        "ex": "除息日",
                        "payment": "派息日",
                    }[kind],
                }
            )

    for receipt in receipts:
        if receipt.received_date.year != year:
            continue
        key = _month_key(receipt.received_date)
        if key in months:
            months[key]["received"] += Decimal(receipt.net_amount)
        calendar.setdefault(receipt.received_date.isoformat(), []).append(
            {
                "date_type": "received",
                "date_type_label": "到账",
                "event_id": None,
                "code": receipt.code,
                "stage": "received",
                "plan": "",
                "record_date": None,
                "ex_date": None,
                "payment_date": receipt.received_date.isoformat(),
                "cash_per_share": None,
                "eligible_quantity": None,
                "amount": _text(Decimal(receipt.net_amount)),
                "entitlement_id": receipt.entitlement_id,
                "received_amount": _text(Decimal(receipt.net_amount)),
                "remaining_amount": None,
                "reason": None,
            }
        )

    monthly = [
        {
            "month": row["month"],
            "received": _text(row["received"]),
            "pending": _text(row["pending"]),
            "proposal": _text(row["proposal"]),
        }
        for row in months.values()
    ]
    year_received = sum(
        (Decimal(row.net_amount) for row in receipts if row.received_date.year == year),
        ZERO,
    )
    year_pending = sum(
        (
            max(Decimal(row.gross_amount) - received_by_entitlement.get(row.id, ZERO), ZERO)
            for row in entitlements
            if row.payment_date and row.payment_date.year == year
        ),
        ZERO,
    )
    year_proposal = sum(
        (Decimal(item["amount"]) for item in proposals if item.get("amount")),
        ZERO,
    )
    upcoming = sorted(
        (
            {
                "code": row.code,
                "amount": _text(
                    max(Decimal(row.gross_amount) - received_by_entitlement.get(row.id, ZERO), ZERO)
                ),
                "payment_date": row.payment_date.isoformat(),
            }
            for row in entitlements
            if row.payment_date
            and row.payment_date >= today
            and Decimal(row.gross_amount) - received_by_entitlement.get(row.id, ZERO) > 0
        ),
        key=lambda item: item["payment_date"],
    )
    return {
        "year": year,
        "as_of": datetime.now(UTC).isoformat(),
        "summary": {
            "received": _text(year_received),
            "pending": _text(year_pending),
            "proposal": _text(year_proposal),
            "contract_pending": _text(
                sum(
                    (
                        max(
                            Decimal(row.gross_amount)
                            - received_by_entitlement.get(row.id, ZERO),
                            ZERO,
                        )
                        for row in entitlements
                    ),
                    ZERO,
                )
            ),
            "unknown_count": len(unknown),
            "next_payment": upcoming[0] if upcoming else None,
        },
        "monthly": monthly,
        "calendar": [
            {"date": key, "items": value} for key, value in sorted(calendar.items())
        ],
        "unknown": unknown,
        "events": event_rows,
        "entitlements": [
            _entitlement_out(
                row,
                received_by_entitlement.get(row.id, ZERO),
                net_by_entitlement.get(row.id, ZERO),
            )
            for row in entitlements
        ],
    }

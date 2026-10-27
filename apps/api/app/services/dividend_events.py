"""Append-only event snapshots and explicit review. No personal entitlement generation."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid4, uuid5

from etl.sources.dividend_events import (
    DATE_FIELDS,
    RULE_VERSION,
    content_fingerprint,
    normalize_observation,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AdminAuditLog,
    DividendEvent,
    DividendEventVersion,
    DividendSourceObservation,
    Instrument,
    StockDividend,
)


class ReviewConflict(ValueError):
    pass


def lock_stock(session: Session, code: str) -> Instrument:
    stock = session.scalar(
        select(Instrument)
        .where(
            Instrument.code == code,
            Instrument.type == "stock",
        )
        .with_for_update()
    )
    if stock is None:
        raise ValueError("stock not found")
    return stock


def record_source_pages(session: Session, pages: list[dict], codes: list[str]) -> int:
    """Capture all raw statuses, including unknown/zero cash. Caller owns transaction."""
    targets = set(codes)
    grouped: dict[str, list[tuple[dict, dict]]] = {}
    for page in pages:
        for raw in page["rows"]:
            code = str(raw.get("SECURITY_CODE") or "")
            if code in targets:
                grouped.setdefault(code, []).append((raw, page))
    written = 0
    for code in sorted(grouped):
        lock_stock(session, code)
        for raw, page in grouped[code]:
            normalized = normalize_observation(raw)
            fingerprint = content_fingerprint(normalized)
            existing = session.scalar(
                select(DividendSourceObservation.id).where(
                    DividendSourceObservation.source == "eastmoney",
                    DividendSourceObservation.code == code,
                    DividendSourceObservation.fingerprint == fingerprint,
                )
            )
            if existing:
                continue
            session.add(
                DividendSourceObservation(
                    id=str(uuid4()),
                    code=code,
                    source="eastmoney",
                    fingerprint=fingerprint,
                    normalized=normalized,
                    raw_payload=raw,
                    source_url=page["url"],
                    observed_at=datetime.fromisoformat(page["observed_at"]),
                    state="pending",
                )
            )
            session.flush()
            written += 1
    return written


def _version(
    data: dict,
    *,
    event: DividendEvent,
    observation: DividendSourceObservation | None,
    reviewer_id: int | None,
    note: str,
    raw: dict,
    observed_at: datetime,
    evidence_status: str,
    source: str,
    source_url: str | None,
) -> DividendEventVersion:
    values = {
        key: date.fromisoformat(data[key]) if data.get(key) else None
        for key in (*DATE_FIELDS, "payment_date")
    }
    return DividendEventVersion(
        event_id=event.id,
        revision=event.current_revision,
        **values,
        observation_id=observation.id if observation else None,
        cash_per_share=Decimal(data["cash_per_share"]) if data.get("cash_per_share") else None,
        plan=data["plan"],
        progress=data["progress"],
        stage=data["stage"],
        announcement_url=data.get("announcement_url"),
        source_event_id=data.get("source_event_id"),
        evidence_status=evidence_status,
        review_reasons=data["review_reasons"],
        rule_version=data["rule_version"],
        raw_payload=raw,
        reviewed_by=reviewer_id,
        review_note=note,
        observed_at=observed_at,
        source=source,
        source_url=source_url,
    )


def backfill_legacy(
    session: Session, *, after_id: int = 0, limit: int = 500, apply: bool = False
) -> dict:
    """One snapshot per legacy row, never merge/rewrite old records; bounded and rerunnable."""
    if after_id < 0 or not 1 <= limit <= 2000:
        raise ValueError("invalid backfill bounds")
    rows = session.scalars(
        select(StockDividend)
        .where(StockDividend.id > after_id)
        .order_by(StockDividend.id)
        .limit(limit)
    ).all()
    # Consistent parent lock order shared with review and ingestion.
    if apply:
        for code in sorted({row.code for row in rows}):
            lock_stock(session, code)
    created = 0
    for row in rows:
        existing = session.scalar(
            select(DividendEvent.id).where(
                DividendEvent.legacy_dividend_id == row.id,
            )
        )
        if existing:
            continue
        created += 1
        if not apply:
            continue
        raw = {
            "SECURITY_CODE": row.code,
            "REPORT_DATE": _iso(row.report_date),
            "NOTICE_DATE": _iso(row.notice_date),
            "EX_DIVIDEND_DATE": _iso(row.ex_date),
            "PRETAX_BONUS_RMB": str(Decimal(str(row.cash_per_share)) * 10),
            "ASSIGN_PROGRESS": row.progress,
            "IMPL_PLAN_PROFILE": row.plan,
            "legacy_id": row.id,
            "legacy_source": row.source,
            "legacy_fiscal_year": row.fiscal_year,
            "snapshot_origin": "legacy_table",
        }
        data = normalize_observation(raw)
        event = DividendEvent(
            id=str(uuid5(NAMESPACE_URL, f"stocklab:legacy:{row.code}:{row.id}")),
            code=row.code,
            legacy_dividend_id=row.id,
            current_revision=1,
            origin="legacy_snapshot",
        )
        session.add(event)
        session.flush()
        session.add(
            _version(
                data,
                event=event,
                observation=None,
                reviewer_id=None,
                note="Legacy snapshot only; no announcement identity/date verification",
                raw=raw,
                observed_at=datetime.now(UTC),
                evidence_status="legacy_unverified",
                source=row.source,
                source_url=None,
            )
        )
        session.flush()
    return {
        "scanned": len(rows),
        "candidates": created,
        "created": created if apply else 0,
        "last_id": rows[-1].id if rows else after_id,
        "applied": apply,
    }


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _reviewed_data(data: dict, patch: dict) -> dict:
    allowed = {
        "report_date",
        "record_date",
        "ex_date",
        "payment_date",
        "cash_per_share",
        "announcement_url",
        "stage",
    }
    if patch.keys() - allowed:
        raise ValueError("unsupported review fields")
    result = {**data, **patch}
    for field in (*DATE_FIELDS, "payment_date"):
        if result.get(field) is not None:
            date.fromisoformat(result[field])
    cash = result.get("cash_per_share")
    if cash is not None:
        amount = Decimal(str(cash))
        if not amount.is_finite() or not 0 <= amount < Decimal("1e12"):
            raise ValueError("invalid cash amount")
        if amount != amount.quantize(Decimal("0.00000001")):
            raise ValueError("cash amount exceeds supported precision")
        result["cash_per_share"] = format(amount, "f")
    if result["stage"] not in {
        "unknown",
        "proposed",
        "approved",
        "implemented",
        "cancelled",
        "no_distribution",
    }:
        raise ValueError("unsupported stage")
    url = result.get("announcement_url")
    if url:
        parts = urlsplit(url)
        if (
            parts.scheme not in {"https", "http"}
            or not parts.hostname
            or parts.username
            or parts.password
        ):
            raise ValueError("announcement must be a public http(s) URL without credentials")
    if result.get("payment_date") and not url:
        raise ValueError("payment date requires announcement evidence URL")
    if result.get("record_date") and result.get("ex_date"):
        if result["record_date"] >= result["ex_date"]:
            raise ValueError("record date must precede ex date")
    if result.get("payment_date") and result.get("record_date"):
        if result["payment_date"] <= result["record_date"]:
            raise ValueError("payment date must follow record date")
    reasons = [f"unknown_{field}" for field in DATE_FIELDS if not result.get(field)]
    if result.get("cash_per_share") is None:
        reasons.append("unknown_cash_amount")
    if result["stage"] == "unknown":
        reasons.append("unknown_stage")
    if not result.get("payment_date"):
        reasons.append("payment_date_unverified")
    if not url:
        reasons.append("announcement_unverified")
    reasons.append("corporate_action_unverified")
    result["review_reasons"] = reasons
    result["rule_version"] = RULE_VERSION
    return result


def review_observation(
    session: Session, observation_id: str, *, reviewer_id: int, decision: dict
) -> tuple[DividendSourceObservation, DividendEventVersion | None]:
    """Explicit create/revise/ignore, with optimistic revision and replay protection."""
    probe = session.get(DividendSourceObservation, observation_id)
    if probe is None:
        raise LookupError("observation not found")
    lock_stock(session, probe.code)
    row = session.scalar(
        select(DividendSourceObservation)
        .where(
            DividendSourceObservation.id == observation_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    decision_hash = hashlib.sha256(
        json.dumps(
            decision,
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    if row.state != "pending":
        if row.decision_hash != decision_hash:
            raise ReviewConflict("observation already resolved differently")
        version = (
            session.get(DividendEventVersion, (row.event_id, row.applied_revision))
            if row.applied_revision
            else None
        )
        return row, version
    action = decision["action"]
    if len(decision["note"].strip()) < 8:
        raise ValueError("review note must explain the evidence")
    version = None
    if action == "ignore":
        if decision.get("event_id") or decision.get("patch") or decision["expected_revision"] != 0:
            raise ValueError("ignore cannot modify an event")
        row.state = "ignored"
    else:
        data = _reviewed_data(row.normalized, decision.get("patch") or {})
        if action == "create":
            if decision.get("event_id") or decision["expected_revision"] != 0:
                raise ValueError("new event requires revision 0 and no event ID")
            event = DividendEvent(
                id=str(uuid4()), code=row.code, origin="reviewed_observation", current_revision=1
            )
            session.add(event)
            session.flush()
        elif action == "revise":
            event = session.scalar(
                select(DividendEvent)
                .where(
                    DividendEvent.id == decision.get("event_id"),
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if event is None or event.code != row.code:
                raise ValueError("event and observation must refer to the same stock")
            if event.current_revision != decision["expected_revision"]:
                raise ReviewConflict("event revision changed; reload before reviewing")
            previous = session.get(DividendEventVersion, (event.id, event.current_revision))
            notice = date.fromisoformat(data["notice_date"]) if data.get("notice_date") else None
            if previous.notice_date and (notice is None or notice < previous.notice_date):
                if not decision.get("allow_older_evidence", False):
                    raise ReviewConflict("older or undated evidence requires explicit override")
            event.current_revision += 1
        else:
            raise ValueError("unknown review action")
        version = _version(
            data,
            event=event,
            observation=row,
            reviewer_id=reviewer_id,
            note=decision["note"],
            raw=row.raw_payload,
            observed_at=row.observed_at,
            evidence_status="reviewed",
            source=row.source,
            source_url=row.source_url,
        )
        session.add(version)
        row.event_id, row.applied_revision = event.id, event.current_revision
        row.state = "applied"
    row.decision_hash = decision_hash
    row.reviewed_by = reviewer_id
    row.reviewed_at = datetime.now(UTC)
    row.review_note = decision["note"]
    session.add(
        AdminAuditLog(
            user_id=reviewer_id,
            action="dividend_review",
            target_type="dividend_observation",
            target_id=row.id,
            detail={
                "decision": decision,
                "event_id": row.event_id,
                "revision": row.applied_revision,
            },
        )
    )
    session.flush()
    return row, version

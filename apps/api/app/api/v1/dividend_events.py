from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import (
    DividendEvent,
    DividendEventVersion,
    DividendSourceObservation,
    Instrument,
    StockProfile,
    User,
)
from app.security import get_current_admin
from app.services.dividend_events import ReviewConflict, review_observation

router = APIRouter(prefix="/stocks", tags=["dividend-events"])
admin_router = APIRouter(prefix="/admin/stocks", tags=["admin-dividend-events"])
STAGE = Literal["unknown", "proposed", "approved", "implemented", "cancelled", "no_distribution"]


class ReviewPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report_date: date | None = None
    record_date: date | None = None
    ex_date: date | None = None
    payment_date: date | None = None
    cash_per_share: Annotated[
        Decimal | None, Field(ge=0, lt=10**12, max_digits=20, decimal_places=8)
    ] = None
    announcement_url: Annotated[HttpUrl | None, Field(max_length=2048)] = None
    stage: STAGE = "unknown"


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["create", "revise", "ignore"]
    event_id: Annotated[str | None, Field(min_length=36, max_length=36)] = None
    expected_revision: Annotated[int, Field(ge=0)]
    note: Annotated[str, Field(min_length=8, max_length=2000)]
    patch: ReviewPatch = Field(default_factory=ReviewPatch)
    allow_older_evidence: bool = False


def version_out(version: DividendEventVersion) -> dict:
    return {
        "event_id": version.event_id,
        "revision": version.revision,
        **{
            field: getattr(version, field)
            for field in (
                "source",
                "source_url",
                "source_event_id",
                "announcement_url",
                "report_date",
                "notice_date",
                "plan_notice_date",
                "record_date",
                "ex_date",
                "payment_date",
                "plan",
                "progress",
                "stage",
                "evidence_status",
                "review_reasons",
                "rule_version",
                "observed_at",
                "created_at",
            )
        },
        # Keep decimal precision; this is a NEW API, old numeric contract is unchanged.
        "cash_per_share": str(version.cash_per_share)
        if version.cash_per_share is not None
        else None,
        "automatic_entitlement_allowed": False,
        "automatic_receipt_allowed": False,
    }


def visible_stock(session: Session, code: str) -> None:
    if (
        session.scalar(
            select(Instrument.code)
            .join(
                StockProfile,
                StockProfile.code == Instrument.code,
            )
            .where(
                Instrument.code == code,
                Instrument.type == "stock",
                StockProfile.status != "excluded",
            )
        )
        is None
    ):
        raise HTTPException(404, "stock not found")


@router.get("/{code}/dividend-events", summary="分红事件当前版本（非个人应收）")
def list_events(
    code: str,
    session: Annotated[Session, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    visible_stock(session, code)
    total = (
        session.scalar(
            select(func.count())
            .select_from(DividendEvent)
            .where(
                DividendEvent.code == code,
            )
        )
        or 0
    )
    rows = session.execute(
        select(DividendEvent, DividendEventVersion)
        .join(
            DividendEventVersion,
            (DividendEventVersion.event_id == DividendEvent.id)
            & (DividendEventVersion.revision == DividendEvent.current_revision),
        )
        .where(DividendEvent.code == code)
        .order_by(
            DividendEvent.created_at.desc(),
            DividendEvent.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    pending = (
        session.scalar(
            select(func.count())
            .select_from(DividendSourceObservation)
            .where(
                DividendSourceObservation.code == code,
                DividendSourceObservation.state == "pending",
            )
        )
        or 0
    )
    return {
        "pending_observations": pending,
        "items": [
            {
                "code": event.code,
                "origin": event.origin,
                "legacy_dividend_id": event.legacy_dividend_id,
                **version_out(version),
            }
            for event, version in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "automatic_entitlement_allowed": False,
        "automatic_receipt_allowed": False,
    }


@router.get("/{code}/dividend-events/{event_id}/versions", summary="分红事件修订历史")
def event_versions(
    code: str,
    event_id: str,
    session: Annotated[Session, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    visible_stock(session, code)
    event = session.get(DividendEvent, event_id)
    if event is None or event.code != code:
        raise HTTPException(404, "event not found")
    query = select(DividendEventVersion).where(DividendEventVersion.event_id == event_id)
    rows = session.scalars(
        query.order_by(DividendEventVersion.revision.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [version_out(row) for row in rows],
        "total": event.current_revision,
        "page": page,
        "page_size": page_size,
    }


@admin_router.get("/dividend-observations", summary="分红来源待核对队列")
def observations(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(get_current_admin)],
    response: Response,
    state: Literal["pending", "applied", "ignored"] = "pending",
    code: str | None = Query(None, pattern=r"^\d{6}$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    response.headers["Cache-Control"] = "private, no-store"
    conditions = [DividendSourceObservation.state == state]
    if code:
        conditions.append(DividendSourceObservation.code == code)
    total = (
        session.scalar(
            select(func.count()).select_from(DividendSourceObservation).where(*conditions)
        )
        or 0
    )
    rows = session.scalars(
        select(DividendSourceObservation)
        .where(*conditions)
        .order_by(
            DividendSourceObservation.observed_at.desc(),
            DividendSourceObservation.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [
            {
                "id": row.id,
                "code": row.code,
                "source": row.source,
                "state": row.state,
                "normalized": row.normalized,
                "source_url": row.source_url,
                "observed_at": row.observed_at,
                "event_id": row.event_id,
                "applied_revision": row.applied_revision,
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@admin_router.get("/dividend-observations/{observation_id}", summary="分红来源原始证据")
def observation_detail(
    observation_id: str,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(get_current_admin)],
    response: Response,
) -> dict:
    response.headers["Cache-Control"] = "private, no-store"
    row = session.get(DividendSourceObservation, observation_id)
    if row is None:
        raise HTTPException(404, "observation not found")
    return {
        "id": row.id,
        "code": row.code,
        "source": row.source,
        "state": row.state,
        "normalized": row.normalized,
        "raw_payload": row.raw_payload,
        "source_url": row.source_url,
        "observed_at": row.observed_at,
        "review_note": row.review_note,
        "reviewed_at": row.reviewed_at,
        "event_id": row.event_id,
        "applied_revision": row.applied_revision,
    }


@admin_router.post(
    "/dividend-observations/{observation_id}/review", summary="人工确认分红事件或修订"
)
def review(
    observation_id: str,
    body: ReviewDecision,
    session: Annotated[Session, Depends(get_session)],
    admin: Annotated[User, Depends(get_current_admin)],
    response: Response,
) -> dict:
    response.headers["Cache-Control"] = "private, no-store"
    decision = body.model_dump(mode="json")
    decision["patch"] = body.patch.model_dump(mode="json", exclude_unset=True)
    try:
        row, version = review_observation(
            session,
            observation_id,
            reviewer_id=admin.id,
            decision=decision,
        )
        session.commit()
    except (LookupError, ValueError) as exc:
        session.rollback()
        status = (
            404 if isinstance(exc, LookupError) else 409 if isinstance(exc, ReviewConflict) else 422
        )
        raise HTTPException(status, str(exc)) from exc
    return {
        "observation_id": row.id,
        "state": row.state,
        "version": version_out(version) if version else None,
    }

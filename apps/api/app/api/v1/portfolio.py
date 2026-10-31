from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import PortfolioAccount, User
from app.security import get_current_user
from app.services.portfolio import (
    POLICY,
    POLICY_SHA256,
    PortfolioError,
    account_out,
    create_account,
    delete_account,
    enabled_for,
    export_portfolio,
    update_account,
)
from app.services.rate_limit import check_rate_limit, rate_limit_key


class PrivateRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handle(request: Request):
            try:
                response = await original(request)
            except RequestValidationError:
                # Never echo submitted names/bodies back into generic error/telemetry paths.
                response = JSONResponse(
                    {
                        "detail": {
                            "code": "invalid_request",
                            "message": "输入格式有误，请检查字段与确认选项",
                        }
                    },
                    status_code=422,
                )
            except PortfolioError as exc:
                response = JSONResponse(
                    {"detail": {"code": exc.code, "message": exc.message}}, status_code=exc.status
                )
            except HTTPException as exc:
                response = JSONResponse(
                    {"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers
                )
            except Exception as exc:  # noqa: BLE001 - redact private SQL/input exception details
                logging.getLogger(__name__).error(
                    "portfolio_request_failed error_type=%s", type(exc).__name__
                )
                response = JSONResponse(
                    {"detail": {"code": "internal_error", "message": "服务暂不可用，请稍后重试"}},
                    status_code=500,
                )
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["Pragma"] = "no-cache"
            response.headers["Vary"] = "Authorization, Cookie"
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
            return response

        return handle


router = APIRouter(prefix="/portfolio", tags=["private-portfolio"], route_class=PrivateRoute)


class Consent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accepted: StrictBool

    @field_validator("accepted")
    @classmethod
    def explicit_acceptance(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("explicit acknowledgement required")
        return value

    version: Annotated[str, Field(min_length=1, max_length=64)]
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class CreateAccount(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, Field(min_length=1, max_length=40)]
    currency: Literal["CNY"] = "CNY"
    consent: Consent


class UpdateAccount(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: Annotated[int, Field(ge=1)]
    name: Annotated[str | None, Field(min_length=1, max_length=40)] = None
    is_archived: StrictBool | None = None

    @model_validator(mode="after")
    def valid_changes(self):
        fields = self.model_fields_set - {"expected_version"}
        if not fields or any(getattr(self, field) is None for field in fields):
            raise ValueError("supply a non-null account change")
        return self


class DeleteAccount(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: Annotated[int, Field(ge=1)]
    confirmation: Literal["DELETE"]


SessionDep = Annotated[Session, Depends(get_session)]
UserDep = Annotated[User, Depends(get_current_user)]


def write_limit(session: Session, user_id: int, *, export: bool = False) -> None:
    check_rate_limit(
        session,
        key=rate_limit_key("portfolio_export" if export else "portfolio_write", str(user_id)),
        limit=10 if export else 30,
        window_seconds=60,
    )


def commit_mutation(session: Session, action):
    try:
        result = action()
        session.commit()
        return result
    except PortfolioError:
        session.rollback()
        raise
    except IntegrityError as exc:
        session.rollback()
        raise PortfolioError("account_conflict", "账户信息发生冲突，请刷新后重试") from exc


@router.get("/policy", summary="私人账本说明的当前版本和文本摘要")
def policy() -> dict:
    return {"policy": POLICY, "sha256": POLICY_SHA256}


@router.get("/accounts", summary="只列出本人账本，不自动创建")
def accounts(session: SessionDep, user: UserDep) -> dict:
    rows = session.scalars(
        select(PortfolioAccount).where(PortfolioAccount.user_id == user.id)
    ).all()
    return {
        "items": [account_out(row) for row in rows],
        "create_enabled": enabled_for(user.id),
        "account_limit": 1,
        "scope": "holdings_and_trades_v2_51",
        "capabilities": {"positions": True, "trades": True, "automatic_dividends": False},
    }


@router.post("/accounts", status_code=201, summary="主动确认说明后创建本人单账户")
def create(body: CreateAccount, session: SessionDep, user: UserDep) -> dict:
    write_limit(session, user.id)
    account = commit_mutation(
        session,
        lambda: create_account(
            session,
            user.id,
            body.name,
            body.consent.model_dump(),
        ),
    )
    return account_out(account)


@router.get("/accounts/{account_id}", summary="本人账本信息")
def detail(account_id: str, session: SessionDep, user: UserDep) -> dict:
    from app.services.portfolio import own_account

    return account_out(own_account(session, user.id, account_id))


@router.patch("/accounts/{account_id}", summary="维护本人账本，不依赖会员")
def update(account_id: str, body: UpdateAccount, session: SessionDep, user: UserDep) -> dict:
    write_limit(session, user.id)
    account = commit_mutation(
        session,
        lambda: update_account(
            session,
            user.id,
            account_id,
            body.expected_version,
            body.model_dump(exclude_unset=True, exclude={"expected_version"}),
        ),
    )
    return account_out(account)


@router.delete("/accounts/{account_id}", summary="明确确认后删除本人账本和关联操作记录")
def remove(account_id: str, body: DeleteAccount, session: SessionDep, user: UserDep) -> dict:
    write_limit(session, user.id)
    commit_mutation(
        session,
        lambda: delete_account(
            session,
            user.id,
            account_id,
            body.expected_version,
        ),
    )
    return {"deleted": True, "retained": "minimal_privacy_acknowledgement_and_deletion_marker"}


@router.get("/export", summary="免费导出本人账户、持仓流水、冲正及说明确认")
def export(session: SessionDep, user: UserDep) -> JSONResponse:
    write_limit(session, user.id, export=True)
    data = export_portfolio(session, user.id)
    return JSONResponse(
        jsonable_encoder(data),
        headers={
            "Content-Disposition": 'attachment; filename="stocklab-portfolio.json"',
            "Content-Type": "application/json; charset=utf-8",
        },
    )


class AcceptLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: Annotated[int, Field(strict=True, ge=1)]
    consent: Consent


class CreateEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: Annotated[int, Field(strict=True, ge=1)]
    request_id: UUID
    code: Annotated[str, Field(pattern=r"^[0-9]{6}$")]
    kind: Literal["opening", "buy", "sell", "adjustment", "reversal", "bonus", "reinvest"]
    event_date: date
    day_order: Annotated[int, Field(strict=True, ge=1, le=1000000)]
    quantity: Annotated[str, Field(max_length=19)]
    price: Annotated[str, Field(max_length=19)] = "0"
    fees: Annotated[str, Field(max_length=19)] = "0"
    total_cost: Annotated[str, Field(max_length=19)] = "0"
    history_status: Literal["since_date", "incomplete"]
    note: Annotated[str, Field(max_length=500)] = ""
    evidence: Annotated[str, Field(max_length=500)] = ""
    reverses_id: UUID | None = None

    @model_validator(mode="after")
    def explicit_opening_cost(self):
        if self.kind in {"opening", "adjustment"} and "total_cost" not in self.model_fields_set:
            raise ValueError("explicit balance cost required")
        return self

    @field_validator("event_date", mode="before")
    @classmethod
    def calendar_date_only(cls, value):
        import re

        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("calendar date required")
        return value


@router.post("/accounts/{account_id}/consent", summary="再次主动确认持仓交易数据范围")
def ledger_consent(account_id: str, body: AcceptLedger, session: SessionDep, user: UserDep):
    from app.services.portfolio_ledger import accept_ledger

    write_limit(session, user.id)
    return commit_mutation(
        session,
        lambda: accept_ledger(
            session, user.id, account_id, body.expected_version, body.consent.model_dump()
        ),
    )


@router.get("/accounts/{account_id}/ledger", summary="本人有效持仓、原始流水及冲正历史")
def ledger(account_id: str, session: SessionDep, user: UserDep):
    from app.services.portfolio_ledger import ledger_snapshot

    return ledger_snapshot(session, user.id, account_id)


@router.post("/accounts/{account_id}/entries", status_code=201, summary="录入或关联冲正后完整重算")
def entry(account_id: str, body: CreateEntry, session: SessionDep, user: UserDep):
    from app.services.portfolio_ledger import add_entry

    write_limit(session, user.id)
    return commit_mutation(
        session, lambda: add_entry(session, user.id, account_id, body.model_dump(mode="json"))
    )


class ReceiptInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: Annotated[int, Field(strict=True, ge=1)]
    request_id: UUID
    entitlement_id: Annotated[str | None, Field(max_length=36)] = None
    code: Annotated[str, Field(pattern=r"^[0-9]{6}$")]
    received_date: date
    net_amount: Annotated[str, Field(max_length=20)]
    gross_amount: Annotated[str | None, Field(max_length=20)] = None
    tax_amount: Annotated[str | None, Field(max_length=20)] = None
    note: Annotated[str, Field(max_length=500)] = ""

    @field_validator("received_date", mode="before")
    @classmethod
    def calendar_date_only(cls, value):
        return CreateEntry.calendar_date_only(value)


class ReverseReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: Annotated[int, Field(strict=True, ge=1)]


@router.get("/accounts/{account_id}/income", summary="本人应收与实收汇总")
def income(account_id: str, session: SessionDep, user: UserDep):
    from app.services.portfolio_income import income_snapshot

    return income_snapshot(session, user.id, account_id)


@router.get("/accounts/{account_id}/income/home", summary="收息首页与分红日历")
def income_home(
    account_id: str,
    session: SessionDep,
    user: UserDep,
    year: int | None = None,
):
    from app.services.portfolio_income import income_home as home

    target = year or datetime.now(UTC).year
    return home(session, user.id, account_id, target)


@router.post("/accounts/{account_id}/income/refresh", summary="按已核对事件重算应收")
def income_refresh(account_id: str, session: SessionDep, user: UserDep):
    from app.services.portfolio_income import sync_entitlements

    write_limit(session, user.id)
    result = commit_mutation(
        session, lambda: sync_entitlements(session, user.id, account_id)
    )
    return result


@router.post("/accounts/{account_id}/receipts", status_code=201, summary="登记实际到账")
def add_receipt(
    account_id: str, body: ReceiptInput, session: SessionDep, user: UserDep
):
    from app.services.portfolio_income import create_receipt

    write_limit(session, user.id)
    return commit_mutation(
        session,
        lambda: create_receipt(
            session,
            user.id,
            account_id,
            expected_version=body.expected_version,
            request_id=str(body.request_id),
            entitlement_id=body.entitlement_id,
            code=body.code,
            received_date=body.received_date,
            net_amount=body.net_amount,
            gross_amount=body.gross_amount,
            tax_amount=body.tax_amount,
            note=body.note,
        ),
    )


@router.post(
    "/accounts/{account_id}/receipts/{receipt_id}/reverse",
    summary="撤销实际到账记录，保留审计链",
)
def reverse_receipt(
    account_id: str,
    receipt_id: str,
    body: ReverseReceipt,
    session: SessionDep,
    user: UserDep,
):
    from app.services.portfolio_income import reverse_receipt as reverse

    write_limit(session, user.id)
    return commit_mutation(
        session,
        lambda: reverse(
            session,
            user.id,
            account_id,
            receipt_id,
            expected_version=body.expected_version,
        ),
    )


class PositionPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    basis: Literal["weighted", "net", "dividend", "unknown"] = "weighted"
    group: Annotated[str, Field(max_length=40)] = ""
    forecast: Literal["skip", "12", "36", "60", "custom"] = "skip"
    custom: Annotated[str | None, Field(max_length=19)] = None


class PositionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: Annotated[int, Field(strict=True, ge=1)]
    request_id: UUID
    code: Annotated[str, Field(pattern=r"^[0-9]{6}$")]
    kind: Literal[
        "snapshot",
        "buy",
        "sell",
        "opening",
        "adjustment",
        "reversal",
        "preference",
        "rebase",
        "bonus",
        "reinvest",
    ]
    event_date: date
    quantity: Annotated[str, Field(max_length=19)] = "0"
    cost: Annotated[str, Field(max_length=20)] = "0"
    input_mode: Literal["per_share", "total"] = "per_share"
    basis: Literal["weighted", "net", "dividend", "unknown"] = "weighted"
    fees: Annotated[str | None, Field(max_length=19)] = None
    preferences: PositionPreferences = Field(default_factory=PositionPreferences)
    day_order: Annotated[int | None, Field(strict=True, ge=1, le=1000000)] = None
    note: Annotated[str, Field(max_length=500)] = ""
    evidence: Annotated[str, Field(max_length=500)] = ""
    reverses_id: UUID | None = None

    @field_validator("event_date", mode="before")
    @classmethod
    def calendar_date_only(cls, value):
        return CreateEntry.calendar_date_only(value)

    @model_validator(mode="after")
    def explicit_baseline(self):
        if self.kind in {"snapshot", "rebase", "opening", "adjustment"} and not {
            "quantity",
            "cost",
            "basis",
        }.issubset(self.model_fields_set):
            raise ValueError("baseline quantity, cost and basis must be explicit")
        if self.kind in {"buy", "sell"} and self.input_mode != "per_share":
            raise ValueError("trade price must be per share")
        return self


class ConfirmPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entry: PositionInput
    preview_token: Annotated[str, Field(min_length=1, max_length=2048)]


class StockSearch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: Annotated[str, Field(max_length=64)]


@router.post("/accounts/{account_id}/stock-search", summary="按名称或代码搜索全部已收录A股")
def position_search(account_id: str, body: StockSearch, session: SessionDep, user: UserDep):
    from app.services.portfolio_positions import search

    return search(session, user.id, account_id, body.query)


@router.get("/accounts/{account_id}/holdings", summary="本人持仓、多口径成本和分红参考")
def position_list(account_id: str, session: SessionDep, user: UserDep):
    from app.services.portfolio_positions import holdings

    return holdings(session, user.id, account_id)


@router.post("/accounts/{account_id}/position-preview", summary="只试算，不保存持仓")
def position_preview(account_id: str, body: PositionInput, session: SessionDep, user: UserDep):
    from app.services.portfolio_positions import preview

    return preview(session, user.id, account_id, body.model_dump(mode="json"))


@router.post(
    "/accounts/{account_id}/position-confirm",
    status_code=201,
    summary="核验预览版本后幂等保存持仓或交易",
)
def position_confirm(account_id: str, body: ConfirmPosition, session: SessionDep, user: UserDep):
    from app.services.portfolio_positions import confirm

    write_limit(session, user.id)
    return commit_mutation(
        session,
        lambda: confirm(
            session, user.id, account_id, body.entry.model_dump(mode="json"), body.preview_token
        ),
    )

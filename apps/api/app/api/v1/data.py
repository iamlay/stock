from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_session
from app.services.status import collect_status

router = APIRouter(prefix="/data", tags=["data"])


class LastJob(BaseModel):
    id: int
    name: str
    status: str
    rows: int
    finished_at: str | None


class DataStatus(BaseModel):
    instruments: int
    etf_profiles: int
    daily_bars: int
    latest_trade_date: str | None
    failed_quality_checks: int
    last_job: LastJob | None


@router.get("/status", response_model=DataStatus, summary="数据管道状态")
def data_status(session: Annotated[Session, Depends(get_session)]) -> DataStatus:
    return DataStatus(**collect_status(session))

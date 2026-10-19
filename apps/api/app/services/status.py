from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    DataJob,
    DataQualityCheck,
    EtfProfile,
    Instrument,
    MarketDaily,
)


def collect_status(session: Session) -> dict:
    instruments = session.scalar(select(func.count()).select_from(Instrument)) or 0
    profiles = session.scalar(select(func.count()).select_from(EtfProfile)) or 0
    bars = session.scalar(select(func.count()).select_from(MarketDaily)) or 0
    latest = session.scalar(select(func.max(MarketDaily.trade_date)))
    failed_checks = (
        session.scalar(
            select(func.count())
            .select_from(DataQualityCheck)
            .where(DataQualityCheck.status == "fail")
        )
        or 0
    )
    last_job = session.scalars(select(DataJob).order_by(DataJob.id.desc()).limit(1)).first()

    return {
        "instruments": instruments,
        "etf_profiles": profiles,
        "daily_bars": bars,
        "latest_trade_date": latest.isoformat() if latest else None,
        "failed_quality_checks": failed_checks,
        "last_job": (
            {
                "id": last_job.id,
                "name": last_job.job_name,
                "status": last_job.status,
                "rows": last_job.rows_written,
                "finished_at": last_job.finished_at.isoformat() if last_job.finished_at else None,
            }
            if last_job
            else None
        ),
    }

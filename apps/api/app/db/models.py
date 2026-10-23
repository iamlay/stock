from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Instrument(TimestampMixin, Base):
    __tablename__ = "instruments"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False, default="etf")
    exchange: Mapped[str] = mapped_column(String(8), nullable=False)
    lot_size: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    listed_on: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class EtfProfile(TimestampMixin, Base):
    __tablename__ = "etf_profiles"

    code: Mapped[str] = mapped_column(
        String(16), ForeignKey("instruments.code", ondelete="CASCADE"), primary_key=True
    )
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    tracked_index: Mapped[str | None] = mapped_column(String(64))
    valuation_index: Mapped[str | None] = mapped_column(String(16))
    manager: Mapped[str | None] = mapped_column(String(64))
    fee_rate: Mapped[float | None] = mapped_column(Numeric(6, 4))
    inception_date: Mapped[date | None] = mapped_column(Date)
    extra: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)


class IndexValuation(Base):
    __tablename__ = "index_valuation"
    __table_args__ = (Index("ix_index_valuation_trade_date", "trade_date"),)

    index_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    pe: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    pb: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    pe_percentile: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    pb_percentile: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    dividend_yield: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    bond_yield: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="danjuan")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TradingCalendar(Base):
    __tablename__ = "trading_calendar"

    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="eastmoney")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MarketDaily(Base):
    __tablename__ = "market_daily"
    __table_args__ = (Index("ix_market_daily_trade_date", "trade_date"),)

    code: Mapped[str] = mapped_column(
        String(16), ForeignKey("instruments.code", ondelete="CASCADE"), primary_key=True
    )
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    prev_close: Mapped[float | None] = mapped_column(Numeric(12, 4))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    amplitude: Mapped[float | None] = mapped_column(Numeric(8, 4))
    adj_factor: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=1)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="eastmoney")
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RealtimeQuote(Base):
    __tablename__ = "realtime_quotes"

    code: Mapped[str] = mapped_column(
        String(16), ForeignKey("instruments.code", ondelete="CASCADE"), primary_key=True
    )
    price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    prev_close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    change_pct: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    quote_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="tencent")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class EtfShareDaily(Base):
    __tablename__ = "etf_share_daily"
    __table_args__ = (Index("ix_etf_share_daily_trade_date", "trade_date"),)

    code: Mapped[str] = mapped_column(
        String(16), ForeignKey("instruments.code", ondelete="CASCADE"), primary_key=True
    )
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    shares: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    aum: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    change_pct: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="tencent")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DataJob(Base):
    __tablename__ = "data_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    params: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    rows_written: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DataQualityCheck(Base):
    __tablename__ = "data_quality_checks"
    __table_args__ = (Index("ix_data_quality_checks_job_id", "job_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("data_jobs.id", ondelete="CASCADE")
    )
    check_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone: Mapped[str | None] = mapped_column(
        String(20), nullable=True, unique=True, index=True
    )
    email: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    password_hash: Mapped[str | None] = mapped_column(String(255))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="member")
    plan: Mapped[str] = mapped_column(String(16), nullable=False, default="free")
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    alert_price_pct: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False, default=5, server_default="5"
    )
    alert_dividend: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    alert_email: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    alert_grid: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    alert_grid_yield: Mapped[float] = mapped_column(
        Numeric(4, 2), nullable=False, default=5, server_default="5"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaymentOrder(Base):
    __tablename__ = "payment_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    external_order_id: Mapped[str | None] = mapped_column(String(64), index=True)
    buyer_phone: Mapped[str | None] = mapped_column(String(20))
    buyer_email: Mapped[str | None] = mapped_column(String(255), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    product: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="delivered")
    note: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RedeemCode(Base):
    __tablename__ = "redeem_codes"
    __table_args__ = (Index("ix_redeem_codes_status", "status"),)

    code: Mapped[str] = mapped_column(String(24), primary_key=True)
    plan: Mapped[str] = mapped_column(String(16), nullable=False, default="member")
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365)
    batch_id: Mapped[str | None] = mapped_column(String(36))
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bound_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_orders.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="issued")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    redeemed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class RateLimitEvent(Base):
    __tablename__ = "rate_limit_events"
    __table_args__ = (Index("ix_rate_limit_key_created", "key", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class InviteCode(Base):
    __tablename__ = "invite_codes"
    __table_args__ = (Index("ix_invite_codes_status", "status"),)

    code: Mapped[str] = mapped_column(String(24), primary_key=True)
    batch_id: Mapped[str | None] = mapped_column(String(36))
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bound_email: Mapped[str | None] = mapped_column(String(255), index=True)
    bound_phone: Mapped[str | None] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="issued")
    note: Mapped[str | None] = mapped_column(String(128))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class InviteUsage(Base):
    __tablename__ = "invite_code_usages"
    __table_args__ = (Index("ix_invite_usages_code_created", "code", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(
        ForeignKey("invite_codes.code", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20))
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("user_id", "code", name="uq_watchlist_user_code"),
        Index("ix_watchlist_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserNotification(Base):
    __tablename__ = "user_notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_user_dedupe"),
        Index("ix_notifications_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(String(256))
    dedupe_key: Mapped[str] = mapped_column(String(128), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"
    __table_args__ = (Index("ix_admin_audit_logs_created", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    __table_args__ = (
        Index("ix_backtest_runs_user_created", "user_id", "created_at"),
        Index("ix_backtest_runs_client_created", "client_key", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    client_key: Mapped[str | None] = mapped_column(String(64))
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    strategy: Mapped[str] = mapped_column(String(32), nullable=False)
    params: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    initial_cash: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="success")
    metrics: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    result: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StockProfile(TimestampMixin, Base):
    __tablename__ = "stock_profiles"

    code: Mapped[str] = mapped_column(
        String(16), ForeignKey("instruments.code", ondelete="CASCADE"), primary_key=True
    )
    industry: Mapped[str | None] = mapped_column(String(32))
    industry_path: Mapped[str | None] = mapped_column(String(128))
    industry_source: Mapped[str | None] = mapped_column(String(16))
    market: Mapped[str | None] = mapped_column(String(16))
    is_st: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    list_date: Mapped[date | None] = mapped_column(Date)
    total_shares: Mapped[float | None] = mapped_column(Numeric(20, 4))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")


class StockDividend(Base):
    __tablename__ = "stock_dividends"
    __table_args__ = (
        UniqueConstraint("code", "ex_date", "plan", name="uq_stock_dividends_code_ex_plan"),
        Index("ix_stock_dividends_code_ex", "code", "ex_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(
        String(16), ForeignKey("instruments.code", ondelete="CASCADE"), nullable=False
    )
    ex_date: Mapped[date] = mapped_column(Date, nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    cash_per_share: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    plan: Mapped[str] = mapped_column(String(128), nullable=False)
    is_special: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_one_off: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="eastmoney")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StockFinancial(Base):
    __tablename__ = "stock_financials"
    __table_args__ = (
        UniqueConstraint("code", "report_date", name="uq_stock_financials_code_report"),
        Index("ix_stock_financials_code_report", "code", "report_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(
        String(16), ForeignKey("instruments.code", ondelete="CASCADE"), nullable=False
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    period: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    revenue: Mapped[float | None] = mapped_column(Numeric(20, 2))
    net_profit: Mapped[float | None] = mapped_column(Numeric(20, 2))
    revenue_yoy: Mapped[float | None] = mapped_column(Numeric(10, 2))
    net_profit_yoy: Mapped[float | None] = mapped_column(Numeric(10, 2))
    disclosure_date: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="eastmoney")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StockMetric(Base):
    __tablename__ = "stock_metrics"
    __table_args__ = (
        Index("ix_stock_metrics_yield", "dividend_yield_ttm"),
        Index("ix_stock_metrics_market_cap", "market_cap"),
    )

    code: Mapped[str] = mapped_column(
        String(16), ForeignKey("instruments.code", ondelete="CASCADE"), primary_key=True
    )
    price: Mapped[float | None] = mapped_column(Numeric(12, 4))
    change_pct: Mapped[float | None] = mapped_column(Numeric(8, 4))
    market_cap: Mapped[float | None] = mapped_column(Numeric(18, 2))
    pe_ttm: Mapped[float | None] = mapped_column(Numeric(12, 4))
    pb: Mapped[float | None] = mapped_column(Numeric(12, 4))
    dividend_yield_ttm: Mapped[float | None] = mapped_column(Numeric(8, 4))
    dividend_yield_fy: Mapped[float | None] = mapped_column(Numeric(8, 4))
    sustainability: Mapped[str | None] = mapped_column(String(16))
    last_ex_date: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class StockWatchlist(TimestampMixin, Base):
    __tablename__ = "stock_watchlist"
    __table_args__ = (UniqueConstraint("user_id", "code", name="uq_stock_watchlist_user_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(
        String(16), ForeignKey("instruments.code", ondelete="CASCADE"), nullable=False
    )

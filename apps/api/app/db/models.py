from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
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


class StockRealtimeQuote(Base):
    __tablename__ = "stock_realtime_quotes"

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
    trial_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entitlement_source: Mapped[str | None] = mapped_column(String(32))
    # Deliberately not a stock FK: deleting a stock must not reset preview consumption.
    advanced_preview_code: Mapped[str | None] = mapped_column(String(16))
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
    alert_resonance: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
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
    group_name: Mapped[str] = mapped_column(
        String(32), nullable=False, default="默认", server_default="默认"
    )
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
    ex_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notice_date: Mapped[date | None] = mapped_column(Date)
    report_date: Mapped[date | None] = mapped_column(Date)
    progress: Mapped[str] = mapped_column(String(32), nullable=False, default="")
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
    roe: Mapped[float | None] = mapped_column(Numeric(8, 2))
    operating_cash_flow_per_share: Mapped[float | None] = mapped_column(
        Numeric(12, 4)
    )
    operating_cash_flow: Mapped[float | None] = mapped_column(Numeric(20, 2))
    gross_margin: Mapped[float | None] = mapped_column(Numeric(8, 2))
    net_margin: Mapped[float | None] = mapped_column(Numeric(8, 2))
    total_assets: Mapped[float | None] = mapped_column(Numeric(20, 2))
    total_liabilities: Mapped[float | None] = mapped_column(Numeric(20, 2))
    debt_asset_ratio: Mapped[float | None] = mapped_column(Numeric(8, 2))
    roa: Mapped[float | None] = mapped_column(Numeric(8, 2))
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
    dividend_yield_ly: Mapped[float | None] = mapped_column(Numeric(8, 4))
    yield_percentile: Mapped[float | None] = mapped_column(Numeric(6, 2))
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
    group_name: Mapped[str] = mapped_column(
        String(32), nullable=False, default="默认", server_default="默认"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DividendEvent(Base):
    __tablename__ = "dividend_events"
    __table_args__ = (Index("ix_dividend_events_code", "code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(
        String(16), ForeignKey("instruments.code", ondelete="CASCADE"), nullable=False
    )
    legacy_dividend_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("stock_dividends.id", ondelete="SET NULL"), unique=True
    )
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    origin: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DividendSourceObservation(Base):
    __tablename__ = "dividend_source_observations"
    __table_args__ = (
        UniqueConstraint("source", "code", "fingerprint", name="uq_dividend_observation_content"),
        Index("ix_dividend_observations_state_code", "state", "code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(
        String(16), ForeignKey("instruments.code", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized: Mapped[dict] = mapped_column(JSONType, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONType, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    event_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("dividend_events.id", ondelete="CASCADE")
    )
    applied_revision: Mapped[int | None] = mapped_column(Integer)
    decision_hash: Mapped[str | None] = mapped_column(String(64))
    reviewed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)


class DividendEventVersion(Base):
    __tablename__ = "dividend_event_versions"

    event_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dividend_events.id", ondelete="CASCADE"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    observation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("dividend_source_observations.id", ondelete="SET NULL")
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_event_id: Mapped[str | None] = mapped_column(String(128))
    announcement_url: Mapped[str | None] = mapped_column(Text)
    report_date: Mapped[date | None] = mapped_column(Date)
    notice_date: Mapped[date | None] = mapped_column(Date)
    plan_notice_date: Mapped[date | None] = mapped_column(Date)
    record_date: Mapped[date | None] = mapped_column(Date)
    ex_date: Mapped[date | None] = mapped_column(Date)
    payment_date: Mapped[date | None] = mapped_column(Date)
    cash_per_share: Mapped[float | None] = mapped_column(Numeric(20, 8))
    plan: Mapped[str] = mapped_column(Text, nullable=False)
    progress: Mapped[str] = mapped_column(String(128), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_status: Mapped[str] = mapped_column(String(32), nullable=False)
    review_reasons: Mapped[list] = mapped_column(JSONType, nullable=False)
    rule_version: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONType, nullable=False)
    reviewed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    review_note: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PortfolioPrivacyAcceptance(Base):
    __tablename__ = "portfolio_privacy_acceptances"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "policy_version", "policy_sha256", name="uq_portfolio_acceptance"
        ),
        UniqueConstraint("id", "user_id", name="uq_portfolio_acceptance_owner"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_snapshot: Mapped[dict] = mapped_column(JSONType, nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PortfolioAccount(Base):
    __tablename__ = "portfolio_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_portfolio_single_account"),
        UniqueConstraint("id", "user_id", name="uq_portfolio_account_owner"),
        ForeignKeyConstraint(
            ["privacy_acceptance_id", "user_id"],
            ["portfolio_privacy_acceptances.id", "portfolio_privacy_acceptances.user_id"],
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    privacy_acceptance_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PortfolioAuditEvent(Base):
    __tablename__ = "portfolio_audit_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id", "user_id"], ["portfolio_accounts.id", "portfolio_accounts.user_id"],
            ondelete="CASCADE",
        ),
        Index("ix_portfolio_audit_owner", "user_id", "account_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    account_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PortfolioDeletion(Base):
    __tablename__ = "portfolio_deletions"
    __table_args__ = (Index("ix_portfolio_deletions_user", "user_id"),)

    # No account FK: this minimal record intentionally survives account removal.
    account_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PortfolioEntry(Base):
    """Append-only facts. Corrections supersede an entry; never update its financial fields."""

    __tablename__ = "portfolio_entries"
    __table_args__ = (
        UniqueConstraint("id", "account_id", "user_id", name="uq_portfolio_entry_owner"),
        UniqueConstraint("account_id", "request_id", name="uq_portfolio_entry_request"),
        UniqueConstraint("reverses_id", name="uq_portfolio_entry_reversal"),
        ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["portfolio_accounts.id", "portfolio_accounts.user_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["reverses_id", "account_id", "user_id"],
            ["portfolio_entries.id", "portfolio_entries.account_id", "portfolio_entries.user_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "quantity >= 0 AND price >= 0 AND fees >= 0 AND total_cost >= 0",
            name="ck_portfolio_entry_nonnegative",
        ),
        CheckConstraint("day_order > 0", name="ck_portfolio_entry_order"),
        CheckConstraint(
            "kind IN ('opening','buy','sell','adjustment','reversal',"
            "'snapshot','preference','rebase','bonus','reinvest')",
            name="ck_portfolio_entry_kind",
        ),
        Index("ix_portfolio_entries_owner", "user_id", "account_id", "event_date"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    code: Mapped[str] = mapped_column(ForeignKey("instruments.code"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    day_order: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fees: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    history_status: Mapped[str] = mapped_column(String(24), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    details: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    note: Mapped[str] = mapped_column(String(500), nullable=False)
    evidence: Mapped[str] = mapped_column(String(500), nullable=False)
    reverses_id: Mapped[str | None] = mapped_column(String(36))
    account_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PortfolioReviewRange(Base):
    """Durable invalidation ranges for V2-52; never represent confirmed dividend income."""

    __tablename__ = "portfolio_review_ranges"
    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["portfolio_accounts.id", "portfolio_accounts.user_id"],
            ondelete="CASCADE",
        ),
        Index("ix_portfolio_review_owner", "user_id", "account_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    account_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DividendEntitlement(Base):
    """V2-52: versioned, evidence-backed gross dividend entitlement."""

    __tablename__ = "dividend_entitlements"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "event_id", "revision", name="uq_dividend_entitlement_version"
        ),
        ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["portfolio_accounts.id", "portfolio_accounts.user_id"],
            ondelete="CASCADE",
        ),
        Index("ix_dividend_entitlements_owner", "user_id", "account_id", "is_active"),
        CheckConstraint(
            "eligible_quantity >= 0 AND cash_per_share >= 0 AND gross_amount >= 0",
            name="ck_dividend_entitlement_nonnegative",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    event_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dividend_events.id", ondelete="CASCADE"), nullable=False
    )
    event_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    account_version: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_date: Mapped[date | None] = mapped_column(Date)
    eligible_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    cash_per_share: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    calculation_version: Mapped[str] = mapped_column(String(32), nullable=False)
    review_reasons: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DividendReceipt(Base):
    """V2-53: user-confirmed actual dividend cash. Reversal is append-only audit, not delete."""

    __tablename__ = "dividend_receipts"
    __table_args__ = (
        UniqueConstraint("account_id", "request_id", name="uq_dividend_receipt_request"),
        ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["portfolio_accounts.id", "portfolio_accounts.user_id"],
            ondelete="CASCADE",
        ),
        Index("ix_dividend_receipts_owner", "user_id", "account_id", "received_date"),
        CheckConstraint(
            "net_amount > 0 AND (gross_amount IS NULL OR gross_amount >= 0)",
            name="ck_dividend_receipt_amount",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    entitlement_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("dividend_entitlements.id", ondelete="SET NULL")
    )
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    cash_per_share: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    gross_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    net_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    note: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

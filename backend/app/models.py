from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

MONEY = Numeric(28, 12)
QUANTITY = Numeric(20, 4)


class ModernTrade(Base):
    __tablename__ = "modern_trades"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    vat_mode: Mapped[str] = mapped_column(String(20), default="include")
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(8, 6), default=Decimal("0.07"))
    show_unmatched_items: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    show_unmatched_branches: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    report_page_size: Mapped[int] = mapped_column(
        Integer, default=25, server_default="25"
    )


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        UniqueConstraint("modern_trade_id", "checksum_sha256", name="uq_batch_mt_checksum"),
        UniqueConstraint("modern_trade_id", "data_date", name="uq_batch_mt_period"),
        Index("ix_batch_mt_period", "modern_trade_id", "data_date"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    modern_trade_id: Mapped[int] = mapped_column(ForeignKey("modern_trades.id"))
    status: Mapped[str] = mapped_column(String(32), index=True)
    data_date: Mapped[date] = mapped_column(Date, index=True)
    source_path: Mapped[str] = mapped_column(Text)
    source_filename: Mapped[str] = mapped_column(String(255))
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    row_count: Mapped[int] = mapped_column(Integer)
    store_count: Mapped[int] = mapped_column(Integer)
    sku_count: Mapped[int] = mapped_column(Integer)
    negative_row_count: Mapped[int] = mapped_column(Integer)
    source_amount: Mapped[Decimal] = mapped_column(MONEY)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    sales_qty: Mapped[Decimal] = mapped_column(QUANTITY)
    stock_on_hand: Mapped[Decimal] = mapped_column(QUANTITY)
    reported_stock_on_hand: Mapped[Decimal] = mapped_column(QUANTITY)
    stock_on_order: Mapped[Decimal] = mapped_column(QUANTITY)
    reconciliation_errors: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    warning_resolution: Mapped[str | None] = mapped_column(String(32))
    warning_resolution_note: Mapped[str | None] = mapped_column(Text)
    warning_resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    warning_resolved_by: Mapped[str | None] = mapped_column(String(200))
    facts: Mapped[list["SalesInventoryFact"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class SalesInventoryFact(Base):
    __tablename__ = "sales_inventory_facts"
    __table_args__ = (
        UniqueConstraint(
            "batch_id", "source_branch_code", "source_sku", name="uq_fact_batch_branch_sku"
        ),
        Index("ix_fact_mt_date_sku", "modern_trade_id", "data_date", "source_sku"),
        Index(
            "ix_fact_mt_date_branch",
            "modern_trade_id",
            "data_date",
            "source_branch_code",
        ),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    modern_trade_id: Mapped[int] = mapped_column(ForeignKey("modern_trades.id"))
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"))
    data_date: Mapped[date] = mapped_column(Date)
    source_branch_code: Mapped[str] = mapped_column(String(30))
    source_branch_name: Mapped[str] = mapped_column(String(300))
    category: Mapped[str | None] = mapped_column(String(30))
    subcategory: Mapped[str | None] = mapped_column(String(30))
    brand: Mapped[str | None] = mapped_column(String(100))
    source_sku: Mapped[str] = mapped_column(String(50))
    barcode: Mapped[str | None] = mapped_column(String(50))
    source_description: Mapped[str | None] = mapped_column(Text)
    product_type: Mapped[str | None] = mapped_column(String(100))
    source_amount: Mapped[Decimal] = mapped_column(MONEY)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    sales_qty: Mapped[Decimal] = mapped_column(QUANTITY)
    stock_on_hand: Mapped[Decimal] = mapped_column(QUANTITY)
    stock_on_order: Mapped[Decimal] = mapped_column(QUANTITY)
    last_sold_date: Mapped[date | None] = mapped_column(Date)
    last_receive_date: Mapped[date | None] = mapped_column(Date)
    batch: Mapped[ImportBatch] = relationship(back_populates="facts")


class MonthlySalesSummary(Base):
    __tablename__ = "monthly_sales_summaries"
    __table_args__ = (
        Index(
            "ix_monthly_sales_mt_month_sku",
            "modern_trade_id",
            "month_start",
            "source_sku",
        ),
        Index(
            "ix_monthly_sales_mt_month_branch",
            "modern_trade_id",
            "month_start",
            "source_branch_code",
        ),
    )
    modern_trade_id: Mapped[int] = mapped_column(
        ForeignKey("modern_trades.id"), primary_key=True
    )
    month_start: Mapped[date] = mapped_column(Date, primary_key=True)
    source_sku: Mapped[str] = mapped_column(String(50), primary_key=True)
    source_branch_code: Mapped[str] = mapped_column(String(30), primary_key=True)
    source_branch_name: Mapped[str] = mapped_column(String(300))
    source_description: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    sales_qty: Mapped[Decimal] = mapped_column(QUANTITY)


class ItemMapping(Base):
    __tablename__ = "item_mappings"
    __table_args__ = (
        Index("ix_item_map_lookup", "modern_trade_id", "source_sku", "effective_from"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    modern_trade_id: Mapped[int] = mapped_column(ForeignKey("modern_trades.id"))
    source_sku: Mapped[str] = mapped_column(String(50))
    source_description: Mapped[str | None] = mapped_column(Text)
    wa_item_code: Mapped[str] = mapped_column(String(50))
    wa_item_description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="confirmed")
    item_type: Mapped[str] = mapped_column(
        String(20), default="normal", server_default="normal"
    )
    report_status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active"
    )
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    changed_by: Mapped[str] = mapped_column(String(200))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BranchMapping(Base):
    __tablename__ = "branch_mappings"
    __table_args__ = (
        Index("ix_branch_map_lookup", "modern_trade_id", "source_branch_code", "effective_from"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    modern_trade_id: Mapped[int] = mapped_column(ForeignKey("modern_trades.id"))
    source_branch_code: Mapped[str] = mapped_column(String(30))
    source_branch_description: Mapped[str | None] = mapped_column(Text)
    wa_branch_code: Mapped[str] = mapped_column(String(30))
    wa_branch_description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="confirmed")
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    changed_by: Mapped[str] = mapped_column(String(200))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50), index=True)
    entity_id: Mapped[str] = mapped_column(String(100), index=True)
    action: Mapped[str] = mapped_column(String(50))
    actor: Mapped[str] = mapped_column(String(200))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    before_json: Mapped[str | None] = mapped_column(Text)
    after_json: Mapped[str | None] = mapped_column(Text)


class SystemSetting(Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[str] = mapped_column(String(200))


class MonitoringSnapshot(Base):
    __tablename__ = "monitoring_snapshots"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    trigger: Mapped[str] = mapped_column(String(30))
    overall_status: Mapped[str] = mapped_column(String(20))
    fact_count: Mapped[int] = mapped_column(BigInteger)
    database_size_bytes: Mapped[int] = mapped_column(BigInteger)
    fact_table_size_bytes: Mapped[int] = mapped_column(BigInteger)
    fact_indexes_size_bytes: Mapped[int] = mapped_column(BigInteger)
    dead_tuple_count: Mapped[int] = mapped_column(BigInteger)
    dead_tuple_ratio: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    active_connections: Mapped[int] = mapped_column(Integer)
    max_connections: Mapped[int] = mapped_column(Integer)
    latest_data_date: Mapped[date | None] = mapped_column(Date)
    latest_import_status: Mapped[str | None] = mapped_column(String(32))
    warning_count: Mapped[int] = mapped_column(Integer)
    last_vacuum_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_analyze_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    modern_trades_json: Mapped[str] = mapped_column(Text)
    slow_queries_json: Mapped[str] = mapped_column(Text)

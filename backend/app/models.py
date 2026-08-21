from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
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


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        UniqueConstraint("modern_trade_id", "checksum_sha256", name="uq_batch_mt_checksum"),
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
    facts: Mapped[list["SalesInventoryFact"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class SalesInventoryFact(Base):
    __tablename__ = "sales_inventory_facts"
    __table_args__ = (
        UniqueConstraint(
            "batch_id", "source_branch_code", "source_sku", name="uq_fact_batch_branch_sku"
        ),
        Index("ix_fact_date_sku", "data_date", "source_sku"),
        Index("ix_fact_date_branch", "data_date", "source_branch_code"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
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

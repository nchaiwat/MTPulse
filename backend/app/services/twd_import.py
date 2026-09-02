from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.importers.twd import TwdExtract, extract_twd_file
from app.models import ImportBatch, ModernTrade, SalesInventoryFact
from app.services.monthly_sales_summary import refresh_monthly_sales_summary
from app.services.sku_interest import sync_sku_interests


class DuplicateImportError(ValueError):
    pass


class PeriodDuplicateError(ValueError):
    pass


def import_twd_file(session: Session, source_path: str | Path) -> ImportBatch:
    return import_twd_extract(session, extract_twd_file(source_path))


def import_twd_extract(session: Session, extract: TwdExtract) -> ImportBatch:
    mt = session.scalar(select(ModernTrade).where(ModernTrade.code == "TWD"))
    if mt is None:
        mt = ModernTrade(code="TWD", name="Thai Watsadu")
        session.add(mt)
        session.flush()
    existing = session.scalar(
        select(ImportBatch).where(
            ImportBatch.modern_trade_id == mt.id,
            ImportBatch.checksum_sha256 == extract.checksum_sha256,
        )
    )
    if existing is not None:
        raise DuplicateImportError(f"ไฟล์นี้เคยนำเข้าแล้วใน Batch {existing.id}")
    period_batch = session.scalar(
        select(ImportBatch).where(
            ImportBatch.modern_trade_id == mt.id,
            ImportBatch.data_date == extract.data_date,
        )
    )
    if period_batch is not None:
        raise PeriodDuplicateError(
            f"TWD วันที่ {extract.data_date:%d/%m/%Y} มีข้อมูลใน Batch {period_batch.id} แล้ว"
        )

    batch = _build_batch(mt.id, extract)
    session.add(batch)
    session.flush()
    interest_sync = sync_sku_interests(
        session,
        mt.id,
        extract,
        baseline=False,
    )
    session.add_all(
        _build_facts(
            mt.id,
            batch.id,
            extract,
            stored_skus=interest_sync.stored_skus,
        )
    )
    session.flush()
    refresh_monthly_sales_summary(session, mt.id, extract.data_date)
    batch.status = "imported_with_warnings" if extract.reconciliation_errors else "imported"
    batch.finished_at = datetime.now(UTC)
    session.commit()
    session.refresh(batch)
    return batch


def replace_twd_batch(
    session: Session,
    batch: ImportBatch,
    extract: TwdExtract,
) -> ImportBatch:
    if extract.data_date != batch.data_date:
        raise ValueError(
            f"ไฟล์ใหม่เป็นวันที่ {extract.data_date:%d/%m/%Y} "
            f"แต่ Batch {batch.id} เป็นวันที่ {batch.data_date:%d/%m/%Y}"
        )
    if extract.checksum_sha256 == batch.checksum_sha256:
        raise DuplicateImportError("ไฟล์ใหม่เหมือนกับไฟล์ที่อยู่ในระบบแล้ว")
    duplicate = session.scalar(
        select(ImportBatch).where(
            ImportBatch.modern_trade_id == batch.modern_trade_id,
            ImportBatch.checksum_sha256 == extract.checksum_sha256,
            ImportBatch.id != batch.id,
        )
    )
    if duplicate is not None:
        raise DuplicateImportError(f"ไฟล์นี้เคยนำเข้าแล้วใน Batch {duplicate.id}")

    replacement = _build_batch(batch.modern_trade_id, extract)
    session.execute(delete(SalesInventoryFact).where(SalesInventoryFact.batch_id == batch.id))
    interest_sync = sync_sku_interests(
        session,
        batch.modern_trade_id,
        extract,
        baseline=False,
    )
    session.add_all(
        _build_facts(
            batch.modern_trade_id,
            batch.id,
            extract,
            stored_skus=interest_sync.stored_skus,
        )
    )
    session.flush()
    refresh_monthly_sales_summary(session, batch.modern_trade_id, extract.data_date)

    for field in (
        "source_path",
        "source_filename",
        "checksum_sha256",
        "started_at",
        "row_count",
        "store_count",
        "sku_count",
        "negative_row_count",
        "source_amount",
        "amount",
        "sales_qty",
        "stock_on_hand",
        "reported_stock_on_hand",
        "stock_on_order",
        "reconciliation_errors",
    ):
        setattr(batch, field, getattr(replacement, field))
    batch.status = "imported_with_warnings" if extract.reconciliation_errors else "imported"
    batch.finished_at = datetime.now(UTC)
    batch.error_message = None
    batch.warning_resolution = None
    batch.warning_resolution_note = None
    batch.warning_resolved_at = None
    batch.warning_resolved_by = None
    session.flush()
    return batch


def _build_batch(modern_trade_id: int, extract: TwdExtract) -> ImportBatch:
    summary = extract.summary
    return ImportBatch(
        modern_trade_id=modern_trade_id,
        status="validating",
        data_date=extract.data_date,
        source_path=extract.source_path,
        source_filename=extract.source_filename,
        checksum_sha256=extract.checksum_sha256,
        started_at=datetime.now(UTC),
        row_count=summary.row_count,
        store_count=summary.store_count,
        sku_count=summary.sku_count,
        negative_row_count=summary.negative_row_count,
        source_amount=summary.source_amount,
        amount=summary.amount,
        sales_qty=summary.sales_qty,
        stock_on_hand=summary.stock_on_hand,
        reported_stock_on_hand=extract.reported_summary.stock_on_hand,
        stock_on_order=summary.stock_on_order,
        reconciliation_errors="\n".join(extract.reconciliation_errors) or None,
    )


def _build_facts(
    modern_trade_id: int,
    batch_id: int,
    extract: TwdExtract,
    *,
    stored_skus: frozenset[str],
) -> list[SalesInventoryFact]:
    return [
        SalesInventoryFact(
            modern_trade_id=modern_trade_id,
            batch_id=batch_id,
            data_date=extract.data_date,
            source_branch_code=row.branch_code,
            source_branch_name=row.branch_name,
            category=row.category,
            subcategory=row.subcategory,
            brand=row.brand,
            source_sku=row.sku,
            barcode=row.barcode,
            source_description=row.description,
            product_type=row.product_type,
            source_amount=row.source_amount,
            amount=row.amount,
            sales_qty=row.sales_qty,
            stock_on_hand=row.stock_on_hand,
            stock_on_order=row.stock_on_order,
            last_sold_date=row.last_sold_date,
            last_receive_date=row.last_receive_date,
        )
        for row in extract.rows
        if row.sku in stored_skus
    ]

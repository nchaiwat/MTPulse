from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.importers.twd import TwdExtract, extract_twd_file
from app.models import ImportBatch, ModernTrade, SalesInventoryFact


class DuplicateImportError(ValueError):
    pass


def import_twd_file(session: Session, source_path: str | Path) -> ImportBatch:
    extract = extract_twd_file(source_path)
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
        raise DuplicateImportError(f"ไฟล์นี้เคยนำเข้าแล้วใน batch {existing.id}")

    batch = _build_batch(mt.id, extract)
    session.add(batch)
    session.flush()
    session.add_all(_build_facts(batch.id, extract))
    batch.status = "imported_with_warnings" if extract.reconciliation_errors else "imported"
    batch.finished_at = datetime.now(UTC)
    session.commit()
    session.refresh(batch)
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


def _build_facts(batch_id: int, extract: TwdExtract) -> list[SalesInventoryFact]:
    return [
        SalesInventoryFact(
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
    ]

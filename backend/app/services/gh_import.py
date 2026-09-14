from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.importers.gh import GhExtract
from app.models import (
    ImportBatch,
    InventoryCoverage,
    ModernTrade,
    SalesInventoryFact,
    SkuInterest,
)
from app.services.daily_sku_summary import refresh_daily_sku_summary
from app.services.monthly_sales_summary import refresh_monthly_sales_summary


class GhImportError(ValueError):
    pass


def ensure_gh_trade(session: Session) -> ModernTrade:
    modern_trade = session.scalar(select(ModernTrade).where(ModernTrade.code == "GH"))
    if modern_trade is None:
        modern_trade = ModernTrade(
            code="GH",
            name="Global House",
            vat_mode="include",
            show_unmatched_items=False,
            show_unmatched_branches=False,
            source_subfolder="GBH",
            source_group_code="GH",
            branch_prefix="GH",
        )
        session.add(modern_trade)
        session.flush()
    else:
        modern_trade.name = "Global House"
        modern_trade.vat_mode = "include"
        modern_trade.show_unmatched_items = False
        modern_trade.show_unmatched_branches = False
        modern_trade.source_group_code = "GH"
        modern_trade.source_subfolder = modern_trade.source_subfolder or "GBH"
        modern_trade.branch_prefix = modern_trade.branch_prefix or "GH"
    return modern_trade


def import_gh_file(
    session: Session,
    extract: GhExtract,
    *,
    actor: str = "system-import",
) -> ImportBatch:
    modern_trade = ensure_gh_trade(session)
    existing = session.scalar(
        select(ImportBatch).where(
            ImportBatch.modern_trade_id == modern_trade.id,
            ImportBatch.data_date == extract.data_date,
        )
    )
    if existing and existing.business_fingerprint == extract.business_fingerprint:
        raise GhImportError("ข้อมูลธุรกิจชุดนี้ถูกนำเข้าแล้ว แม้ชื่อไฟล์อาจต่างกัน")
    if existing:
        session.execute(
            delete(SalesInventoryFact).where(SalesInventoryFact.batch_id == existing.id)
        )
        batch = existing
    else:
        batch = _new_batch(
            modern_trade_id=modern_trade.id,
            status="validating",
            data_date=extract.data_date,
            source_path=extract.source_path,
            source_filename=extract.source_filename,
            checksum_sha256=_checksum(extract.business_fingerprint),
            row_count=0,
            store_count=0,
            sku_count=0,
            negative_row_count=0,
            source_amount=0,
            amount=0,
            sales_qty=0,
            stock_on_hand=0,
            reported_stock_on_hand=0,
            stock_on_order=0,
            stock_value=0,
        )
        session.add(batch)
        session.flush()

    summary = extract.summary
    batch.status = "validating"
    batch.source_path = extract.source_path
    batch.source_filename = extract.source_filename
    batch.checksum_sha256 = _checksum(extract.business_fingerprint)
    batch.business_fingerprint = extract.business_fingerprint
    batch.source_pair_json = json.dumps(
        {
            "source": {
                "path": extract.source_path,
                "filename": extract.source_filename,
            },
            "productStatusCounts": dict(extract.product_status_counts),
            "footerTotals": {key: str(value) for key, value in extract.footer_totals},
        },
        ensure_ascii=False,
    )
    batch.started_at = datetime.now(UTC)
    batch.row_count = summary.row_count
    batch.store_count = summary.store_count
    batch.sku_count = summary.sku_count
    batch.negative_row_count = summary.negative_row_count
    batch.source_amount = summary.source_amount
    batch.amount = summary.amount
    batch.sales_qty = summary.sales_qty
    batch.stock_on_hand = summary.stock_on_hand
    batch.reported_stock_on_hand = summary.stock_on_hand
    batch.stock_on_order = 0
    batch.stock_value = summary.stock_value
    batch.reconciliation_errors = "\n".join(extract.reconciliation_errors) or None

    descriptions = {row.sku: row.description for row in extract.rows if row.description}
    existing_interests = {
        interest.source_sku: interest
        for interest in session.scalars(
            select(SkuInterest).where(SkuInterest.modern_trade_id == modern_trade.id)
        )
    }
    now = datetime.now(UTC)
    for source_sku in extract.inventory_skus:
        interest = existing_interests.get(source_sku)
        if interest is None:
            session.add(
                SkuInterest(
                    modern_trade_id=modern_trade.id,
                    source_sku=source_sku,
                    source_description=descriptions.get(source_sku),
                    status="active",
                    first_seen_date=extract.data_date,
                    last_seen_date=extract.data_date,
                    first_seen_at=now,
                    last_seen_at=now,
                    decided_by=f"{actor}:gh-import",
                    decided_at=now,
                )
            )
            continue
        interest.first_seen_date = min(interest.first_seen_date, extract.data_date)
        interest.last_seen_date = max(interest.last_seen_date, extract.data_date)
        interest.last_seen_at = now
        if descriptions.get(source_sku) and not interest.source_description:
            interest.source_description = descriptions[source_sku]

    session.add_all(
        _new_fact(
            modern_trade_id=modern_trade.id,
            batch_id=batch.id,
            data_date=extract.data_date,
            source_branch_code=row.branch_code,
            source_branch_name=row.branch_name,
            category=None,
            subcategory=None,
            brand=None,
            source_sku=row.sku,
            barcode=None,
            source_description=row.description,
            product_type=None,
            source_amount=row.source_amount,
            amount=row.amount,
            sales_qty=row.sales_qty,
            stock_on_hand=row.stock_on_hand,
            stock_on_order=0,
            stock_value=row.stock_value,
            last_sold_date=None,
            last_receive_date=None,
        )
        for row in extract.rows
    )
    session.execute(
        delete(InventoryCoverage).where(
            InventoryCoverage.modern_trade_id == modern_trade.id,
            InventoryCoverage.data_date == extract.data_date,
        )
    )
    session.add(
        _new_coverage(
            modern_trade_id=modern_trade.id,
            data_date=extract.data_date,
            source_skus_json=json.dumps(sorted(extract.inventory_skus)),
            source_branches_json=json.dumps(sorted(extract.inventory_branches)),
            source_row_count=summary.row_count,
        )
    )
    session.flush()
    refresh_daily_sku_summary(session, modern_trade.id, extract.data_date)
    refresh_monthly_sales_summary(session, modern_trade.id, extract.data_date)
    batch.status = "imported_with_warnings" if extract.reconciliation_errors else "imported"
    batch.finished_at = datetime.now(UTC)
    batch.error_message = None
    session.flush()
    return batch


def append_gh_sku_facts(
    session: Session,
    batch: ImportBatch,
    extract: GhExtract,
    source_sku: str,
) -> int:
    if extract.data_date != batch.data_date:
        raise ValueError("วันที่ข้อมูลในไฟล์ไม่ตรงกับ Batch เดิม")
    existing = session.scalar(
        select(SalesInventoryFact.id)
        .where(
            SalesInventoryFact.batch_id == batch.id,
            SalesInventoryFact.source_sku == source_sku,
        )
        .limit(1)
    )
    if existing is not None:
        return 0
    matching = [row for row in extract.rows if row.sku == source_sku]
    if not matching:
        return 0
    session.add_all(
        _new_fact(
            modern_trade_id=batch.modern_trade_id,
            batch_id=batch.id,
            data_date=extract.data_date,
            source_branch_code=row.branch_code,
            source_branch_name=row.branch_name,
            source_sku=row.sku,
            source_description=row.description,
            source_amount=row.source_amount,
            amount=row.amount,
            sales_qty=row.sales_qty,
            stock_on_hand=row.stock_on_hand,
            stock_on_order=0,
            stock_value=row.stock_value,
        )
        for row in matching
    )
    session.flush()
    refresh_daily_sku_summary(session, batch.modern_trade_id, extract.data_date)
    refresh_monthly_sales_summary(session, batch.modern_trade_id, extract.data_date)
    return len(matching)


def _checksum(fingerprint: str) -> str:
    return sha256(f"{fingerprint}:GH".encode()).hexdigest()


def _new_batch(**values: object) -> ImportBatch:
    return ImportBatch(**values)


def _new_fact(**values: object) -> SalesInventoryFact:
    return SalesInventoryFact(**values)


def _new_coverage(**values: object) -> InventoryCoverage:
    return InventoryCoverage(**values)

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.importers.dh import DhPairExtract
from app.models import (
    ImportBatch,
    InventoryCoverage,
    ModernTrade,
    SalesInventoryFact,
    SkuInterest,
)
from app.services.daily_sku_summary import refresh_daily_sku_summary
from app.services.dh_price_master import (
    DhPriceMasterError,
    load_effective_dh_prices,
    lock_dh_price_changes,
)
from app.services.dh_pricing import DhPricedPair, DhPricingError, price_dh_pair
from app.services.monthly_sales_summary import refresh_monthly_sales_summary


class DhImportError(ValueError):
    pass


def ensure_dh_trade(session: Session) -> ModernTrade:
    modern_trade = session.scalar(select(ModernTrade).where(ModernTrade.code == "DH"))
    if modern_trade is None:
        modern_trade = ModernTrade(
            code="DH",
            name="DoHome",
            vat_mode="exclude",
            show_unmatched_items=True,
            show_unmatched_branches=True,
            source_subfolder="DoHome",
            source_group_code="DH",
        )
        session.add(modern_trade)
        session.flush()
    else:
        modern_trade.name = "DoHome"
        modern_trade.vat_mode = "exclude"
        modern_trade.show_unmatched_items = True
        modern_trade.show_unmatched_branches = True
        modern_trade.source_group_code = "DH"
    return modern_trade


def price_dh_import_preview(session: Session, pair: DhPairExtract) -> DhPricedPair:
    try:
        prices = load_effective_dh_prices(
            session,
            pair.sales_date,
            {row.sku for row in pair.sales_rows if row.sales_qty != 0},
        )
        return price_dh_pair(pair, prices)
    except (DhPriceMasterError, DhPricingError) as exc:
        raise DhImportError(str(exc)) from exc


def import_dh_pair(
    session: Session,
    pair: DhPairExtract,
    *,
    actor: str = "system-import",
    expected_fingerprint: str | None = None,
) -> ImportBatch:
    lock_dh_price_changes(session)
    modern_trade = ensure_dh_trade(session)
    priced = price_dh_import_preview(session, pair)
    if expected_fingerprint is not None and priced.business_fingerprint != expected_fingerprint:
        raise DhImportError(
            "ข้อมูลคู่ไฟล์หรือราคา DH เปลี่ยนจากรอบ Preview กรุณาตรวจสอบใหม่"
        )

    existing = session.scalar(
        select(ImportBatch).where(
            ImportBatch.modern_trade_id == modern_trade.id,
            ImportBatch.data_date == pair.batch_date,
        )
    )
    if existing and existing.business_fingerprint == priced.business_fingerprint:
        raise DhImportError("ข้อมูลธุรกิจและราคาชุดนี้ถูกนำเข้าแล้ว")
    if existing:
        session.execute(
            delete(SalesInventoryFact).where(SalesInventoryFact.batch_id == existing.id)
        )
        batch = existing
    else:
        batch = ImportBatch(
            modern_trade_id=modern_trade.id,
            status="validating",
            data_date=pair.batch_date,
            source_path=pair.inventory_path,
            source_filename="",
            checksum_sha256=_checksum(priced.business_fingerprint),
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

    _update_batch(batch, priced)
    _update_sku_interests(session, modern_trade.id, priced, actor)
    session.add_all(
        SalesInventoryFact(
            modern_trade_id=modern_trade.id,
            batch_id=batch.id,
            data_date=pair.batch_date,
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
            stock_value=0,
            last_sold_date=None,
            last_receive_date=None,
        )
        for row in priced.rows
    )
    inventory_skus = sorted({row.sku for row in pair.stock_rows})
    inventory_branches = sorted({row.branch_code for row in pair.stock_rows})
    session.execute(
        delete(InventoryCoverage).where(
            InventoryCoverage.modern_trade_id == modern_trade.id,
            InventoryCoverage.data_date == pair.batch_date,
        )
    )
    session.add(
        InventoryCoverage(
            modern_trade_id=modern_trade.id,
            data_date=pair.batch_date,
            source_skus_json=json.dumps(inventory_skus),
            source_branches_json=json.dumps(inventory_branches),
            source_row_count=len(pair.stock_rows),
        )
    )
    session.flush()
    refresh_daily_sku_summary(session, modern_trade.id, pair.batch_date)
    refresh_monthly_sales_summary(session, modern_trade.id, pair.batch_date)
    batch.status = "imported_with_warnings" if priced.reconciliation_errors else "imported"
    batch.finished_at = datetime.now(UTC)
    batch.error_message = None
    session.flush()
    return batch


def append_dh_sku_facts(
    session: Session,
    batch: ImportBatch,
    pair: DhPairExtract,
    source_sku: str,
) -> int:
    if pair.batch_date != batch.data_date:
        raise DhImportError("วันที่ข้อมูลในคู่ไฟล์ไม่ตรงกับ Batch เดิม")
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
    lock_dh_price_changes(session)
    priced = price_dh_import_preview(session, pair)
    matching = [row for row in priced.rows if row.sku == source_sku]
    if not matching:
        return 0
    session.add_all(
        SalesInventoryFact(
            modern_trade_id=batch.modern_trade_id,
            batch_id=batch.id,
            data_date=pair.batch_date,
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
            stock_value=0,
            last_sold_date=None,
            last_receive_date=None,
        )
        for row in matching
    )
    session.flush()
    refresh_daily_sku_summary(session, batch.modern_trade_id, pair.batch_date)
    refresh_monthly_sales_summary(session, batch.modern_trade_id, pair.batch_date)
    return len(matching)


def _update_batch(batch: ImportBatch, priced: DhPricedPair) -> None:
    pair = priced.source
    summary = priced.summary
    batch.status = "validating"
    batch.data_date = pair.batch_date
    batch.source_path = pair.inventory_path
    batch.source_filename = f"{pair.inventory_filename} + {pair.sales_filename}"
    batch.checksum_sha256 = _checksum(priced.business_fingerprint)
    batch.business_fingerprint = priced.business_fingerprint
    batch.source_pair_json = json.dumps(
        {
            "stock": {
                "path": pair.inventory_path,
                "filename": pair.inventory_filename,
                "checksum": pair.inventory_checksum,
                "dataDate": pair.stock_date.isoformat(),
            },
            "sales": {
                "path": pair.sales_path,
                "filename": pair.sales_filename,
                "checksum": pair.sales_checksum,
                "dataDate": pair.sales_date.isoformat(),
            },
            "footerAmounts": [
                {
                    "branchCode": row.branch_code,
                    "branchName": row.branch_name,
                    "amount": str(row.amount),
                }
                for row in pair.branch_amounts
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    batch.started_at = datetime.now(UTC)
    batch.row_count = summary.row_count
    batch.store_count = summary.store_count
    batch.sku_count = summary.sku_count
    batch.negative_row_count = summary.negative_row_count
    batch.source_amount = summary.source_footer_amount
    batch.amount = summary.derived_amount
    batch.sales_qty = summary.sales_qty
    batch.stock_on_hand = summary.stock_on_hand
    batch.reported_stock_on_hand = summary.stock_on_hand
    batch.stock_on_order = 0
    batch.stock_value = 0
    batch.reconciliation_errors = "\n".join(priced.reconciliation_errors) or None


def _update_sku_interests(
    session: Session,
    modern_trade_id: int,
    priced: DhPricedPair,
    actor: str,
) -> None:
    pair = priced.source
    descriptions = {row.sku: row.description for row in priced.rows if row.description}
    existing = {
        row.source_sku: row
        for row in session.scalars(
            select(SkuInterest).where(SkuInterest.modern_trade_id == modern_trade_id)
        )
    }
    now = datetime.now(UTC)
    for source_sku in sorted(pair.source_skus):
        interest = existing.get(source_sku)
        if interest is None:
            session.add(
                SkuInterest(
                    modern_trade_id=modern_trade_id,
                    source_sku=source_sku,
                    source_description=descriptions.get(source_sku),
                    status="active",
                    first_seen_date=pair.batch_date,
                    last_seen_date=pair.batch_date,
                    first_seen_at=now,
                    last_seen_at=now,
                    decided_by=actor,
                    decided_at=now,
                )
            )
            continue
        interest.first_seen_date = min(interest.first_seen_date, pair.batch_date)
        interest.last_seen_date = max(interest.last_seen_date, pair.batch_date)
        interest.last_seen_at = now
        if descriptions.get(source_sku) and not interest.source_description:
            interest.source_description = descriptions[source_sku]


def _checksum(fingerprint: str) -> str:
    return sha256(f"{fingerprint}:DH".encode()).hexdigest()

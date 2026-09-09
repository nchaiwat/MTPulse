from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.importers.hp_mh import HpMhMtExtract, HpMhPairExtract
from app.models import (
    AuditEvent,
    ImportBatch,
    InventoryCoverage,
    ModernTrade,
    SalesInventoryFact,
    SkuInterest,
)
from app.services.daily_sku_summary import refresh_daily_sku_summary
from app.services.monthly_sales_summary import refresh_monthly_sales_summary
from app.services.sku_interest import STORED_STATUSES


class HpMhImportError(ValueError):
    pass


def ensure_hp_mh_trades(session: Session) -> dict[str, ModernTrade]:
    existing = {
        mt.code: mt
        for mt in session.scalars(select(ModernTrade).where(ModernTrade.code.in_(("HP", "MH"))))
    }
    for code, name, prefix in (
        ("HP", "HomePro", "S"),
        ("MH", "MegaHome", "M"),
    ):
        mt = existing.get(code)
        if mt is None:
            mt = ModernTrade(
                code=code,
                name=name,
                source_subfolder="HP_MH",
                source_group_code="HP_MH",
                branch_prefix=prefix,
            )
            session.add(mt)
            session.flush()
            existing[code] = mt
        else:
            mt.source_group_code = "HP_MH"
            mt.branch_prefix = prefix
    return existing


def import_hp_mh_pair(
    session: Session,
    pair: HpMhPairExtract,
    *,
    baseline: bool = False,
    actor: str = "system-import",
) -> dict[str, ImportBatch]:
    trades = ensure_hp_mh_trades(session)
    extracts = {"HP": pair.hp, "MH": pair.mh}
    existing = {
        code: session.scalar(
            select(ImportBatch).where(
                ImportBatch.modern_trade_id == trades[code].id,
                ImportBatch.data_date == pair.data_date,
            )
        )
        for code in ("HP", "MH")
    }
    present = [code for code, batch in existing.items() if batch is not None]
    if present and len(present) != 2:
        raise HpMhImportError("ข้อมูลวันเดิมของ HP/MH ไม่ครบคู่ กรุณาตรวจสอบก่อน Reimport")
    if len(present) == 2 and all(
        batch and batch.business_fingerprint == pair.business_fingerprint
        for batch in existing.values()
    ):
        raise HpMhImportError("ข้อมูลธุรกิจชุดนี้ถูกนำเข้าแล้ว แม้ชื่อไฟล์อาจต่างกัน")

    replacing = len(present) == 2
    previous = {
        code: {
            "batchId": batch.id,
            "businessFingerprint": batch.business_fingerprint,
            "sourcePair": json.loads(batch.source_pair_json or "null"),
        }
        for code, batch in existing.items()
        if batch is not None
    }

    batches: dict[str, ImportBatch] = {}
    pair_json = json.dumps(
        {
            "inventory": {
                "path": pair.inventory_path,
                "filename": pair.inventory_filename,
                "checksum": pair.inventory_checksum,
            },
            "sales": {
                "path": pair.sales_path,
                "filename": pair.sales_filename,
                "checksum": pair.sales_checksum,
            },
        },
        ensure_ascii=False,
    )
    for code in ("HP", "MH"):
        mt = trades[code]
        extract = extracts[code]
        stored_skus = _sync_sale_interests(
            session,
            mt.id,
            extract,
            baseline=baseline,
        )
        batch = existing[code]
        if batch is None:
            batch = _new_import_batch(
                modern_trade_id=mt.id,
                status="validating",
                data_date=pair.data_date,
                source_path=pair.inventory_path,
                source_filename=f"{pair.inventory_filename} + {pair.sales_filename}",
                checksum_sha256=_mt_checksum(pair.business_fingerprint, code),
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
        else:
            session.execute(
                delete(SalesInventoryFact).where(SalesInventoryFact.batch_id == batch.id)
            )
        _update_batch(batch, extract, pair, pair_json)
        session.add_all(_build_facts(mt.id, batch.id, extract, stored_skus=stored_skus))
        _replace_coverage(session, mt.id, extract)
        session.flush()
        refresh_daily_sku_summary(session, mt.id, pair.data_date)
        refresh_monthly_sales_summary(session, mt.id, pair.data_date)
        batch.status = "imported_with_warnings" if pair.reconciliation_errors else "imported"
        batch.finished_at = datetime.now(UTC)
        batch.error_message = None
        batch.warning_resolution = None
        batch.warning_resolution_note = None
        batch.warning_resolved_at = None
        batch.warning_resolved_by = None
        batches[code] = batch
    if replacing:
        session.add(
            AuditEvent(
                entity_type="hp_mh_pair",
                entity_id=pair.data_date.isoformat(),
                action="corrected_reimport",
                actor=actor,
                before_json=json.dumps(previous, ensure_ascii=False),
                after_json=json.dumps(
                    {
                        "businessFingerprint": pair.business_fingerprint,
                        "batchIds": {code: batch.id for code, batch in batches.items()},
                    },
                    ensure_ascii=False,
                ),
            )
        )
    session.flush()
    return batches


def append_hp_mh_sku_facts(
    session: Session,
    batch: ImportBatch,
    extract: HpMhMtExtract,
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
    facts = _build_facts(
        batch.modern_trade_id,
        batch.id,
        extract,
        stored_skus=frozenset({source_sku}),
    )
    if not facts:
        return 0
    session.add_all(facts)
    session.flush()
    refresh_daily_sku_summary(session, batch.modern_trade_id, extract.data_date)
    refresh_monthly_sales_summary(session, batch.modern_trade_id, extract.data_date)
    return len(facts)


def _sync_sale_interests(
    session: Session,
    modern_trade_id: int,
    extract: HpMhMtExtract,
    *,
    baseline: bool,
) -> frozenset[str]:
    descriptions = {
        row.sku: row.description for row in extract.rows if row.sku in extract.sale_skus
    }
    existing = {
        row.source_sku: row
        for row in session.scalars(
            select(SkuInterest).where(SkuInterest.modern_trade_id == modern_trade_id)
        )
    }
    now = datetime.now(UTC)
    for sku in extract.sale_skus:
        interest = existing.get(sku)
        if interest is None:
            interest = SkuInterest(
                modern_trade_id=modern_trade_id,
                source_sku=sku,
                source_description=descriptions.get(sku),
                status="ignored" if baseline else "pending",
                first_seen_date=extract.data_date,
                last_seen_date=extract.data_date,
                first_seen_at=now,
                last_seen_at=now,
                decided_by="system:initial-scan" if baseline else None,
                decided_at=now if baseline else None,
            )
            session.add(interest)
            existing[sku] = interest
        else:
            interest.first_seen_date = min(interest.first_seen_date, extract.data_date)
            interest.last_seen_date = max(interest.last_seen_date, extract.data_date)
            interest.last_seen_at = now
            if descriptions.get(sku) and not interest.source_description:
                interest.source_description = descriptions[sku]
    return frozenset(
        sku for sku, interest in existing.items() if interest.status in STORED_STATUSES
    )


def _mt_checksum(fingerprint: str, code: str) -> str:
    return sha256(f"{fingerprint}:{code}".encode()).hexdigest()


def _update_batch(
    batch: ImportBatch,
    extract: HpMhMtExtract,
    pair: HpMhPairExtract,
    pair_json: str,
) -> None:
    summary = extract.summary
    batch.status = "validating"
    batch.source_path = pair.inventory_path
    batch.source_filename = f"{pair.inventory_filename} + {pair.sales_filename}"
    batch.checksum_sha256 = _mt_checksum(pair.business_fingerprint, extract.code)
    batch.business_fingerprint = pair.business_fingerprint
    batch.source_pair_json = pair_json
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
    batch.reconciliation_errors = "\n".join(pair.reconciliation_errors) or None


def _build_facts(
    modern_trade_id: int,
    batch_id: int,
    extract: HpMhMtExtract,
    *,
    stored_skus: frozenset[str],
) -> list[SalesInventoryFact]:
    return [
        _new_fact(
            modern_trade_id=modern_trade_id,
            batch_id=batch_id,
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
        if row.sku in stored_skus
    ]


def _replace_coverage(
    session: Session,
    modern_trade_id: int,
    extract: HpMhMtExtract,
) -> None:
    session.execute(
        delete(InventoryCoverage).where(
            InventoryCoverage.modern_trade_id == modern_trade_id,
            InventoryCoverage.data_date == extract.data_date,
        )
    )
    session.add(
        _new_coverage(
            modern_trade_id=modern_trade_id,
            data_date=extract.data_date,
            source_skus_json=json.dumps(sorted(extract.inventory_skus)),
            source_branches_json=json.dumps(sorted(extract.inventory_branches)),
            source_row_count=len(extract.inventory_skus) * len(extract.inventory_branches),
        )
    )


def _new_import_batch(**values: object) -> ImportBatch:
    return ImportBatch(**values)


def _new_fact(**values: object) -> SalesInventoryFact:
    return SalesInventoryFact(**values)


def _new_coverage(**values: object) -> InventoryCoverage:
    return InventoryCoverage(**values)

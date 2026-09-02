from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.importers.twd import TwdExtract, extract_twd_file, sha256_file
from app.models import AuditEvent, ImportBatch, ModernTrade, SalesInventoryFact


@dataclass(frozen=True)
class BatchRepair:
    batch: ImportBatch
    extract: TwdExtract
    changes: tuple[tuple[SalesInventoryFact, Decimal, Decimal], ...]


def _source_index(root: Path) -> dict[str, Path]:
    paths = sorted(
        path
        for pattern in ("*.xls", "*.xlsx")
        for path in root.rglob(pattern)
        if not path.name.startswith("~$")
    )
    result: dict[str, Path] = {}
    for path in paths:
        checksum = sha256_file(path)
        if checksum in result:
            raise ValueError(f"พบ Checksum ซ้ำใน Source Root: {path} และ {result[checksum]}")
        result[checksum] = path
    return result


def _build_repair(
    session,
    batch: ImportBatch,
    source_path: Path,
) -> BatchRepair:
    extract = extract_twd_file(source_path)
    if extract.checksum_sha256 != batch.checksum_sha256:
        raise ValueError(f"Batch {batch.id}: Checksum ของไฟล์ต้นทางไม่ตรง")
    if extract.data_date != batch.data_date:
        raise ValueError(f"Batch {batch.id}: วันที่ของไฟล์ต้นทางไม่ตรง")
    if extract.reported_summary.stock_on_hand != batch.reported_stock_on_hand:
        raise ValueError(f"Batch {batch.id}: Source Total เปลี่ยนจากตอนนำเข้า")
    if batch.stock_on_hand - extract.summary.stock_on_hand != Decimal("525"):
        raise ValueError(f"Batch {batch.id}: ส่วนต่างไม่ใช่ 525 จึงไม่อยู่ในขอบเขตการแก้ครั้งนี้")

    facts = list(
        session.scalars(
            select(SalesInventoryFact).where(SalesInventoryFact.batch_id == batch.id)
        )
    )
    facts_by_key = {(fact.source_branch_code, fact.source_sku): fact for fact in facts}
    rows_by_key = {(row.branch_code, row.sku): row for row in extract.rows}
    if facts_by_key.keys() != rows_by_key.keys():
        raise ValueError(f"Batch {batch.id}: Branch × SKU ในฐานข้อมูลไม่ตรงกับไฟล์ต้นทาง")

    changes = tuple(
        (facts_by_key[key], facts_by_key[key].stock_on_hand, row.stock_on_hand)
        for key, row in rows_by_key.items()
        if facts_by_key[key].stock_on_hand != row.stock_on_hand
    )
    if len(changes) != 35 or any(before != 15 or after != 0 for _, before, after in changes):
        raise ValueError(
            f"Batch {batch.id}: รูปแบบแถวที่ต้องแก้ไม่ใช่ 35 แถวจาก 15 เป็น 0"
        )
    return BatchRepair(batch=batch, extract=extract, changes=changes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--batch-id", action="append", type=int, dest="batch_ids")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    source_index = _source_index(args.source_root)
    with SessionLocal() as session:
        modern_trade_id = session.scalar(
            select(ModernTrade.id).where(ModernTrade.code == "TWD")
        )
        if modern_trade_id is None:
            raise ValueError("ไม่พบ Modern Trade TWD")
        batch_query = select(ImportBatch).where(
            ImportBatch.modern_trade_id == modern_trade_id,
            ImportBatch.stock_on_hand - ImportBatch.reported_stock_on_hand
            == Decimal("525"),
        )
        if args.batch_ids:
            batch_query = batch_query.where(ImportBatch.id.in_(args.batch_ids))
        batches = list(
            session.scalars(batch_query.order_by(ImportBatch.data_date, ImportBatch.id))
        )
        if args.batch_ids and {batch.id for batch in batches} != set(args.batch_ids):
            raise ValueError("Batch ที่ระบุไม่ครบหรือไม่เข้าเงื่อนไขส่วนต่าง 525")
        missing = [batch.id for batch in batches if batch.checksum_sha256 not in source_index]
        if missing:
            raise ValueError(f"ไม่พบไฟล์ต้นทางสำหรับ Batch: {missing}")

        repairs = tuple(
            _build_repair(session, batch, source_index[batch.checksum_sha256])
            for batch in batches
        )
        preview = [
            {
                "batchId": repair.batch.id,
                "dataDate": repair.batch.data_date.isoformat(),
                "before": str(repair.batch.stock_on_hand),
                "after": str(repair.extract.summary.stock_on_hand),
                "reported": str(repair.batch.reported_stock_on_hand),
                "changedRows": len(repair.changes),
                "warnings": list(repair.extract.reconciliation_errors),
            }
            for repair in repairs
        ]
        print(json.dumps({"apply": args.apply, "repairs": preview}, ensure_ascii=False, indent=2))
        if not args.apply:
            session.rollback()
            return

        for repair in repairs:
            before_summary = {
                "stockOnHand": str(repair.batch.stock_on_hand),
                "warnings": repair.batch.reconciliation_errors,
            }
            for fact, _, after in repair.changes:
                fact.stock_on_hand = after
            repair.batch.stock_on_hand = repair.extract.summary.stock_on_hand
            repair.batch.reconciliation_errors = (
                "\n".join(repair.extract.reconciliation_errors) or None
            )
            repair.batch.status = (
                "imported_with_warnings"
                if repair.extract.reconciliation_errors
                else "imported"
            )
            session.add(
                AuditEvent(
                    entity_type="import_corrective",
                    entity_id=str(repair.batch.id),
                    action="excel_error_stock_repaired",
                    actor="codex-maintenance",
                    before_json=json.dumps(before_summary, ensure_ascii=False),
                    after_json=json.dumps(
                        {
                            "stockOnHand": str(repair.batch.stock_on_hand),
                            "reportedStockOnHand": str(
                                repair.batch.reported_stock_on_hand
                            ),
                            "changedRows": len(repair.changes),
                            "warnings": repair.batch.reconciliation_errors,
                        },
                        ensure_ascii=False,
                    ),
                )
            )
        session.commit()


if __name__ == "__main__":
    main()

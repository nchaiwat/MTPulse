from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import smbclient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.importers.twd import TwdFormatError
from app.local_time import bangkok_now
from app.models import (
    AuditEvent,
    ImportBatch,
    ImportRun,
    ItemMapping,
    ModernTrade,
    SalesInventoryFact,
    SkuInterest,
    SourceFile,
)
from app.services.automatic_import import (
    ACTIVE_RUN_STATUSES,
    ActiveRunError,
    AutomaticImportError,
    SourceCandidate,
    _credentials,
    download_twd_extract,
)
from app.services.hp_mh_import import append_hp_mh_sku_facts
from app.services.telegram import send_telegram
from app.services.twd_import import append_twd_sku_facts

logger = logging.getLogger("mtpulse.sku_backfill")
AVAILABLE_BATCH_STATUSES = {"imported", "imported_with_warnings"}
USABLE_SOURCE_STATUSES = {"imported", "ready", "skipped", "duplicate"}


def _mapping(
    session: Session,
    modern_trade_id: int,
    source_sku: str,
    range_end: date,
) -> ItemMapping:
    mapping = session.scalar(
        select(ItemMapping)
        .where(
            ItemMapping.modern_trade_id == modern_trade_id,
            ItemMapping.source_sku == source_sku,
            ItemMapping.status == "confirmed",
            ItemMapping.report_status == "active",
            (ItemMapping.effective_to.is_(None) | (ItemMapping.effective_to >= range_end)),
        )
        .order_by(ItemMapping.effective_from.desc(), ItemMapping.id.desc())
        .limit(1)
    )
    if mapping is None:
        raise ValueError("SKU ต้องมี Mapping สถานะ confirmed และ active ก่อน Backfill")
    return mapping


def backfill_options(session: Session, mt: ModernTrade) -> dict[str, object]:
    mappings = session.scalars(
        select(ItemMapping)
        .where(
            ItemMapping.modern_trade_id == mt.id,
            ItemMapping.status == "confirmed",
            ItemMapping.report_status == "active",
            ItemMapping.effective_to.is_(None),
        )
        .order_by(ItemMapping.source_sku)
    ).all()
    mapped_skus = {item.source_sku for item in mappings}
    unmapped_interests = [
        interest
        for interest in session.scalars(
            select(SkuInterest)
            .where(SkuInterest.modern_trade_id == mt.id)
            .order_by(SkuInterest.source_sku)
        ).all()
        if interest.source_sku not in mapped_skus
    ]
    registry_mt_id = mt.id
    if mt.source_group_code == "HP_MH":
        registry_mt_id = (
            session.scalar(select(ModernTrade.id).where(ModernTrade.code == "HP")) or mt.id
        )
    earliest, latest = session.execute(
        select(
            func.min(SourceFile.detected_data_date),
            func.max(SourceFile.detected_data_date),
        ).where(
            SourceFile.modern_trade_id == registry_mt_id,
            SourceFile.detected_data_date.is_not(None),
            SourceFile.size_bytes > 0,
        )
    ).one()
    refreshed_at = session.scalar(
        select(func.max(ImportRun.finished_at)).where(
            ImportRun.modern_trade_id == registry_mt_id,
            ImportRun.mode.in_({"scan", "import", "registry"}),
            ImportRun.status.in_({"success", "success_with_warnings"}),
        )
    )
    return {
        "mappings": [
            {
                "sourceSku": item.source_sku,
                "sourceDescription": item.source_description,
                "waItemCode": item.wa_item_code,
                "waItemDescription": item.wa_item_description,
                "effectiveFrom": item.effective_from.isoformat(),
            }
            for item in mappings
        ],
        "unmappedSkus": [
            {
                "sourceSku": item.source_sku,
                "sourceDescription": item.source_description,
                "interestStatus": item.status,
                "firstSeenDate": item.first_seen_date.isoformat(),
                "lastSeenDate": item.last_seen_date.isoformat(),
            }
            for item in unmapped_interests
        ],
        "registry": {
            "earliestDate": earliest.isoformat() if earliest else None,
            "latestDate": latest.isoformat() if latest else None,
            "refreshedAt": refreshed_at.isoformat() if refreshed_at else None,
        },
    }


def _plan(
    session: Session,
    mt: ModernTrade,
    source_sku: str,
    range_start: date,
    range_end: date,
) -> tuple[ItemMapping, list[dict[str, object]], bool]:
    if mt.source_group_code == "HP_MH":
        return _plan_hp_mh(session, mt, source_sku, range_start, range_end)
    mapping = _mapping(session, mt.id, source_sku, range_end)
    source_rows = session.scalars(
        select(SourceFile)
        .where(
            SourceFile.modern_trade_id == mt.id,
            SourceFile.detected_data_date >= range_start,
            SourceFile.detected_data_date <= range_end,
        )
        .order_by(SourceFile.detected_data_date, SourceFile.id)
    ).all()
    grouped: dict[date, list[SourceFile]] = defaultdict(list)
    for row in source_rows:
        assert row.detected_data_date is not None
        grouped[row.detected_data_date].append(row)
    batches = {
        batch.data_date: batch
        for batch in session.scalars(
            select(ImportBatch).where(
                ImportBatch.modern_trade_id == mt.id,
                ImportBatch.data_date >= range_start,
                ImportBatch.data_date <= range_end,
                ImportBatch.status.in_(AVAILABLE_BATCH_STATUSES),
            )
        )
    }
    existing_dates = set(
        session.scalars(
            select(SalesInventoryFact.data_date)
            .where(
                SalesInventoryFact.modern_trade_id == mt.id,
                SalesInventoryFact.source_sku == source_sku,
                SalesInventoryFact.data_date >= range_start,
                SalesInventoryFact.data_date <= range_end,
            )
            .distinct()
        )
    )
    items: list[dict[str, object]] = []
    for data_date, rows in sorted(grouped.items()):
        batch = batches.get(data_date)
        usable = [
            row
            for row in rows
            if row.size_bytes > 0
            and Path(row.source_filename).suffix.lower() in {".xls", ".xlsx"}
            and row.status in USABLE_SOURCE_STATUSES
        ]
        status = "candidate"
        message = "พร้อมดึงเฉพาะ SKU"
        source_id = usable[0].id if len(usable) == 1 else None
        if data_date in existing_dates:
            status, message = "already_present", "มีข้อมูล SKU วันนี้แล้ว ไม่เขียนทับ"
        elif batch is None:
            status, message = "waiting_for_batch", "รอ Import ข้อมูลของวันนี้ก่อน"
        elif len(usable) != 1:
            status, message = (
                "source_conflict",
                "ไม่พบไฟล์ที่ใช้ได้เพียงหนึ่งไฟล์ใน File Registry",
            )
        elif usable[0].imported_batch_id is not None and usable[0].imported_batch_id != batch.id:
            status, message = "source_conflict", "ไฟล์ใน Registry ผูกกับ Batch อื่น"
        elif (
            usable[0].imported_batch_id != batch.id
            and usable[0].checksum_sha256 != batch.checksum_sha256
        ):
            status, message = (
                "source_conflict",
                "Checksum ของไฟล์ใน Registry ไม่ตรงกับ Batch เดิม",
            )
        items.append(
            {
                "dataDate": data_date.isoformat(),
                "status": status,
                "message": message,
                "sourceFileId": source_id,
                "batchId": batch.id if batch else None,
            }
        )
    prior_end = mapping.effective_from - timedelta(days=1)
    conflict = (
        range_start < mapping.effective_from
        and session.scalar(
            select(ItemMapping.id)
            .where(
                ItemMapping.modern_trade_id == mt.id,
                ItemMapping.source_sku == source_sku,
                ItemMapping.id != mapping.id,
                ItemMapping.effective_from <= prior_end,
                (ItemMapping.effective_to.is_(None) | (ItemMapping.effective_to >= range_start)),
            )
            .limit(1)
        )
        is not None
    )
    return mapping, items, conflict


def _plan_hp_mh(
    session: Session,
    mt: ModernTrade,
    source_sku: str,
    range_start: date,
    range_end: date,
) -> tuple[ItemMapping, list[dict[str, object]], bool]:
    mapping = _mapping(session, mt.id, source_sku, range_end)
    owner_id = session.scalar(select(ModernTrade.id).where(ModernTrade.code == "HP")) or mt.id
    source_rows = session.scalars(
        select(SourceFile)
        .where(
            SourceFile.modern_trade_id == owner_id,
            SourceFile.detected_data_date >= range_start,
            SourceFile.detected_data_date <= range_end,
            SourceFile.source_kind.in_(("inventory", "sales")),
        )
        .order_by(SourceFile.detected_data_date, SourceFile.id)
    ).all()
    grouped: dict[date, list[SourceFile]] = defaultdict(list)
    for row in source_rows:
        if row.detected_data_date is not None:
            grouped[row.detected_data_date].append(row)
    batches = {
        batch.data_date: batch
        for batch in session.scalars(
            select(ImportBatch).where(
                ImportBatch.modern_trade_id == mt.id,
                ImportBatch.data_date >= range_start,
                ImportBatch.data_date <= range_end,
                ImportBatch.status.in_(AVAILABLE_BATCH_STATUSES),
            )
        )
    }
    existing_dates = set(
        session.scalars(
            select(SalesInventoryFact.data_date)
            .where(
                SalesInventoryFact.modern_trade_id == mt.id,
                SalesInventoryFact.source_sku == source_sku,
                SalesInventoryFact.data_date >= range_start,
                SalesInventoryFact.data_date <= range_end,
            )
            .distinct()
        )
    )
    items: list[dict[str, object]] = []
    for data_date, rows in sorted(grouped.items()):
        inventory = [
            row
            for row in rows
            if row.source_kind == "inventory"
            and row.size_bytes > 0
            and row.status in USABLE_SOURCE_STATUSES
        ]
        sales = [
            row
            for row in rows
            if row.source_kind == "sales"
            and row.size_bytes > 0
            and row.status in USABLE_SOURCE_STATUSES
        ]
        batch = batches.get(data_date)
        status, message = "candidate", "พร้อมดึงเฉพาะ SKU"
        if data_date in existing_dates:
            status, message = "already_present", "มีข้อมูล SKU วันนี้แล้ว ไม่เขียนทับ"
        elif batch is None:
            status, message = "waiting_for_batch", "รอ Import ข้อมูลของวันนี้ก่อน"
        elif len(inventory) != 1 or len(sales) != 1:
            status, message = "source_conflict", "ไม่พบคู่ไฟล์ Inventory/Sale Out ที่ใช้ได้"
        items.append(
            {
                "dataDate": data_date.isoformat(),
                "status": status,
                "message": message,
                "sourceFileId": inventory[0].id if len(inventory) == 1 else None,
                "inventorySourceFileId": inventory[0].id if len(inventory) == 1 else None,
                "salesSourceFileId": sales[0].id if len(sales) == 1 else None,
                "batchId": batch.id if batch else None,
            }
        )
    prior_end = mapping.effective_from - timedelta(days=1)
    conflict = (
        range_start < mapping.effective_from
        and session.scalar(
            select(ItemMapping.id)
            .where(
                ItemMapping.modern_trade_id == mt.id,
                ItemMapping.source_sku == source_sku,
                ItemMapping.id != mapping.id,
                ItemMapping.effective_from <= prior_end,
                ItemMapping.effective_to.is_(None) | (ItemMapping.effective_to >= range_start),
            )
            .limit(1)
        )
        is not None
    )
    return mapping, items, conflict


def preview_sku_backfill(
    session: Session,
    mt: ModernTrade,
    source_sku: str,
    range_start: date | None,
) -> dict[str, object]:
    registry = backfill_options(session, mt)["registry"]
    earliest = registry["earliestDate"]
    latest = registry["latestDate"]
    if not earliest or not latest:
        raise ValueError(f"File Registry ยังไม่มีวันที่ข้อมูลสำหรับ {mt.code}")
    selected_start = range_start or date.fromisoformat(str(earliest))
    selected_end = date.fromisoformat(str(latest))
    if selected_start < date.fromisoformat(str(earliest)):
        raise ValueError("วันที่เริ่มต้นต้องไม่ก่อนวันแรกใน File Registry")
    if selected_start > selected_end:
        raise ValueError("วันที่เริ่มต้นต้องไม่เกินวันที่ล่าสุดใน File Registry")
    mapping, items, conflict = _plan(
        session,
        mt,
        source_sku.strip(),
        selected_start,
        selected_end,
    )
    counts = {
        status: sum(item["status"] == status for item in items)
        for status in (
            "candidate",
            "already_present",
            "waiting_for_batch",
            "source_conflict",
        )
    }
    return {
        "sourceSku": source_sku.strip(),
        "rangeStart": selected_start.isoformat(),
        "rangeEnd": selected_end.isoformat(),
        "mappingEffectiveFrom": mapping.effective_from.isoformat(),
        "mappingWillMoveTo": (
            selected_start.isoformat() if selected_start < mapping.effective_from else None
        ),
        "mappingConflict": conflict,
        "registry": registry,
        "counts": counts,
        "dates": items,
    }


def create_sku_backfill_run(
    session: Session,
    mt: ModernTrade,
    *,
    source_sku: str,
    range_start: date | None,
    actor: str,
) -> ImportRun:
    preview = preview_sku_backfill(session, mt, source_sku, range_start)
    if preview["mappingConflict"]:
        raise ValueError("ช่วงวันที่ Backfill ชนกับ Mapping เดิมของ SKU นี้")
    if preview["counts"]["candidate"] == 0:
        raise ValueError("ไม่พบวันที่ที่ต้อง Backfill")
    active = session.scalar(
        select(ImportRun.id)
        .where(
            ImportRun.modern_trade_id == mt.id,
            ImportRun.status.in_(ACTIVE_RUN_STATUSES),
        )
        .limit(1)
    )
    if active is not None:
        raise ActiveRunError(f"{mt.code} กำลังประมวลผลอยู่ใน Run {active}")
    selected_start = date.fromisoformat(str(preview["rangeStart"]))
    selected_end = date.fromisoformat(str(preview["rangeEnd"]))
    mapping = _mapping(session, mt.id, source_sku, selected_end)
    if selected_start < mapping.effective_from:
        before = mapping.effective_from
        mapping.effective_from = selected_start
        mapping.changed_by = actor
        session.add(
            AuditEvent(
                entity_type="item_mapping",
                entity_id=source_sku,
                action="extend_effective_from_for_backfill",
                actor=actor,
                before_json=json.dumps({"effectiveFrom": before.isoformat()}),
                after_json=json.dumps({"effectiveFrom": selected_start.isoformat()}),
            )
        )
    interest = session.scalar(
        select(SkuInterest).where(
            SkuInterest.modern_trade_id == mt.id,
            SkuInterest.source_sku == source_sku,
        )
    )
    if interest is None:
        interest = SkuInterest(
            modern_trade_id=mt.id,
            source_sku=source_sku,
            source_description=mapping.source_description,
            status="active",
            first_seen_date=selected_start,
            last_seen_date=selected_end,
            decided_by=actor,
            decided_at=bangkok_now(),
        )
        session.add(interest)
        session.add(
            AuditEvent(
                entity_type="sku_interest",
                entity_id=f"{mt.id}:{source_sku}",
                action="activate_for_backfill",
                actor=actor,
                before_json=None,
                after_json=json.dumps({"status": "active"}),
            )
        )
    elif interest.status != "active":
        before_status = interest.status
        interest.status = "active"
        interest.decided_by = actor
        interest.decided_at = bangkok_now()
        session.add(
            AuditEvent(
                entity_type="sku_interest",
                entity_id=f"{mt.id}:{source_sku}",
                action="activate_for_backfill",
                actor=actor,
                before_json=json.dumps({"status": before_status}),
                after_json=json.dumps({"status": "active"}),
            )
        )
    run = ImportRun(
        modern_trade_id=mt.id,
        trigger="manual",
        mode="sku_backfill",
        status="queued",
        requested_by=actor,
        target_sku=source_sku,
        range_start=selected_start,
        range_end=selected_end,
        results_json="[]",
        summary_message="รอ Worker เริ่ม Single-SKU Backfill",
    )
    session.add(run)
    try:
        session.flush()
        session.add(
            AuditEvent(
                entity_type="import_run",
                entity_id=str(run.id),
                action="queued",
                actor=actor,
                before_json=None,
                after_json=json.dumps(
                    {
                        "mode": "sku_backfill",
                        "sourceSku": source_sku,
                        "rangeStart": selected_start.isoformat(),
                        "rangeEnd": selected_end.isoformat(),
                    }
                ),
            )
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ActiveRunError(f"{mt.code} กำลังประมวลผลอยู่") from exc
    session.refresh(run)
    return run


def _save_progress(
    session: Session,
    run: ImportRun,
    results: list[dict[str, object]],
    total: int,
    message: str,
) -> None:
    run.found_count = total
    run.imported_count = sum(item["status"] == "imported" for item in results)
    run.skipped_count = sum(item["status"] in {"already_present", "not_found"} for item in results)
    run.pending_count = sum(
        item["status"] in {"waiting_for_batch", "source_conflict"} for item in results
    )
    run.failed_count = sum(item["status"] == "failed" for item in results)
    run.results_json = json.dumps(results, ensure_ascii=False)
    run.summary_message = message


def _finish(
    session: Session,
    run: ImportRun,
    mt: ModernTrade,
    results: list[dict[str, object]],
    total: int,
) -> None:
    _save_progress(session, run, results, total, "")
    run.status = "success_with_warnings" if run.pending_count or run.failed_count else "success"
    run.finished_at = bangkok_now()
    run.summary_message = (
        f"SKU {run.target_sku} · ตรวจ {len(results)}/{total} วัน · "
        f"เติมสำเร็จ {run.imported_count} · ข้าม {run.skipped_count} · "
        f"รอตรวจสอบ {run.pending_count} · ล้มเหลว {run.failed_count}"
    )
    delivery = send_telegram(
        session,
        (
            f"⚠️ {mt.code} SKU Backfill สำเร็จพร้อมคำเตือน"
            if run.status == "success_with_warnings"
            else f"✅ {mt.code} SKU Backfill สำเร็จ"
        ),
        [
            f"SKU: {run.target_sku}",
            f"ช่วงวันที่: {run.range_start:%d/%m/%Y} – {run.range_end:%d/%m/%Y}",
            (
                f"เติมสำเร็จ {run.imported_count} · ข้าม {run.skipped_count} · "
                f"รอตรวจสอบ {run.pending_count} · ล้มเหลว {run.failed_count}"
            ),
        ],
        force=True,
    )
    session.add(
        AuditEvent(
            entity_type="import_run",
            entity_id=str(run.id),
            action=run.status,
            actor=run.requested_by,
            before_json=None,
            after_json=json.dumps(
                {
                    "mode": run.mode,
                    "sourceSku": run.target_sku,
                    "results": results,
                    "notification": {
                        "status": delivery.status,
                        "message": delivery.message,
                    },
                },
                ensure_ascii=False,
            ),
        )
    )
    session.commit()


def process_sku_backfill_run(session: Session, run_id: int) -> None:
    run = session.get(ImportRun, run_id)
    if run is None or run.status != "running" or run.mode != "sku_backfill":
        return
    mt = session.get(ModernTrade, run.modern_trade_id)
    if mt is None or not run.target_sku or not run.range_start or not run.range_end:
        raise AutomaticImportError("ข้อมูล Single-SKU Backfill Run ไม่ครบ")
    try:
        _, username, password = _credentials(session, mt)
        _, plan, conflict = _plan(
            session,
            mt,
            run.target_sku,
            run.range_start,
            run.range_end,
        )
        if conflict:
            raise ValueError("ช่วงวันที่ Backfill ชนกับ Mapping เดิมของ SKU นี้")
        try:
            results = json.loads(run.results_json or "[]")
        except json.JSONDecodeError:
            results = []
        if not isinstance(results, list):
            results = []
        finished_dates = {item.get("dataDate") for item in results}
        total = len(plan)
        run.found_count = total
        session.commit()
        for index, item in enumerate(plan, start=1):
            data_date_text = str(item["dataDate"])
            if data_date_text in finished_dates:
                continue
            run = session.get(ImportRun, run_id)
            assert run is not None
            run.summary_message = (
                f"กำลังตรวจวันที่ {index}/{total} · {data_date_text} · SKU {run.target_sku}"
            )
            session.commit()
            if item["status"] != "candidate":
                results.append(item)
                _save_progress(session, run, results, total, run.summary_message)
                session.commit()
            else:
                try:
                    source = session.get(SourceFile, int(item["sourceFileId"]))
                    batch = session.get(ImportBatch, int(item["batchId"]))
                    if source is None or batch is None:
                        raise ValueError("File Registry หรือ Batch เปลี่ยนระหว่าง Run")
                    if mt.source_group_code == "HP_MH":
                        from app.services.hp_mh_automatic_import import (
                            HpMhPairCandidate,
                            _download_pair,
                        )

                        inventory = session.get(SourceFile, int(item["inventorySourceFileId"]))
                        sales = session.get(SourceFile, int(item["salesSourceFileId"]))
                        if inventory is None or sales is None:
                            raise ValueError("คู่ไฟล์ใน Registry เปลี่ยนระหว่าง Run")
                        pair_extract = _download_pair(
                            HpMhPairCandidate(
                                key=inventory.pair_key or str(inventory.detected_data_date),
                                inventory=SourceCandidate(
                                    inventory.source_path,
                                    inventory.source_filename,
                                    inventory.size_bytes,
                                    inventory.modified_at,
                                ),
                                sales=SourceCandidate(
                                    sales.source_path,
                                    sales.source_filename,
                                    sales.size_bytes,
                                    sales.modified_at,
                                ),
                                superseded=(),
                            ),
                            username=username,
                            password=password,
                        )
                        extract = pair_extract.hp if mt.code == "HP" else pair_extract.mh
                        count = append_hp_mh_sku_facts(session, batch, extract, run.target_sku)
                    else:
                        candidate = SourceCandidate(
                            path=source.source_path,
                            filename=source.source_filename,
                            size_bytes=source.size_bytes,
                            modified_at=source.modified_at,
                        )
                        extract = download_twd_extract(
                            candidate, username=username, password=password
                        )
                        if extract.data_date.isoformat() != data_date_text:
                            raise ValueError("วันที่ในไฟล์เปลี่ยนจาก File Registry")
                        count = append_twd_sku_facts(session, batch, extract, run.target_sku)
                    outcome = {
                        **item,
                        "status": "imported" if count else "not_found",
                        "message": (
                            f"เติม {count} Branch สำเร็จ" if count else "ไม่พบ SKU นี้ในไฟล์ต้นทาง"
                        ),
                    }
                    results.append(outcome)
                    _save_progress(session, run, results, total, str(outcome["message"]))
                    session.commit()
                except (TwdFormatError, OSError, ValueError) as exc:
                    session.rollback()
                    run = session.get(ImportRun, run_id)
                    assert run is not None
                    outcome = {
                        **item,
                        "status": "failed",
                        "message": str(exc)[:1000],
                    }
                    results.append(outcome)
                    _save_progress(session, run, results, total, str(outcome["message"]))
                    session.commit()
            session.expire_all()
            run = session.get(ImportRun, run_id)
            assert run is not None
            if run.status == "stop_requested":
                run.status = "stopped"
                run.finished_at = bangkok_now()
                run.summary_message = (
                    f"หยุดหลังจบไฟล์ปัจจุบัน · ทำแล้ว {len(results)}/{total} วัน สามารถกดทำต่อได้"
                )
                session.commit()
                return
        run = session.get(ImportRun, run_id)
        assert run is not None
        _finish(session, run, mt, results, total)
    except Exception as exc:
        logger.exception("SKU backfill run %s failed", run_id)
        session.rollback()
        run = session.get(ImportRun, run_id)
        assert run is not None
        run.status = "failed"
        run.finished_at = bangkok_now()
        run.error_message = f"{type(exc).__name__}: {exc}"[:1000]
        run.summary_message = "Single-SKU Backfill ไม่สำเร็จ ข้อมูลวันที่ที่ Commit แล้วไม่ถูกลบ"
        session.commit()
        send_telegram(
            session,
            f"❌ {mt.code} SKU Backfill ไม่สำเร็จ",
            [f"SKU: {run.target_sku}", f"สาเหตุ: {run.error_message}"],
            force=True,
        )
    finally:
        smbclient.reset_connection_cache()

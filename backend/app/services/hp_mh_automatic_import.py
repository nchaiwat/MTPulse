from __future__ import annotations

import json
import logging
import ntpath
import re
import shutil
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import smbclient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.importers.hp_mh import HpMhFormatError, HpMhPairExtract, extract_hp_mh_pair
from app.local_time import bangkok_now
from app.models import AuditEvent, ImportBatch, ImportRun, ModernTrade, SkuInterest, SourceFile
from app.services.automatic_import import (
    AutomaticImportError,
    SourceCandidate,
    _credentials,
    list_twd_source_files,
)
from app.services.hp_mh_import import HpMhImportError, _sync_sale_interests, import_hp_mh_pair
from app.services.telegram import send_telegram

SOURCE_GROUP = "HP_MH"
INCREMENTAL_LOOKBACK_DAYS = 7
GENERATION_PATTERN = re.compile(r"_(\d{8})_(\d{6})(?:\.[^.]+)?$", re.I)
logger = logging.getLogger("mtpulse.hp_mh_automatic_import")


@dataclass(frozen=True)
class HpMhPairCandidate:
    key: str
    inventory: SourceCandidate | None
    sales: SourceCandidate | None
    superseded: tuple[tuple[str, SourceCandidate], ...]


def hp_mh_owner(session: Session) -> ModernTrade:
    owner = session.scalar(select(ModernTrade).where(ModernTrade.code == "HP"))
    if owner is None:
        raise AutomaticImportError("ยังไม่มี Modern Trade HP กรุณารัน Migration ล่าสุด")
    return owner


def list_hp_mh_pairs(candidates: list[SourceCandidate]) -> list[HpMhPairCandidate]:
    grouped: dict[str, dict[str, list[SourceCandidate]]] = defaultdict(
        lambda: {"inventory": [], "sales": []}
    )
    for candidate in candidates:
        lower = candidate.filename.lower()
        kind = (
            "inventory" if "inventorydata" in lower else "sales" if "salesdata" in lower else None
        )
        if kind is None or Path(candidate.filename).suffix.lower() != ".zip":
            continue
        grouped[ntpath.dirname(candidate.path).lower()][kind].append(candidate)

    pairs = []
    for key, files in grouped.items():
        selected = {
            kind: max(values, key=_candidate_order) if values else None
            for kind, values in files.items()
        }
        superseded = tuple(
            (kind, candidate)
            for kind, values in files.items()
            for candidate in values
            if candidate != selected[kind]
        )
        pairs.append(
            HpMhPairCandidate(
                key=key,
                inventory=selected["inventory"],
                sales=selected["sales"],
                superseded=superseded,
            )
        )
    return sorted(pairs, key=lambda pair: pair.key)


def _candidate_order(candidate: SourceCandidate) -> tuple[datetime, datetime, str]:
    match = GENERATION_PATTERN.search(candidate.filename)
    if match:
        try:
            generated = datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S")
        except ValueError:
            generated = candidate.modified_at.replace(tzinfo=None)
    else:
        generated = candidate.modified_at.replace(tzinfo=None)
    return generated, candidate.modified_at.replace(tzinfo=None), candidate.filename.lower()


def process_hp_mh_run(session: Session, run_id: int) -> None:
    run = session.get(ImportRun, run_id)
    if run is None or run.status != "running":
        return
    owner = session.get(ModernTrade, run.modern_trade_id)
    if owner is None or owner.code != "HP":
        raise AutomaticImportError("Shared HP/MH Run ต้องผูกกับ HP coordinator")
    try:
        root, username, password = _credentials(session, owner)
        candidates = list_twd_source_files(root, username=username, password=password)
        pairs = list_hp_mh_pairs(candidates)
        if run.mode != "scan":
            pairs = _incremental_pairs(session, owner.id, pairs)
        run.found_count = len(pairs)
        run.summary_message = f"พบ {len(pairs)} คู่ไฟล์ · กำลังตรวจสอบ HP/MH"
        session.commit()
        results: list[dict] = []
        for index, pair in enumerate(pairs, start=1):
            run.summary_message = f"กำลังตรวจคู่ไฟล์ {index}/{len(pairs)} · {pair.key}"
            session.commit()
            results.append(
                _process_pair(
                    session,
                    run,
                    owner,
                    pair,
                    username=username,
                    password=password,
                )
            )
        _finish_hp_mh_run(session, run, results)
    except Exception as exc:
        logger.exception("shared HP/MH import run %s failed", run_id)
        session.rollback()
        run = session.get(ImportRun, run_id)
        assert run is not None
        run.status = "failed"
        run.finished_at = bangkok_now()
        run.error_message = f"ประมวลผล HP/MH ไม่สำเร็จ: {type(exc).__name__}: {exc}"[:1000]
        run.summary_message = "Shared Run ไม่สำเร็จและไม่มีการลบข้อมูลเดิม"
        session.commit()
        send_telegram(
            session,
            "❌ Automatic Import HP/MH ไม่สำเร็จ",
            [f"⚠️ {run.error_message}"],
            force=True,
        )
    finally:
        smbclient.reset_connection_cache()


def _incremental_pairs(
    session: Session,
    owner_id: int,
    pairs: list[HpMhPairCandidate],
) -> list[HpMhPairCandidate]:
    threshold = bangkok_now() - timedelta(days=INCREMENTAL_LOOKBACK_DAYS)
    result = []
    for pair in pairs:
        selected = [item for item in (pair.inventory, pair.sales) if item is not None]
        rows = [
            session.scalar(
                select(SourceFile).where(
                    SourceFile.modern_trade_id == owner_id,
                    SourceFile.source_path == candidate.path,
                )
            )
            for candidate in selected
        ]
        unchanged_success = bool(selected) and all(
            row is not None
            and row.size_bytes == candidate.size_bytes
            and row.modified_at == candidate.modified_at
            and row.status in {"imported", "duplicate", "superseded"}
            for row, candidate in zip(rows, selected, strict=True)
        )
        recently_modified = any(candidate.modified_at >= threshold for candidate in selected)
        needs_retry = any(
            row is None or row.status in {"failed", "pending_review", "missing", "ready"}
            for row in rows
        )
        if not unchanged_success or recently_modified or needs_retry:
            result.append(pair)
    return result


def _process_pair(
    session: Session,
    run: ImportRun,
    owner: ModernTrade,
    pair: HpMhPairCandidate,
    *,
    username: str,
    password: str,
) -> dict:
    for kind, candidate in pair.superseded:
        row = _source_row(session, owner.id, run.id, candidate, kind, pair.key)
        row.status = "superseded"
        row.error_message = "มีไฟล์รุ่นใหม่กว่าในโฟลเดอร์วันเดียวกัน"
    if pair.inventory is None or pair.sales is None:
        missing = "Inventory" if pair.inventory is None else "Sale Out"
        for kind, candidate in (
            ("inventory", pair.inventory),
            ("sales", pair.sales),
        ):
            if candidate is not None:
                row = _source_row(session, owner.id, run.id, candidate, kind, pair.key)
                row.status = "pending_review"
                row.error_message = f"คู่ไฟล์ไม่ครบ: ไม่พบ {missing}"
        session.commit()
        return _outcome(
            pair,
            "pending_review",
            f"คู่ไฟล์ไม่ครบ: ไม่พบ {missing}",
        )

    inventory_unchanged = _candidate_is_imported_unchanged(session, owner.id, pair.inventory)
    sales_unchanged = _candidate_is_imported_unchanged(session, owner.id, pair.sales)
    inventory_row = _source_row(session, owner.id, run.id, pair.inventory, "inventory", pair.key)
    sales_row = _source_row(session, owner.id, run.id, pair.sales, "sales", pair.key)
    if inventory_unchanged and sales_unchanged:
        session.commit()
        return _outcome(pair, "skipped", "ข้อมูลคู่ไฟล์นี้ถูกนำเข้าแล้ว", event="unchanged")

    try:
        extract = _download_pair(
            pair,
            username=username,
            password=password,
        )
        inventory_row.checksum_sha256 = extract.inventory_checksum
        sales_row.checksum_sha256 = extract.sales_checksum
        for row in (inventory_row, sales_row):
            row.detected_data_date = extract.data_date
            row.business_fingerprint = extract.business_fingerprint

        trades = {
            mt.code: mt
            for mt in session.scalars(select(ModernTrade).where(ModernTrade.code.in_(("HP", "MH"))))
        }
        existing = {
            code: session.scalar(
                select(ImportBatch).where(
                    ImportBatch.modern_trade_id == trades[code].id,
                    ImportBatch.data_date == extract.data_date,
                )
            )
            for code in ("HP", "MH")
        }
        if all(
            batch is not None and batch.business_fingerprint == extract.business_fingerprint
            for batch in existing.values()
        ):
            for row in (inventory_row, sales_row):
                row.status = "duplicate"
                row.error_message = "Business Fingerprint เหมือนข้อมูลที่นำเข้าแล้ว"
                row.imported_batch_id = existing["HP"].id
            session.commit()
            return _outcome(
                pair,
                "skipped",
                "Business Fingerprint เหมือนข้อมูลที่นำเข้าแล้ว",
                extract=extract,
            )

        if run.mode in {"scan", "registry"}:
            for code, mt_extract in (("HP", extract.hp), ("MH", extract.mh)):
                _sync_sale_interests(
                    session,
                    trades[code].id,
                    mt_extract,
                    baseline=True,
                )
            for row in (inventory_row, sales_row):
                row.status = "ready"
                row.error_message = "คู่ไฟล์ใหม่พร้อมนำเข้า"
            session.commit()
            return _outcome(
                pair,
                "ready",
                "คู่ไฟล์ใหม่พร้อมนำเข้า",
                extract=extract,
            )

        before_pending = _pending_counts(session)
        batches = import_hp_mh_pair(
            session,
            extract,
            actor=run.requested_by,
        )
        after_pending = _pending_counts(session)
        for row in (inventory_row, sales_row):
            row.status = "imported"
            row.error_message = None
            row.imported_batch_id = batches["HP"].id
        session.commit()
        return _outcome(
            pair,
            "imported",
            "นำเข้า HP และ MH สำเร็จ",
            extract=extract,
            batch_ids={code: batch.id for code, batch in batches.items()},
            new_pending={
                code: max(0, after_pending[code] - before_pending[code]) for code in ("HP", "MH")
            },
        )
    except (HpMhFormatError, HpMhImportError, OSError, ValueError) as exc:
        session.rollback()
        _record_pair_failure(session, run, owner, pair, str(exc))
        return _outcome(pair, "failed", f"ข้ามคู่ไฟล์: {exc}")


def _download_pair(
    pair: HpMhPairCandidate,
    *,
    username: str,
    password: str,
) -> HpMhPairExtract:
    assert pair.inventory is not None and pair.sales is not None
    with tempfile.TemporaryDirectory(prefix="mtpulse-hp-mh-") as temp_dir:
        local_inventory = Path(temp_dir) / pair.inventory.filename
        local_sales = Path(temp_dir) / pair.sales.filename
        for candidate, target in (
            (pair.inventory, local_inventory),
            (pair.sales, local_sales),
        ):
            with (
                smbclient.open_file(
                    candidate.path,
                    mode="rb",
                    username=username,
                    password=password,
                    port=445,
                    connection_timeout=20,
                ) as source,
                target.open("wb") as destination,
            ):
                shutil.copyfileobj(source, destination, length=1024 * 1024)
        extract = extract_hp_mh_pair(local_inventory, local_sales)
    return HpMhPairExtract(
        **{
            **extract.__dict__,
            "inventory_path": pair.inventory.path,
            "sales_path": pair.sales.path,
            "inventory_filename": pair.inventory.filename,
            "sales_filename": pair.sales.filename,
        }
    )


def _source_row(
    session: Session,
    owner_id: int,
    run_id: int,
    candidate: SourceCandidate,
    kind: str,
    pair_key: str,
) -> SourceFile:
    row = session.scalar(
        select(SourceFile).where(
            SourceFile.modern_trade_id == owner_id,
            SourceFile.source_path == candidate.path,
        )
    )
    if row is None:
        row = SourceFile(
            modern_trade_id=owner_id,
            source_path=candidate.path,
            source_filename=candidate.filename,
            size_bytes=candidate.size_bytes,
            modified_at=candidate.modified_at,
            status="discovered",
        )
        session.add(row)
        session.flush()
    row.source_filename = candidate.filename
    row.size_bytes = candidate.size_bytes
    row.modified_at = candidate.modified_at
    row.last_seen_run_id = run_id
    row.last_seen_at = bangkok_now()
    row.source_kind = kind
    row.pair_key = pair_key
    match = GENERATION_PATTERN.search(candidate.filename)
    if match:
        row.pair_generation_at = datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S").replace(
            tzinfo=UTC
        )
    return row


def _candidate_is_imported_unchanged(
    session: Session,
    owner_id: int,
    candidate: SourceCandidate,
) -> bool:
    row = session.scalar(
        select(SourceFile).where(
            SourceFile.modern_trade_id == owner_id,
            SourceFile.source_path == candidate.path,
        )
    )
    return bool(
        row
        and row.status in {"imported", "duplicate"}
        and row.size_bytes == candidate.size_bytes
        and row.modified_at == candidate.modified_at
    )


def _record_pair_failure(
    session: Session,
    run: ImportRun,
    owner: ModernTrade,
    pair: HpMhPairCandidate,
    message: str,
) -> None:
    for kind, candidate in (
        ("inventory", pair.inventory),
        ("sales", pair.sales),
    ):
        if candidate is None:
            continue
        row = _source_row(session, owner.id, run.id, candidate, kind, pair.key)
        row.status = "failed"
        row.error_message = f"ข้ามคู่ไฟล์: {message}"[:1000]
    session.commit()


def _pending_counts(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(ModernTrade.code, func.count(SkuInterest.id))
        .join(SkuInterest, SkuInterest.modern_trade_id == ModernTrade.id)
        .where(
            ModernTrade.code.in_(("HP", "MH")),
            SkuInterest.status == "pending",
        )
        .group_by(ModernTrade.code)
    ).all()
    result = {"HP": 0, "MH": 0}
    result.update({code: int(count) for code, count in rows})
    return result


def _outcome(
    pair: HpMhPairCandidate,
    status: str,
    message: str,
    *,
    extract: HpMhPairExtract | None = None,
    batch_ids: dict[str, int] | None = None,
    new_pending: dict[str, int] | None = None,
    event: str | None = None,
) -> dict:
    mt = {}
    if extract:
        for code, mt_extract in (("HP", extract.hp), ("MH", extract.mh)):
            mt[code] = {
                "rows": mt_extract.summary.row_count,
                "stores": mt_extract.summary.store_count,
                "skus": mt_extract.summary.sku_count,
                "returns": mt_extract.summary.negative_row_count,
                "salesQty": float(mt_extract.summary.sales_qty),
                "salesAmount": float(mt_extract.summary.amount),
                "stockOnHand": float(mt_extract.summary.stock_on_hand),
                "stockValue": float(mt_extract.summary.stock_value),
                "newPendingSkus": (new_pending or {}).get(code, 0),
                "batchId": (batch_ids or {}).get(code),
            }
    return {
        "pairKey": pair.key,
        "inventoryFilename": pair.inventory.filename if pair.inventory else None,
        "salesFilename": pair.sales.filename if pair.sales else None,
        "dataDate": extract.data_date.isoformat() if extract else None,
        "status": status,
        "message": message,
        "event": event,
        "mt": mt,
    }


def _finish_hp_mh_run(
    session: Session,
    run: ImportRun,
    results: list[dict],
) -> None:
    counts = {
        "imported": sum(item["status"] == "imported" for item in results),
        "ready": sum(item["status"] == "ready" for item in results),
        "pending": sum(item["status"] == "pending_review" for item in results),
        "failed": sum(item["status"] == "failed" for item in results),
    }
    counts["skipped"] = len(results) - sum(counts.values())
    run.found_count = len(results)
    run.imported_count = counts["imported"]
    run.ready_count = counts["ready"]
    run.pending_count = counts["pending"]
    run.failed_count = counts["failed"]
    run.skipped_count = counts["skipped"]
    run.status = "success_with_warnings" if counts["pending"] or counts["failed"] else "success"
    run.finished_at = bangkok_now()
    run.summary_message = (
        f"พบ {len(results)} คู่ · นำเข้า {counts['imported']} · "
        f"พร้อม {counts['ready']} · ข้าม {counts['skipped']} · "
        f"รอตรวจ {counts['pending']} · ล้มเหลว {counts['failed']}"
    )
    run.results_json = json.dumps(results, ensure_ascii=False)
    event_results = [item for item in results if item.get("event") != "unchanged"]
    lines = [
        f"▶️ Trigger: {run.trigger}",
        f"📂 Mode: {run.mode}",
        ("📊 ไม่พบไฟล์ใหม่หรือการเปลี่ยนแปลง" if not event_results else f"📊 {run.summary_message}"),
    ]
    for code in ("HP", "MH"):
        totals = {
            "rows": sum(item.get("mt", {}).get(code, {}).get("rows", 0) for item in event_results),
            "new": sum(
                item.get("mt", {}).get(code, {}).get("newPendingSkus", 0) for item in event_results
            ),
        }
        lines.append(f"{code}: records {totals['rows']:,} · SKU ใหม่ {totals['new']:,}")
    delivery = send_telegram(
        session,
        (
            "⚠️ Automatic Import HP/MH สำเร็จพร้อมคำเตือน"
            if counts["pending"] or counts["failed"]
            else "✅ Automatic Import HP/MH สำเร็จ"
        ),
        lines,
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
                    "sourceGroup": SOURCE_GROUP,
                    "counts": counts,
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

from __future__ import annotations

import logging
import ntpath
import shutil
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import smbclient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.importers.hh import HhFormatError, HhPairExtract, extract_hh_pair
from app.local_time import bangkok_now
from app.models import ImportBatch, ImportRun, ModernTrade, SourceFile
from app.services.automatic_import import (
    AutomaticImportError,
    SourceCandidate,
    _credentials,
    _finish_run,
    list_twd_source_files,
)
from app.services.hh_import import HhImportError, import_hh_pair
from app.services.telegram import send_telegram

INCREMENTAL_LOOKBACK_DAYS = 7
logger = logging.getLogger("mtpulse.hh_automatic_import")


@dataclass(frozen=True)
class HhPairCandidate:
    key: str
    inventory: SourceCandidate | None
    sales: SourceCandidate | None
    superseded: tuple[tuple[str, SourceCandidate], ...] = ()


def list_hh_pairs(candidates: list[SourceCandidate]) -> list[HhPairCandidate]:
    grouped: dict[str, dict[str, list[SourceCandidate]]] = defaultdict(
        lambda: {"inventory": [], "sales": []}
    )
    for candidate in candidates:
        filename = candidate.filename.lower()
        kind = (
            "inventory"
            if filename == "stockreport.xlsx"
            else "sales"
            if filename == "salereport.xlsx"
            else None
        )
        if kind:
            grouped[ntpath.dirname(candidate.path).lower()][kind].append(candidate)

    pairs: list[HhPairCandidate] = []
    for key, files in grouped.items():
        selected = {
            kind: max(values, key=lambda item: (item.modified_at, item.filename.lower()))
            if values
            else None
            for kind, values in files.items()
        }
        superseded = tuple(
            (kind, candidate)
            for kind, values in files.items()
            for candidate in values
            if candidate != selected[kind]
        )
        pairs.append(
            HhPairCandidate(
                key=key,
                inventory=selected["inventory"],
                sales=selected["sales"],
                superseded=superseded,
            )
        )
    return sorted(pairs, key=lambda item: item.key)


def process_hh_run(session: Session, run_id: int) -> None:
    run = session.get(ImportRun, run_id)
    if run is None or run.status != "running":
        return
    owner = session.get(ModernTrade, run.modern_trade_id)
    if owner is None or owner.code != "HH":
        raise AutomaticImportError("HH Run ต้องผูกกับ HomeHub coordinator")
    try:
        root, username, password = _credentials(session, owner)
        candidates = list_twd_source_files(root, username=username, password=password)
        pairs = list_hh_pairs(candidates)
        if run.mode != "scan":
            pairs = _incremental_pairs(session, owner.id, pairs)
        run.found_count = len(pairs)
        run.summary_message = f"พบ {len(pairs)} คู่ไฟล์ · กำลังตรวจสอบ HH"
        session.commit()
        results = []
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
        _finish_run(session, run, owner, results)
    except Exception as exc:
        logger.exception("HH automatic import run %s failed", run_id)
        session.rollback()
        run = session.get(ImportRun, run_id)
        assert run is not None
        run.status = "failed"
        run.finished_at = bangkok_now()
        run.error_message = f"ประมวลผล HH ไม่สำเร็จ: {type(exc).__name__}: {exc}"[:1000]
        run.summary_message = "HH Run ไม่สำเร็จและไม่มีการลบข้อมูลเดิม"
        session.commit()
        send_telegram(
            session,
            "❌ Automatic Import HomeHub (HH) ไม่สำเร็จ",
            [f"⚠️ {run.error_message}"],
            force=True,
        )
    finally:
        smbclient.reset_connection_cache()


def _incremental_pairs(
    session: Session,
    owner_id: int,
    pairs: list[HhPairCandidate],
) -> list[HhPairCandidate]:
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
        unchanged = bool(selected) and all(
            row is not None
            and row.size_bytes == candidate.size_bytes
            and row.modified_at == candidate.modified_at
            and row.status in {"imported", "duplicate", "superseded"}
            for row, candidate in zip(rows, selected, strict=True)
        )
        recent = any(candidate.modified_at >= threshold for candidate in selected)
        retry = any(
            row is None or row.status in {"failed", "pending_review", "missing", "ready"}
            for row in rows
        )
        if not unchanged or recent or retry:
            result.append(pair)
    return result


def _process_pair(
    session: Session,
    run: ImportRun,
    owner: ModernTrade,
    pair: HhPairCandidate,
    *,
    username: str,
    password: str,
) -> dict:
    for kind, candidate in pair.superseded:
        row = _source_row(session, owner.id, run.id, candidate, kind, pair.key)
        row.status = "superseded"
        row.error_message = "มีไฟล์รุ่นใหม่กว่าในโฟลเดอร์วันเดียวกัน"
    if pair.inventory is None or pair.sales is None:
        missing = "StockReport.xlsx" if pair.inventory is None else "SaleReport.xlsx"
        for kind, candidate in (("inventory", pair.inventory), ("sales", pair.sales)):
            if candidate:
                row = _source_row(session, owner.id, run.id, candidate, kind, pair.key)
                row.status = "pending_review"
                row.error_message = f"คู่ไฟล์ไม่ครบ: ไม่พบ {missing}"
        session.commit()
        return _outcome(pair, "pending_review", f"คู่ไฟล์ไม่ครบ: ไม่พบ {missing}")

    inventory_row = _source_row(
        session, owner.id, run.id, pair.inventory, "inventory", pair.key
    )
    sales_row = _source_row(session, owner.id, run.id, pair.sales, "sales", pair.key)
    if _unchanged(inventory_row, pair.inventory) and _unchanged(sales_row, pair.sales):
        session.commit()
        return _outcome(pair, "skipped", "ข้อมูลคู่ไฟล์นี้ถูกนำเข้าแล้ว", event="unchanged")

    try:
        extract = _download_pair(pair, username=username, password=password)
        for row, checksum in (
            (inventory_row, extract.inventory_checksum),
            (sales_row, extract.sales_checksum),
        ):
            row.checksum_sha256 = checksum
            row.detected_data_date = extract.data_date
            row.business_fingerprint = extract.business_fingerprint
        existing = session.scalar(
            select(ImportBatch).where(
                ImportBatch.modern_trade_id == owner.id,
                ImportBatch.data_date == extract.data_date,
            )
        )
        if existing and existing.business_fingerprint == extract.business_fingerprint:
            for row in (inventory_row, sales_row):
                row.status = "duplicate"
                row.error_message = "Business Fingerprint เหมือนข้อมูลที่นำเข้าแล้ว"
                row.imported_batch_id = existing.id
            session.commit()
            return _outcome(pair, "skipped", "Business Fingerprint เหมือนข้อมูลที่นำเข้าแล้ว", extract)
        if existing:
            for row in (inventory_row, sales_row):
                row.status = "pending_review"
                row.error_message = "พบข้อมูลวันที่เดิมแต่เนื้อหาเปลี่ยน กรุณาตรวจ Corrective Import"
                row.imported_batch_id = existing.id
            session.commit()
            return _outcome(pair, "pending_review", inventory_row.error_message or "", extract)
        if run.mode in {"scan", "registry"}:
            for row in (inventory_row, sales_row):
                row.status = "ready"
                row.error_message = "คู่ไฟล์ใหม่พร้อมนำเข้า"
            session.commit()
            return _outcome(pair, "ready", "คู่ไฟล์ใหม่พร้อมนำเข้า", extract)
        batch = import_hh_pair(session, extract, actor=run.requested_by)
        for row in (inventory_row, sales_row):
            row.status = "imported"
            row.error_message = None
            row.imported_batch_id = batch.id
        session.commit()
        return _outcome(pair, "imported", "นำเข้า HomeHub (HH) สำเร็จ", extract, batch.id)
    except (HhFormatError, HhImportError, OSError, ValueError) as exc:
        session.rollback()
        for kind, candidate in (("inventory", pair.inventory), ("sales", pair.sales)):
            row = _source_row(session, owner.id, run.id, candidate, kind, pair.key)
            row.status = "failed"
            row.error_message = f"ข้ามคู่ไฟล์: {exc}"[:1000]
        session.commit()
        return _outcome(pair, "failed", f"ข้ามคู่ไฟล์: {exc}")


def _download_pair(
    pair: HhPairCandidate,
    *,
    username: str,
    password: str,
) -> HhPairExtract:
    assert pair.inventory is not None and pair.sales is not None
    with tempfile.TemporaryDirectory(prefix="mtpulse-hh-") as temp_dir:
        inventory_path = Path(temp_dir) / "StockReport.xlsx"
        sales_path = Path(temp_dir) / "SaleReport.xlsx"
        for candidate, target in ((pair.inventory, inventory_path), (pair.sales, sales_path)):
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
        extract = extract_hh_pair(inventory_path, sales_path)
    return HhPairExtract(
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
    return row


def _unchanged(row: SourceFile, candidate: SourceCandidate) -> bool:
    return bool(
        row.status in {"imported", "duplicate"}
        and row.size_bytes == candidate.size_bytes
        and row.modified_at == candidate.modified_at
    )


def _outcome(
    pair: HhPairCandidate,
    status: str,
    message: str,
    extract: HhPairExtract | None = None,
    batch_id: int | None = None,
    *,
    event: str | None = None,
) -> dict:
    return {
        "path": pair.key,
        "filename": " + ".join(
            candidate.filename
            for candidate in (pair.inventory, pair.sales)
            if candidate is not None
        ),
        "dataDate": extract.data_date.isoformat() if extract else None,
        "status": status,
        "message": message,
        "batchId": batch_id,
        "event": event,
    }

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

import smbclient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.importers.ta import FILENAME_PATTERN, TaExtract, TaFormatError, extract_ta_file
from app.local_time import bangkok_now
from app.models import ImportBatch, ImportRun, ModernTrade, SourceFile
from app.services.automatic_import import (
    AutomaticImportError,
    SourceCandidate,
    _credentials,
    _finish_run,
    _mark_missing,
    _source_row,
    _unchanged_outcome,
    list_twd_source_files,
)
from app.services.ta_import import TaImportError, import_ta_file
from app.services.telegram import send_telegram

logger = logging.getLogger("mtpulse.ta_automatic_import")


def process_ta_run(session: Session, run_id: int) -> None:
    run = session.get(ImportRun, run_id)
    if run is None or run.status != "running":
        return
    owner = session.get(ModernTrade, run.modern_trade_id)
    if owner is None or owner.code != "TA":
        raise AutomaticImportError("TA Run ต้องผูกกับ Thai-Aust coordinator")
    try:
        root, username, password = _credentials(session, owner)
        candidates = [
            candidate
            for candidate in list_twd_source_files(root, username=username, password=password)
            if FILENAME_PATTERN.fullmatch(candidate.filename)
        ]
        run.found_count = len(candidates)
        run.summary_message = f"พบ {len(candidates)} ไฟล์ · กำลังตรวจสอบ TA"
        session.commit()
        results = []
        for index, candidate in enumerate(candidates, start=1):
            run.summary_message = f"กำลังตรวจไฟล์ {index}/{len(candidates)} · {candidate.filename}"
            session.commit()
            results.append(
                _process_candidate(
                    session,
                    run,
                    owner,
                    candidate,
                    username=username,
                    password=password,
                )
            )
        results.extend(_mark_missing(session, run, owner, {item.path for item in candidates}))
        _finish_run(session, run, owner, results)
    except Exception as exc:
        logger.exception("TA automatic import run %s failed", run_id)
        session.rollback()
        run = session.get(ImportRun, run_id)
        assert run is not None
        run.status = "failed"
        run.finished_at = bangkok_now()
        run.error_message = f"ประมวลผล TA ไม่สำเร็จ: {type(exc).__name__}: {exc}"[:1000]
        run.summary_message = "TA Run ไม่สำเร็จและไม่มีการลบข้อมูลเดิม"
        session.commit()
        send_telegram(
            session,
            "❌ Automatic Import Thai-Aust (TA) ไม่สำเร็จ",
            [f"⚠️ {run.error_message}"],
            force=True,
        )
    finally:
        smbclient.reset_connection_cache()


def _process_candidate(
    session: Session,
    run: ImportRun,
    owner: ModernTrade,
    candidate: SourceCandidate,
    *,
    username: str,
    password: str,
) -> dict:
    row = _source_row(session, owner, candidate)
    unchanged = _ta_unchanged_outcome(row, candidate)
    if unchanged is not None:
        row.last_seen_run_id = run.id
        row.last_seen_at = bangkok_now()
        session.commit()
        return unchanged
    row.source_filename = candidate.filename
    row.size_bytes = candidate.size_bytes
    row.modified_at = candidate.modified_at
    row.last_seen_run_id = run.id
    row.last_seen_at = bangkok_now()
    row.source_kind = "combined"
    try:
        extract = _download(candidate, username=username, password=password)
        row.checksum_sha256 = extract.checksum_sha256
        row.detected_data_date = extract.data_date
        row.business_fingerprint = extract.business_fingerprint
        existing = session.scalar(
            select(ImportBatch).where(
                ImportBatch.modern_trade_id == owner.id,
                ImportBatch.data_date == extract.data_date,
            )
        )
        if existing and existing.business_fingerprint == extract.business_fingerprint:
            return _save_outcome(
                session,
                row,
                candidate,
                extract,
                "duplicate",
                "Business Fingerprint เหมือนข้อมูลที่นำเข้าแล้ว",
                existing.id,
            )
        if existing:
            return _save_outcome(
                session,
                row,
                candidate,
                extract,
                "pending_review",
                "พบข้อมูลวันที่เดิมแต่เนื้อหาเปลี่ยน กรุณาตรวจ Corrective Import",
                existing.id,
            )
        if run.mode in {"scan", "registry"}:
            return _save_outcome(session, row, candidate, extract, "ready", "ไฟล์ใหม่พร้อมนำเข้า", None)
        batch = import_ta_file(session, extract, actor=run.requested_by)
        row = session.get(SourceFile, row.id)
        assert row is not None
        return _save_outcome(
            session, row, candidate, extract, "imported", "นำเข้า Thai-Aust (TA) สำเร็จ", batch.id
        )
    except (TaFormatError, TaImportError, OSError, ValueError) as exc:
        session.rollback()
        row = _source_row(session, owner, candidate)
        row.source_filename = candidate.filename
        row.size_bytes = candidate.size_bytes
        row.modified_at = candidate.modified_at
        row.last_seen_run_id = run.id
        row.last_seen_at = bangkok_now()
        row.status = "failed"
        row.error_message = f"ข้ามไฟล์: {exc}"[:1000]
        session.commit()
        return {
            "path": candidate.path,
            "filename": candidate.filename,
            "dataDate": None,
            "status": "failed",
            "message": row.error_message,
            "batchId": None,
        }


def _save_outcome(
    session: Session,
    row: SourceFile,
    candidate: SourceCandidate,
    extract: TaExtract,
    status: str,
    message: str,
    batch_id: int | None,
) -> dict:
    row.status = status
    row.error_message = None if status == "imported" else message
    row.imported_batch_id = batch_id
    session.commit()
    return {
        "path": candidate.path,
        "filename": candidate.filename,
        "dataDate": extract.data_date.isoformat(),
        "status": status,
        "message": message,
        "batchId": batch_id,
    }


def _ta_unchanged_outcome(row: SourceFile, candidate: SourceCandidate) -> dict | None:
    if row.status == "failed":
        return None
    return _unchanged_outcome(row, candidate)


def _download(candidate: SourceCandidate, *, username: str, password: str) -> TaExtract:
    with tempfile.TemporaryDirectory(prefix="mtpulse-ta-") as temp_dir:
        path = Path(temp_dir) / candidate.filename
        with (
            smbclient.open_file(
                candidate.path,
                mode="rb",
                username=username,
                password=password,
                port=445,
                connection_timeout=20,
            ) as source,
            path.open("wb") as destination,
        ):
            shutil.copyfileobj(source, destination, length=1024 * 1024)
        extract = extract_ta_file(path)
    return TaExtract(
        **{**extract.__dict__, "source_path": candidate.path, "source_filename": candidate.filename}
    )

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter

import smbclient
from smbprotocol.exceptions import SMBException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.importers.twd import TwdExtract, TwdFormatError, extract_twd_file
from app.local_time import bangkok_now
from app.models import (
    AuditEvent,
    ImportBatch,
    ImportRun,
    ModernTrade,
    SkuInterest,
    SourceFile,
)
from app.services.fileshare import (
    BASE_UNC_KEY,
    DOMAIN_KEY,
    USERNAME_KEY,
    FileShareSettingsError,
    compose_unc,
    effective_username,
    password_value,
    safe_fileshare_error,
    setting_value,
)
from app.services.sku_interest import sync_sku_interests
from app.services.telegram import send_telegram
from app.services.twd_import import (
    DuplicateImportError,
    PeriodDuplicateError,
    import_twd_extract,
)

TERMINAL_RUN_STATUSES = {"success", "success_with_warnings", "failed"}
ACTIVE_RUN_STATUSES = {"queued", "running"}
SUPPORTED_TWD_SUFFIXES = {".xls", ".xlsx"}
logger = logging.getLogger("mtpulse.automatic_import")


class ActiveRunError(ValueError):
    pass


class AutomaticImportError(ValueError):
    pass


@dataclass(frozen=True)
class SourceCandidate:
    path: str
    filename: str
    size_bytes: int
    modified_at: datetime


@dataclass(frozen=True)
class ImportDecision:
    action: str
    message: str
    batch_id: int | None = None


def initial_scan_completed(session: Session, modern_trade_id: int) -> bool:
    return (
        session.scalar(
            select(ImportRun.id)
            .where(
                ImportRun.modern_trade_id == modern_trade_id,
                ImportRun.mode == "scan",
                ImportRun.status.in_({"success", "success_with_warnings"}),
            )
            .limit(1)
        )
        is not None
    )


def _live_run_progress(session: Session, run: ImportRun) -> dict[str, object] | None:
    if run.status not in ACTIVE_RUN_STATUSES:
        return None

    status_rows = session.execute(
        select(SourceFile.status, func.count(SourceFile.id))
        .where(SourceFile.last_seen_run_id == run.id)
        .group_by(SourceFile.status)
    ).all()
    statuses = {status: int(count) for status, count in status_rows}
    processed = sum(statuses.values())
    total = run.found_count
    latest = session.scalar(
        select(SourceFile)
        .where(SourceFile.last_seen_run_id == run.id)
        .order_by(SourceFile.last_seen_at.desc(), SourceFile.id.desc())
        .limit(1)
    )
    issues = list(
        session.scalars(
            select(SourceFile)
            .where(
                SourceFile.last_seen_run_id == run.id,
                SourceFile.status.in_({"failed", "pending_review", "missing"}),
            )
            .order_by(SourceFile.last_seen_at.desc(), SourceFile.id.desc())
            .limit(3)
        )
    )
    counts = {
        "found": total,
        "imported": statuses.get("imported", 0),
        "ready": statuses.get("ready", 0),
        "pending": statuses.get("pending_review", 0) + statuses.get("missing", 0),
        "failed": statuses.get("failed", 0),
    }
    counts["skipped"] = processed - sum(
        counts[key] for key in ("imported", "ready", "pending", "failed")
    )
    return {
        "phase": (
            "queued"
            if run.status == "queued"
            else "discovering"
            if total == 0
            else "processing"
        ),
        "processed": processed,
        "total": total,
        "percent": round(processed * 100 / total, 1) if total else 0,
        "lastProcessedFile": latest.source_filename if latest else None,
        "lastProcessedPath": latest.source_path if latest else None,
        "lastActivityAt": latest.last_seen_at.isoformat() if latest else None,
        "counts": counts,
        "recentIssues": [
            {
                "filename": issue.source_filename,
                "status": issue.status,
                "message": issue.error_message,
            }
            for issue in issues
        ],
    }


def run_payload(
    run: ImportRun,
    mt: ModernTrade | None = None,
    *,
    session: Session | None = None,
) -> dict[str, object]:
    try:
        results = json.loads(run.results_json or "[]")
    except json.JSONDecodeError:
        results = []
    progress = _live_run_progress(session, run) if session else None
    counts = progress["counts"] if progress else {
        "found": run.found_count,
        "imported": run.imported_count,
        "skipped": run.skipped_count,
        "ready": run.ready_count,
        "pending": run.pending_count,
        "failed": run.failed_count,
    }
    return {
        "runId": run.id,
        "mtCode": mt.code if mt else None,
        "mtName": mt.name if mt else None,
        "trigger": run.trigger,
        "mode": run.mode,
        "status": run.status,
        "requestedBy": run.requested_by,
        "scheduledLocalDate": (
            run.scheduled_local_date.isoformat() if run.scheduled_local_date else None
        ),
        "requestedAt": run.requested_at.isoformat() if run.requested_at else None,
        "startedAt": run.started_at.isoformat() if run.started_at else None,
        "finishedAt": run.finished_at.isoformat() if run.finished_at else None,
        "counts": counts,
        "progress": progress,
        "message": run.summary_message,
        "error": run.error_message,
        "results": results if isinstance(results, list) else [],
    }


def create_run(
    session: Session,
    mt: ModernTrade,
    *,
    trigger: str,
    actor: str,
    mode: str | None = None,
    scheduled_local_date: date | None = None,
) -> ImportRun:
    active = session.scalar(
        select(ImportRun)
        .where(
            ImportRun.modern_trade_id == mt.id,
            ImportRun.status.in_(ACTIVE_RUN_STATUSES),
        )
        .limit(1)
    )
    if active is not None:
        raise ActiveRunError(f"{mt.code} กำลังประมวลผลอยู่ใน Run {active.id}")
    selected_mode = mode or (
        "import" if initial_scan_completed(session, mt.id) else "scan"
    )
    run = ImportRun(
        modern_trade_id=mt.id,
        trigger=trigger,
        mode=selected_mode,
        status="queued",
        requested_by=actor,
        scheduled_local_date=scheduled_local_date,
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
                        "mtCode": mt.code,
                        "trigger": trigger,
                        "mode": selected_mode,
                        "scheduledLocalDate": (
                            scheduled_local_date.isoformat()
                            if scheduled_local_date
                            else None
                        ),
                    },
                    ensure_ascii=False,
                ),
            )
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ActiveRunError(f"{mt.code} กำลังประมวลผลอยู่") from exc
    session.refresh(run)
    return run


def list_twd_source_files(
    root: str,
    *,
    username: str,
    password: str,
) -> list[SourceCandidate]:
    candidates: list[SourceCandidate] = []
    kwargs = {
        "username": username,
        "password": password,
        "port": 445,
        "connection_timeout": 10,
    }
    with smbclient.scandir(root, **kwargs) as folders:
        for folder in folders:
            if not folder.is_dir() or folder.name.startswith((".", "~")):
                continue
            with smbclient.scandir(folder.path, **kwargs) as files:
                for entry in files:
                    if not entry.is_file():
                        continue
                    stat = entry.stat()
                    candidates.append(
                        SourceCandidate(
                            path=entry.path,
                            filename=entry.name,
                            size_bytes=int(stat.st_size),
                            modified_at=datetime.fromtimestamp(stat.st_mtime, UTC),
                        )
                    )
    return sorted(candidates, key=lambda item: item.path.lower())


def download_twd_extract(
    candidate: SourceCandidate,
    *,
    username: str,
    password: str,
) -> TwdExtract:
    extract, _, _ = download_twd_extract_with_timings(
        candidate,
        username=username,
        password=password,
    )
    return extract


def download_twd_extract_with_timings(
    candidate: SourceCandidate,
    *,
    username: str,
    password: str,
) -> tuple[TwdExtract, float, float]:
    with tempfile.TemporaryDirectory(prefix="mtpulse-fileshare-") as temp_dir:
        local_path = Path(temp_dir) / candidate.filename
        download_started = perf_counter()
        with (
            smbclient.open_file(
                candidate.path,
                mode="rb",
                username=username,
                password=password,
                port=445,
                connection_timeout=10,
            ) as source,
            local_path.open("wb") as target,
        ):
            shutil.copyfileobj(source, target, length=1024 * 1024)
        downloaded = perf_counter()
        extract = extract_twd_file(local_path)
        parsed = perf_counter()
    normalized = replace(
        extract,
        source_path=candidate.path,
        source_filename=candidate.filename,
    )
    return normalized, downloaded - download_started, parsed - downloaded


def decide_twd_extract(
    session: Session,
    mt: ModernTrade,
    extract: TwdExtract,
    *,
    mode: str,
) -> ImportDecision:
    checksum_batch = session.scalar(
        select(ImportBatch)
        .where(
            ImportBatch.modern_trade_id == mt.id,
            ImportBatch.checksum_sha256 == extract.checksum_sha256,
        )
        .limit(1)
    )
    if checksum_batch is not None:
        return ImportDecision(
            "skipped",
            f"ไฟล์นี้อยู่ใน Batch {checksum_batch.id} แล้ว",
            checksum_batch.id,
        )
    if extract.reconciliation_errors and not _tolerable_stock_warnings(
        extract.reconciliation_errors
    ):
        return ImportDecision(
            "pending_review",
            "ไฟล์มีคำเตือน: " + " · ".join(extract.reconciliation_errors[:3]),
        )
    period_batch = session.scalar(
        select(ImportBatch)
        .where(
            ImportBatch.modern_trade_id == mt.id,
            ImportBatch.data_date == extract.data_date,
        )
        .limit(1)
    )
    if period_batch is not None:
        return ImportDecision(
            "pending_review",
            (
                f"วันที่ {extract.data_date:%d/%m/%Y} มี Batch "
                f"{period_batch.id} แต่ checksum ต่างกัน"
            ),
            period_batch.id,
        )
    if mode == "scan":
        return ImportDecision("ready", "ไฟล์ใหม่พร้อมนำเข้า")
    return ImportDecision("import", "ไฟล์ใหม่ผ่านการตรวจสอบ")


def _tolerable_stock_warnings(warnings: tuple[str, ...]) -> bool:
    return bool(warnings) and all(
        warning.startswith("Stock On Hand:") for warning in warnings
    ) and any("#VALUE!" in warning for warning in warnings)


def _source_row(
    session: Session,
    mt: ModernTrade,
    candidate: SourceCandidate,
) -> SourceFile:
    row = session.scalar(
        select(SourceFile).where(
            SourceFile.modern_trade_id == mt.id,
            SourceFile.source_path == candidate.path,
        )
    )
    if row is None:
        row = SourceFile(
            modern_trade_id=mt.id,
            source_path=candidate.path,
            source_filename=candidate.filename,
            size_bytes=candidate.size_bytes,
            modified_at=candidate.modified_at,
            status="discovered",
        )
        session.add(row)
        session.flush()
    return row


def _unchanged_outcome(row: SourceFile, candidate: SourceCandidate) -> dict | None:
    if (
        row.size_bytes != candidate.size_bytes
        or row.modified_at != candidate.modified_at
    ):
        return None
    status = row.status
    if not row.checksum_sha256 and status not in {"failed", "unsupported"}:
        return None
    if status == "ready" or (
        status == "pending_review"
        and row.error_message
        and "#VALUE!" in row.error_message
    ):
        return None
    return {
        "path": candidate.path,
        "filename": candidate.filename,
        "dataDate": (
            row.detected_data_date.isoformat() if row.detected_data_date else None
        ),
        "status": status,
        "message": row.error_message or "ไฟล์ไม่เปลี่ยนแปลง",
        "batchId": row.imported_batch_id,
        "event": "unchanged",
    }


def _process_candidate(
    session: Session,
    run: ImportRun,
    mt: ModernTrade,
    candidate: SourceCandidate,
    *,
    username: str,
    password: str,
) -> dict:
    row = _source_row(session, mt, candidate)
    unchanged = _unchanged_outcome(row, candidate)
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
    suffix = Path(candidate.filename).suffix.lower()
    if suffix not in SUPPORTED_TWD_SUFFIXES:
        row.status = "unsupported"
        row.error_message = "รองรับเฉพาะไฟล์ .xls และ .xlsx"
        row.checksum_sha256 = None
        row.detected_data_date = None
        row.imported_batch_id = None
        outcome = {
            "path": candidate.path,
            "filename": candidate.filename,
            "dataDate": None,
            "status": "unsupported",
            "message": row.error_message,
            "batchId": None,
        }
        session.commit()
        return outcome
    try:
        extract = download_twd_extract(
            candidate,
            username=username,
            password=password,
        )
        if run.mode == "scan":
            sync_sku_interests(
                session,
                mt.id,
                extract,
                baseline=True,
            )
        row.checksum_sha256 = extract.checksum_sha256
        row.detected_data_date = extract.data_date
        decision = decide_twd_extract(session, mt, extract, mode=run.mode)
        batch_id = decision.batch_id
        if decision.action == "import":
            batch = import_twd_extract(session, extract)
            batch_id = batch.id
            row = session.get(SourceFile, row.id)
            assert row is not None
            row.status = "imported"
            row.error_message = None
            row.imported_batch_id = batch.id
            message = f"นำเข้า Batch {batch.id} สำเร็จ"
            status = "imported"
        else:
            row.status = decision.action
            row.error_message = decision.message
            row.imported_batch_id = decision.batch_id
            message = decision.message
            status = decision.action
        session.commit()
        return {
            "path": candidate.path,
            "filename": candidate.filename,
            "dataDate": extract.data_date.isoformat(),
            "status": status,
            "message": message,
            "batchId": batch_id,
        }
    except (
        TwdFormatError,
        DuplicateImportError,
        PeriodDuplicateError,
        OSError,
        ValueError,
    ) as exc:
        session.rollback()
        row = _source_row(session, mt, candidate)
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


def _credentials(session: Session, mt: ModernTrade) -> tuple[str, str, str]:
    base_unc = setting_value(session, BASE_UNC_KEY) or ""
    domain = setting_value(session, DOMAIN_KEY) or ""
    username = setting_value(session, USERNAME_KEY) or ""
    password = password_value(session) or ""
    if not base_unc or not username or not password or not mt.source_subfolder:
        raise AutomaticImportError("FileShare Setting ของ MT นี้ยังไม่ครบ")
    return (
        compose_unc(base_unc, mt.source_subfolder),
        effective_username(domain, username),
        password,
    )


def _mark_missing(
    session: Session,
    run: ImportRun,
    mt: ModernTrade,
    seen_paths: set[str],
) -> list[dict]:
    missing: list[dict] = []
    rows = session.scalars(
        select(SourceFile).where(
            SourceFile.modern_trade_id == mt.id,
            SourceFile.source_path.not_in(seen_paths),
            SourceFile.status != "missing",
        )
    ).all()
    for row in rows:
        row.status = "missing"
        row.error_message = "ไม่พบไฟล์ต้นฉบับ แต่ข้อมูลในระบบยังคงอยู่"
        row.last_seen_run_id = run.id
        missing.append(
            {
                "path": row.source_path,
                "filename": row.source_filename,
                "dataDate": (
                    row.detected_data_date.isoformat()
                    if row.detected_data_date
                    else None
                ),
                "status": "missing",
                "message": row.error_message,
                "batchId": row.imported_batch_id,
            }
        )
    return missing


def _finish_run(
    session: Session,
    run: ImportRun,
    mt: ModernTrade,
    results: list[dict],
) -> None:
    pending_sku_count = (
        session.scalar(
            select(func.count()).select_from(SkuInterest).where(
                SkuInterest.modern_trade_id == mt.id,
                SkuInterest.status == "pending",
            )
        )
        or 0
    )
    counts = {
        "imported": sum(item["status"] == "imported" for item in results),
        "ready": sum(item["status"] == "ready" for item in results),
        "pending": sum(
            item["status"] in {"pending_review", "missing"} for item in results
        ),
        "failed": sum(item["status"] == "failed" for item in results),
    }
    counts["skipped"] = len(results) - sum(counts.values())
    run.found_count = len(results)
    run.imported_count = counts["imported"]
    run.skipped_count = counts["skipped"]
    run.ready_count = counts["ready"]
    run.pending_count = counts["pending"]
    run.failed_count = counts["failed"]
    run.status = (
        "success_with_warnings"
        if counts["pending"] or counts["failed"]
        else "success"
    )
    run.finished_at = bangkok_now()
    run.summary_message = (
        f"พบ {len(results)} · นำเข้า {counts['imported']} · "
        f"พร้อมนำเข้า {counts['ready']} · ข้าม {counts['skipped']} · "
        f"รอตรวจสอบ {counts['pending']} · ล้มเหลว {counts['failed']}"
    )
    if pending_sku_count:
        run.summary_message += f" · SKU ใหม่รอตัดสินใจ {pending_sku_count}"
    run.results_json = json.dumps(results, ensure_ascii=False)
    event_results = [item for item in results if item.get("event") != "unchanged"]
    event_counts = {
        "imported": sum(item["status"] == "imported" for item in event_results),
        "ready": sum(item["status"] == "ready" for item in event_results),
        "pending": sum(
            item["status"] in {"pending_review", "missing"}
            for item in event_results
        ),
        "failed": sum(item["status"] == "failed" for item in event_results),
    }
    event_counts["skipped"] = len(event_results) - sum(event_counts.values())
    if event_results:
        event_summary = (
            f"Event ใหม่ {len(event_results)} · นำเข้า {event_counts['imported']} · "
            f"พร้อมนำเข้า {event_counts['ready']} · ข้าม {event_counts['skipped']} · "
            f"รอตรวจสอบ {event_counts['pending']} · ล้มเหลว {event_counts['failed']}"
        )
    else:
        event_summary = "ไม่พบไฟล์ใหม่หรือการเปลี่ยนแปลง"
    event_has_warning = bool(event_counts["pending"] or event_counts["failed"])
    delivery = send_telegram(
        session,
        (
            f"⚠️ Automatic Import {mt.code} สำเร็จพร้อมคำเตือน"
            if event_has_warning
            else f"✅ Automatic Import {mt.code} สำเร็จ"
        ),
        [
            f"▶️ Trigger: {run.trigger}",
            f"📂 Mode: {run.mode}",
            f"📊 {event_summary}",
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
                    "mtCode": mt.code,
                    "trigger": run.trigger,
                    "mode": run.mode,
                    "counts": counts,
                    "eventCounts": event_counts,
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


def process_run(session: Session, run_id: int) -> None:
    run = session.get(ImportRun, run_id)
    if run is None or run.status != "running":
        return
    mt = session.get(ModernTrade, run.modern_trade_id)
    if mt is None:
        raise AutomaticImportError("ไม่พบ Modern Trade ของ Run")
    try:
        root, username, password = _credentials(session, mt)
        candidates = list_twd_source_files(root, username=username, password=password)
        run.found_count = len(candidates)
        run.summary_message = f"พบ {len(candidates)} ไฟล์ · กำลังเริ่มตรวจสอบ"
        session.commit()
        results = []
        for index, candidate in enumerate(candidates, start=1):
            run.summary_message = (
                f"กำลังตรวจไฟล์ {index}/{len(candidates)} · {candidate.filename}"
            )
            session.commit()
            results.append(_process_candidate(
                session,
                run,
                mt,
                candidate,
                username=username,
                password=password,
            ))
        results.extend(
            _mark_missing(
                session,
                run,
                mt,
                {candidate.path for candidate in candidates},
            )
        )
        _finish_run(session, run, mt, results)
    except Exception as exc:
        logger.exception("automatic import run %s failed", run_id)
        session.rollback()
        run = session.get(ImportRun, run_id)
        assert run is not None
        run.status = "failed"
        run.finished_at = bangkok_now()
        if isinstance(exc, (AutomaticImportError, FileShareSettingsError)):
            run.error_message = str(exc)
        elif isinstance(exc, (SMBException, OSError)):
            run.error_message = safe_fileshare_error(exc)
        else:
            run.error_message = (
                f"ประมวลผลไฟล์ไม่สำเร็จ: {type(exc).__name__}: {str(exc)}"
            )[:1000]
        run.summary_message = "Run ไม่สำเร็จและไม่มีการลบข้อมูลเดิม"
        session.add(
            AuditEvent(
                entity_type="import_run",
                entity_id=str(run.id),
                action="failed",
                actor=run.requested_by,
                before_json=None,
                after_json=json.dumps(
                    {"mtCode": mt.code, "error": run.error_message},
                    ensure_ascii=False,
                ),
            )
        )
        session.commit()
        send_telegram(
            session,
            f"❌ Automatic Import {mt.code} ไม่สำเร็จ",
            [f"⚠️ {run.error_message}"],
            force=True,
        )
    finally:
        smbclient.reset_connection_cache()

from __future__ import annotations

import hashlib
import json
import logging
import tempfile
from dataclasses import replace
from pathlib import Path
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from smbprotocol.exceptions import SMBException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.importers.twd import TwdExtract, TwdFormatError, extract_twd_file
from app.models import AuditEvent, ImportBatch, ModernTrade, SkuInterest, SourceFile
from app.services.automatic_import import (
    AutomaticImportError,
    SourceCandidate,
    _credentials,
    download_twd_extract_with_timings,
)
from app.services.fileshare import (
    FileShareSettingsError,
    safe_fileshare_error,
)
from app.services.manual_upload_contracts import MAX_UPLOAD_BYTES
from app.services.monitoring import capture_monitoring_snapshot
from app.services.telegram import (
    TelegramDelivery,
    format_thai_date,
    send_telegram,
)
from app.services.twd_import import (
    DuplicateImportError,
    PeriodDuplicateError,
    import_twd_extract,
)

router = APIRouter(prefix="/api/imports", tags=["imports"])
logger = logging.getLogger(__name__)


def _extract_upload(content: bytes, filename: str) -> TwdExtract:
    safe_name = Path(filename).name or "twd-upload.xls"
    if Path(safe_name).suffix.lower() not in {".xls", ".xlsx"}:
        raise TwdFormatError(
            "รองรับไฟล์ Raw Data TWD นามสกุล .xls และ .xlsx เท่านั้น"
        )
    with tempfile.TemporaryDirectory(prefix="mtpulse-manual-upload-") as temp_dir:
        path = Path(temp_dir) / safe_name
        path.write_bytes(content)
        extract = extract_twd_file(path)
    return replace(
        extract,
        source_path=f"manual-upload:{safe_name}",
        source_filename=safe_name,
    )


def _duplicate_reason(session: Session, extract: TwdExtract) -> str | None:
    modern_trade = session.scalar(select(ModernTrade).where(ModernTrade.code == "TWD"))
    if modern_trade is None:
        return None
    checksum_batch = session.scalar(
        select(ImportBatch).where(
            ImportBatch.modern_trade_id == modern_trade.id,
            ImportBatch.checksum_sha256 == extract.checksum_sha256,
        )
    )
    if checksum_batch:
        return f"ไฟล์นี้เคยนำเข้าแล้วใน Batch {checksum_batch.id}"
    period_batch = session.scalar(
        select(ImportBatch).where(
            ImportBatch.modern_trade_id == modern_trade.id,
            ImportBatch.data_date == extract.data_date,
        )
    )
    if period_batch:
        return f"TWD วันที่ {format_thai_date(extract.data_date)} มีข้อมูลใน Batch {period_batch.id} แล้ว"
    return None


def _record(
    session: Session,
    *,
    checksum: str,
    action: str,
    status: str,
    message: str,
    filename: str,
    data_date: str | None = None,
    batch_id: int | None = None,
    notification: TelegramDelivery | None = None,
    actor: str = "manual-upload",
) -> None:
    payload = {
        "status": status,
        "message": message,
        "filename": Path(filename).name,
        "mtCode": "TWD",
        "dataDate": data_date,
        "batchId": batch_id,
    }
    if notification:
        payload["notification"] = {
            "status": notification.status,
            "message": notification.message,
        }
    session.add(
        AuditEvent(
            entity_type="data_import",
            entity_id=checksum[:100],
            action=action,
            actor=actor,
            before_json=None,
            after_json=json.dumps(payload, ensure_ascii=False),
        )
    )
    session.commit()


def _preview(
    extract: TwdExtract,
    duplicate_reason: str | None,
    *,
    timings: dict[str, float] | None = None,
    source_mode: str = "upload",
    source_file_id: int | None = None,
) -> dict:
    summary = extract.summary
    payload = {
        "detectedMt": "TWD",
        "detectedMtName": "ไทวัสดุ",
        "filename": extract.source_filename,
        "checksum": extract.checksum_sha256,
        "dataDate": extract.data_date.isoformat(),
        "rowCount": summary.row_count,
        "skuCount": summary.sku_count,
        "branchCount": summary.store_count,
        "sourceAmount": float(summary.source_amount),
        "amount": float(summary.amount),
        "salesQty": float(summary.sales_qty),
        "stockOnHand": float(summary.stock_on_hand),
        "stockOnOrder": float(summary.stock_on_order),
        "negativeRowCount": summary.negative_row_count,
        "warnings": list(extract.reconciliation_errors),
        "canImport": duplicate_reason is None,
        "duplicateReason": duplicate_reason,
        "sourceMode": source_mode,
        "sourceFileId": source_file_id,
        "timings": timings or {},
    }
    return payload


def _twd_source_file(session: Session, source_file_id: int) -> SourceFile:
    source = session.scalar(
        select(SourceFile)
        .join(ModernTrade, ModernTrade.id == SourceFile.modern_trade_id)
        .where(
            SourceFile.id == source_file_id,
            ModernTrade.code == "TWD",
        )
    )
    if source is None:
        raise HTTPException(status_code=404, detail="ไม่พบไฟล์ TWD ในทะเบียน FileShare")
    if source.status != "ready":
        raise HTTPException(
            status_code=409,
            detail="ไฟล์นี้ไม่อยู่ในสถานะพร้อมนำเข้า กรุณา Refresh รายการ",
        )
    return source


def _extract_fileshare_source(
    session: Session,
    source: SourceFile,
) -> tuple[TwdExtract, dict[str, float]]:
    modern_trade = session.get(ModernTrade, source.modern_trade_id)
    if modern_trade is None or modern_trade.code != "TWD":
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูล Modern Trade ของไฟล์")
    _, username, password = _credentials(session, modern_trade)
    candidate = SourceCandidate(
        path=source.source_path,
        filename=source.source_filename,
        size_bytes=source.size_bytes,
        modified_at=source.modified_at,
    )
    extract, download_seconds, parse_seconds = download_twd_extract_with_timings(
        candidate,
        username=username,
        password=password,
    )
    return extract, {
        "downloadMs": round(download_seconds * 1000, 1),
        "parseMs": round(parse_seconds * 1000, 1),
    }


def _fileshare_failure_message(exc: Exception) -> str:
    if isinstance(exc, TwdFormatError):
        return f"ตรวจสอบไฟล์ไม่ผ่าน: {exc}"
    if isinstance(exc, (AutomaticImportError, FileShareSettingsError)):
        return str(exc)
    return f"อ่านไฟล์จาก FileShare ไม่สำเร็จ: {safe_fileshare_error(exc)}"


def _record_fileshare_failure(
    session: Session,
    source: SourceFile,
    *,
    action: str,
    message: str,
) -> None:
    delivery = send_telegram(
        session,
        "❌ นำเข้าข้อมูลไทวัสดุจาก FileShare ไม่สำเร็จ",
        [
            "🏪 Modern Trade: ไทวัสดุ (TWD)",
            "📥 วิธีนำเข้า: FileShare",
            f"📄 ไฟล์: {source.source_filename}",
            f"⚠️ สาเหตุ: {message}",
        ],
    )
    _record(
        session,
        checksum=source.checksum_sha256 or f"source-file-{source.id}",
        action=action,
        status="failed",
        message=message,
        filename=source.source_filename,
        data_date=(
            source.detected_data_date.isoformat()
            if source.detected_data_date
            else None
        ),
        notification=delivery,
        actor="fileshare-import",
    )


@router.get("/fileshare-ready")
def fileshare_ready_imports(
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 1000,
) -> dict:
    modern_trade = session.scalar(
        select(ModernTrade).where(ModernTrade.code == "TWD")
    )
    if modern_trade is None:
        return {"count": 0, "items": []}
    sources = session.scalars(
        select(SourceFile)
        .where(
            SourceFile.modern_trade_id == modern_trade.id,
            SourceFile.status == "ready",
        )
        .order_by(
            SourceFile.detected_data_date.desc().nullslast(),
            SourceFile.id.desc(),
        )
        .limit(limit)
    ).all()
    return {
        "count": len(sources),
        "items": [
            {
                "id": source.id,
                "filename": source.source_filename,
                "dataDate": (
                    source.detected_data_date.isoformat()
                    if source.detected_data_date
                    else None
                ),
                "sizeBytes": source.size_bytes,
                "discoveredAt": source.discovered_at.isoformat(),
            }
            for source in sources
        ],
    }


@router.post("/fileshare/{source_file_id}/preview")
def preview_fileshare_import(
    source_file_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    source = _twd_source_file(session, source_file_id)
    try:
        extract, timings = _extract_fileshare_source(session, source)
    except (
        AutomaticImportError,
        FileShareSettingsError,
        SMBException,
        TwdFormatError,
        OSError,
    ) as exc:
        session.rollback()
        message = _fileshare_failure_message(exc)
        _record_fileshare_failure(
            session,
            source,
            action="fileshare_preview_failed",
            message=message,
        )
        raise HTTPException(status_code=409, detail=message) from exc
    if source.checksum_sha256 and extract.checksum_sha256 != source.checksum_sha256:
        raise HTTPException(
            status_code=409,
            detail="ไฟล์มีการเปลี่ยนแปลงหลัง Initial Scan กรุณา Run Scan ใหม่",
        )
    duplicate_started = perf_counter()
    duplicate_reason = _duplicate_reason(session, extract)
    timings["duplicateCheckMs"] = round(
        (perf_counter() - duplicate_started) * 1000,
        1,
    )
    _record(
        session,
        checksum=extract.checksum_sha256,
        action="fileshare_preview",
        status="duplicate" if duplicate_reason else "validated",
        message=duplicate_reason or "ตรวจสอบไฟล์จาก FileShare ผ่าน รอผู้ใช้ยืนยัน Import",
        filename=extract.source_filename,
        data_date=extract.data_date.isoformat(),
        actor="fileshare-import",
    )
    return _preview(
        extract,
        duplicate_reason,
        timings=timings,
        source_mode="fileshare",
        source_file_id=source.id,
    )


def _completed_import_response(
    session: Session,
    batch: ImportBatch,
    *,
    method_label: str,
    actor: str,
    timings: dict[str, float] | None = None,
) -> dict:
    status_label = (
        "สำเร็จพร้อมคำเตือน"
        if batch.status == "imported_with_warnings"
        else "สำเร็จ"
    )
    pending_skus = session.scalars(
        select(SkuInterest.source_sku)
        .where(
            SkuInterest.modern_trade_id == batch.modern_trade_id,
            SkuInterest.status == "pending",
        )
        .order_by(SkuInterest.source_sku)
    ).all()
    notification_lines = [
        "🏪 Modern Trade: ไทวัสดุ (TWD)",
        f"📥 วิธีนำเข้า: {method_label}",
        f"📅 วันที่ข้อมูล: {format_thai_date(batch.data_date)}",
        f"📄 ไฟล์: {batch.source_filename}",
        f"🆔 Batch ID: {batch.id}",
        f"✅ สถานะ: {status_label}",
        f"📊 จำนวนรายการ: {batch.row_count:,}",
        f"🏷️ จำนวน SKU: {batch.sku_count:,}",
        f"🏬 จำนวนสาขา: {batch.store_count:,}",
        f"💰 Amount: {batch.amount:,.2f}",
        f"🔢 Qty: {batch.sales_qty:,.2f}",
        f"📦 Stock On Hand: {batch.stock_on_hand:,.2f}",
        f"🚚 Stock On Order: {batch.stock_on_order:,.2f}",
        f"↩️ รายการติดลบ: {batch.negative_row_count:,}",
    ]
    if pending_skus:
        notification_lines.append(
            f"🆕 SKU ใหม่รอตัดสินใจ: {len(pending_skus):,} SKU"
        )
    delivery = send_telegram(
        session,
        "✅ นำเข้าข้อมูลไทวัสดุสำเร็จ",
        notification_lines,
    )
    message = f"นำเข้าข้อมูล TWD วันที่ {format_thai_date(batch.data_date)} สำเร็จ"
    if pending_skus:
        message += (
            f" · พบ SKU ใหม่ {len(pending_skus):,} SKU "
            "กรุณา Accept หรือ Ignore ที่หน้า Monitoring"
        )
    _record(
        session,
        checksum=batch.checksum_sha256,
        action="import_completed",
        status=batch.status,
        message=message,
        filename=batch.source_filename,
        data_date=batch.data_date.isoformat(),
        batch_id=batch.id,
        notification=delivery,
        actor=actor,
    )
    try:
        capture_monitoring_snapshot(
            session,
            trigger="import",
            upsert_today=True,
        )
    except Exception:
        session.rollback()
        logger.exception(
            "Import completed, but the daily monitoring snapshot could not be saved"
        )
    return {
        "batchId": batch.id,
        "status": batch.status,
        "message": message,
        "dataDate": batch.data_date.isoformat(),
        "rowCount": batch.row_count,
        "pendingSkus": pending_skus,
        "timings": timings or {},
        "notification": {
            "status": delivery.status,
            "message": delivery.message,
        },
    }


@router.post("/fileshare/{source_file_id}/confirm")
def confirm_fileshare_import(
    source_file_id: int,
    expected_checksum: Annotated[str, Form(max_length=64)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    source = _twd_source_file(session, source_file_id)
    try:
        extract, timings = _extract_fileshare_source(session, source)
        if (
            extract.checksum_sha256 != expected_checksum
            or (
                source.checksum_sha256
                and extract.checksum_sha256 != source.checksum_sha256
            )
        ):
            raise ValueError(
                "ไฟล์มีการเปลี่ยนแปลงหลัง Preview กรุณา Run Scan และตรวจสอบใหม่"
            )
        import_started = perf_counter()
        batch = import_twd_extract(session, extract)
        timings["importMs"] = round((perf_counter() - import_started) * 1000, 1)
    except (
        AutomaticImportError,
        FileShareSettingsError,
        SMBException,
        TwdFormatError,
        DuplicateImportError,
        PeriodDuplicateError,
        OSError,
        ValueError,
    ) as exc:
        session.rollback()
        message = (
            str(exc)
            if isinstance(exc, (DuplicateImportError, PeriodDuplicateError, ValueError))
            else _fileshare_failure_message(exc)
        )
        _record_fileshare_failure(
            session,
            source,
            action="fileshare_import_failed",
            message=message,
        )
        raise HTTPException(status_code=409, detail=message) from exc
    refreshed_source = session.get(SourceFile, source.id)
    if refreshed_source is not None:
        refreshed_source.status = "imported"
        refreshed_source.error_message = None
        refreshed_source.imported_batch_id = batch.id
        refreshed_source.checksum_sha256 = extract.checksum_sha256
        refreshed_source.detected_data_date = extract.data_date
        session.commit()
    return _completed_import_response(
        session,
        batch,
        method_label="FileShare",
        actor="fileshare-import",
        timings=timings,
    )


async def _read_file(file: UploadFile) -> tuple[str, bytes]:
    filename = Path(file.filename or "upload.xls").name
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="ไฟล์มีขนาดเกิน 25 MB")
    if not content:
        raise HTTPException(status_code=400, detail="ไฟล์ว่าง")
    return filename, content


@router.post("/preview")
async def preview_import(
    session: Annotated[Session, Depends(get_session)],
    file: Annotated[UploadFile, File()],
) -> dict:
    read_started = perf_counter()
    filename, content = await _read_file(file)
    read_finished = perf_counter()
    checksum = hashlib.sha256(content).hexdigest()
    try:
        parse_started = perf_counter()
        extract = _extract_upload(content, filename)
        parse_finished = perf_counter()
    except (TwdFormatError, OSError, ValueError) as exc:
        message = f"ตรวจสอบไฟล์ไม่ผ่าน: {exc}"
        delivery = send_telegram(
            session,
            "❌ ตรวจสอบไฟล์นำเข้าไม่สำเร็จ",
            [
                "🏪 Modern Trade: ไทวัสดุ (TWD)",
                "📥 วิธีนำเข้า: Manual Upload",
                f"📄 ไฟล์: {filename}",
                f"⚠️ สาเหตุ: {message}",
            ],
        )
        _record(
            session,
            checksum=checksum,
            action="preview_failed",
            status="failed",
            message=message,
            filename=filename,
            notification=delivery,
        )
        raise HTTPException(status_code=400, detail=message) from exc
    duplicate_started = perf_counter()
    duplicate_reason = _duplicate_reason(session, extract)
    duplicate_finished = perf_counter()
    _record(
        session,
        checksum=extract.checksum_sha256,
        action="preview",
        status="duplicate" if duplicate_reason else "validated",
        message=duplicate_reason or "ตรวจสอบไฟล์ผ่าน รอผู้ใช้ยืนยัน Import",
        filename=filename,
        data_date=extract.data_date.isoformat(),
    )
    return _preview(
        extract,
        duplicate_reason,
        timings={
            "serverReadMs": round((read_finished - read_started) * 1000, 1),
            "parseMs": round((parse_finished - parse_started) * 1000, 1),
            "duplicateCheckMs": round(
                (duplicate_finished - duplicate_started) * 1000,
                1,
            ),
        },
    )


@router.post("/confirm")
async def confirm_import(
    session: Annotated[Session, Depends(get_session)],
    file: Annotated[UploadFile, File()],
    expected_checksum: Annotated[str, Form(max_length=64)],
) -> dict:
    read_started = perf_counter()
    filename, content = await _read_file(file)
    read_finished = perf_counter()
    checksum = hashlib.sha256(content).hexdigest()
    try:
        parse_started = perf_counter()
        extract = _extract_upload(content, filename)
        parse_finished = perf_counter()
        if extract.checksum_sha256 != expected_checksum:
            raise ValueError("ไฟล์เปลี่ยนจากรอบ Preview กรุณาตรวจสอบใหม่")
        import_started = perf_counter()
        batch = import_twd_extract(session, extract)
        import_finished = perf_counter()
    except (TwdFormatError, DuplicateImportError, PeriodDuplicateError, OSError, ValueError) as exc:
        session.rollback()
        message = str(exc)
        delivery = send_telegram(
            session,
            "❌ นำเข้าข้อมูลไทวัสดุไม่สำเร็จ",
            [
                "🏪 Modern Trade: ไทวัสดุ (TWD)",
                "📥 วิธีนำเข้า: Manual Upload",
                f"📄 ไฟล์: {filename}",
                f"⚠️ สาเหตุ: {message}",
            ],
        )
        _record(
            session,
            checksum=checksum,
            action="import_failed",
            status="failed",
            message=message,
            filename=filename,
            notification=delivery,
        )
        raise HTTPException(status_code=409, detail=message) from exc
    return _completed_import_response(
        session,
        batch,
        method_label="Manual Upload",
        actor="manual-upload",
        timings={
            "serverReadMs": round((read_finished - read_started) * 1000, 1),
            "parseMs": round((parse_finished - parse_started) * 1000, 1),
            "importMs": round((import_finished - import_started) * 1000, 1),
        },
    )


@router.get("/activity")
def import_activity(
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict:
    events = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.entity_type == "data_import")
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .limit(limit)
    ).all()
    items = []
    for event in events:
        payload = json.loads(event.after_json or "{}")
        items.append(
            {
                "id": event.id,
                "occurredAt": event.occurred_at.isoformat(),
                "action": event.action,
                **payload,
            }
        )
    return {"items": items}

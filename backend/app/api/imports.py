from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.importers.twd import TwdExtract, TwdFormatError, extract_twd_file
from app.models import AuditEvent, ImportBatch, ModernTrade
from app.services.telegram import TelegramDelivery, send_telegram
from app.services.twd_import import (
    DuplicateImportError,
    PeriodDuplicateError,
    import_twd_extract,
)

router = APIRouter(prefix="/api/imports", tags=["imports"])
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _extract_upload(content: bytes, filename: str) -> TwdExtract:
    safe_name = Path(filename).name or "twd-upload.xls"
    if not safe_name.lower().endswith(".xls"):
        raise TwdFormatError("Phase นี้รองรับไฟล์ Raw Data TWD นามสกุล .xls เท่านั้น")
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
        return f"TWD วันที่ {extract.data_date.isoformat()} มีข้อมูลใน Batch {period_batch.id} แล้ว"
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
            actor="manual-upload",
            before_json=None,
            after_json=json.dumps(payload, ensure_ascii=False),
        )
    )
    session.commit()


def _preview(extract: TwdExtract, duplicate_reason: str | None) -> dict:
    summary = extract.summary
    return {
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
    }


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
    filename, content = await _read_file(file)
    checksum = hashlib.sha256(content).hexdigest()
    try:
        extract = _extract_upload(content, filename)
    except (TwdFormatError, OSError, ValueError) as exc:
        message = f"ตรวจสอบไฟล์ไม่ผ่าน: {exc}"
        delivery = send_telegram(
            session,
            f"MT Pulse — Manual Import Failed\nไฟล์: {filename}\nสาเหตุ: {message}",
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
    duplicate_reason = _duplicate_reason(session, extract)
    _record(
        session,
        checksum=extract.checksum_sha256,
        action="preview",
        status="duplicate" if duplicate_reason else "validated",
        message=duplicate_reason or "ตรวจสอบไฟล์ผ่าน รอผู้ใช้ยืนยัน Import",
        filename=filename,
        data_date=extract.data_date.isoformat(),
    )
    return _preview(extract, duplicate_reason)


@router.post("/confirm")
async def confirm_import(
    session: Annotated[Session, Depends(get_session)],
    file: Annotated[UploadFile, File()],
    expected_checksum: Annotated[str, Form(max_length=64)],
) -> dict:
    filename, content = await _read_file(file)
    checksum = hashlib.sha256(content).hexdigest()
    try:
        extract = _extract_upload(content, filename)
        if extract.checksum_sha256 != expected_checksum:
            raise ValueError("ไฟล์เปลี่ยนจากรอบ Preview กรุณาตรวจสอบใหม่")
        batch = import_twd_extract(session, extract)
    except (TwdFormatError, DuplicateImportError, PeriodDuplicateError, OSError, ValueError) as exc:
        session.rollback()
        message = str(exc)
        delivery = send_telegram(
            session,
            f"MT Pulse — Manual Import Failed\nMT: TWD\nไฟล์: {filename}\nสาเหตุ: {message}",
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
    delivery = send_telegram(
        session,
        "\n".join(
            [
                "MT Pulse — Manual Import Completed",
                "MT: TWD",
                f"วันที่ข้อมูล: {batch.data_date.isoformat()}",
                f"ไฟล์: {batch.source_filename}",
                f"จำนวนรายการ: {batch.row_count:,}",
            ]
        ),
    )
    message = f"นำเข้าข้อมูล TWD วันที่ {batch.data_date.isoformat()} สำเร็จ"
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
    )
    return {
        "batchId": batch.id,
        "status": batch.status,
        "message": message,
        "dataDate": batch.data_date.isoformat(),
        "rowCount": batch.row_count,
        "notification": {
            "status": delivery.status,
            "message": delivery.message,
        },
    }


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
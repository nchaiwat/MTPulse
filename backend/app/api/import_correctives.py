from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.imports import _extract_upload, _read_file
from app.database import get_session
from app.importers.twd import TwdExtract, TwdFormatError
from app.models import AuditEvent, ImportBatch
from app.services.monitoring import capture_monitoring_snapshot
from app.services.telegram import format_thai_date, send_telegram
from app.services.twd_import import DuplicateImportError, replace_twd_batch

router = APIRouter(prefix="/api/imports/batches", tags=["imports"])
logger = logging.getLogger(__name__)


class AcknowledgeWarningBody(BaseModel):
    note: str = Field(min_length=3, max_length=1_000)


def _batch_or_404(session: Session, batch_id: int) -> ImportBatch:
    batch = session.get(ImportBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail=f"ไม่พบ Import Batch {batch_id}")
    return batch


def _summary(batch: ImportBatch) -> dict[str, object]:
    return {
        "rowCount": batch.row_count,
        "skuCount": batch.sku_count,
        "branchCount": batch.store_count,
        "amount": float(batch.amount),
        "salesQty": float(batch.sales_qty),
        "stockOnHand": float(batch.stock_on_hand),
        "reportedStockOnHand": float(batch.reported_stock_on_hand),
        "stockOnOrder": float(batch.stock_on_order),
        "negativeRowCount": batch.negative_row_count,
    }


def _extract_summary(extract: TwdExtract) -> dict[str, object]:
    summary = extract.summary
    return {
        "rowCount": summary.row_count,
        "skuCount": summary.sku_count,
        "branchCount": summary.store_count,
        "amount": float(summary.amount),
        "salesQty": float(summary.sales_qty),
        "stockOnHand": float(summary.stock_on_hand),
        "reportedStockOnHand": float(extract.reported_summary.stock_on_hand),
        "stockOnOrder": float(summary.stock_on_order),
        "negativeRowCount": summary.negative_row_count,
    }


def _batch_detail(batch: ImportBatch) -> dict[str, object]:
    return {
        "batchId": batch.id,
        "dataDate": batch.data_date.isoformat(),
        "filename": batch.source_filename,
        "status": batch.status,
        "warnings": [
            line.strip()
            for line in (batch.reconciliation_errors or "").splitlines()
            if line.strip()
        ],
        "summary": _summary(batch),
        "resolution": (
            {
                "type": batch.warning_resolution,
                "note": batch.warning_resolution_note,
                "resolvedAt": batch.warning_resolved_at.isoformat()
                if batch.warning_resolved_at
                else None,
                "resolvedBy": batch.warning_resolved_by,
            }
            if batch.warning_resolution
            else None
        ),
    }


def _replacement_block_reason(
    session: Session,
    batch: ImportBatch,
    extract: TwdExtract,
) -> str | None:
    if extract.data_date != batch.data_date:
        return (
            f"ไฟล์ใหม่เป็นวันที่ {extract.data_date:%d/%m/%Y} "
            f"แต่ Batch {batch.id} เป็นวันที่ {batch.data_date:%d/%m/%Y}"
        )
    if extract.checksum_sha256 == batch.checksum_sha256:
        return "ไฟล์ใหม่เหมือนกับไฟล์ที่อยู่ในระบบแล้ว"
    duplicate = session.scalar(
        select(ImportBatch).where(
            ImportBatch.modern_trade_id == batch.modern_trade_id,
            ImportBatch.checksum_sha256 == extract.checksum_sha256,
            ImportBatch.id != batch.id,
        )
    )
    return f"ไฟล์นี้เคยนำเข้าแล้วใน Batch {duplicate.id}" if duplicate else None


@router.get("/{batch_id}")
def import_batch_detail(
    batch_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    return _batch_detail(_batch_or_404(session, batch_id))


@router.post("/{batch_id}/acknowledge")
def acknowledge_import_warning(
    batch_id: int,
    body: AcknowledgeWarningBody,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    batch = _batch_or_404(session, batch_id)
    if not batch.reconciliation_errors:
        raise HTTPException(status_code=409, detail="Batch นี้ไม่มีคำเตือนที่ต้องรับทราบ")
    if batch.warning_resolution:
        raise HTTPException(status_code=409, detail="คำเตือนของ Batch นี้ถูกดำเนินการแล้ว")

    note = body.note.strip()
    if len(note) < 3:
        raise HTTPException(status_code=422, detail="กรุณาระบุหมายเหตุอย่างน้อย 3 ตัวอักษร")
    resolved_at = datetime.now(UTC)
    batch.warning_resolution = "acknowledged"
    batch.warning_resolution_note = note
    batch.warning_resolved_at = resolved_at
    batch.warning_resolved_by = "manual-user"
    session.add(
        AuditEvent(
            entity_type="import_corrective",
            entity_id=str(batch.id),
            action="warning_acknowledged",
            actor="manual-user",
            before_json=json.dumps({"warnings": batch.reconciliation_errors}, ensure_ascii=False),
            after_json=json.dumps({"resolution": "acknowledged", "note": note}, ensure_ascii=False),
        )
    )
    session.commit()
    send_telegram(
        session,
        "✅ รับทราบคำเตือน Import แล้ว",
        [
            "🏪 Modern Trade: ไทวัสดุ (TWD)",
            f"🆔 Batch ID: {batch.id}",
            f"📅 วันที่ข้อมูล: {format_thai_date(batch.data_date)}",
            f"📝 หมายเหตุ: {note}",
        ],
    )
    try:
        capture_monitoring_snapshot(session, trigger="corrective", upsert_today=True)
    except Exception:
        session.rollback()
        logger.exception("Warning acknowledged, but monitoring snapshot could not be saved")
    return _batch_detail(batch)


@router.post("/{batch_id}/replacement-preview")
async def preview_batch_replacement(
    batch_id: int,
    session: Annotated[Session, Depends(get_session)],
    file: Annotated[UploadFile, File()],
) -> dict[str, object]:
    batch = _batch_or_404(session, batch_id)
    filename, content = await _read_file(file)
    try:
        extract = _extract_upload(content, filename)
    except (TwdFormatError, OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"ตรวจสอบไฟล์ไม่ผ่าน: {exc}") from exc
    blocked_reason = _replacement_block_reason(session, batch, extract)
    return {
        "batchId": batch.id,
        "checksum": extract.checksum_sha256,
        "filename": extract.source_filename,
        "dataDate": extract.data_date.isoformat(),
        "current": _summary(batch),
        "replacement": _extract_summary(extract),
        "warnings": list(extract.reconciliation_errors),
        "canReplace": blocked_reason is None,
        "blockedReason": blocked_reason,
    }


@router.post("/{batch_id}/replace")
async def confirm_batch_replacement(
    batch_id: int,
    session: Annotated[Session, Depends(get_session)],
    file: Annotated[UploadFile, File()],
    expected_checksum: Annotated[str, Form(max_length=64)],
) -> dict[str, object]:
    batch = _batch_or_404(session, batch_id)
    filename, content = await _read_file(file)
    try:
        extract = _extract_upload(content, filename)
        if extract.checksum_sha256 != expected_checksum:
            raise ValueError("ไฟล์เปลี่ยนจากรอบ Preview กรุณาตรวจสอบใหม่")
        blocked_reason = _replacement_block_reason(session, batch, extract)
        if blocked_reason:
            raise ValueError(blocked_reason)
        before = _batch_detail(batch)
        replace_twd_batch(session, batch, extract)
        after = _batch_detail(batch)
        session.add(
            AuditEvent(
                entity_type="import_corrective",
                entity_id=str(batch.id),
                action="batch_replaced",
                actor="manual-user",
                before_json=json.dumps(before, ensure_ascii=False),
                after_json=json.dumps(after, ensure_ascii=False),
            )
        )
        session.commit()
    except (TwdFormatError, DuplicateImportError, OSError, ValueError) as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    send_telegram(
        session,
        "♻️ แทนที่ข้อมูล Import สำเร็จ",
        [
            "🏪 Modern Trade: ไทวัสดุ (TWD)",
            f"🆔 Batch ID: {batch.id}",
            f"📅 วันที่ข้อมูล: {format_thai_date(batch.data_date)}",
            f"📄 ไฟล์ใหม่: {batch.source_filename}",
            f"✅ สถานะ: {batch.status}",
        ],
    )
    try:
        capture_monitoring_snapshot(session, trigger="corrective", upsert_today=True)
    except Exception:
        session.rollback()
        logger.exception("Batch replaced, but monitoring snapshot could not be saved")
    return _batch_detail(batch)

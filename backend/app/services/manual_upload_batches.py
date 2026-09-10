from __future__ import annotations

import hashlib
import json
import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.importers.hp_mh import HpMhFormatError, extract_hp_mh_pair
from app.importers.twd import TwdFormatError, extract_twd_file
from app.models import AuditEvent, ManualUploadBatch, ManualUploadFile
from app.services.hp_mh_import import HpMhImportError, import_hp_mh_pair
from app.services.manual_upload_contracts import STAGING_RETENTION_DAYS
from app.services.manual_upload_detection import detect_upload_file
from app.services.twd_import import (
    DuplicateImportError,
    PeriodDuplicateError,
    import_twd_extract,
)

TERMINAL_BATCH_STATUSES = {"completed", "completed_with_issues", "failed"}


def staging_root() -> Path:
    root = Path(get_settings().manual_upload_staging_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def batch_payload(session: Session, batch: ManualUploadBatch) -> dict:
    files = session.scalars(
        select(ManualUploadFile)
        .where(ManualUploadFile.upload_batch_id == batch.id)
        .order_by(ManualUploadFile.id)
    ).all()
    return {
        "id": batch.id,
        "sourceMode": batch.source_mode,
        "status": batch.status,
        "detectionStatus": batch.detection_status,
        "detectedSourceGroup": batch.detected_source_group,
        "requestedBy": batch.requested_by,
        "createdAt": batch.created_at.isoformat(),
        "expiresAt": batch.expires_at.isoformat(),
        "summaryMessage": batch.summary_message,
        "errorMessage": batch.error_message,
        "counts": {
            "total": batch.total_count,
            "uploaded": batch.uploaded_count,
            "new": batch.new_count,
            "duplicate": batch.duplicate_count,
            "eligible": batch.eligible_count,
            "imported": batch.imported_count,
            "failed": batch.failed_count,
            "needsReview": batch.needs_review_count,
        },
        "files": [
            {
                "id": row.id,
                "filename": row.display_filename,
                "sizeBytes": row.size_bytes,
                "status": row.status,
                "detectionStatus": row.detection_status,
                "detectedMtCode": row.detected_mt_code,
                "detectedSourceGroup": row.detected_source_group,
                "sourceKind": row.source_kind,
                "dataDate": row.data_date.isoformat() if row.data_date else None,
                "reason": row.status_reason,
                "retryCount": row.retry_count,
            }
            for row in files
        ],
    }


def create_folder_batch(
    session: Session,
    *,
    file_count: int,
    actor: str,
) -> ManualUploadBatch:
    now = datetime.now(UTC)
    batch = ManualUploadBatch(
        status="uploading",
        source_mode="folder",
        detection_status="pending",
        requested_by=actor,
        total_count=file_count,
        expires_at=now + timedelta(days=STAGING_RETENTION_DAYS),
        last_activity_at=now,
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)
    (staging_root() / str(batch.id)).mkdir(parents=True, exist_ok=True)
    return batch


def store_folder_file(
    session: Session,
    batch: ManualUploadBatch,
    *,
    filename: str,
    content: bytes,
    idempotency_key: str,
) -> ManualUploadFile:
    existing = session.scalar(
        select(ManualUploadFile).where(
            ManualUploadFile.upload_batch_id == batch.id,
            ManualUploadFile.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return existing
    if batch.status != "uploading":
        raise ValueError("Batch นี้ไม่อยู่ในสถานะรับไฟล์")
    if batch.uploaded_count >= batch.total_count:
        raise ValueError("จำนวนไฟล์เกินกว่าที่กำหนดไว้ใน Batch")

    safe_name = Path(filename).name
    checksum = hashlib.sha256(content).hexdigest()
    staging_key = f"{batch.id}/{batch.uploaded_count + 1:04d}-{checksum[:12]}-{safe_name}"
    target = staging_root() / staging_key
    target.write_bytes(content)
    detection = detect_upload_file(target)
    detected_mt = detection.mt_codes[0] if len(detection.mt_codes) == 1 else None
    row = ManualUploadFile(
        upload_batch_id=batch.id,
        display_filename=safe_name,
        size_bytes=len(content),
        checksum_sha256=checksum,
        staging_key=staging_key,
        relative_depth=1,
        idempotency_key=idempotency_key,
        detected_mt_code=detected_mt,
        detected_source_group=detection.source_group_code,
        source_kind=detection.source_kind,
        detection_status=detection.status,
        validation_status="pending",
        status="uploaded" if detection.status == "detected" else "needs_review",
        status_reason=detection.reason,
        uploaded_at=datetime.now(UTC),
        expires_at=batch.expires_at,
    )
    session.add(row)
    batch.uploaded_count += 1
    batch.last_activity_at = datetime.now(UTC)
    session.commit()
    session.refresh(row)
    return row


def finalize_folder_batch(
    session: Session,
    batch: ManualUploadBatch,
    *,
    expected_source_group: str,
) -> ManualUploadBatch:
    if batch.status != "uploading":
        raise ValueError("Batch นี้ไม่อยู่ในสถานะรอตรวจสอบ")
    if batch.uploaded_count != batch.total_count:
        raise ValueError(
            f"ส่งไฟล์ยังไม่ครบ {batch.uploaded_count}/{batch.total_count} ไฟล์"
        )
    files = session.scalars(
        select(ManualUploadFile).where(ManualUploadFile.upload_batch_id == batch.id)
    ).all()
    groups = {
        row.detected_source_group
        for row in files
        if row.detection_status == "detected" and row.detected_source_group
    }
    batch.upload_completed_at = datetime.now(UTC)
    batch.last_activity_at = datetime.now(UTC)
    batch.needs_review_count = sum(row.status == "needs_review" for row in files)
    if len(groups) != 1:
        batch.status = "failed"
        batch.detection_status = "conflict" if len(groups) > 1 else "needs_review"
        batch.error_message = (
            "พบข้อมูลมากกว่าหนึ่ง Modern Trade/Source Group ใน Folder เดียว"
            if len(groups) > 1
            else "ไม่พบไฟล์ที่ระบบระบุ Modern Trade ได้"
        )
    else:
        detected = next(iter(groups))
        batch.detected_source_group = detected
        if detected != expected_source_group:
            batch.status = "failed"
            batch.detection_status = "conflict"
            batch.error_message = (
                f"เลือกหน้า {expected_source_group} แต่ระบบตรวจพบข้อมูล {detected}"
            )
        else:
            batch.status = "awaiting_confirmation"
            batch.detection_status = "detected"
            batch.eligible_count = sum(row.status == "uploaded" for row in files)
            batch.new_count = batch.eligible_count
            batch.summary_message = (
                f"ตรวจพบ {detected} · พร้อมนำเข้า {batch.eligible_count} ไฟล์"
            )
    session.commit()
    session.refresh(batch)
    return batch


def queue_folder_batch(session: Session, batch: ManualUploadBatch) -> ManualUploadBatch:
    if batch.status != "awaiting_confirmation":
        raise ValueError("Batch ยังไม่ผ่านการตรวจสอบหรือถูกยืนยันไปแล้ว")
    batch.status = "queued"
    batch.confirmed_at = datetime.now(UTC)
    batch.last_activity_at = datetime.now(UTC)
    session.commit()
    session.refresh(batch)
    return batch


def process_folder_batch(session: Session, batch_id: int) -> None:
    batch = session.get(ManualUploadBatch, batch_id)
    if batch is None:
        return
    batch.status = "processing"
    batch.last_activity_at = datetime.now(UTC)
    session.commit()
    if batch.detected_source_group == "TWD":
        _process_twd_folder(session, batch)
    elif batch.detected_source_group == "HP_MH":
        _process_hp_mh_folder(session, batch)
    else:
        batch.status = "failed"
        batch.error_message = "ไม่พบ Source Group ที่รองรับ"
        batch.finished_at = datetime.now(UTC)
        session.commit()
        return
    _finish_batch(session, batch)


def _files(session: Session, batch: ManualUploadBatch) -> list[ManualUploadFile]:
    return list(
        session.scalars(
            select(ManualUploadFile)
            .where(
                ManualUploadFile.upload_batch_id == batch.id,
                ManualUploadFile.status == "uploaded",
            )
            .order_by(ManualUploadFile.id)
        )
    )


def _process_twd_folder(session: Session, batch: ManualUploadBatch) -> None:
    for source in _files(session, batch):
        try:
            path = staging_root() / str(source.staging_key)
            extract = extract_twd_file(path)
            extract = replace(
                extract,
                source_path=f"manual-folder:{source.display_filename}",
                source_filename=source.display_filename,
            )
            imported = import_twd_extract(session, extract)
            source.status = "imported"
            source.validation_status = "valid"
            source.import_batch_id = imported.id
            source.data_date = extract.data_date
            source.processed_at = datetime.now(UTC)
            session.commit()
        except (
            TwdFormatError,
            DuplicateImportError,
            PeriodDuplicateError,
            OSError,
            ValueError,
        ) as exc:
            session.rollback()
            source = session.get(ManualUploadFile, source.id)
            if source is None:
                continue
            source.status = (
                "duplicate"
                if isinstance(exc, (DuplicateImportError, PeriodDuplicateError))
                else "failed"
            )
            source.validation_status = "invalid"
            source.status_reason = str(exc)
            source.processed_at = datetime.now(UTC)
            session.commit()


def _pair_key(filename: str) -> str:
    value = filename.lower()
    value = re.sub("inventorydata|salesdata", "data", value)
    return value


def _process_hp_mh_folder(session: Session, batch: ManualUploadBatch) -> None:
    rows = _files(session, batch)
    inventory = {
        _pair_key(row.display_filename): row
        for row in rows
        if row.source_kind == "inventory"
    }
    sales = {
        _pair_key(row.display_filename): row
        for row in rows
        if row.source_kind == "sales"
    }
    keys = sorted(set(inventory) | set(sales))
    if len(inventory) == len(sales) == 1 and not (set(inventory) & set(sales)):
        keys = ["single-pair"]
        inventory = {"single-pair": next(iter(inventory.values()))}
        sales = {"single-pair": next(iter(sales.values()))}
    for key in keys:
        pair_rows = [row for row in (inventory.get(key), sales.get(key)) if row]
        if len(pair_rows) != 2:
            for row in pair_rows:
                row.status = "failed"
                row.validation_status = "invalid"
                row.status_reason = "ไม่พบไฟล์ Inventory/Sales ที่เป็นคู่กัน"
                row.processed_at = datetime.now(UTC)
            session.commit()
            continue
        inventory_row, sales_row = inventory[key], sales[key]
        try:
            pair = extract_hp_mh_pair(
                staging_root() / str(inventory_row.staging_key),
                staging_root() / str(sales_row.staging_key),
            )
            pair = replace(
                pair,
                inventory_path=f"manual-folder:{inventory_row.display_filename}",
                sales_path=f"manual-folder:{sales_row.display_filename}",
                inventory_filename=inventory_row.display_filename,
                sales_filename=sales_row.display_filename,
            )
            batches = import_hp_mh_pair(session, pair, actor=batch.requested_by)
            for row in (inventory_row, sales_row):
                row.status = "imported"
                row.validation_status = "valid"
                row.data_date = pair.data_date
                row.business_fingerprint = pair.business_fingerprint
                row.import_batch_id = batches["HP"].id
                row.processed_at = datetime.now(UTC)
            session.commit()
        except (HpMhFormatError, HpMhImportError, OSError, ValueError) as exc:
            session.rollback()
            for row_id in (inventory_row.id, sales_row.id):
                row = session.get(ManualUploadFile, row_id)
                if row is None:
                    continue
                row.status = "duplicate" if isinstance(exc, HpMhImportError) else "failed"
                row.validation_status = "invalid"
                row.status_reason = str(exc)
                row.processed_at = datetime.now(UTC)
            session.commit()


def _finish_batch(session: Session, batch: ManualUploadBatch) -> None:
    rows = session.scalars(
        select(ManualUploadFile).where(ManualUploadFile.upload_batch_id == batch.id)
    ).all()
    batch.imported_count = sum(row.status == "imported" for row in rows)
    batch.duplicate_count = sum(row.status == "duplicate" for row in rows)
    batch.failed_count = sum(row.status == "failed" for row in rows)
    batch.needs_review_count = sum(row.status == "needs_review" for row in rows)
    issue_count = batch.failed_count + batch.needs_review_count
    batch.status = "completed_with_issues" if issue_count else "completed"
    batch.finished_at = datetime.now(UTC)
    batch.last_activity_at = datetime.now(UTC)
    batch.summary_message = (
        f"นำเข้าสำเร็จ {batch.imported_count} · ซ้ำ {batch.duplicate_count} · "
        f"ผิดพลาด {batch.failed_count} · รอตรวจสอบ {batch.needs_review_count}"
    )
    mt_codes = ("TWD",) if batch.detected_source_group == "TWD" else ("HP", "MH")
    for mt_code in mt_codes:
        session.add(
            AuditEvent(
                entity_type="data_import",
                entity_id=f"manual-folder:{batch.id}:{mt_code}",
                action="folder_import_completed",
                actor=batch.requested_by,
                before_json=None,
                after_json=json.dumps(
                    {
                        "status": batch.status,
                        "message": batch.summary_message,
                        "filename": f"Folder Batch {batch.id}",
                        "mtCode": mt_code,
                        "dataDate": None,
                        "batchId": batch.id,
                    },
                    ensure_ascii=False,
                ),
            )
        )
    session.commit()

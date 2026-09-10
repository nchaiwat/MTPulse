from __future__ import annotations

from typing import Literal

MAX_FOLDER_FILES = 200
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
UPLOAD_CONCURRENCY = 3
STAGING_RETENTION_DAYS = 7

UploadSourceMode = Literal["single", "folder"]


class ManualUploadContractError(ValueError):
    """Raised when a manual-upload request violates the approved limits."""


def validate_upload_batch_request(
    *,
    source_mode: UploadSourceMode,
    file_count: int,
    is_admin: bool,
) -> None:
    if file_count < 1:
        raise ManualUploadContractError("ต้องเลือกอย่างน้อย 1 ไฟล์")
    if source_mode == "single":
        if file_count != 1:
            raise ManualUploadContractError("การนำเข้าแบบไฟล์เดียวเลือกได้ครั้งละ 1 ไฟล์")
        return
    if not is_admin:
        raise ManualUploadContractError("เฉพาะ Admin เท่านั้นที่เลือก Folder ได้")
    if file_count > MAX_FOLDER_FILES:
        raise ManualUploadContractError(
            f"Folder มีไฟล์เกิน {MAX_FOLDER_FILES} ไฟล์ต่อ Batch"
        )


def validate_upload_file_contract(*, size_bytes: int, relative_depth: int) -> None:
    if size_bytes < 1:
        raise ManualUploadContractError("ไฟล์ต้องไม่เป็นไฟล์ว่าง")
    if size_bytes > MAX_UPLOAD_BYTES:
        raise ManualUploadContractError("ขนาดไฟล์ต้องไม่เกิน 25 MB")
    if relative_depth != 1:
        raise ManualUploadContractError("รองรับเฉพาะไฟล์ระดับแรกของ Folder")

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import require_system_admin
from app.database import get_session
from app.models import ManualUploadBatch
from app.services.manual_upload_batches import (
    batch_payload,
    create_folder_batch,
    finalize_folder_batch,
    queue_folder_batch,
    store_folder_file,
)
from app.services.manual_upload_contracts import (
    MAX_UPLOAD_BYTES,
    ManualUploadContractError,
    validate_upload_batch_request,
    validate_upload_file_contract,
)

router = APIRouter(
    prefix="/api/admin/imports/manual-batches",
    tags=["manual-folder-imports"],
    dependencies=[Depends(require_system_admin)],
)


class CreateFolderBatchRequest(BaseModel):
    file_count: int = Field(ge=1)


class FinalizeFolderBatchRequest(BaseModel):
    expected_source_group: Literal["TWD", "HP_MH"]


def _batch(session: Session, batch_id: int) -> ManualUploadBatch:
    batch = session.get(ManualUploadBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="ไม่พบ Folder Import Batch")
    return batch


@router.post("")
def create_batch(
    request: CreateFolderBatchRequest,
    session: Annotated[Session, Depends(get_session)],
    actor: Annotated[str, Depends(require_system_admin)],
) -> dict:
    try:
        validate_upload_batch_request(
            source_mode="folder",
            file_count=request.file_count,
            is_admin=True,
        )
    except ManualUploadContractError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return batch_payload(
        session,
        create_folder_batch(session, file_count=request.file_count, actor=actor),
    )


@router.post("/{batch_id}/files")
async def upload_batch_file(
    batch_id: int,
    session: Annotated[Session, Depends(get_session)],
    file: Annotated[UploadFile, File()],
    idempotency_key: Annotated[str, Form(min_length=1, max_length=64)],
    relative_depth: Annotated[int, Form(ge=1)] = 1,
) -> dict:
    filename = file.filename or "upload"
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        validate_upload_file_contract(
            size_bytes=len(content),
            relative_depth=relative_depth,
        )
        stored = store_folder_file(
            session,
            _batch(session, batch_id),
            filename=filename,
            content=content,
            idempotency_key=idempotency_key,
        )
    except (ManualUploadContractError, ValueError) as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": stored.id,
        "filename": stored.display_filename,
        "status": stored.status,
        "detectionStatus": stored.detection_status,
        "detectedSourceGroup": stored.detected_source_group,
        "sourceKind": stored.source_kind,
        "reason": stored.status_reason,
    }


@router.post("/{batch_id}/finalize")
def finalize_batch(
    batch_id: int,
    request: FinalizeFolderBatchRequest,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    try:
        batch = finalize_folder_batch(
            session,
            _batch(session, batch_id),
            expected_source_group=request.expected_source_group,
        )
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return batch_payload(session, batch)


@router.post("/{batch_id}/confirm")
def confirm_batch(
    batch_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    try:
        batch = queue_folder_batch(session, _batch(session, batch_id))
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return batch_payload(session, batch)


@router.get("/{batch_id}")
def get_batch(
    batch_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    return batch_payload(session, _batch(session, batch_id))

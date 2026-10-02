from dataclasses import asdict
from datetime import date
from io import BytesIO
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth import require_data_operator
from app.database import get_session
from app.local_time import bangkok_now, bangkok_today
from app.services.dh_price_master import (
    DhPriceMasterError,
    DhPricePreviewStaleError,
    build_dh_price_template,
    confirm_dh_price_master,
    list_dh_prices,
    preview_dh_price_master,
)

router = APIRouter(prefix="/api/dh-prices", tags=["DH prices"])
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/template")
def download_dh_price_template(
    _actor: Annotated[str, Depends(require_data_operator)],
) -> StreamingResponse:
    filename = "DH_Price_Master_Template.xlsx"
    return StreamingResponse(
        BytesIO(build_dh_price_template()),
        media_type=XLSX_TYPE,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"
        },
    )


@router.post("/preview")
async def preview_dh_prices(
    session: Annotated[Session, Depends(get_session)],
    _actor: Annotated[str, Depends(require_data_operator)],
    file: Annotated[UploadFile, File()],
) -> dict:
    _, content = await _read_workbook(file)
    try:
        return asdict(preview_dh_price_master(session, content))
    except DhPriceMasterError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/confirm")
async def confirm_dh_prices(
    session: Annotated[Session, Depends(get_session)],
    actor: Annotated[str, Depends(require_data_operator)],
    file: Annotated[UploadFile, File()],
    preview_fingerprint: Annotated[str, Form(min_length=64, max_length=64)],
) -> dict:
    filename, content = await _read_workbook(file)
    try:
        report = confirm_dh_price_master(
            session,
            content,
            filename=filename,
            actor=actor,
            expected_preview_fingerprint=preview_fingerprint,
        )
    except DhPricePreviewStaleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DhPriceMasterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        **asdict(report),
        "confirmed_by": actor,
        "confirmed_at": bangkok_now().isoformat(),
    }


@router.get("")
def get_dh_prices(
    session: Annotated[Session, Depends(get_session)],
    _actor: Annotated[str, Depends(require_data_operator)],
    as_of: Annotated[date | None, Query()] = None,
    status: Annotated[
        Literal["current", "upcoming", "expired"] | None,
        Query(),
    ] = None,
    q: Annotated[str | None, Query(max_length=50)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
) -> dict:
    try:
        result = list_dh_prices(
            session,
            as_of=as_of or bangkok_today(),
            status=status,
            query=q,
            page=page,
            page_size=page_size,
        )
    except DhPriceMasterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return asdict(result)


async def _read_workbook(file: UploadFile) -> tuple[str, bytes]:
    filename = file.filename or "dh-price-master.xlsx"
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="รองรับเฉพาะไฟล์ .xlsx")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="ไฟล์มีขนาดเกิน 10 MB")
    return filename, content

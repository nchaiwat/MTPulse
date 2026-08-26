from datetime import date
from io import BytesIO
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import ImportBatch, ModernTrade
from app.services.data_coverage_export import (
    CoverageBatch,
    build_data_coverage_workbook,
    data_coverage_filename,
)

router = APIRouter(prefix="/api/data-coverage", tags=["data coverage"])
AVAILABLE_STATUSES = ("imported", "imported_with_warnings")


@router.get("/export")
def export_data_coverage(
    session: Annotated[Session, Depends(get_session)],
    mt_code: Annotated[str, Query(min_length=1, max_length=20)],
    year: Annotated[int, Query(ge=2025, le=9999)],
) -> StreamingResponse:
    today = date.today()
    if year > today.year:
        raise HTTPException(status_code=422, detail="เลือกปีได้ไม่เกินปีปัจจุบัน")

    normalized_code = mt_code.strip().upper()
    modern_trade = session.scalar(
        select(ModernTrade).where(ModernTrade.code == normalized_code)
    )
    if modern_trade is None:
        raise HTTPException(
            status_code=404,
            detail=f"ไม่พบ Modern Trade รหัส {normalized_code}",
        )

    start_date = date(year, 1, 1)
    end_date = min(date(year, 12, 31), today)
    batches = session.scalars(
        select(ImportBatch)
        .where(
            ImportBatch.modern_trade_id == modern_trade.id,
            ImportBatch.data_date >= start_date,
            ImportBatch.data_date <= end_date,
            ImportBatch.status.in_(AVAILABLE_STATUSES),
        )
        .order_by(ImportBatch.data_date)
    ).all()
    content = build_data_coverage_workbook(
        mt_code=modern_trade.code,
        mt_name=modern_trade.name,
        year=year,
        end_date=end_date,
        batches=[
            CoverageBatch(
                batch_id=batch.id,
                data_date=batch.data_date,
                status=batch.status,
                branch_count=batch.store_count,
                item_count=batch.sku_count,
                row_count=batch.row_count,
                source_filename=batch.source_filename,
                finished_at=batch.finished_at,
            )
            for batch in batches
        ],
    )
    filename = data_coverage_filename(modern_trade.code, year)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )

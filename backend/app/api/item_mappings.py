from dataclasses import asdict
from datetime import date
from io import BytesIO
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.local_time import bangkok_today
from app.models import BranchMapping, ItemMapping, ModernTrade, SalesInventoryFact
from app.services.item_mapping_exchange import (
    ExportBranch,
    ExportItem,
    build_item_mapping_workbook,
    export_filename,
    import_item_mapping_workbook,
)

router = APIRouter(prefix="/api/item-mappings", tags=["item mappings"])
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.get("/export")
def export_item_mappings(
    session: Annotated[Session, Depends(get_session)],
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> StreamingResponse:
    modern_trade = session.scalar(select(ModernTrade).where(ModernTrade.code == "TWD"))
    if modern_trade is None:
        raise HTTPException(status_code=404, detail="ไม่พบ Modern Trade รหัส TWD")

    min_date, max_date = session.execute(
        select(func.min(SalesInventoryFact.data_date), func.max(SalesInventoryFact.data_date))
    ).one()
    range_from = date_from or min_date or bangkok_today()
    range_to = date_to or max_date or range_from
    source_rows = session.execute(
        select(
            SalesInventoryFact.source_sku,
            func.min(SalesInventoryFact.source_description),
        )
        .where(
            SalesInventoryFact.data_date >= range_from,
            SalesInventoryFact.data_date <= range_to,
        )
        .group_by(SalesInventoryFact.source_sku)
        .order_by(SalesInventoryFact.source_sku)
    ).all()
    mappings = session.scalars(
        select(ItemMapping)
        .where(
            ItemMapping.modern_trade_id == modern_trade.id,
            ItemMapping.effective_from <= range_to,
            (ItemMapping.effective_to.is_(None) | (ItemMapping.effective_to >= range_from)),
        )
        .order_by(ItemMapping.effective_from)
    ).all()
    mapping_by_sku = {mapping.source_sku: mapping for mapping in mappings}
    source_by_sku = {sku: description or "" for sku, description in source_rows}
    items = []
    for sku in sorted(set(source_by_sku) | set(mapping_by_sku)):
        mapping = mapping_by_sku.get(sku)
        items.append(
            ExportItem(
                source_sku=sku,
                source_description=source_by_sku.get(sku)
                or (mapping.source_description or "" if mapping else ""),
                wa_item_code=mapping.wa_item_code if mapping else "",
                wa_item_description=(mapping.wa_item_description or "") if mapping else "",
                status=mapping.status if mapping else "unmatched",
                item_type=mapping.item_type if mapping else "normal",
                report_status=mapping.report_status if mapping else "active",
            )
        )
    source_branch_rows = session.execute(
        select(
            SalesInventoryFact.source_branch_code,
            func.min(SalesInventoryFact.source_branch_name),
        )
        .where(
            SalesInventoryFact.data_date >= range_from,
            SalesInventoryFact.data_date <= range_to,
        )
        .group_by(SalesInventoryFact.source_branch_code)
        .order_by(SalesInventoryFact.source_branch_code)
    ).all()
    branch_mappings = session.scalars(
        select(BranchMapping)
        .where(
            BranchMapping.modern_trade_id == modern_trade.id,
            BranchMapping.effective_from <= range_to,
            (
                BranchMapping.effective_to.is_(None)
                | (BranchMapping.effective_to >= range_from)
            ),
        )
        .order_by(BranchMapping.effective_from)
    ).all()
    source_branch_by_code = {
        code: description or "" for code, description in source_branch_rows
    }
    branch_mapping_by_code = {
        mapping.source_branch_code: mapping for mapping in branch_mappings
    }
    branches = []
    for code in sorted(set(source_branch_by_code) | set(branch_mapping_by_code)):
        mapping = branch_mapping_by_code.get(code)
        branches.append(
            ExportBranch(
                source_branch_code=code,
                source_branch_description=source_branch_by_code.get(code)
                or (mapping.source_branch_description or "" if mapping else ""),
                wa_branch_code=mapping.wa_branch_code if mapping else "",
                wa_branch_description=(mapping.wa_branch_description or "") if mapping else "",
                status=mapping.status if mapping else "unmatched",
            )
        )

    content = build_item_mapping_workbook(items, branches)
    filename = export_filename(range_from, range_to)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.post("/import")
async def import_item_mappings(
    session: Annotated[Session, Depends(get_session)],
    file: Annotated[UploadFile, File()],
    effective_from: Annotated[date | None, Form()] = None,
) -> dict:
    filename = file.filename or "item-mapping.xlsx"
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="รองรับเฉพาะไฟล์ .xlsx")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="ไฟล์มีขนาดเกิน 10 MB")
    mapping_date = effective_from or session.scalar(
        select(func.max(SalesInventoryFact.data_date))
    ) or bangkok_today()
    try:
        report = import_item_mapping_workbook(session, content, mapping_date, filename)
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return asdict(report)

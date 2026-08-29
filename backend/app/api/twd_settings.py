import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import (
    AuditEvent,
    BranchMapping,
    ImportBatch,
    ItemMapping,
    ModernTrade,
    SalesInventoryFact,
)

router = APIRouter(prefix="/api/settings/twd", tags=["TWD settings"])


class UnmatchedVisibilityUpdate(BaseModel):
    show_unmatched_items: bool
    show_unmatched_branches: bool

class ReportPageSizeUpdate(BaseModel):
    report_page_size: int



def _twd(session: Session) -> ModernTrade:
    modern_trade = session.scalar(select(ModernTrade).where(ModernTrade.code == "TWD"))
    if modern_trade is None:
        raise HTTPException(status_code=404, detail="ไม่พบ Modern Trade รหัส TWD")
    return modern_trade


def _mapping_attention(session: Session, modern_trade: ModernTrade) -> tuple[int, int]:
    confirmed_items = select(ItemMapping.source_sku).where(
        ItemMapping.modern_trade_id == modern_trade.id,
        ItemMapping.status == "confirmed",
    )
    confirmed_branches = select(BranchMapping.source_branch_code).where(
        BranchMapping.modern_trade_id == modern_trade.id,
        BranchMapping.status == "confirmed",
    )
    item_count = session.scalar(
        select(func.count(distinct(SalesInventoryFact.source_sku)))
        .join(ImportBatch, SalesInventoryFact.batch_id == ImportBatch.id)
        .where(
            ImportBatch.modern_trade_id == modern_trade.id,
            ~SalesInventoryFact.source_sku.in_(confirmed_items),
        )
    ) or 0
    branch_count = session.scalar(
        select(func.count(distinct(SalesInventoryFact.source_branch_code)))
        .join(ImportBatch, SalesInventoryFact.batch_id == ImportBatch.id)
        .where(
            ImportBatch.modern_trade_id == modern_trade.id,
            ~SalesInventoryFact.source_branch_code.in_(confirmed_branches),
        )
    ) or 0
    return item_count, branch_count


@router.get("/unmatched-visibility")
def get_unmatched_visibility(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    modern_trade = _twd(session)
    item_attention, branch_attention = _mapping_attention(session, modern_trade)
    return {
        "showUnmatchedItems": modern_trade.show_unmatched_items,
        "showUnmatchedBranches": modern_trade.show_unmatched_branches,
        "mappingAttentionItems": item_attention,
        "mappingAttentionBranches": branch_attention,
        "reportPageSize": modern_trade.report_page_size,
    }


@router.patch("/unmatched-visibility")
def update_unmatched_visibility(
    update: UnmatchedVisibilityUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    modern_trade = _twd(session)
    before = {
        "show_unmatched_items": modern_trade.show_unmatched_items,
        "show_unmatched_branches": modern_trade.show_unmatched_branches,
    }
    modern_trade.show_unmatched_items = update.show_unmatched_items
    modern_trade.show_unmatched_branches = update.show_unmatched_branches
    after = {
        "show_unmatched_items": modern_trade.show_unmatched_items,
        "show_unmatched_branches": modern_trade.show_unmatched_branches,
    }
    session.add(
        AuditEvent(
            entity_type="modern_trade",
            entity_id=modern_trade.code,
            action="update_unmatched_visibility",
            actor="twd-settings",
            before_json=json.dumps(before),
            after_json=json.dumps(after),
        )
    )
    session.commit()
    item_attention, branch_attention = _mapping_attention(session, modern_trade)
    return {
        "showUnmatchedItems": modern_trade.show_unmatched_items,
        "showUnmatchedBranches": modern_trade.show_unmatched_branches,
        "mappingAttentionItems": item_attention,
        "mappingAttentionBranches": branch_attention,
        "reportPageSize": modern_trade.report_page_size,
    }


@router.patch("/report-page-size")
def update_report_page_size(
    update: ReportPageSizeUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    if update.report_page_size not in (0, 25, 50, 100):
        raise HTTPException(
            status_code=422,
            detail="จำนวน SKU ต่อหน้าต้องเป็น ทั้งหมด, 25, 50 หรือ 100",
        )
    modern_trade = _twd(session)
    before = {"report_page_size": modern_trade.report_page_size}
    modern_trade.report_page_size = update.report_page_size
    session.add(
        AuditEvent(
            entity_type="modern_trade",
            entity_id=modern_trade.code,
            action="update_report_page_size",
            actor="twd-settings",
            before_json=json.dumps(before),
            after_json=json.dumps({"report_page_size": modern_trade.report_page_size}),
        )
    )
    session.commit()
    return {
        "reportPageSize": modern_trade.report_page_size,
    }

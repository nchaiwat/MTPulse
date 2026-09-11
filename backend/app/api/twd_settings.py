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
from app.modern_trade_registry import active_modern_trade_codes

router = APIRouter(prefix="/api/settings/twd", tags=["TWD settings"])
modern_trade_router = APIRouter(
    prefix="/api/settings/modern-trades",
    tags=["Modern Trade settings"],
)


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


def _modern_trade(session: Session, code: str) -> ModernTrade:
    normalized = code.strip().upper()
    if normalized not in active_modern_trade_codes("settings"):
        raise HTTPException(status_code=404, detail=f"ไม่รองรับ Modern Trade รหัส {normalized}")
    modern_trade = session.scalar(select(ModernTrade).where(ModernTrade.code == normalized))
    if modern_trade is None:
        raise HTTPException(status_code=404, detail=f"ไม่พบ Modern Trade รหัส {normalized}")
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
    item_count = (
        session.scalar(
            select(func.count(distinct(SalesInventoryFact.source_sku)))
            .join(ImportBatch, SalesInventoryFact.batch_id == ImportBatch.id)
            .where(
                ImportBatch.modern_trade_id == modern_trade.id,
                ~SalesInventoryFact.source_sku.in_(confirmed_items),
            )
        )
        or 0
    )
    branch_count = (
        session.scalar(
            select(func.count(distinct(SalesInventoryFact.source_branch_code)))
            .join(ImportBatch, SalesInventoryFact.batch_id == ImportBatch.id)
            .where(
                ImportBatch.modern_trade_id == modern_trade.id,
                ~SalesInventoryFact.source_branch_code.in_(confirmed_branches),
            )
        )
        or 0
    )
    return item_count, branch_count


def _settings_payload(session: Session, modern_trade: ModernTrade) -> dict:
    item_attention, branch_attention = _mapping_attention(session, modern_trade)
    has_data = (
        session.scalar(
            select(SalesInventoryFact.id)
            .where(SalesInventoryFact.modern_trade_id == modern_trade.id)
            .limit(1)
        )
        is not None
    )
    return {
        "showUnmatchedItems": modern_trade.show_unmatched_items,
        "showUnmatchedBranches": modern_trade.show_unmatched_branches,
        "mappingAttentionItems": item_attention,
        "mappingAttentionBranches": branch_attention,
        "reportPageSize": modern_trade.report_page_size,
        "hasData": has_data,
    }


@router.get("/unmatched-visibility")
def get_unmatched_visibility(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    modern_trade = _twd(session)
    return _settings_payload(session, modern_trade)


@modern_trade_router.get("/{code}/unmatched-visibility")
def get_modern_trade_settings(
    code: str,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    return _settings_payload(session, _modern_trade(session, code))


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
    return _settings_payload(session, modern_trade)


@modern_trade_router.patch("/{code}/unmatched-visibility")
def update_modern_trade_visibility(
    code: str,
    update: UnmatchedVisibilityUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    modern_trade = _modern_trade(session, code)
    before = {
        "show_unmatched_items": modern_trade.show_unmatched_items,
        "show_unmatched_branches": modern_trade.show_unmatched_branches,
    }
    modern_trade.show_unmatched_items = update.show_unmatched_items
    modern_trade.show_unmatched_branches = update.show_unmatched_branches
    session.add(
        AuditEvent(
            entity_type="modern_trade",
            entity_id=modern_trade.code,
            action="update_unmatched_visibility",
            actor=f"{modern_trade.code.lower()}-settings",
            before_json=json.dumps(before),
            after_json=json.dumps(
                {
                    "show_unmatched_items": modern_trade.show_unmatched_items,
                    "show_unmatched_branches": modern_trade.show_unmatched_branches,
                }
            ),
        )
    )
    session.commit()
    return _settings_payload(session, modern_trade)


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


@modern_trade_router.patch("/{code}/report-page-size")
def update_modern_trade_report_page_size(
    code: str,
    update: ReportPageSizeUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    if update.report_page_size not in (0, 25, 50, 100):
        raise HTTPException(status_code=422, detail="จำนวน SKU ต่อหน้าต้องเป็น ทั้งหมด, 25, 50 หรือ 100")
    modern_trade = _modern_trade(session, code)
    before = {"report_page_size": modern_trade.report_page_size}
    modern_trade.report_page_size = update.report_page_size
    session.add(
        AuditEvent(
            entity_type="modern_trade",
            entity_id=modern_trade.code,
            action="update_report_page_size",
            actor=f"{modern_trade.code.lower()}-settings",
            before_json=json.dumps(before),
            after_json=json.dumps({"report_page_size": modern_trade.report_page_size}),
        )
    )
    session.commit()
    return {"reportPageSize": modern_trade.report_page_size}

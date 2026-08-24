import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import AuditEvent, ModernTrade

router = APIRouter(prefix="/api/settings/twd", tags=["TWD settings"])


class UnmatchedVisibilityUpdate(BaseModel):
    show_unmatched_items: bool
    show_unmatched_branches: bool


def _twd(session: Session) -> ModernTrade:
    modern_trade = session.scalar(select(ModernTrade).where(ModernTrade.code == "TWD"))
    if modern_trade is None:
        raise HTTPException(status_code=404, detail="ไม่พบ Modern Trade รหัส TWD")
    return modern_trade


@router.get("/unmatched-visibility")
def get_unmatched_visibility(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    modern_trade = _twd(session)
    return {
        "showUnmatchedItems": modern_trade.show_unmatched_items,
        "showUnmatchedBranches": modern_trade.show_unmatched_branches,
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
    return {
        "showUnmatchedItems": modern_trade.show_unmatched_items,
        "showUnmatchedBranches": modern_trade.show_unmatched_branches,
    }

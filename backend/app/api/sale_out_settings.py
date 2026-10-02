from __future__ import annotations

import json
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_system_admin
from app.database import get_session
from app.models import AuditEvent, ModernTrade
from app.modern_trade_registry import active_modern_trade_codes
from app.services.sale_out import (
    CommonCutoffEvaluation,
    evaluate_common_cutoff,
    refresh_common_cutoff,
    set_cutoff_auto_advance,
    set_cutoff_frozen,
)

router = APIRouter(prefix="/api/settings/sale-out", tags=["Sale Out settings"])


class SaleOutModernTradeUpdate(BaseModel):
    start_date: date | None
    include_in_total: bool


class SaleOutCutoffControlUpdate(BaseModel):
    frozen: bool | None = None
    auto_advance_enabled: bool | None = None


def _modern_trade(session: Session, code: str) -> ModernTrade:
    normalized = code.strip().upper()
    if normalized not in active_modern_trade_codes("settings"):
        raise HTTPException(status_code=404, detail=f"ไม่รองรับ Modern Trade รหัส {normalized}")
    modern_trade = session.scalar(select(ModernTrade).where(ModernTrade.code == normalized))
    if modern_trade is None:
        raise HTTPException(status_code=404, detail=f"ไม่พบ Modern Trade รหัส {normalized}")
    return modern_trade


def _modern_trade_payload(modern_trade: ModernTrade) -> dict:
    return {
        "code": modern_trade.code,
        "name": modern_trade.name,
        "startDate": modern_trade.sale_out_start_date,
        "includeInTotal": modern_trade.sale_out_include_in_total,
    }


def _cutoff_payload(evaluation: CommonCutoffEvaluation) -> dict:
    return {
        "activeDate": evaluation.active_date,
        "candidateDate": evaluation.candidate_date,
        "frozen": evaluation.frozen,
        "autoAdvanceEnabled": evaluation.auto_advance_enabled,
        "advanced": evaluation.advanced,
        "members": [
            {
                "code": member.code,
                "startDate": member.start_date,
                "coveredThrough": member.covered_through,
                "latestSourceDate": member.latest_source_date,
                "blockingDate": member.blocking_date,
            }
            for member in evaluation.members
        ],
    }


@router.get("")
def get_sale_out_settings(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    supported_codes = active_modern_trade_codes("settings")
    modern_trades = session.scalars(
        select(ModernTrade)
        .where(ModernTrade.code.in_(supported_codes))
        .order_by(ModernTrade.code)
    ).all()
    return {
        "modernTrades": [_modern_trade_payload(modern_trade) for modern_trade in modern_trades],
        "cutoff": _cutoff_payload(evaluate_common_cutoff(session)),
    }


@router.patch("/modern-trades/{code}")
def update_sale_out_modern_trade(
    code: str,
    update: SaleOutModernTradeUpdate,
    session: Annotated[Session, Depends(get_session)],
    actor: Annotated[str, Depends(require_system_admin)],
) -> dict:
    if update.include_in_total and update.start_date is None:
        raise HTTPException(
            status_code=422,
            detail="MT ที่รวมใน Total ต้องกำหนด Sale Out Start Date",
        )
    modern_trade = _modern_trade(session, code)
    before = _modern_trade_payload(modern_trade)
    modern_trade.sale_out_start_date = update.start_date
    modern_trade.sale_out_include_in_total = update.include_in_total
    after = _modern_trade_payload(modern_trade)
    session.add(
        AuditEvent(
            entity_type="modern_trade",
            entity_id=modern_trade.code,
            action="update_sale_out_settings",
            actor=actor,
            before_json=json.dumps(before, ensure_ascii=False, default=str),
            after_json=json.dumps(after, ensure_ascii=False, default=str),
        )
    )
    session.commit()
    refresh_common_cutoff(session, actor=actor)
    return _modern_trade_payload(modern_trade)


@router.patch("/cutoff-control")
def update_sale_out_cutoff_control(
    update: SaleOutCutoffControlUpdate,
    session: Annotated[Session, Depends(get_session)],
    actor: Annotated[str, Depends(require_system_admin)],
) -> dict:
    if update.frozen is None and update.auto_advance_enabled is None:
        raise HTTPException(status_code=422, detail="ต้องระบุ Auto-advance หรือ Freeze อย่างน้อยหนึ่งค่า")
    if update.auto_advance_enabled is not None:
        set_cutoff_auto_advance(
            session,
            enabled=update.auto_advance_enabled,
            actor=actor,
        )
    if update.frozen is not None:
        set_cutoff_frozen(session, frozen=update.frozen, actor=actor)
    evaluation = refresh_common_cutoff(session, actor=actor)
    return _cutoff_payload(evaluation)


@router.post("/refresh-cutoff")
def refresh_sale_out_cutoff(
    session: Annotated[Session, Depends(get_session)],
    actor: Annotated[str, Depends(require_system_admin)],
) -> dict:
    return _cutoff_payload(refresh_common_cutoff(session, actor=actor))

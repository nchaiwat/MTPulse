from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_system_admin
from app.database import get_session
from app.models import ModernTrade, SkuInterest
from app.services.sku_interest import decide_sku_interest

router = APIRouter(
    prefix="/api/admin/modern-trades",
    tags=["sku interests"],
    dependencies=[Depends(require_system_admin)],
)


class SkuInterestDecision(BaseModel):
    decision: Literal["accept", "ignore"]


@router.patch("/{code}/sku-interests/{source_sku}")
def update_sku_interest(
    code: str,
    source_sku: str,
    request: SkuInterestDecision,
    session: Annotated[Session, Depends(get_session)],
    actor: Annotated[str, Depends(require_system_admin)],
) -> dict:
    modern_trade = session.scalar(
        select(ModernTrade).where(ModernTrade.code == code.strip().upper())
    )
    if modern_trade is None:
        raise HTTPException(status_code=404, detail=f"ไม่พบ Modern Trade {code}")
    interest = session.scalar(
        select(SkuInterest).where(
            SkuInterest.modern_trade_id == modern_trade.id,
            SkuInterest.source_sku == source_sku.strip(),
        )
    )
    if interest is None:
        raise HTTPException(status_code=404, detail=f"ไม่พบ SKU {source_sku}")
    updated = decide_sku_interest(
        session,
        interest,
        decision=request.decision,
        actor=actor,
    )
    return {
        "mtCode": modern_trade.code,
        "sku": updated.source_sku,
        "status": updated.status,
        "message": (
            "Accept แล้ว กรุณาทำ Mapping ก่อนแสดงในรายงาน"
            if updated.status == "active"
            else "Ignore แล้ว ระบบจะไม่เก็บ Fact ของ SKU นี้ใน Import ถัดไป"
        ),
    }

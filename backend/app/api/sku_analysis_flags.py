import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import AuditEvent, ItemMapping, ModernTrade, SkuAnalysisFlag, SkuInterest

router = APIRouter(prefix="/api/performance/sku-flags", tags=["SKU analysis flags"])


class SkuAnalysisFlagUpdate(BaseModel):
    flag: Literal["sho", "pro"]
    enabled: bool


def _payload(flag: SkuAnalysisFlag, mt_code: str) -> dict:
    return {
        "mtCode": mt_code,
        "sku": flag.source_sku,
        "isSho": flag.is_showroom,
        "isPro": flag.is_promotion,
        "updatedAt": flag.updated_at.isoformat() if flag.updated_at else None,
    }


@router.patch("/{mt_code}/{source_sku}")
def update_sku_analysis_flag(
    mt_code: str,
    source_sku: str,
    request: SkuAnalysisFlagUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    normalized_mt_code = mt_code.strip().upper()
    modern_trade = session.scalar(
        select(ModernTrade)
        .where(ModernTrade.code == normalized_mt_code)
        .with_for_update()
    )
    if modern_trade is None:
        raise HTTPException(
            status_code=404,
            detail=f"ไม่พบ Modern Trade รหัส {normalized_mt_code}",
        )

    normalized_sku = source_sku.strip()
    if not normalized_sku:
        raise HTTPException(status_code=422, detail="กรุณาระบุ SKU")
    known_sku = session.scalar(
        select(ItemMapping.id)
        .where(
            ItemMapping.modern_trade_id == modern_trade.id,
            ItemMapping.source_sku == normalized_sku,
        )
        .limit(1)
    ) or session.scalar(
        select(SkuInterest.id)
        .where(
            SkuInterest.modern_trade_id == modern_trade.id,
            SkuInterest.source_sku == normalized_sku,
        )
        .limit(1)
    )
    if known_sku is None:
        raise HTTPException(
            status_code=404,
            detail=f"ไม่พบ SKU {normalized_sku} ของ {normalized_mt_code}",
        )

    analysis_flag = session.scalar(
        select(SkuAnalysisFlag).where(
            SkuAnalysisFlag.modern_trade_id == modern_trade.id,
            SkuAnalysisFlag.source_sku == normalized_sku,
        )
    )
    if analysis_flag is None:
        analysis_flag = SkuAnalysisFlag(
            modern_trade_id=modern_trade.id,
            source_sku=normalized_sku,
            updated_by="performance-user",
        )
        session.add(analysis_flag)
        session.flush()

    before = {
        "isSho": analysis_flag.is_showroom,
        "isPro": analysis_flag.is_promotion,
    }
    if request.flag == "sho":
        analysis_flag.is_showroom = request.enabled
    else:
        analysis_flag.is_promotion = request.enabled
    analysis_flag.updated_by = "performance-user"
    after = {
        "isSho": analysis_flag.is_showroom,
        "isPro": analysis_flag.is_promotion,
    }
    if before != after:
        session.add(
            AuditEvent(
                entity_type="sku_analysis_flag",
                entity_id=f"{normalized_mt_code}:{normalized_sku}",
                action=f"set_{request.flag}",
                actor="performance-user",
                before_json=json.dumps(before),
                after_json=json.dumps(after),
            )
        )
    session.commit()
    session.refresh(analysis_flag)
    return _payload(analysis_flag, normalized_mt_code)

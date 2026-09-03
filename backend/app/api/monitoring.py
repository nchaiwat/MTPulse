from datetime import date
from pathlib import PureWindowsPath
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import ImportRun, ItemMapping, ModernTrade, SkuInterest, SourceFile
from app.services.automatic_import import run_payload
from app.services.monitoring import capture_monitoring_snapshot, monitoring_history

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


def _source_folder_date(source_path: str) -> str | None:
    folder = PureWindowsPath(source_path).parent.name
    try:
        return date.fromisoformat(folder).isoformat()
    except ValueError:
        return None


def _automatic_imports(session: Session) -> dict:
    run_rows = session.execute(
        select(ImportRun, ModernTrade)
        .join(ModernTrade, ModernTrade.id == ImportRun.modern_trade_id)
        .order_by(ImportRun.requested_at.desc(), ImportRun.id.desc())
        .limit(10)
    ).all()
    pending_rows = session.execute(
        select(SourceFile, ModernTrade)
        .join(ModernTrade, ModernTrade.id == SourceFile.modern_trade_id)
        .where(SourceFile.status.in_({"pending_review", "failed", "missing"}))
        .order_by(SourceFile.last_seen_at.desc(), SourceFile.id.desc())
        .limit(50)
    ).all()
    active_mapped_skus = (
        select(ItemMapping.source_sku)
        .where(
            ItemMapping.modern_trade_id == SkuInterest.modern_trade_id,
            ItemMapping.report_status == "active",
            ItemMapping.effective_to.is_(None),
        )
        .correlate(SkuInterest)
    )
    pending_skus = session.execute(
        select(SkuInterest, ModernTrade)
        .join(ModernTrade, ModernTrade.id == SkuInterest.modern_trade_id)
        .where(
            or_(
                SkuInterest.status == "pending",
                (
                    (SkuInterest.status == "active")
                    & (~SkuInterest.source_sku.in_(active_mapped_skus))
                ),
            )
        )
        .order_by(SkuInterest.last_seen_at.desc(), SkuInterest.id.desc())
        .limit(100)
    ).all()
    return {
        "runs": [run_payload(run, mt, session=session) for run, mt in run_rows],
        "pendingFiles": [
            {
                "sourceFileId": source.id,
                "mtCode": mt.code,
                "filename": source.source_filename,
                "dataDate": (
                    source.detected_data_date.isoformat()
                    if source.detected_data_date
                    else None
                ),
                "sourceFolderDate": _source_folder_date(source.source_path),
                "status": source.status,
                "message": source.error_message,
                "lastSeenAt": source.last_seen_at.isoformat(),
                "batchId": source.imported_batch_id,
            }
            for source, mt in pending_rows
        ],
        "pendingSkus": [
            {
                "skuInterestId": interest.id,
                "mtCode": mt.code,
                "sku": interest.source_sku,
                "description": interest.source_description,
                "status": (
                    "pending" if interest.status == "pending" else "accepted"
                ),
                "firstSeenDate": interest.first_seen_date.isoformat(),
                "lastSeenDate": interest.last_seen_date.isoformat(),
                "lastSeenAt": interest.last_seen_at.isoformat(),
            }
            for interest, mt in pending_skus
        ],
    }


def _payload(session: Session, *, trigger: str, upsert_today: bool) -> dict:
    current = capture_monitoring_snapshot(
        session,
        trigger=trigger,
        upsert_today=upsert_today,
    )
    return {
        "current": current,
        "history": monitoring_history(session),
        "automaticImports": _automatic_imports(session),
    }


@router.get("")
def get_monitoring(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    return _payload(session, trigger="page_open", upsert_today=False)


@router.post("/refresh")
def refresh_monitoring(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    return _payload(session, trigger="manual_refresh", upsert_today=True)

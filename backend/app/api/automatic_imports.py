import json
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_system_admin
from app.database import get_session
from app.local_time import bangkok_now
from app.models import AuditEvent, ImportRun, ModernTrade
from app.modern_trade_registry import (
    ModernTradeCapability,
    active_capability_label,
    active_modern_trade_codes,
    modern_trade_definition,
)
from app.services.automatic_import import (
    ActiveRunError,
    create_run,
    run_payload,
)
from app.services.sku_backfill import (
    backfill_options,
    create_sku_backfill_run,
    preview_sku_backfill,
)

router = APIRouter(
    prefix="/api/admin",
    tags=["automatic imports"],
    dependencies=[Depends(require_system_admin)],
)


class RunNowRequest(BaseModel):
    confirmed: bool


class SkuBackfillRequest(BaseModel):
    source_sku: str
    range_start: date | None = None


class SkuBackfillConfirmRequest(SkuBackfillRequest):
    confirmed: bool


def _modern_trade(session: Session, code: str) -> ModernTrade:
    mt = session.scalar(select(ModernTrade).where(ModernTrade.code == code.strip().upper()))
    if mt is None:
        raise HTTPException(status_code=404, detail=f"ไม่พบ Modern Trade {code}")
    return mt


def _require_capability(
    mt: ModernTrade,
    capability: ModernTradeCapability,
    feature_name: str,
) -> None:
    if mt.code not in active_modern_trade_codes(capability):
        supported = active_capability_label(capability)
        raise HTTPException(
            status_code=409,
            detail=f"{feature_name} รองรับเฉพาะ {supported}",
        )


def _run_owner(session: Session, mt: ModernTrade) -> ModernTrade:
    definition = modern_trade_definition(mt.code)
    if definition is None:
        raise HTTPException(status_code=409, detail=f"ยังไม่มี Package ของ {mt.code}")
    return _modern_trade(session, definition.source_owner_code)


@router.post("/modern-trades/{code}/runs", status_code=202)
def run_now(
    code: str,
    request: RunNowRequest,
    session: Annotated[Session, Depends(get_session)],
    actor: Annotated[str, Depends(require_system_admin)],
) -> dict:
    if not request.confirmed:
        raise HTTPException(status_code=400, detail="กรุณายืนยัน Run ก่อนเริ่มงาน")
    mt = _modern_trade(session, code)
    _require_capability(mt, "automatic_import", "Automatic Import")
    run_owner = _run_owner(session, mt)
    if not run_owner.source_enabled:
        raise HTTPException(
            status_code=409,
            detail=f"{run_owner.code} ปิดใช้งาน FileShare",
        )
    try:
        run = create_run(session, run_owner, trigger="manual", actor=actor)
    except ActiveRunError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return run_payload(run, run_owner, session=session)


@router.get("/modern-trades/{code}/sku-backfills/options")
def sku_backfill_options(
    code: str,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    mt = _modern_trade(session, code)
    _require_capability(mt, "sku_backfill", "Backfill")
    return backfill_options(session, mt)


@router.post("/modern-trades/{code}/source-registry/refresh", status_code=202)
def refresh_source_registry(
    code: str,
    request: RunNowRequest,
    session: Annotated[Session, Depends(get_session)],
    actor: Annotated[str, Depends(require_system_admin)],
) -> dict:
    if not request.confirmed:
        raise HTTPException(status_code=400, detail="กรุณายืนยันก่อนอัปเดต File Registry")
    mt = _modern_trade(session, code)
    _require_capability(mt, "automatic_import", "File Registry")
    if not mt.source_enabled:
        raise HTTPException(status_code=409, detail=f"{mt.code} ปิดใช้งาน FileShare")
    run_owner = _run_owner(session, mt)
    try:
        run = create_run(
            session,
            run_owner,
            trigger="manual",
            actor=actor,
            mode="registry",
        )
    except ActiveRunError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return run_payload(run, run_owner, session=session)


@router.post("/modern-trades/{code}/sku-backfills/preview")
def preview_backfill(
    code: str,
    request: SkuBackfillRequest,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    mt = _modern_trade(session, code)
    _require_capability(mt, "sku_backfill", "Backfill")
    try:
        return preview_sku_backfill(
            session,
            mt,
            request.source_sku,
            request.range_start,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/modern-trades/{code}/sku-backfills", status_code=202)
def start_backfill(
    code: str,
    request: SkuBackfillConfirmRequest,
    session: Annotated[Session, Depends(get_session)],
    actor: Annotated[str, Depends(require_system_admin)],
) -> dict:
    if not request.confirmed:
        raise HTTPException(status_code=400, detail="กรุณายืนยัน Backfill ก่อนเริ่มงาน")
    mt = _modern_trade(session, code)
    _require_capability(mt, "sku_backfill", "Backfill")
    if not mt.source_enabled:
        raise HTTPException(status_code=409, detail=f"{mt.code} ปิดใช้งาน FileShare")
    try:
        run = create_sku_backfill_run(
            session,
            mt,
            source_sku=request.source_sku.strip(),
            range_start=request.range_start,
            actor=actor,
        )
    except (ActiveRunError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return run_payload(run, mt, session=session)


@router.post("/import-runs/{run_id}/stop")
def stop_import_run(
    run_id: int,
    session: Annotated[Session, Depends(get_session)],
    actor: Annotated[str, Depends(require_system_admin)],
) -> dict:
    run = session.get(ImportRun, run_id)
    if run is None or run.mode != "sku_backfill":
        raise HTTPException(status_code=404, detail=f"ไม่พบ SKU Backfill Run {run_id}")
    if run.status == "queued":
        run.status = "stopped"
        run.finished_at = bangkok_now()
        run.summary_message = "หยุดก่อน Worker เริ่มงาน สามารถกดทำต่อได้"
    elif run.status == "running":
        run.status = "stop_requested"
        run.stop_requested_at = bangkok_now()
        run.summary_message = "รับคำขอหยุดแล้ว ระบบจะหยุดหลังจบไฟล์ปัจจุบัน"
    elif run.status != "stop_requested":
        raise HTTPException(status_code=409, detail="Run นี้ไม่ได้อยู่ในสถานะที่หยุดได้")
    session.add(
        AuditEvent(
            entity_type="import_run",
            entity_id=str(run.id),
            action="stop_requested",
            actor=actor,
            before_json=None,
            after_json=json.dumps({"status": run.status}),
        )
    )
    session.commit()
    mt = session.get(ModernTrade, run.modern_trade_id)
    return run_payload(run, mt, session=session)


@router.post("/import-runs/{run_id}/resume", status_code=202)
def resume_import_run(
    run_id: int,
    session: Annotated[Session, Depends(get_session)],
    actor: Annotated[str, Depends(require_system_admin)],
) -> dict:
    run = session.get(ImportRun, run_id)
    if run is None or run.mode != "sku_backfill":
        raise HTTPException(status_code=404, detail=f"ไม่พบ SKU Backfill Run {run_id}")
    if run.status != "stopped":
        raise HTTPException(status_code=409, detail="ทำต่อได้เฉพาะ Run ที่หยุดแล้ว")
    active = session.scalar(
        select(ImportRun.id)
        .where(
            ImportRun.modern_trade_id == run.modern_trade_id,
            ImportRun.id != run.id,
            ImportRun.status.in_({"queued", "running", "stop_requested"}),
        )
        .limit(1)
    )
    if active is not None:
        raise HTTPException(status_code=409, detail=f"TWD กำลังประมวลผล Run {active}")
    run.status = "queued"
    run.finished_at = None
    run.stop_requested_at = None
    run.summary_message = "รอ Worker ทำต่อจากวันที่ที่ยังเหลือ"
    session.add(
        AuditEvent(
            entity_type="import_run",
            entity_id=str(run.id),
            action="resumed",
            actor=actor,
            before_json=json.dumps({"status": "stopped"}),
            after_json=json.dumps({"status": "queued"}),
        )
    )
    session.commit()
    mt = session.get(ModernTrade, run.modern_trade_id)
    return run_payload(run, mt, session=session)


@router.get("/import-runs")
def import_runs(
    session: Annotated[Session, Depends(get_session)],
    mt_code: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    statement = (
        select(ImportRun, ModernTrade)
        .join(ModernTrade, ModernTrade.id == ImportRun.modern_trade_id)
        .order_by(ImportRun.requested_at.desc(), ImportRun.id.desc())
        .limit(limit)
    )
    if mt_code:
        statement = statement.where(ModernTrade.code == mt_code.strip().upper())
    rows = session.execute(statement).all()
    return {"runs": [run_payload(run, mt, session=session) for run, mt in rows]}


@router.get("/import-runs/{run_id}")
def import_run_detail(
    run_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    row = session.execute(
        select(ImportRun, ModernTrade)
        .join(ModernTrade, ModernTrade.id == ImportRun.modern_trade_id)
        .where(ImportRun.id == run_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"ไม่พบ Import Run {run_id}")
    return run_payload(row[0], row[1], session=session)

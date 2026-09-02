from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_system_admin
from app.database import get_session
from app.models import ImportRun, ModernTrade
from app.services.automatic_import import (
    ActiveRunError,
    create_run,
    run_payload,
)

router = APIRouter(
    prefix="/api/admin",
    tags=["automatic imports"],
    dependencies=[Depends(require_system_admin)],
)


class RunNowRequest(BaseModel):
    confirmed: bool


def _modern_trade(session: Session, code: str) -> ModernTrade:
    mt = session.scalar(
        select(ModernTrade).where(ModernTrade.code == code.strip().upper())
    )
    if mt is None:
        raise HTTPException(status_code=404, detail=f"ไม่พบ Modern Trade {code}")
    return mt


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
    if mt.code != "TWD":
        raise HTTPException(
            status_code=409,
            detail="Automatic Import Phase นี้รองรับเฉพาะ TWD",
        )
    if not mt.source_enabled:
        raise HTTPException(status_code=409, detail=f"{mt.code} ปิดใช้งาน FileShare")
    try:
        run = create_run(session, mt, trigger="manual", actor=actor)
    except ActiveRunError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return run_payload(run, mt)


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
    return {"runs": [run_payload(run, mt) for run, mt in rows]}


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
    return run_payload(row[0], row[1])

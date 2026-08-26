from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.services.monitoring import capture_monitoring_snapshot, monitoring_history

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


def _payload(session: Session, *, trigger: str, upsert_today: bool) -> dict:
    current = capture_monitoring_snapshot(
        session,
        trigger=trigger,
        upsert_today=upsert_today,
    )
    return {
        "current": current,
        "history": monitoring_history(session),
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

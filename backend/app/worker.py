from __future__ import annotations

import logging
import time
from datetime import datetime

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.local_time import bangkok_now
from app.models import ImportRun, ModernTrade
from app.services.automatic_import import ActiveRunError, create_run, process_run

logger = logging.getLogger("mtpulse.worker")
logging.basicConfig(level=logging.INFO)


def enqueue_due_runs(now: datetime | None = None) -> int:
    current = now or bangkok_now()
    queued = 0
    with SessionLocal() as session:
        modern_trades = session.scalars(
            select(ModernTrade).where(
                ModernTrade.code == "TWD",
                ModernTrade.source_enabled.is_(True),
                ModernTrade.schedule_enabled.is_(True),
                ModernTrade.schedule_time.is_not(None),
            )
        ).all()
        for mt in modern_trades:
            assert mt.schedule_time is not None
            if current.time().replace(tzinfo=None) < mt.schedule_time:
                continue
            already_scheduled = session.scalar(
                select(ImportRun.id)
                .where(
                    ImportRun.modern_trade_id == mt.id,
                    ImportRun.scheduled_local_date == current.date(),
                    ImportRun.trigger.in_({"scheduled", "catch_up"}),
                )
                .limit(1)
            )
            if already_scheduled is not None:
                continue
            scheduled_at = datetime.combine(
                current.date(),
                mt.schedule_time,
                tzinfo=current.tzinfo,
            )
            trigger = (
                "scheduled"
                if (current - scheduled_at).total_seconds() <= 120
                else "catch_up"
            )
            try:
                create_run(
                    session,
                    mt,
                    trigger=trigger,
                    actor="system-scheduler",
                    scheduled_local_date=current.date(),
                )
                queued += 1
            except ActiveRunError:
                logger.info("%s already has an active run", mt.code)
    return queued


def claim_next_run() -> int | None:
    with SessionLocal() as session:
        run = session.scalar(
            select(ImportRun)
            .where(ImportRun.status == "queued")
            .order_by(ImportRun.requested_at, ImportRun.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if run is None:
            return None
        run.status = "running"
        run.started_at = bangkok_now()
        session.commit()
        return run.id


def recover_interrupted_runs() -> int:
    with SessionLocal() as session:
        runs = session.scalars(
            select(ImportRun).where(ImportRun.status == "running")
        ).all()
        if not runs:
            return 0
        finished_at = bangkok_now()
        for run in runs:
            run.status = "failed"
            run.finished_at = finished_at
            run.error_message = "Worker ถูก Restart ระหว่างประมวลผล"
            run.summary_message = (
                "Run ถูกยุติ แต่ข้อมูลที่นำเข้าสำเร็จแล้วไม่ถูกลบ "
                "Run ครั้งถัดไปจะข้ามไฟล์เดิมด้วย checksum"
            )
        session.commit()
        return len(runs)


def run_forever() -> None:
    poll_seconds = max(5, get_settings().worker_poll_seconds)
    recovered = recover_interrupted_runs()
    if recovered:
        logger.warning("marked %s interrupted run(s) as failed", recovered)
    logger.info("MT Pulse import worker started; poll=%ss", poll_seconds)
    while True:
        try:
            enqueue_due_runs()
            run_id = claim_next_run()
            if run_id is None:
                time.sleep(poll_seconds)
                continue
            with SessionLocal() as session:
                process_run(session, run_id)
        except Exception:
            logger.exception("worker loop failed")
            time.sleep(poll_seconds)


if __name__ == "__main__":
    run_forever()

"""Separate Compose process; PostgreSQL advisory lock excludes duplicate replicas."""

import logging
import time

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine
from app.services.ciam_agent import cycle

logger = logging.getLogger("mtpulse.ciam_agent")
LOCK = 782614035


def run_once():
    with engine.connect() as connection:
        locked = connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK}
        ).scalar()
        connection.commit()
        if not locked:
            return
        try:
            with Session(bind=connection, expire_on_commit=False) as db:
                cycle(db)
        finally:
            connection.rollback()
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK})
            connection.commit()


def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            run_once()
        except Exception as exc:
            logger.error("Agent cycle failed: %s", type(exc).__name__)
        time.sleep(5)


if __name__ == "__main__":
    main()

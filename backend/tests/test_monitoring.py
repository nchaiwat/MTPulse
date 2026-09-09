from datetime import datetime
from types import SimpleNamespace

from sqlalchemy.exc import IntegrityError

from app.api.monitoring import _source_folder_date
from app.services.monitoring import (
    _overall_status,
    _warning_count,
    _warning_details,
    capture_monitoring_snapshot,
)


def test_overall_status_uses_highest_severity() -> None:
    notices = [
        {"level": "warning", "title": "warning", "detail": "detail"},
        {"level": "critical", "title": "critical", "detail": "detail"},
    ]

    assert _overall_status(notices) == "critical"
    assert _overall_status([]) == "healthy"


def test_warning_count_ignores_blank_reconciliation_lines() -> None:
    batch = SimpleNamespace(reconciliation_errors="first\n\nsecond\n")

    assert _warning_count(batch) == 2
    assert _warning_count(None) == 0


def test_warning_details_returns_actionable_reconciliation_text() -> None:
    batch = SimpleNamespace(
        reconciliation_errors="Stock On Hand: calculated=77904.0, source=77379\n\nsecond warning"
    )

    assert _warning_details(batch) == (
        "Stock On Hand: calculated=77904.0, source=77379 · second warning"
    )


def test_source_folder_date_is_only_a_hint_for_unreadable_file() -> None:
    assert (
        _source_folder_date(
            r"\\server\share\TWD\2025-01-13\empty.xls"
        )
        == "2025-01-13"
    )
    assert _source_folder_date(r"\\server\share\TWD\unknown\file.xls") is None


def test_capture_snapshot_tolerates_concurrent_daily_insert(monkeypatch) -> None:
    captured_at = datetime.fromisoformat("2026-09-08T07:00:00+07:00")
    metrics = {
        "capturedAt": captured_at.isoformat(),
        "overallStatus": "healthy",
        "notices": [],
        "api": {"status": "healthy"},
        "host": {
            "cpuPercent": 1.0,
            "memoryUsedPercent": 2.0,
            "memoryTotalBytes": 3,
            "diskUsedPercent": 4.0,
            "diskTotalBytes": 5,
            "uptimeSeconds": 6,
        },
        "database": {
            "factCount": 10,
            "databaseSizeBytes": 20,
            "factTableSizeBytes": 30,
            "factIndexesSizeBytes": 40,
            "deadTupleCount": 0,
            "deadTupleRatio": 0,
            "currentConnections": 1,
            "maxConnections": 100,
            "lastVacuumAt": None,
            "lastAnalyzeAt": None,
        },
        "workerHeartbeatAt": None,
        "technicalMetrics": [],
        "latestDataDate": None,
        "latestImport": None,
        "modernTrades": [],
        "pgStatStatementsAvailable": False,
        "slowQueries": [],
    }

    class RacingSession:
        def __init__(self) -> None:
            self.scalar_calls = 0
            self.rolled_back = False

        def scalar(self, _statement):
            self.scalar_calls += 1
            return None if self.scalar_calls == 1 else SimpleNamespace(id=99)

        def add(self, _snapshot) -> None:
            pass

        def flush(self) -> None:
            raise IntegrityError("INSERT", {}, Exception("duplicate snapshot date"))

        def rollback(self) -> None:
            self.rolled_back = True

    session = RacingSession()
    monkeypatch.setattr(
        "app.services.monitoring.collect_monitoring_metrics",
        lambda _session: metrics,
    )
    monkeypatch.setattr("app.services.monitoring.bangkok_now", lambda: captured_at)

    assert capture_monitoring_snapshot(
        session, trigger="page_open", upsert_today=False
    ) == metrics
    assert session.rolled_back is True
    assert session.scalar_calls == 2

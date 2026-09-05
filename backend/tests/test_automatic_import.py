from datetime import UTC, date, datetime, time
from decimal import Decimal
from itertools import count

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app import worker
from app.database import Base
from app.importers.twd import TwdExtract, TwdFormatError, TwdSummary
from app.models import AuditEvent, ImportBatch, ImportRun, ModernTrade, SourceFile
from app.services import automatic_import
from app.services.automatic_import import (
    ActiveRunError,
    SourceCandidate,
    create_run,
    decide_twd_extract,
    process_run,
    run_payload,
)


def _summary() -> TwdSummary:
    return TwdSummary(
        row_count=0,
        store_count=0,
        sku_count=0,
        negative_row_count=0,
        source_amount=Decimal("0"),
        amount=Decimal("0"),
        sales_qty=Decimal("0"),
        stock_on_hand=Decimal("0"),
        stock_on_order=Decimal("0"),
    )


def _extract(
    *,
    checksum: str = "a" * 64,
    data_date: date = date(2026, 8, 31),
    warnings: tuple[str, ...] = (),
) -> TwdExtract:
    summary = _summary()
    return TwdExtract(
        source_path=r"\\server\share\TWD\2026-08-31\file.xlsx",
        source_filename="file.xlsx",
        checksum_sha256=checksum,
        data_date=data_date,
        rows=(),
        summary=summary,
        reported_summary=summary,
        reconciliation_errors=warnings,
    )


def _batch(mt_id: int, *, checksum: str, data_date: date) -> ImportBatch:
    return ImportBatch(
        id=1,
        modern_trade_id=mt_id,
        status="imported",
        data_date=data_date,
        source_path="manual-upload:file.xls",
        source_filename="file.xls",
        checksum_sha256=checksum,
        row_count=0,
        store_count=0,
        sku_count=0,
        negative_row_count=0,
        source_amount=Decimal("0"),
        amount=Decimal("0"),
        sales_qty=Decimal("0"),
        stock_on_hand=Decimal("0"),
        reported_stock_on_hand=Decimal("0"),
        stock_on_order=Decimal("0"),
    )


@pytest.fixture
def engine():
    value = create_engine("sqlite://")
    Base.metadata.create_all(value)
    return value


def test_decision_skips_checksum_and_stops_period_conflict_or_warning(engine) -> None:
    with Session(engine) as session:
        mt = ModernTrade(id=1, code="TWD", name="Thai Watsadu")
        session.add(mt)
        session.add(
            _batch(
                mt.id,
                checksum="a" * 64,
                data_date=date(2026, 8, 30),
            )
        )
        session.commit()

        assert decide_twd_extract(session, mt, _extract(), mode="import").action == "skipped"
        period_conflict = decide_twd_extract(
            session,
            mt,
            _extract(checksum="b" * 64, data_date=date(2026, 8, 30)),
            mode="import",
        )
        assert period_conflict.action == "pending_review"
        assert "checksum ต่างกัน" in period_conflict.message
        warning = decide_twd_extract(
            session,
            mt,
            _extract(checksum="c" * 64, warnings=("Stock On Hand ไม่ตรง",)),
            mode="import",
        )
        assert warning.action == "pending_review"
        assert "Stock On Hand ไม่ตรง" in warning.message


def test_stock_value_source_errors_are_ready_for_import(engine) -> None:
    with Session(engine) as session:
        mt = ModernTrade(id=1, code="TWD", name="Thai Watsadu")
        session.add(mt)
        session.commit()

        warnings = (
            "Stock On Hand: calculated=78998.0, source=78473",
            (
                "Stock On Hand: พบเซลล์ต้นทาง #VALUE! จำนวน 35 เซลล์ "
                "ระบบไม่นำมารวมยอด"
            ),
        )
        scan = decide_twd_extract(
            session,
            mt,
            _extract(warnings=warnings),
            mode="scan",
        )
        automatic_import = decide_twd_extract(
            session,
            mt,
            _extract(warnings=warnings),
            mode="import",
        )

        assert scan.action == "ready"
        assert automatic_import.action == "import"


def test_first_run_is_scan_and_active_run_is_rejected(engine, monkeypatch) -> None:
    audit_ids = count(1)
    monkeypatch.setattr(
        automatic_import,
        "AuditEvent",
        lambda **values: AuditEvent(id=next(audit_ids), **values),
    )
    with Session(engine) as session:
        mt = ModernTrade(id=1, code="TWD", name="Thai Watsadu")
        session.add(mt)
        session.commit()

        first = create_run(session, mt, trigger="manual", actor="admin")
        assert first.mode == "scan"
        with pytest.raises(ActiveRunError):
            create_run(session, mt, trigger="manual", actor="admin")

        first.status = "success"
        session.commit()
        second = create_run(session, mt, trigger="manual", actor="admin")
        assert second.mode == "import"


def test_running_payload_reports_live_file_progress(engine) -> None:
    started_at = datetime(2026, 9, 3, 1, 21, tzinfo=UTC)
    with Session(engine) as session:
        mt = ModernTrade(id=1, code="TWD", name="Thai Watsadu")
        run = ImportRun(
            id=1,
            modern_trade_id=mt.id,
            trigger="manual",
            mode="scan",
            status="running",
            requested_by="admin",
            started_at=started_at,
            found_count=4,
        )
        session.add_all([mt, run])
        session.add_all(
            [
                SourceFile(
                    modern_trade_id=mt.id,
                    source_path=rf"\\server\share\TWD\2026-09-0{index}\{filename}",
                    source_filename=filename,
                    size_bytes=100,
                    modified_at=started_at,
                    status=status,
                    error_message=error,
                    last_seen_run_id=run.id,
                    last_seen_at=started_at.replace(minute=21 + index),
                )
                for index, (filename, status, error) in enumerate(
                    (
                        ("ready.xls", "ready", None),
                        ("empty.xls", "failed", "File size is 0 bytes"),
                        ("Thumbs.db", "unsupported", "รองรับเฉพาะ .xls และ .xlsx"),
                    ),
                    start=1,
                )
            ]
        )
        session.commit()

        payload = run_payload(run, mt, session=session)

        assert payload["counts"] == {
            "found": 4,
            "imported": 0,
            "ready": 1,
            "pending": 0,
            "failed": 1,
            "skipped": 1,
        }
        assert payload["progress"] == {
            "phase": "processing",
            "processed": 3,
            "total": 4,
            "percent": 75.0,
            "lastProcessedFile": "Thumbs.db",
            "lastProcessedPath": r"\\server\share\TWD\2026-09-03\Thumbs.db",
            "lastActivityAt": "2026-09-03T01:24:00",
            "counts": payload["counts"],
            "recentIssues": [
                {
                    "filename": "empty.xls",
                    "status": "failed",
                    "message": "File size is 0 bytes",
                }
            ],
        }


def test_initial_scan_registers_new_file_without_importing_fact(
    engine,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        automatic_import,
        "AuditEvent",
        lambda **values: AuditEvent(id=1, **values),
    )
    candidate = SourceCandidate(
        path=r"\\server\share\TWD\2026-08-31\file.xlsx",
        filename="file.xlsx",
        size_bytes=100,
        modified_at=datetime(2026, 8, 31, tzinfo=UTC),
    )
    monkeypatch.setattr(
        automatic_import,
        "_credentials",
        lambda session, mt: (r"\\server\share\TWD", r"WA\user", "secret"),
    )
    monkeypatch.setattr(
        automatic_import,
        "list_twd_source_files",
        lambda root, username, password: [candidate],
    )
    monkeypatch.setattr(
        automatic_import,
        "download_twd_extract",
        lambda candidate, username, password: _extract(),
    )
    monkeypatch.setattr(
        automatic_import,
        "send_telegram",
        lambda *args, **kwargs: type(
            "Delivery",
            (),
            {"status": "skipped", "message": "test"},
        )(),
    )
    monkeypatch.setattr(
        automatic_import.smbclient,
        "reset_connection_cache",
        lambda: None,
    )

    with Session(engine) as session:
        mt = ModernTrade(
            id=1,
            code="TWD",
            name="Thai Watsadu",
            source_subfolder="TWD",
            source_enabled=True,
        )
        run = ImportRun(
            id=1,
            modern_trade_id=mt.id,
            trigger="manual",
            mode="scan",
            status="running",
            requested_by="admin",
        )
        session.add_all([mt, run])
        session.commit()

        process_run(session, run.id)

        stored_run = session.get(ImportRun, run.id)
        source = session.scalar(select(SourceFile))
        assert stored_run is not None
        assert stored_run.status == "success"
        assert stored_run.ready_count == 1
        assert source is not None
        assert source.status == "ready"
        assert session.scalar(select(func.count(ImportBatch.id))) == 0


def test_initial_scan_continues_after_one_invalid_file(engine, monkeypatch) -> None:
    audit_ids = count(1)
    monkeypatch.setattr(
        automatic_import,
        "AuditEvent",
        lambda **values: AuditEvent(id=next(audit_ids), **values),
    )
    candidates = [
        SourceCandidate(
            path=rf"\\server\share\TWD\2026-08-3{index}\{name}",
            filename=name,
            size_bytes=size,
            modified_at=datetime(2026, 8, 31, tzinfo=UTC),
        )
        for index, (name, size) in enumerate(
            (("empty.xls", 0), ("valid.xlsx", 100))
        )
    ]
    monkeypatch.setattr(
        automatic_import,
        "_credentials",
        lambda session, mt: (r"\\server\share\TWD", r"WA\user", "secret"),
    )
    monkeypatch.setattr(
        automatic_import,
        "list_twd_source_files",
        lambda root, username, password: candidates,
    )

    def download(candidate, *, username, password):
        if candidate.filename == "empty.xls":
            raise TwdFormatError("เปิดไฟล์ empty.xls ไม่สำเร็จ: File size is 0 bytes")
        return _extract()

    monkeypatch.setattr(automatic_import, "download_twd_extract", download)
    monkeypatch.setattr(
        automatic_import,
        "send_telegram",
        lambda *args, **kwargs: type(
            "Delivery",
            (),
            {"status": "skipped", "message": "test"},
        )(),
    )
    monkeypatch.setattr(
        automatic_import.smbclient,
        "reset_connection_cache",
        lambda: None,
    )

    with Session(engine) as session:
        session.add(
            ModernTrade(
                id=1,
                code="TWD",
                name="Thai Watsadu",
                source_subfolder="TWD",
                source_enabled=True,
            )
        )
        session.add(
            ImportRun(
                id=1,
                modern_trade_id=1,
                trigger="manual",
                mode="scan",
                status="running",
                requested_by="admin",
            )
        )
        session.commit()

        process_run(session, 1)

        run = session.get(ImportRun, 1)
        sources = session.scalars(
            select(SourceFile).order_by(SourceFile.source_filename)
        ).all()
        assert run is not None
        assert run.status == "success_with_warnings"
        assert run.failed_count == 1
        assert run.ready_count == 1
        assert [(row.source_filename, row.status) for row in sources] == [
            ("empty.xls", "failed"),
            ("valid.xlsx", "ready"),
        ]


def test_schedule_fields_are_persisted_with_profile_settings(engine, monkeypatch) -> None:
    from app.api.fileshare_settings import (
        FileShareSettingsUpdate,
        SourceProfileUpdate,
        update_fileshare_settings,
    )

    monkeypatch.setattr(
        "app.api.fileshare_settings.setting_value",
        lambda session, key: None,
    )
    monkeypatch.setattr(
        "app.api.fileshare_settings.AuditEvent",
        lambda **values: AuditEvent(id=1, **values),
    )
    with Session(engine) as session:
        session.add(
            ModernTrade(
                id=1,
                code="TWD",
                name="Thai Watsadu",
                source_subfolder="TWD",
                source_enabled=True,
            )
        )
        session.commit()
        update_fileshare_settings(
            FileShareSettingsUpdate(
                base_unc=r"\\server\share",
                domain="WA",
                username="user",
                profiles=[
                    SourceProfileUpdate(
                        code="TWD",
                        subfolder="TWD",
                        enabled=True,
                        schedule_enabled=True,
                        schedule_time=time(7, 30),
                    )
                ],
            ),
            session,
            "admin",
        )
        mt = session.get(ModernTrade, 1)
        assert mt is not None
        assert mt.schedule_enabled is True
        assert mt.schedule_time == time(7, 30)


def test_schedule_requires_time() -> None:
    from app.api.fileshare_settings import SourceProfileUpdate

    with pytest.raises(ValueError, match="กรุณาระบุเวลา"):
        SourceProfileUpdate(
            code="TWD",
            subfolder="TWD",
            enabled=True,
            schedule_enabled=True,
        )


def test_worker_marks_interrupted_run_failed(engine, monkeypatch) -> None:
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    with Session(engine) as session:
        session.add(ModernTrade(id=1, code="TWD", name="Thai Watsadu"))
        session.add(
            ImportRun(
                id=1,
                modern_trade_id=1,
                trigger="manual",
                mode="import",
                status="running",
                requested_by="admin",
            )
        )
        session.commit()

    assert worker.recover_interrupted_runs() == 1

    with Session(engine) as session:
        run = session.get(ImportRun, 1)
        assert run is not None
        assert run.status == "failed"
        assert run.finished_at is not None
        assert "Worker ถูก Restart" in (run.error_message or "")


def test_scheduled_notification_excludes_unchanged_historical_issues(
    engine,
    monkeypatch,
) -> None:
    audit_ids = count(1)
    modified_at = datetime(2026, 9, 5, 1, 0)
    candidates = [
        SourceCandidate(
            path=rf"\\server\share\TWD\2026-09-0{index}\{filename}",
            filename=filename,
            size_bytes=size,
            modified_at=modified_at,
        )
        for index, (filename, size) in enumerate(
            (("old-empty.xls", 0), ("old-warning.xls", 100)),
            start=1,
        )
    ]
    deliveries: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(
        automatic_import,
        "AuditEvent",
        lambda **values: AuditEvent(id=next(audit_ids), **values),
    )
    monkeypatch.setattr(
        automatic_import,
        "_credentials",
        lambda session, mt: (r"\\server\share\TWD", r"WA\user", "secret"),
    )
    monkeypatch.setattr(
        automatic_import,
        "list_twd_source_files",
        lambda root, username, password: candidates,
    )
    monkeypatch.setattr(
        automatic_import,
        "download_twd_extract",
        lambda *args, **kwargs: pytest.fail("unchanged historical file was read again"),
    )

    def capture_delivery(session, title, details, **kwargs):
        deliveries.append((title, list(details)))
        return type("Delivery", (), {"status": "sent", "message": "test"})()

    monkeypatch.setattr(automatic_import, "send_telegram", capture_delivery)
    monkeypatch.setattr(
        automatic_import.smbclient,
        "reset_connection_cache",
        lambda: None,
    )

    with Session(engine) as session:
        mt = ModernTrade(
            id=1,
            code="TWD",
            name="Thai Watsadu",
            source_subfolder="TWD",
            source_enabled=True,
        )
        run = ImportRun(
            id=1,
            modern_trade_id=1,
            trigger="scheduled",
            mode="import",
            status="running",
            requested_by="system-scheduler",
        )
        session.add_all([mt, run])
        session.add_all(
            [
                SourceFile(
                    modern_trade_id=1,
                    source_path=candidates[0].path,
                    source_filename=candidates[0].filename,
                    size_bytes=candidates[0].size_bytes,
                    modified_at=modified_at,
                    checksum_sha256=None,
                    status="failed",
                    error_message="ข้ามไฟล์: File size is 0 bytes",
                ),
                SourceFile(
                    modern_trade_id=1,
                    source_path=candidates[1].path,
                    source_filename=candidates[1].filename,
                    size_bytes=candidates[1].size_bytes,
                    modified_at=modified_at,
                    checksum_sha256="b" * 64,
                    status="pending_review",
                    error_message="ไฟล์มีคำเตือนเดิม",
                ),
            ]
        )
        session.commit()

        process_run(session, run.id)

        stored = session.get(ImportRun, run.id)
        assert stored is not None
        assert stored.status == "success_with_warnings"
        assert stored.failed_count == 1
        assert stored.pending_count == 1

    assert len(deliveries) == 1
    title, details = deliveries[0]
    assert title == "✅ Automatic Import TWD สำเร็จ"
    assert any("ไม่พบไฟล์ใหม่หรือการเปลี่ยนแปลง" in detail for detail in details)
    assert all("ล้มเหลว 1" not in detail for detail in details)
    assert all("รอตรวจสอบ 1" not in detail for detail in details)

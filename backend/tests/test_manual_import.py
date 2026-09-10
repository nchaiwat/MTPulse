import asyncio
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app.api import imports, system_settings
from app.api.imports import _preview
from app.database import Base
from app.importers.hp_mh import HpMhMtExtract, HpMhPairExtract, HpMhSummary
from app.importers.twd import TwdExtract, TwdSummary
from app.models import ImportBatch, ModernTrade, SourceFile
from app.services import telegram, twd_import
from app.services.twd_import import (
    DuplicateImportError,
    PeriodDuplicateError,
    _build_batch,
    import_twd_extract,
)


def extract(checksum: str, data_date: date = date(2026, 8, 18)) -> TwdExtract:
    summary = TwdSummary(
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
    return TwdExtract(
        source_path="manual-upload:test.xls",
        source_filename="test.xls",
        checksum_sha256=checksum,
        data_date=data_date,
        rows=(),
        summary=summary,
        reported_summary=summary,
        reconciliation_errors=(),
    )


def hp_mh_pair(fingerprint: str = "b" * 64) -> HpMhPairExtract:
    summary = HpMhSummary(
        row_count=0,
        store_count=0,
        sku_count=0,
        negative_row_count=0,
        source_amount=Decimal("0"),
        amount=Decimal("0"),
        sales_qty=Decimal("0"),
        stock_on_hand=Decimal("0"),
        stock_value=Decimal("0"),
    )
    extracts = {
        code: HpMhMtExtract(
            code=code,
            data_date=date(2026, 9, 9),
            rows=(),
            summary=summary,
            sale_skus=frozenset(),
            inventory_skus=frozenset(),
            inventory_branches=frozenset(),
        )
        for code in ("HP", "MH")
    }
    return HpMhPairExtract(
        data_date=date(2026, 9, 9),
        inventory_path="manual-upload:Inventory.zip",
        sales_path="manual-upload:Sales.zip",
        inventory_filename="Inventory.zip",
        sales_filename="Sales.zip",
        inventory_checksum="c" * 64,
        sales_checksum="d" * 64,
        business_fingerprint=fingerprint,
        hp=extracts["HP"],
        mh=extracts["MH"],
        ignored_branch_codes=(),
        reconciliation_errors=(),
    )


def test_preview_is_read_only_and_reports_twd() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        before = session.scalar(select(func.count()).select_from(ImportBatch))
        result = _preview(extract("a" * 64), None)
        after = session.scalar(select(func.count()).select_from(ImportBatch))
    assert (before, after) == (0, 0)
    assert result["detectedMt"] == "TWD"
    assert result["canImport"] is True


def test_hp_mh_preview_accepts_two_files_and_reports_both_mts(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    pair = hp_mh_pair()

    async def read_pair(*_args):
        return "Inventory.zip", b"inventory", "Sales.zip", b"sales"

    monkeypatch.setattr(imports, "_read_hp_mh_files", read_pair)
    monkeypatch.setattr(imports, "_extract_hp_mh_uploads", lambda *_args: pair)
    monkeypatch.setattr(imports, "_record_hp_mh_pair", lambda *_args, **_kwargs: None)

    with Session(engine) as session:
        result = asyncio.run(
            imports.preview_hp_mh_import(
                session=session,
                inventory_file=UploadFile(
                    filename="Inventory.zip",
                    file=BytesIO(b"inventory"),
                ),
                sales_file=UploadFile(
                    filename="Sales.zip",
                    file=BytesIO(b"sales"),
                ),
            )
        )
        batch_count = session.scalar(select(func.count()).select_from(ImportBatch))

    assert batch_count == 0
    assert result["detectedSourceGroup"] == "HP_MH"
    assert result["detectedMtCodes"] == ["HP", "MH"]
    assert result["canImport"] is True


def test_hp_mh_confirm_rejects_files_changed_after_preview(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    async def read_pair(*_args):
        return "Inventory.zip", b"inventory", "Sales.zip", b"sales"

    imported = False

    def unexpected_import(*_args, **_kwargs):
        nonlocal imported
        imported = True

    monkeypatch.setattr(imports, "_read_hp_mh_files", read_pair)
    monkeypatch.setattr(
        imports,
        "_extract_hp_mh_uploads",
        lambda *_args: hp_mh_pair("e" * 64),
    )
    monkeypatch.setattr(imports, "import_hp_mh_pair", unexpected_import)

    with Session(engine) as session, pytest.raises(HTTPException) as error:
        asyncio.run(
            imports.confirm_hp_mh_import(
                session=session,
                inventory_file=UploadFile(
                    filename="Inventory.zip",
                    file=BytesIO(b"inventory"),
                ),
                sales_file=UploadFile(
                    filename="Sales.zip",
                    file=BytesIO(b"sales"),
                ),
                expected_fingerprint="f" * 64,
            )
        )

    assert error.value.status_code == 409
    assert "เปลี่ยนจากรอบ Preview" in str(error.value.detail)
    assert imported is False


def test_import_rejects_checksum_and_period_duplicates() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ModernTrade(id=1, code="TWD", name="Thai Watsadu"))
        existing = _build_batch(1, extract("a" * 64))
        existing.id = 1
        existing.status = "imported"
        session.add(existing)
        session.commit()
        with pytest.raises(DuplicateImportError):
            import_twd_extract(session, extract("a" * 64))
        session.rollback()
        with pytest.raises(PeriodDuplicateError):
            import_twd_extract(session, extract("b" * 64))


def test_import_refreshes_daily_sku_summary_in_the_same_flow(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    twd_extract = extract("c" * 64, date(2026, 8, 19))
    original_build_batch = twd_import._build_batch
    refreshed: list[tuple[int, date]] = []

    def build_batch_with_sqlite_id(modern_trade_id: int, payload: TwdExtract):
        batch = original_build_batch(modern_trade_id, payload)
        batch.id = 1
        return batch

    monkeypatch.setattr(twd_import, "_build_batch", build_batch_with_sqlite_id)
    monkeypatch.setattr(
        twd_import,
        "refresh_daily_sku_summary",
        lambda _session, modern_trade_id, data_date: refreshed.append(
            (modern_trade_id, data_date)
        ),
    )
    with Session(engine) as session:
        session.add(ModernTrade(id=1, code="TWD", name="Thai Watsadu"))
        session.commit()

        import_twd_extract(session, twd_extract)

    assert refreshed == [(1, date(2026, 8, 19))]


def test_telegram_message_uses_standard_header_and_no_bullets() -> None:
    message = telegram.format_telegram_message(
        "📣 ทดสอบการส่งข้อความเข้า Telegram",
        [
            "👥 กลุ่มเป้าหมาย: MT Pulse Notification Group",
            "✅ สถานะ: สำเร็จ",
        ],
        occurred_at=datetime(
            2026,
            8,
            25,
            8,
            37,
            tzinfo=ZoneInfo("Asia/Bangkok"),
        ),
    )
    assert message.splitlines() == [
        "📦 MT Pulse · 25/08/2026 08:37 น.",
        "────────────",
        "📣 ทดสอบการส่งข้อความเข้า Telegram",
        "👥 กลุ่มเป้าหมาย: MT Pulse Notification Group",
        "✅ สถานะ: สำเร็จ",
    ]
    assert "•" not in message


def test_telegram_token_is_encrypted_and_revealed_only_when_enabled(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(
        telegram,
        "get_settings",
        lambda: SimpleNamespace(settings_encryption_key=key),
    )
    monkeypatch.setattr(
        system_settings,
        "get_settings",
        lambda: SimpleNamespace(allow_secret_reveal=True),
    )
    with Session(engine) as session:
        telegram.set_bot_token(session, "123456:SECRET", "test")
        telegram.set_setting(session, telegram.GROUP_KEY, "-100123", secret=False, actor="test")
        session.commit()
        config = telegram.telegram_config(session)
        stored = telegram.setting_value(session, telegram.TOKEN_KEY)
        assert telegram.bot_token(session) == "123456:SECRET"
        assert system_settings.get_telegram_token(session) == {"botToken": "123456:SECRET"}
    assert "SECRET" not in (stored or "")
    assert config == {
        "telegramConfigured": True,
        "botTokenMasked": "••••••••",
        "groupId": "-100123",
        "notifyManualImport": True,
    }


def test_telegram_token_reveal_is_disabled_by_default(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(
        system_settings,
        "get_settings",
        lambda: SimpleNamespace(allow_secret_reveal=False),
    )
    with Session(engine) as session, pytest.raises(HTTPException) as error:
        system_settings.get_telegram_token(session)
    assert error.value.status_code == 403


def test_telegram_without_config_is_skipped() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = telegram.send_telegram(session, "test")
    assert result.status == "skipped"

def test_telegram_invalid_token_reports_specific_reason(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    class UnauthorizedResponse:
        status_code = 401

        @staticmethod
        def json() -> dict:
            return {
                "ok": False,
                "error_code": 401,
                "description": "Unauthorized",
            }

    monkeypatch.setattr(telegram, "bot_token", lambda _session: "invalid-token")
    monkeypatch.setattr(telegram.httpx, "post", lambda *args, **kwargs: UnauthorizedResponse())

    with Session(engine) as session:
        telegram.set_setting(
            session,
            telegram.GROUP_KEY,
            "-100123",
            secret=False,
            actor="test",
        )
        session.commit()
        result = telegram.send_telegram(session, "test", force=True)

    assert result.status == "failed"
    assert result.message == "Telegram ปฏิเสธ Bot Token กรุณาตรวจสอบ Token ที่บันทึกไว้"


def source_file(
    *,
    source_id: int,
    modern_trade_id: int,
    status: str,
    data_date: date,
    filename: str,
    checksum: str,
) -> SourceFile:
    timestamp = datetime(2026, 9, 3, 8, 0, tzinfo=ZoneInfo("Asia/Bangkok"))
    return SourceFile(
        id=source_id,
        modern_trade_id=modern_trade_id,
        source_path=rf"\\nas\share\TWD\{filename}",
        source_filename=filename,
        size_bytes=5_652_416,
        modified_at=timestamp,
        checksum_sha256=checksum,
        detected_data_date=data_date,
        status=status,
        discovered_at=timestamp,
        last_seen_at=timestamp,
    )


def test_fileshare_ready_lists_only_twd_ready_without_unc_path() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                ModernTrade(id=1, code="TWD", name="Thai Watsadu"),
                ModernTrade(id=2, code="OTHER", name="Other"),
                source_file(
                    source_id=1,
                    modern_trade_id=1,
                    status="ready",
                    data_date=date(2026, 8, 30),
                    filename="older.xls",
                    checksum="a" * 64,
                ),
                source_file(
                    source_id=2,
                    modern_trade_id=1,
                    status="ready",
                    data_date=date(2026, 8, 31),
                    filename="latest.xls",
                    checksum="b" * 64,
                ),
                source_file(
                    source_id=3,
                    modern_trade_id=1,
                    status="pending_review",
                    data_date=date(2026, 9, 1),
                    filename="pending.xls",
                    checksum="c" * 64,
                ),
                source_file(
                    source_id=4,
                    modern_trade_id=2,
                    status="ready",
                    data_date=date(2026, 9, 2),
                    filename="other.xls",
                    checksum="d" * 64,
                ),
            ]
        )
        session.commit()
        result = imports.fileshare_ready_imports(session=session, limit=100)

    assert [item["filename"] for item in result["items"]] == [
        "latest.xls",
        "older.xls",
    ]
    assert result["count"] == 2
    assert "sourcePath" not in str(result)
    assert "\\nas" not in str(result)


def test_fileshare_preview_is_read_only_and_includes_timings(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    checksum = "e" * 64
    with Session(engine) as session:
        session.add(ModernTrade(id=1, code="TWD", name="Thai Watsadu"))
        session.add(
            source_file(
                source_id=1,
                modern_trade_id=1,
                status="ready",
                data_date=date(2026, 8, 31),
                filename="ready.xls",
                checksum=checksum,
            )
        )
        session.commit()
        monkeypatch.setattr(
            imports,
            "_extract_fileshare_source",
            lambda _session, _source: (
                extract(checksum, date(2026, 8, 31)),
                {"downloadMs": 1200, "parseMs": 400},
            ),
        )
        recorded: dict = {}
        monkeypatch.setattr(
            imports,
            "_record",
            lambda *_args, **kwargs: recorded.update(kwargs),
        )

        result = imports.preview_fileshare_import(source_file_id=1, session=session)
        batch_count = session.scalar(select(func.count()).select_from(ImportBatch))

    assert batch_count == 0
    assert result["sourceMode"] == "fileshare"
    assert result["sourceFileId"] == 1
    assert recorded["actor"] == "fileshare-import"
    assert result["timings"] == {
        "downloadMs": 1200,
        "parseMs": 400,
        "duplicateCheckMs": pytest.approx(0, abs=50),
    }


def test_fileshare_preview_rejects_changed_checksum(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ModernTrade(id=1, code="TWD", name="Thai Watsadu"))
        session.add(
            source_file(
                source_id=1,
                modern_trade_id=1,
                status="ready",
                data_date=date(2026, 8, 31),
                filename="changed.xls",
                checksum="a" * 64,
            )
        )
        session.commit()
        monkeypatch.setattr(
            imports,
            "_extract_fileshare_source",
            lambda _session, _source: (
                extract("b" * 64, date(2026, 8, 31)),
                {"downloadMs": 1, "parseMs": 1},
            ),
        )

        with pytest.raises(HTTPException) as error:
            imports.preview_fileshare_import(source_file_id=1, session=session)

    assert error.value.status_code == 409
    assert "ไฟล์มีการเปลี่ยนแปลง" in str(error.value.detail)


def test_fileshare_preview_does_not_expose_unc_on_read_error(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ModernTrade(id=1, code="TWD", name="Thai Watsadu"))
        session.add(
            source_file(
                source_id=1,
                modern_trade_id=1,
                status="ready",
                data_date=date(2026, 8, 31),
                filename="unavailable.xls",
                checksum="a" * 64,
            )
        )
        session.commit()

        def unavailable(*_args):
            raise OSError(r"cannot open \\secret-nas\private\unavailable.xls")

        monkeypatch.setattr(imports, "_extract_fileshare_source", unavailable)
        monkeypatch.setattr(imports, "_record", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(
            imports,
            "send_telegram",
            lambda *_args, **_kwargs: SimpleNamespace(status="skipped", message="skip"),
        )
        with pytest.raises(HTTPException) as error:
            imports.preview_fileshare_import(source_file_id=1, session=session)

    assert error.value.status_code == 409
    assert "secret-nas" not in str(error.value.detail)
    assert "FileShare" in str(error.value.detail)


def test_fileshare_confirm_updates_source_only_after_success(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    checksum = "f" * 64
    with Session(engine) as session:
        session.add(ModernTrade(id=1, code="TWD", name="Thai Watsadu"))
        session.add(
            source_file(
                source_id=1,
                modern_trade_id=1,
                status="ready",
                data_date=date(2026, 8, 31),
                filename="ready.xls",
                checksum=checksum,
            )
        )
        session.commit()
        monkeypatch.setattr(
            imports,
            "_extract_fileshare_source",
            lambda _session, _source: (
                extract(checksum, date(2026, 8, 31)),
                {"downloadMs": 1000, "parseMs": 300},
            ),
        )
        batch = SimpleNamespace(
            id=99,
            status="imported",
            checksum_sha256=checksum,
            data_date=date(2026, 8, 31),
            source_filename="ready.xls",
        )
        monkeypatch.setattr(imports, "import_twd_extract", lambda *_args: batch)
        monkeypatch.setattr(
            imports,
            "_completed_import_response",
            lambda _session, imported_batch, **_kwargs: {
                "batchId": imported_batch.id,
                "status": imported_batch.status,
            },
        )

        result = imports.confirm_fileshare_import(
            source_file_id=1,
            expected_checksum=checksum,
            session=session,
        )
        stored = session.get(SourceFile, 1)

    assert result == {"batchId": 99, "status": "imported"}
    assert stored is not None
    assert stored.status == "imported"
    assert stored.imported_batch_id == 99


def test_fileshare_confirm_does_not_import_when_preview_checksum_changed(
    monkeypatch,
) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ModernTrade(id=1, code="TWD", name="Thai Watsadu"))
        session.add(
            source_file(
                source_id=1,
                modern_trade_id=1,
                status="ready",
                data_date=date(2026, 8, 31),
                filename="changed.xls",
                checksum="a" * 64,
            )
        )
        session.commit()
        monkeypatch.setattr(
            imports,
            "_extract_fileshare_source",
            lambda _session, _source: (
                extract("b" * 64, date(2026, 8, 31)),
                {"downloadMs": 1, "parseMs": 1},
            ),
        )
        imported = False

        def unexpected_import(*_args):
            nonlocal imported
            imported = True

        monkeypatch.setattr(imports, "import_twd_extract", unexpected_import)
        monkeypatch.setattr(imports, "_record", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(
            imports,
            "send_telegram",
            lambda *_args, **_kwargs: SimpleNamespace(status="skipped", message="skip"),
        )
        with pytest.raises(HTTPException) as error:
            imports.confirm_fileshare_import(
                source_file_id=1,
                expected_checksum="a" * 64,
                session=session,
            )
        stored = session.get(SourceFile, 1)

    assert error.value.status_code == 409
    assert imported is False
    assert stored is not None
    assert stored.status == "ready"

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.api.imports import _preview
from app.database import Base
from app.importers.twd import TwdExtract, TwdSummary
from app.models import ImportBatch, ModernTrade
from app.services import telegram
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


def test_telegram_token_is_encrypted_and_never_returned(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(
        telegram,
        "get_settings",
        lambda: SimpleNamespace(settings_encryption_key=key),
    )
    with Session(engine) as session:
        telegram.set_bot_token(session, "123456:SECRET", "test")
        telegram.set_setting(session, telegram.GROUP_KEY, "-100123", secret=False, actor="test")
        session.commit()
        config = telegram.telegram_config(session)
        stored = telegram.setting_value(session, telegram.TOKEN_KEY)
        assert telegram.bot_token(session) == "123456:SECRET"
    assert "SECRET" not in (stored or "")
    assert config == {
        "telegramConfigured": True,
        "botTokenMasked": "••••••••",
        "groupId": "-100123",
        "notifyManualImport": True,
    }


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
    assert result.message == "Bot Token ไม่ถูกต้องหรือถูกยกเลิก"
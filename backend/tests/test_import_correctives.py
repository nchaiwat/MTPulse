from dataclasses import replace
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.importers.twd import TwdExtract, TwdSummary
from app.models import ModernTrade
from app.services.twd_import import _build_batch, replace_twd_batch


def _extract(checksum: str, filename: str = "source.xls") -> TwdExtract:
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
        source_path=f"manual-upload:{filename}",
        source_filename=filename,
        checksum_sha256=checksum,
        data_date=date(2026, 8, 2),
        rows=(),
        summary=summary,
        reported_summary=summary,
        reconciliation_errors=(),
    )


def test_replace_batch_updates_in_place_and_rollback_restores_original() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ModernTrade(id=1, code="TWD", name="Thai Watsadu"))
        original = _build_batch(1, _extract("a" * 64))
        original.id = 1
        original.status = "imported_with_warnings"
        original.reconciliation_errors = "Stock On Hand: calculated=10, source=9"
        original.warning_resolution = "acknowledged"
        original.warning_resolution_note = "ตรวจแล้ว"
        session.add(original)
        session.commit()

        corrected = replace(_extract("b" * 64), source_filename="corrected.xls")
        replace_twd_batch(session, original, corrected)
        assert original.id == 1
        assert original.checksum_sha256 == "b" * 64
        assert original.source_filename == "corrected.xls"
        assert original.warning_resolution is None

        session.rollback()
        session.refresh(original)
        assert original.checksum_sha256 == "a" * 64
        assert original.source_filename == "source.xls"

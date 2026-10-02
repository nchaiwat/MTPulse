import asyncio
from datetime import date
from decimal import Decimal
from io import BytesIO
from itertools import count

import pytest
from fastapi import HTTPException
from sqlalchemy import BigInteger, create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.datastructures import UploadFile

from app.api import import_correctives, imports
from app.database import Base
from app.importers.dh import (
    DhBranchAmount,
    DhFactRow,
    DhPairExtract,
    DhSummary,
)
from app.models import (
    BranchMapping,
    DailySkuSummary,
    DhEffectivePrice,
    ImportBatch,
    InventoryCoverage,
    ModernTrade,
    MonthlySalesSummary,
    SalesInventoryFact,
)
from app.services import dh_import
from app.services.dh_import import DhImportError, import_dh_pair


def _pair() -> DhPairExtract:
    sales_rows = (
        DhFactRow(
            branch_code="B1",
            branch_name="Branch 1",
            sku="00123",
            description="Item A",
            sales_qty=Decimal("2"),
        ),
    )
    stock_rows = (
        DhFactRow(
            branch_code="B1",
            branch_name="Branch 1",
            sku="00123",
            description="Item A",
            stock_on_hand=Decimal("10"),
        ),
        DhFactRow(
            branch_code="B1",
            branch_name="Branch 1",
            sku="STOCK-ONLY",
            description="Stock only",
            stock_on_hand=Decimal("5"),
        ),
    )
    return DhPairExtract(
        batch_date=date(2025, 1, 7),
        sales_date=date(2025, 1, 6),
        stock_date=date(2025, 1, 7),
        inventory_path="manual-upload:stock.xlsx",
        sales_path="manual-upload:sales.xlsx",
        inventory_filename="stock.xlsx",
        sales_filename="sales.xlsx",
        inventory_checksum="a" * 64,
        sales_checksum="b" * 64,
        business_fingerprint="c" * 64,
        sales_rows=sales_rows,
        stock_rows=stock_rows,
        branch_amounts=(
            DhBranchAmount("B1", "Branch 1", Decimal("250")),
        ),
        sales_summary=DhSummary(
            row_count=1,
            store_count=1,
            sku_count=1,
            negative_row_count=0,
            source_amount=Decimal("250"),
            amount=Decimal("250"),
            sales_qty=Decimal("2"),
            stock_on_hand=Decimal("0"),
        ),
        stock_summary=DhSummary(
            row_count=2,
            store_count=1,
            sku_count=2,
            negative_row_count=0,
            source_amount=Decimal("0"),
            amount=Decimal("0"),
            sales_qty=Decimal("0"),
            stock_on_hand=Decimal("15"),
        ),
        source_skus=frozenset({"00123", "STOCK-ONLY"}),
        source_branches=(("B1", "Branch 1"),),
        reconciliation_errors=(),
    )


@pytest.fixture
def database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    generated_ids = count(1)

    @event.listens_for(Session, "before_flush")
    def assign_sqlite_bigint_ids(
        session: Session,
        _flush_context: object,
        _instances: object,
    ) -> None:
        if session.bind is not engine:
            return
        for row in session.new:
            primary_key = row.__mapper__.primary_key
            if (
                len(primary_key) == 1
                and isinstance(primary_key[0].type, BigInteger)
                and getattr(row, primary_key[0].key) is None
            ):
                setattr(row, primary_key[0].key, next(generated_ids))

    with Session(engine) as session:
        session.add(
            ModernTrade(
                id=1,
                code="DH",
                name="DoHome",
                vat_mode="exclude",
                source_group_code="DH",
            )
        )
        session.add(
            BranchMapping(
                id=10,
                modern_trade_id=1,
                source_branch_code="B1",
                source_branch_description="Branch 1",
                wa_branch_code="WA-B1",
                wa_branch_description="Branch 1",
                status="confirmed",
                effective_from=date(2025, 1, 1),
                effective_to=None,
                changed_by="test",
            )
        )
        session.commit()
    try:
        yield engine
    finally:
        event.remove(Session, "before_flush", assign_sqlite_bigint_ids)
        engine.dispose()


def _add_price(session: Session, value: Decimal = Decimal("120")) -> None:
    session.add(
        DhEffectivePrice(
            modern_trade_id=1,
            source_sku="00123",
            unit_price_ex_vat=value,
            effective_from=date(2025, 1, 1),
            effective_to=None,
            source_filename="prices.xlsx",
            source_checksum_sha256="d" * 64,
            changed_by="operator",
        )
    )
    session.commit()


def test_import_dh_pair_writes_priced_facts_summaries_coverage_and_warning(
    database,
) -> None:
    with Session(database) as session:
        _add_price(session)

        batch = import_dh_pair(session, _pair(), actor="data-operator")
        session.commit()

        facts = session.scalars(
            select(SalesInventoryFact).order_by(SalesInventoryFact.source_sku)
        ).all()
        coverage = session.scalar(select(InventoryCoverage))
        daily = session.scalar(
            select(DailySkuSummary).where(DailySkuSummary.source_sku == "00123")
        )
        monthly = session.scalar(
            select(MonthlySalesSummary).where(
                MonthlySalesSummary.source_sku == "00123"
            )
        )

        assert batch.data_date == date(2025, 1, 7)
        assert batch.status == "imported_with_warnings"
        assert batch.source_amount == Decimal("250")
        assert batch.amount == Decimal("240")
        assert batch.sales_qty == Decimal("2")
        assert batch.stock_on_hand == Decimal("15")
        assert batch.business_fingerprint != _pair().business_fingerprint
        assert "Qty × ราคา" in (batch.reconciliation_errors or "")
        assert [
            (
                row.source_sku,
                row.amount,
                row.sales_qty,
                row.stock_on_hand,
            )
            for row in facts
        ] == [
            ("00123", Decimal("240"), Decimal("2"), Decimal("10")),
            ("STOCK-ONLY", Decimal("0"), Decimal("0"), Decimal("5")),
        ]
        assert coverage is not None
        assert coverage.source_row_count == 2
        assert daily is not None and daily.amount == Decimal("240")
        assert monthly is not None and monthly.amount == Decimal("240")


def test_import_dh_pair_blocks_missing_price_before_writing(database) -> None:
    with Session(database) as session:
        with pytest.raises(DhImportError, match="00123"):
            import_dh_pair(session, _pair(), actor="data-operator")
        session.rollback()

        assert session.scalars(select(ImportBatch)).all() == []
        assert session.scalars(select(SalesInventoryFact)).all() == []


def test_import_uses_the_same_transaction_lock_as_price_confirm(
    database,
    monkeypatch,
) -> None:
    calls = []
    monkeypatch.setattr(
        dh_import,
        "lock_dh_price_changes",
        lambda session: calls.append(session),
    )
    with Session(database) as session:
        _add_price(session)
        import_dh_pair(session, _pair(), actor="data-operator")

    assert len(calls) == 1


def test_selected_price_changes_fingerprint_and_explicit_reimport_replaces_batch(
    database,
) -> None:
    with Session(database) as session:
        _add_price(session)
        first = import_dh_pair(session, _pair(), actor="manual-upload")
        session.commit()
        first_id = first.id
        first_fingerprint = first.business_fingerprint

        price = session.scalar(select(DhEffectivePrice))
        assert price is not None
        price.unit_price_ex_vat = Decimal("121")
        session.commit()

        replaced = import_dh_pair(session, _pair(), actor="manual-corrective")
        session.commit()

        assert replaced.id == first_id
        assert replaced.amount == Decimal("242")
        assert replaced.business_fingerprint != first_fingerprint
        assert session.scalar(select(ImportBatch).where(ImportBatch.id == first_id)) is replaced
        with pytest.raises(DhImportError, match="ถูกนำเข้าแล้ว"):
            import_dh_pair(session, _pair(), actor="manual-upload")


def test_manual_preview_and_confirm_use_priced_fingerprint(
    database,
    monkeypatch,
) -> None:
    async def read_pair(*_args):
        return "stock.xlsx", b"stock", "sales.xlsx", b"sales"

    monkeypatch.setattr(imports, "_read_hp_mh_files", read_pair)
    monkeypatch.setattr(imports, "_extract_dh_uploads", lambda *_args: _pair())
    monkeypatch.setattr(imports, "_record", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        imports,
        "capture_monitoring_snapshot",
        lambda *_args, **_kwargs: None,
    )
    with Session(database) as session:
        _add_price(session)
        preview = asyncio.run(
            imports.preview_dh_import(
                session=session,
                stock_file=UploadFile(
                    filename="stock.xlsx",
                    file=BytesIO(b"stock"),
                ),
                sales_file=UploadFile(
                    filename="sales.xlsx",
                    file=BytesIO(b"sales"),
                ),
            )
        )
        result = asyncio.run(
            imports.confirm_dh_import(
                session=session,
                stock_file=UploadFile(
                    filename="stock.xlsx",
                    file=BytesIO(b"stock"),
                ),
                sales_file=UploadFile(
                    filename="sales.xlsx",
                    file=BytesIO(b"sales"),
                ),
                expected_fingerprint=preview["businessFingerprint"],
            )
        )

        assert preview["detectedMtCode"] == "DH"
        assert preview["summary"]["amount"] == 240.0
        assert preview["warnings"]
        assert result["status"] == "imported_with_warnings"


def test_manual_confirm_rejects_price_changed_after_preview(
    database,
    monkeypatch,
) -> None:
    async def read_pair(*_args):
        return "stock.xlsx", b"stock", "sales.xlsx", b"sales"

    monkeypatch.setattr(imports, "_read_hp_mh_files", read_pair)
    monkeypatch.setattr(imports, "_extract_dh_uploads", lambda *_args: _pair())
    monkeypatch.setattr(imports, "_record", lambda *_args, **_kwargs: None)
    with Session(database) as session:
        _add_price(session)
        priced = imports.price_dh_import_preview(session, _pair())
        price = session.scalar(select(DhEffectivePrice))
        assert price is not None
        price.unit_price_ex_vat = Decimal("121")
        session.commit()

        with pytest.raises(HTTPException) as error:
            asyncio.run(
                imports.confirm_dh_import(
                    session=session,
                    stock_file=UploadFile(
                        filename="stock.xlsx",
                        file=BytesIO(b"stock"),
                    ),
                    sales_file=UploadFile(
                        filename="sales.xlsx",
                        file=BytesIO(b"sales"),
                    ),
                    expected_fingerprint=priced.business_fingerprint,
                )
            )

        assert error.value.status_code == 409
        assert "เปลี่ยนจากรอบ Preview" in str(error.value.detail)
        assert session.scalars(select(ImportBatch)).all() == []


def test_explicit_corrective_reprices_existing_dh_batch(
    database,
    monkeypatch,
) -> None:
    async def read_pair(*_args):
        return "stock.xlsx", b"stock", "sales.xlsx", b"sales"

    monkeypatch.setattr(import_correctives, "_read_hp_mh_files", read_pair)
    monkeypatch.setattr(
        import_correctives,
        "_extract_dh_uploads",
        lambda *_args: _pair(),
    )
    with Session(database) as session:
        _add_price(session)
        batch = import_dh_pair(session, _pair(), actor="manual-upload")
        session.commit()
        batch_id = batch.id
        price = session.scalar(select(DhEffectivePrice))
        assert price is not None
        price.unit_price_ex_vat = Decimal("121")
        session.commit()

        preview = asyncio.run(
            import_correctives.preview_dh_batch_replacement(
                batch_id=batch_id,
                session=session,
                stock_file=UploadFile(
                    filename="stock.xlsx",
                    file=BytesIO(b"stock"),
                ),
                sales_file=UploadFile(
                    filename="sales.xlsx",
                    file=BytesIO(b"sales"),
                ),
            )
        )
        result = asyncio.run(
            import_correctives.confirm_dh_batch_replacement(
                batch_id=batch_id,
                session=session,
                stock_file=UploadFile(
                    filename="stock.xlsx",
                    file=BytesIO(b"stock"),
                ),
                sales_file=UploadFile(
                    filename="sales.xlsx",
                    file=BytesIO(b"sales"),
                ),
                expected_fingerprint=preview["businessFingerprint"],
            )
        )

        assert preview["canReplace"] is True
        assert preview["replacement"]["amount"] == 242.0
        assert result["batchId"] == batch_id
        assert result["summary"]["amount"] == 242.0

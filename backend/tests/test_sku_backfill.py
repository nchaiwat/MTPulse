from datetime import UTC, date, datetime
from decimal import Decimal
from itertools import count

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.api import automatic_imports
from app.database import Base
from app.importers.twd import TwdExtract, TwdRow, summarize
from app.models import (
    AuditEvent,
    BranchMapping,
    DailySkuSummary,
    ImportBatch,
    ImportRun,
    ItemMapping,
    ModernTrade,
    MonthlySalesSummary,
    SalesInventoryFact,
    SkuInterest,
    SourceFile,
)
from app.services import sku_backfill, twd_import


def _row(branch: str, sku: str, amount: str) -> TwdRow:
    source_amount = Decimal(amount)
    return TwdRow(
        branch_code=branch,
        branch_name=f"Branch {branch}",
        category=None,
        subcategory=None,
        brand=None,
        sku=sku,
        barcode=None,
        description=f"Product {sku}",
        product_type=None,
        source_amount=source_amount,
        amount=source_amount,
        sales_qty=Decimal("1"),
        stock_on_hand=Decimal("2"),
        stock_on_order=Decimal("3"),
        last_sold_date=None,
        last_receive_date=None,
    )


def _extract() -> TwdExtract:
    rows = (
        _row("B1", "SKU-A", "100"),
        _row("B2", "SKU-A", "200"),
        _row("B1", "OTHER", "900"),
    )
    summary = summarize(rows)
    return TwdExtract(
        source_path=r"\\server\share\TWD\2026-08-01\data.xlsx",
        source_filename="data.xlsx",
        checksum_sha256="a" * 64,
        data_date=date(2026, 8, 1),
        rows=rows,
        summary=summary,
        reported_summary=summary,
        reconciliation_errors=(),
    )


def test_backfill_adds_only_missing_sku_to_existing_batch(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    audit_ids = count(1)
    monkeypatch.setattr(
        sku_backfill,
        "AuditEvent",
        lambda **values: AuditEvent(id=next(audit_ids), **values),
    )
    monkeypatch.setattr(
        sku_backfill,
        "_credentials",
        lambda session, mt: (r"\\server\share\TWD", "WA\\user", "secret"),
    )
    monkeypatch.setattr(
        sku_backfill,
        "download_twd_extract",
        lambda candidate, **kwargs: _extract(),
    )
    monkeypatch.setattr(
        sku_backfill,
        "send_telegram",
        lambda *args, **kwargs: type(
            "Delivery", (), {"status": "sent", "message": "sent"}
        )(),
    )
    build_facts = twd_import._build_facts

    def build_facts_with_sqlite_ids(*args, **kwargs):
        facts = build_facts(*args, **kwargs)
        for fact_id, fact in enumerate(facts, start=1):
            fact.id = fact_id
        return facts

    monkeypatch.setattr(twd_import, "_build_facts", build_facts_with_sqlite_ids)
    at = datetime(2026, 8, 2, tzinfo=UTC)
    with Session(engine) as session:
        mt = ModernTrade(
            id=1,
            code="TWD",
            name="Thai Watsadu",
            source_enabled=True,
            source_subfolder="TWD",
        )
        batch = ImportBatch(
            id=1,
            modern_trade_id=1,
            status="imported",
            data_date=date(2026, 8, 1),
            source_path=r"\\server\share\TWD\2026-08-01\data.xlsx",
            source_filename="data.xlsx",
            checksum_sha256="a" * 64,
            row_count=12_000,
            store_count=102,
            sku_count=2_000,
            negative_row_count=0,
            source_amount=Decimal("9999"),
            amount=Decimal("9344"),
            sales_qty=Decimal("500"),
            stock_on_hand=Decimal("1000"),
            reported_stock_on_hand=Decimal("1000"),
            stock_on_order=Decimal("20"),
        )
        session.add_all(
            [
                mt,
                batch,
                SourceFile(
                    id=1,
                    modern_trade_id=1,
                    source_path=batch.source_path,
                    source_filename=batch.source_filename,
                    size_bytes=100,
                    modified_at=at,
                    checksum_sha256=batch.checksum_sha256,
                    detected_data_date=batch.data_date,
                    status="skipped",
                    imported_batch_id=1,
                    last_seen_at=at,
                ),
                ItemMapping(
                    id=1,
                    modern_trade_id=1,
                    source_sku="SKU-A",
                    source_description="Product SKU-A",
                    wa_item_code="WA-A",
                    status="confirmed",
                    report_status="active",
                    effective_from=date(2026, 9, 1),
                    changed_by="test",
                ),
                SkuInterest(
                    id=1,
                    modern_trade_id=1,
                    source_sku="SKU-A",
                    status="ignored",
                    first_seen_date=date(2026, 8, 1),
                    last_seen_date=date(2026, 9, 1),
                ),
                BranchMapping(
                    id=1,
                    modern_trade_id=1,
                    source_branch_code="B1",
                    wa_branch_code="WA-B1",
                    status="confirmed",
                    effective_from=date(2026, 8, 1),
                    changed_by="test",
                ),
                BranchMapping(
                    id=2,
                    modern_trade_id=1,
                    source_branch_code="B2",
                    wa_branch_code="WA-B2",
                    status="confirmed",
                    effective_from=date(2026, 8, 1),
                    changed_by="test",
                ),
            ]
        )
        session.commit()

        preview = sku_backfill.preview_sku_backfill(
            session,
            mt,
            "SKU-A",
            date(2026, 8, 1),
        )
        assert preview["counts"]["candidate"] == 1
        run = sku_backfill.create_sku_backfill_run(
            session,
            mt,
            source_sku="SKU-A",
            range_start=date(2026, 8, 1),
            actor="admin",
        )
        run.status = "running"
        session.commit()
        sku_backfill.process_sku_backfill_run(session, run.id)

        stored_run = session.get(type(run), run.id)
        stored_batch = session.get(ImportBatch, 1)
        facts = session.scalars(
            select(SalesInventoryFact).order_by(SalesInventoryFact.source_branch_code)
        ).all()
        mapping = session.get(ItemMapping, 1)
        interest = session.get(SkuInterest, 1)
        daily_count = session.scalar(select(func.count()).select_from(DailySkuSummary))
        monthly_count = session.scalar(
            select(func.count()).select_from(MonthlySalesSummary)
        )

    assert stored_run.status == "success"
    assert stored_run.imported_count == 1
    assert [(fact.source_branch_code, fact.source_sku) for fact in facts] == [
        ("B1", "SKU-A"),
        ("B2", "SKU-A"),
    ]
    assert stored_batch.row_count == 12_000
    assert stored_batch.amount == Decimal("9344")
    assert mapping.effective_from == date(2026, 8, 1)
    assert interest.status == "active"
    assert daily_count == 1
    assert monthly_count == 2


def test_stopped_backfill_can_resume_without_losing_checkpoint(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    audit_ids = count(1)
    monkeypatch.setattr(
        automatic_imports,
        "AuditEvent",
        lambda **values: AuditEvent(id=next(audit_ids), **values),
    )
    with Session(engine) as session:
        mt = ModernTrade(id=1, code="TWD", name="Thai Watsadu")
        run = ImportRun(
            id=1,
            modern_trade_id=1,
            trigger="manual",
            mode="sku_backfill",
            status="stopped",
            requested_by="admin",
            target_sku="SKU-A",
            range_start=date(2026, 8, 1),
            range_end=date(2026, 8, 2),
            results_json='[{"dataDate":"2026-08-01","status":"imported"}]',
        )
        session.add_all([mt, run])
        session.commit()

        resumed = automatic_imports.resume_import_run(1, session, "admin")
        stopped = automatic_imports.stop_import_run(1, session, "admin")

    assert resumed["status"] == "queued"
    assert resumed["results"][0]["dataDate"] == "2026-08-01"
    assert stopped["status"] == "stopped"


def test_preview_blocks_registry_file_with_different_batch_checksum() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    at = datetime(2026, 8, 2, tzinfo=UTC)
    with Session(engine) as session:
        mt = ModernTrade(id=1, code="TWD", name="Thai Watsadu")
        session.add_all(
            [
                mt,
                ImportBatch(
                    id=1,
                    modern_trade_id=1,
                    status="imported",
                    data_date=date(2026, 8, 1),
                    source_path="manual-upload:data.xlsx",
                    source_filename="data.xlsx",
                    checksum_sha256="a" * 64,
                    row_count=1,
                    store_count=1,
                    sku_count=1,
                    negative_row_count=0,
                    source_amount=Decimal("1"),
                    amount=Decimal("1"),
                    sales_qty=Decimal("1"),
                    stock_on_hand=Decimal("1"),
                    reported_stock_on_hand=Decimal("1"),
                    stock_on_order=Decimal("1"),
                ),
                SourceFile(
                    id=1,
                    modern_trade_id=1,
                    source_path=r"\\server\share\TWD\2026-08-01\other.xlsx",
                    source_filename="other.xlsx",
                    size_bytes=100,
                    modified_at=at,
                    checksum_sha256="b" * 64,
                    detected_data_date=date(2026, 8, 1),
                    status="ready",
                    last_seen_at=at,
                ),
                ItemMapping(
                    id=1,
                    modern_trade_id=1,
                    source_sku="SKU-A",
                    wa_item_code="WA-A",
                    status="confirmed",
                    report_status="active",
                    effective_from=date(2026, 8, 1),
                    changed_by="test",
                ),
            ]
        )
        session.commit()

        preview = sku_backfill.preview_sku_backfill(
            session,
            mt,
            "SKU-A",
            date(2026, 8, 1),
        )

    assert preview["counts"]["candidate"] == 0
    assert preview["counts"]["source_conflict"] == 1


def test_preview_rejects_start_before_file_registry() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    at = datetime(2026, 8, 2, tzinfo=UTC)
    with Session(engine) as session:
        mt = ModernTrade(id=1, code="TWD", name="Thai Watsadu")
        session.add_all(
            [
                mt,
                SourceFile(
                    id=1,
                    modern_trade_id=1,
                    source_path=r"\\server\share\TWD\2026-08-01\data.xlsx",
                    source_filename="data.xlsx",
                    size_bytes=100,
                    modified_at=at,
                    checksum_sha256="a" * 64,
                    detected_data_date=date(2026, 8, 1),
                    status="ready",
                    last_seen_at=at,
                ),
            ]
        )
        session.commit()

        with pytest.raises(ValueError, match="วันแรกใน File Registry"):
            sku_backfill.preview_sku_backfill(
                session,
                mt,
                "SKU-A",
                date(2026, 7, 1),
            )

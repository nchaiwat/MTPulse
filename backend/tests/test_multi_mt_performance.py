from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.performance import performance, sku_options
from app.database import Base
from app.models import (
    BranchMapping,
    ImportBatch,
    ItemMapping,
    ModernTrade,
    SalesInventoryFact,
)
from app.services.monthly_sales_summary import refresh_monthly_sales_summary


def _batch(batch_id: int, modern_trade_id: int, checksum: str) -> ImportBatch:
    return ImportBatch(
        id=batch_id,
        modern_trade_id=modern_trade_id,
        status="imported",
        data_date=date(2026, 8, 17),
        source_path=f"{checksum}.xlsx",
        source_filename=f"{checksum}.xlsx",
        checksum_sha256=checksum * 64,
        row_count=1,
        store_count=1,
        sku_count=1,
        negative_row_count=0,
        source_amount=100,
        amount=100,
        sales_qty=1,
        stock_on_hand=0,
        reported_stock_on_hand=0,
        stock_on_order=0,
    )


def _fact(fact_id: int, modern_trade_id: int, batch_id: int, amount: int) -> SalesInventoryFact:
    return SalesInventoryFact(
        id=fact_id,
        modern_trade_id=modern_trade_id,
        batch_id=batch_id,
        data_date=date(2026, 8, 17),
        source_branch_code="SHARED-BRANCH",
        source_branch_name="Shared branch",
        source_sku="SHARED-SKU",
        source_description="Shared item",
        source_amount=amount,
        amount=amount,
        sales_qty=1,
        stock_on_hand=0,
        stock_on_order=0,
    )


def test_monthly_report_does_not_mix_modern_trades() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                ModernTrade(id=1, code="TWD", name="Thai Watsadu"),
                ModernTrade(id=2, code="TA", name="Test MT"),
                _batch(1, 1, "a"),
                _batch(2, 2, "b"),
                ItemMapping(
                    id=1,
                    modern_trade_id=1,
                    source_sku="SHARED-SKU",
                    source_description="Shared item",
                    wa_item_code="WA-SKU",
                    status="confirmed",
                    effective_from=date(2026, 8, 1),
                    changed_by="test",
                ),
                BranchMapping(
                    id=1,
                    modern_trade_id=1,
                    source_branch_code="SHARED-BRANCH",
                    source_branch_description="Shared branch",
                    wa_branch_code="WA-BRANCH",
                    status="confirmed",
                    effective_from=date(2026, 8, 1),
                    changed_by="test",
                ),
                _fact(1, 1, 1, 100),
                _fact(2, 2, 2, 900),
            ]
        )
        session.commit()
        refresh_monthly_sales_summary(session, 1, date(2026, 8, 17))
        refresh_monthly_sales_summary(session, 2, date(2026, 8, 17))
        session.commit()

        report = performance(
            session=session,
            date_from=None,
            date_to=None,
            page=1,
            page_size=25,
            branch_id=None,
            branch_ids=None,
            sku_ids=None,
            mapping_status=None,
            hide_unmapped=False,
            search=None,
            grain="branch_month",
            period_month="2026-08",
        )

    assert report["summary"]["amount"] == 100
    assert report["summary"]["qty"] == 1
    assert report["columnTotals"] == {
        "SHARED-BRANCH": {"amount": 100.0, "qty": 1.0}
    }


def test_hp_report_exposes_stock_value_without_twd_data() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                ModernTrade(id=1, code="TWD", name="Thai Watsadu"),
                ModernTrade(id=2, code="HP", name="HomePro"),
                _batch(1, 1, "a"),
                _batch(2, 2, "b"),
                ItemMapping(
                    id=1,
                    modern_trade_id=2,
                    source_sku="1165985",
                    source_description="HP item",
                    wa_item_code="WA-HP",
                    status="confirmed",
                    effective_from=date(2026, 8, 1),
                    changed_by="test",
                ),
                BranchMapping(
                    id=1,
                    modern_trade_id=2,
                    source_branch_code="S880",
                    source_branch_description="HomePro branch",
                    wa_branch_code="WA-S880",
                    status="confirmed",
                    effective_from=date(2026, 8, 1),
                    changed_by="test",
                ),
                SalesInventoryFact(
                    id=1,
                    modern_trade_id=1,
                    batch_id=1,
                    data_date=date(2026, 8, 17),
                    source_branch_code="60920",
                    source_branch_name="TWD branch",
                    source_sku="TWD-SKU",
                    source_description="TWD item",
                    source_amount=900,
                    amount=900,
                    sales_qty=9,
                    stock_on_hand=90,
                    stock_on_order=9,
                    stock_value=9000,
                ),
                SalesInventoryFact(
                    id=2,
                    modern_trade_id=2,
                    batch_id=2,
                    data_date=date(2026, 8, 17),
                    source_branch_code="S880",
                    source_branch_name="HomePro branch",
                    source_sku="1165985",
                    source_description="HP item",
                    source_amount=100,
                    amount=100,
                    sales_qty=1,
                    stock_on_hand=5,
                    stock_on_order=0,
                    stock_value=1250,
                ),
            ]
        )
        session.commit()

        report = performance(session=session, mt_code="HP", latest_only=True)
        options = sku_options(session=session, mt_code="HP")

    assert report["mtCode"] == "HP"
    assert report["metricCapabilities"]["inventory"] == ["stockOh", "stockValue"]
    assert report["inventorySummary"] == {
        "stockOh": 5.0,
        "stockOnOrder": 0.0,
        "stockValue": 1250.0,
    }
    assert report["items"][0]["points"][0]["stockValue"] == 1250.0
    assert [item["sku"] for item in options["items"]] == ["1165985"]

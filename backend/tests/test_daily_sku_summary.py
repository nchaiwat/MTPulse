from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models import (
    BranchMapping,
    DailySkuSummary,
    ImportBatch,
    ModernTrade,
    SalesInventoryFact,
)
from app.services.daily_sku_summary import (
    rebuild_daily_sku_summaries,
    refresh_daily_sku_summary,
)


def _batch(batch_id: int, modern_trade_id: int, data_date: date) -> ImportBatch:
    return ImportBatch(
        id=batch_id,
        modern_trade_id=modern_trade_id,
        status="imported",
        data_date=data_date,
        source_path=f"{batch_id}.xls",
        source_filename=f"{batch_id}.xls",
        checksum_sha256=str(batch_id) * 64,
        row_count=1,
        store_count=1,
        sku_count=1,
        negative_row_count=0,
        source_amount=0,
        amount=0,
        sales_qty=0,
        stock_on_hand=0,
        reported_stock_on_hand=0,
        stock_on_order=0,
    )


def _fact(
    fact_id: int,
    batch_id: int,
    modern_trade_id: int,
    data_date: date,
    branch: str,
    amount: int,
) -> SalesInventoryFact:
    return SalesInventoryFact(
        id=fact_id,
        modern_trade_id=modern_trade_id,
        batch_id=batch_id,
        data_date=data_date,
        source_branch_code=branch,
        source_branch_name=branch,
        source_sku="SKU-1",
        source_description="Item 1",
        source_amount=amount,
        amount=amount,
        sales_qty=1,
        stock_on_hand=10,
        stock_on_order=2,
    )


def test_refresh_daily_sku_summary_replaces_only_selected_mt_and_date() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    first_date = date(2026, 8, 30)
    second_date = date(2026, 8, 31)
    with Session(engine) as session:
        session.add_all(
            [
                ModernTrade(id=1, code="TWD", name="Thai Watsadu"),
                ModernTrade(id=2, code="OTHER", name="Other"),
                BranchMapping(
                    id=1,
                    modern_trade_id=1,
                    source_branch_code="B1",
                    wa_branch_code="WA-B1",
                    status="confirmed",
                    effective_from=first_date,
                    changed_by="test",
                ),
                BranchMapping(
                    id=2,
                    modern_trade_id=2,
                    source_branch_code="B1",
                    wa_branch_code="OTHER-B1",
                    status="confirmed",
                    effective_from=first_date,
                    changed_by="test",
                ),
                _batch(1, 1, first_date),
                _batch(2, 1, second_date),
                _batch(3, 2, first_date),
                _fact(1, 1, 1, first_date, "B1", 100),
                _fact(2, 1, 1, first_date, "B2", 200),
                _fact(3, 2, 1, second_date, "B1", 300),
                _fact(4, 3, 2, first_date, "B1", 900),
            ]
        )
        session.commit()
        refresh_daily_sku_summary(session, 1, first_date)
        refresh_daily_sku_summary(session, 1, second_date)
        refresh_daily_sku_summary(session, 2, first_date)
        session.commit()

        first_fact = session.get(SalesInventoryFact, 1)
        assert first_fact is not None
        first_fact.amount = 150
        refresh_daily_sku_summary(session, 1, first_date)
        session.commit()
        summaries = session.scalars(
            select(DailySkuSummary).order_by(
                DailySkuSummary.modern_trade_id,
                DailySkuSummary.data_date,
            )
        ).all()
        summary_values = [
            (row.modern_trade_id, row.data_date, float(row.amount))
            for row in summaries
        ]
        first_measures = (
            float(summaries[0].sales_qty),
            float(summaries[0].stock_on_hand),
            float(summaries[0].stock_on_order),
        )
        session.add(
            BranchMapping(
                id=3,
                modern_trade_id=1,
                source_branch_code="B2",
                wa_branch_code="WA-B2",
                status="confirmed",
                effective_from=first_date,
                changed_by="test",
            )
        )
        session.flush()
        rebuild_daily_sku_summaries(session, 1)
        session.commit()
        rebuilt_values = [
            (row.modern_trade_id, row.data_date, float(row.amount))
            for row in session.scalars(
                select(DailySkuSummary).order_by(
                    DailySkuSummary.modern_trade_id,
                    DailySkuSummary.data_date,
                )
            ).all()
        ]

    assert summary_values == [
        (1, first_date, 150.0),
        (1, second_date, 300.0),
        (2, first_date, 900.0),
    ]
    assert first_measures == (1.0, 10.0, 2.0)
    assert rebuilt_values == [
        (1, first_date, 350.0),
        (1, second_date, 300.0),
        (2, first_date, 900.0),
    ]

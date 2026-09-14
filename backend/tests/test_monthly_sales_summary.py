from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models import ImportBatch, ModernTrade, MonthlySalesSummary, SalesInventoryFact
from app.services.monthly_sales_summary import refresh_monthly_sales_summary


def test_monthly_summary_excludes_rolling_sales() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ModernTrade(id=1, code="GH", name="Global House"))
        for identity, data_date, grain, amount in (
            (1, date(2026, 8, 3), "daily", 100),
            (2, date(2026, 8, 4), "rolling_30d", 3000),
        ):
            session.add(
                ImportBatch(
                    id=identity,
                    modern_trade_id=1,
                    status="imported",
                    data_date=data_date,
                    sales_grain=grain,
                    sales_window_days=30 if grain == "rolling_30d" else None,
                    source_path=str(identity),
                    source_filename=str(identity),
                    checksum_sha256=str(identity) * 64,
                    row_count=1,
                    store_count=1,
                    sku_count=1,
                    negative_row_count=0,
                    source_amount=amount,
                    amount=amount,
                    sales_qty=1,
                    stock_on_hand=1,
                    reported_stock_on_hand=1,
                    stock_on_order=0,
                )
            )
            session.add(
                SalesInventoryFact(
                    id=identity,
                    modern_trade_id=1,
                    batch_id=identity,
                    data_date=data_date,
                    sales_grain=grain,
                    sales_window_days=30 if grain == "rolling_30d" else None,
                    source_branch_code="GH-001",
                    source_branch_name="Branch",
                    source_sku="SKU",
                    source_amount=amount,
                    amount=amount,
                    sales_qty=1,
                    stock_on_hand=1,
                    stock_on_order=0,
                )
            )
        session.flush()
        refresh_monthly_sales_summary(session, 1, date(2026, 8, 4))
        session.commit()
        summary = session.scalar(select(MonthlySalesSummary))

    assert summary is not None
    assert float(summary.amount) == 100
    assert float(summary.sales_qty) == 1

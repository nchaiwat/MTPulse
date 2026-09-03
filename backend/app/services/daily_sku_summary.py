from datetime import date

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from app.models import DailySkuSummary, SalesInventoryFact


def refresh_daily_sku_summary(
    session: Session,
    modern_trade_id: int,
    data_date: date,
) -> None:
    session.execute(
        delete(DailySkuSummary).where(
            DailySkuSummary.modern_trade_id == modern_trade_id,
            DailySkuSummary.data_date == data_date,
        )
    )
    aggregate = (
        select(
            SalesInventoryFact.modern_trade_id,
            SalesInventoryFact.data_date,
            SalesInventoryFact.source_sku,
            func.min(SalesInventoryFact.source_description),
            func.sum(SalesInventoryFact.amount),
            func.sum(SalesInventoryFact.sales_qty),
            func.sum(SalesInventoryFact.stock_on_hand),
            func.sum(SalesInventoryFact.stock_on_order),
        )
        .where(
            SalesInventoryFact.modern_trade_id == modern_trade_id,
            SalesInventoryFact.data_date == data_date,
        )
        .group_by(
            SalesInventoryFact.modern_trade_id,
            SalesInventoryFact.data_date,
            SalesInventoryFact.source_sku,
        )
    )
    session.execute(
        insert(DailySkuSummary).from_select(
            [
                "modern_trade_id",
                "data_date",
                "source_sku",
                "source_description",
                "amount",
                "sales_qty",
                "stock_on_hand",
                "stock_on_order",
            ],
            aggregate,
        )
    )

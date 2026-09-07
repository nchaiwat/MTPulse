from calendar import monthrange
from datetime import date

from sqlalchemy import case, delete, func, insert, literal, select
from sqlalchemy.orm import Session

from app.models import MonthlySalesSummary, SalesInventoryFact


def month_bounds(value: date) -> tuple[date, date]:
    month_start = value.replace(day=1)
    month_end = value.replace(day=monthrange(value.year, value.month)[1])
    return month_start, month_end


def refresh_monthly_sales_summary(
    session: Session,
    modern_trade_id: int,
    data_date: date,
) -> None:
    month_start, month_end = month_bounds(data_date)
    session.execute(
        delete(MonthlySalesSummary).where(
            MonthlySalesSummary.modern_trade_id == modern_trade_id,
            MonthlySalesSummary.month_start == month_start,
        )
    )
    aggregate = (
        select(
            SalesInventoryFact.modern_trade_id,
            literal(month_start),
            SalesInventoryFact.source_sku,
            SalesInventoryFact.source_branch_code,
            func.min(SalesInventoryFact.source_branch_name),
            func.min(SalesInventoryFact.source_description),
            func.sum(SalesInventoryFact.amount),
            func.sum(SalesInventoryFact.sales_qty),
            func.sum(
                case(
                    (SalesInventoryFact.amount > 0, SalesInventoryFact.amount),
                    else_=0,
                )
            ),
            func.sum(
                case(
                    (
                        SalesInventoryFact.sales_qty > 0,
                        SalesInventoryFact.sales_qty,
                    ),
                    else_=0,
                )
            ),
        )
        .where(
            SalesInventoryFact.modern_trade_id == modern_trade_id,
            SalesInventoryFact.data_date >= month_start,
            SalesInventoryFact.data_date <= month_end,
        )
        .group_by(
            SalesInventoryFact.modern_trade_id,
            SalesInventoryFact.source_sku,
            SalesInventoryFact.source_branch_code,
        )
    )
    session.execute(
        insert(MonthlySalesSummary).from_select(
            [
                "modern_trade_id",
                "month_start",
                "source_sku",
                "source_branch_code",
                "source_branch_name",
                "source_description",
                "amount",
                "sales_qty",
                "gross_amount",
                "gross_sales_qty",
            ],
            aggregate,
        )
    )

from datetime import date

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from app.models import BranchMapping, DailySkuSummary, ImportBatch, SalesInventoryFact

AVAILABLE_BATCH_STATUSES = ("imported", "imported_with_warnings")


def _mapping_reference_date(
    session: Session,
    modern_trade_id: int,
    data_date: date | None = None,
) -> date | None:
    latest_imported = session.scalar(
        select(func.max(ImportBatch.data_date)).where(
            ImportBatch.modern_trade_id == modern_trade_id,
            ImportBatch.status.in_(AVAILABLE_BATCH_STATUSES),
        )
    )
    if data_date is None:
        return latest_imported
    return max(latest_imported, data_date) if latest_imported else data_date


def _insert_daily_sku_summaries(
    session: Session,
    modern_trade_id: int,
    mapping_reference_date: date,
    data_date: date | None = None,
) -> None:
    active_branches = select(BranchMapping.source_branch_code).where(
        BranchMapping.modern_trade_id == modern_trade_id,
        BranchMapping.effective_from <= mapping_reference_date,
        (
            BranchMapping.effective_to.is_(None)
            | (BranchMapping.effective_to >= mapping_reference_date)
        ),
    )
    fact_filters = [
        SalesInventoryFact.modern_trade_id == modern_trade_id,
        SalesInventoryFact.source_branch_code.in_(active_branches),
    ]
    if data_date is not None:
        fact_filters.append(SalesInventoryFact.data_date == data_date)
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
        .where(*fact_filters)
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
    mapping_reference_date = _mapping_reference_date(
        session,
        modern_trade_id,
        data_date,
    )
    if mapping_reference_date is not None:
        _insert_daily_sku_summaries(
            session,
            modern_trade_id,
            mapping_reference_date,
            data_date,
        )


def rebuild_daily_sku_summaries(
    session: Session,
    modern_trade_id: int,
) -> None:
    session.execute(
        delete(DailySkuSummary).where(
            DailySkuSummary.modern_trade_id == modern_trade_id
        )
    )
    mapping_reference_date = _mapping_reference_date(session, modern_trade_id)
    if mapping_reference_date is not None:
        _insert_daily_sku_summaries(
            session,
            modern_trade_id,
            mapping_reference_date,
        )

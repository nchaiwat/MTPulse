from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, cast, distinct, func, or_, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import BranchMapping, ImportBatch, ItemMapping, ModernTrade, SalesInventoryFact

router = APIRouter(prefix="/api", tags=["performance"])


def _number(value: Decimal) -> float:
    return float(value)


def _month_bounds(month_key: str) -> tuple[date, date]:
    year, month = (int(part) for part in month_key.split("-"))
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


@router.get("/performance")
def performance(
    session: Annotated[Session, Depends(get_session)],
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=250)] = 100,
    branch_id: Annotated[str | None, Query(max_length=30)] = None,
    mapping_status: Annotated[Literal["confirmed", "pending", "unmatched"] | None, Query()] = None,
    hide_unmapped: Annotated[bool, Query()] = False,
    search: Annotated[str | None, Query(max_length=200)] = None,
    grain: Annotated[Literal["day", "month", "branch_month"], Query()] = "day",
    period_month: Annotated[str | None, Query(max_length=7)] = None,
) -> dict:
    all_dates = session.scalars(
        select(distinct(SalesInventoryFact.data_date)).order_by(SalesInventoryFact.data_date)
    ).all()
    available_months = sorted({value.strftime("%Y-%m") for value in all_dates})
    min_date, max_date = session.execute(
        select(func.min(SalesInventoryFact.data_date), func.max(SalesInventoryFact.data_date))
    ).one()
    range_from = date_from or min_date or date.today()
    range_to = date_to or max_date or range_from
    selected_month = None
    if grain == "branch_month":
        selected_month = (
            available_months[-1]
            if period_month in (None, "latest") and available_months
            else period_month
        )
        if selected_month:
            try:
                range_from, range_to = _month_bounds(selected_month)
            except (TypeError, ValueError) as error:
                raise HTTPException(
                    status_code=422, detail="period_month must use YYYY-MM"
                ) from error
    filters = []
    if date_from or grain == "branch_month":
        filters.append(SalesInventoryFact.data_date >= range_from)
    if date_to or grain == "branch_month":
        filters.append(SalesInventoryFact.data_date <= range_to)
    twd_id = select(ModernTrade.id).where(ModernTrade.code == "TWD").scalar_subquery()
    active_mapping_filters = (
        ItemMapping.modern_trade_id == twd_id,
        ItemMapping.effective_from <= range_to,
        (ItemMapping.effective_to.is_(None) | (ItemMapping.effective_to >= range_from)),
    )
    mapped_skus = select(ItemMapping.source_sku).where(*active_mapping_filters)
    if branch_id:
        filters.append(SalesInventoryFact.source_branch_code == branch_id)
    if mapping_status:
        if mapping_status == "unmatched":
            filters.append(~SalesInventoryFact.source_sku.in_(mapped_skus))
        else:
            filters.append(
                SalesInventoryFact.source_sku.in_(
                    mapped_skus.where(ItemMapping.status == mapping_status)
                )
            )
    elif hide_unmapped:
        filters.append(SalesInventoryFact.source_sku.in_(mapped_skus))
    normalized_search = search.strip() if search else ""
    if normalized_search:
        wa_matches = select(ItemMapping.source_sku).where(
            *active_mapping_filters,
            or_(
                ItemMapping.wa_item_code.icontains(normalized_search, autoescape=True),
                ItemMapping.wa_item_description.icontains(normalized_search, autoescape=True),
            ),
        )
        filters.append(
            or_(
                SalesInventoryFact.source_sku.icontains(normalized_search, autoescape=True),
                SalesInventoryFact.source_description.icontains(normalized_search, autoescape=True),
                SalesInventoryFact.source_sku.in_(wa_matches),
            )
        )
    total_skus = (
        session.scalar(select(func.count(distinct(SalesInventoryFact.source_sku))).where(*filters))
        or 0
    )
    total_amount, total_qty = session.execute(
        select(
            func.coalesce(func.sum(SalesInventoryFact.amount), 0),
            func.coalesce(func.sum(SalesInventoryFact.sales_qty), 0),
        ).where(*filters)
    ).one()
    active_branch_count = (
        session.scalar(
            select(func.count(distinct(SalesInventoryFact.source_branch_code))).where(*filters)
        )
        or 0
    )
    confirmed_skus = select(ItemMapping.source_sku).where(
        *active_mapping_filters, ItemMapping.status == "confirmed"
    )
    mapping_attention = (
        session.scalar(
            select(func.count(distinct(SalesInventoryFact.source_sku))).where(
                *filters, ~SalesInventoryFact.source_sku.in_(confirmed_skus)
            )
        )
        or 0
    )
    column_totals: dict[str, dict[str, float]] = {}
    if grain == "branch_month":
        total_rows = session.execute(
            select(
                SalesInventoryFact.source_branch_code,
                func.coalesce(func.sum(SalesInventoryFact.amount), 0),
                func.coalesce(func.sum(SalesInventoryFact.sales_qty), 0),
            )
            .where(*filters)
            .group_by(SalesInventoryFact.source_branch_code)
            .order_by(SalesInventoryFact.source_branch_code)
        ).all()
        column_totals = {
            branch_code: {"amount": _number(amount), "qty": _number(qty)}
            for branch_code, amount, qty in total_rows
        }
    elif grain == "month":
        total_year = cast(func.extract("year", SalesInventoryFact.data_date), Integer)
        total_month = cast(func.extract("month", SalesInventoryFact.data_date), Integer)
        total_rows = session.execute(
            select(
                total_year,
                total_month,
                func.coalesce(func.sum(SalesInventoryFact.amount), 0),
                func.coalesce(func.sum(SalesInventoryFact.sales_qty), 0),
            )
            .where(*filters)
            .group_by(total_year, total_month)
            .order_by(total_year, total_month)
        ).all()
        column_totals = {
            f"{year:04d}-{month:02d}": {"amount": _number(amount), "qty": _number(qty)}
            for year, month, amount, qty in total_rows
        }
    skus = session.scalars(
        select(SalesInventoryFact.source_sku)
        .where(*filters)
        .group_by(SalesInventoryFact.source_sku)
        .order_by(SalesInventoryFact.source_sku)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    facts = []
    monthly_rows = []
    monthly_branch_rows = []
    if grain == "month":
        year_part = cast(func.extract("year", SalesInventoryFact.data_date), Integer)
        month_part = cast(func.extract("month", SalesInventoryFact.data_date), Integer)
        monthly_rows = session.execute(
            select(
                SalesInventoryFact.source_sku,
                func.min(SalesInventoryFact.source_description),
                year_part,
                month_part,
                func.sum(SalesInventoryFact.amount),
                func.sum(SalesInventoryFact.sales_qty),
            )
            .where(*filters, SalesInventoryFact.source_sku.in_(skus))
            .group_by(SalesInventoryFact.source_sku, year_part, month_part)
            .order_by(SalesInventoryFact.source_sku, year_part, month_part)
        ).all()
    elif grain == "branch_month":
        monthly_branch_rows = session.execute(
            select(
                SalesInventoryFact.source_sku,
                func.min(SalesInventoryFact.source_description),
                SalesInventoryFact.source_branch_code,
                func.sum(SalesInventoryFact.amount),
                func.sum(SalesInventoryFact.sales_qty),
            )
            .where(*filters, SalesInventoryFact.source_sku.in_(skus))
            .group_by(SalesInventoryFact.source_sku, SalesInventoryFact.source_branch_code)
            .order_by(SalesInventoryFact.source_sku, SalesInventoryFact.source_branch_code)
        ).all()
    else:
        facts = session.scalars(
            select(SalesInventoryFact)
            .where(*filters, SalesInventoryFact.source_sku.in_(skus))
            .order_by(
                SalesInventoryFact.source_sku,
                SalesInventoryFact.data_date,
                SalesInventoryFact.source_branch_code,
            )
        ).all()
    branch_rows = session.execute(
        select(
            SalesInventoryFact.source_branch_code,
            func.min(SalesInventoryFact.source_branch_name),
        )
        .group_by(SalesInventoryFact.source_branch_code)
        .order_by(SalesInventoryFact.source_branch_code)
    ).all()
    branch_mappings = session.scalars(
        select(BranchMapping)
        .where(
            BranchMapping.modern_trade_id == twd_id,
            BranchMapping.effective_from <= range_to,
            (
                BranchMapping.effective_to.is_(None)
                | (BranchMapping.effective_to >= range_from)
            ),
        )
        .order_by(BranchMapping.effective_from)
    ).all()
    branch_mapping_by_code = {
        mapping.source_branch_code: mapping for mapping in branch_mappings
    }
    dates = session.scalars(
        select(distinct(SalesInventoryFact.data_date))
        .where(*filters)
        .order_by(SalesInventoryFact.data_date)
    ).all()
    mappings = session.scalars(
        select(ItemMapping)
        .where(
            ItemMapping.source_sku.in_(skus),
            *active_mapping_filters,
        )
        .order_by(ItemMapping.effective_from)
    ).all()
    mapping_by_sku = {mapping.source_sku: mapping for mapping in mappings}

    items: dict[str, dict] = {}

    def item_for(source_sku: str, source_description: str | None) -> dict:
        mapping = mapping_by_sku.get(source_sku)
        return items.setdefault(
            source_sku,
            {
                "sku": source_sku,
                "twdDescription": source_description
                or (mapping.source_description if mapping else None)
                or "ไม่มีรายละเอียด TWD",
                "waItem": mapping.wa_item_code if mapping else None,
                "waDescription": mapping.wa_item_description if mapping else None,
                "mappingStatus": mapping.status if mapping else "unmatched",
                "points": [],
            },
        )

    for fact in facts:
        item = item_for(fact.source_sku, fact.source_description)
        item["points"].append(
            {
                "date": fact.data_date.isoformat(),
                "branchId": fact.source_branch_code,
                "amount": _number(fact.amount),
                "qty": _number(fact.sales_qty),
                "stockOh": _number(fact.stock_on_hand),
                "stockOnOrder": _number(fact.stock_on_order),
            }
        )

    for source_sku, source_description, year, month, amount, qty in monthly_rows:
        item = item_for(source_sku, source_description)
        item["points"].append(
            {
                "date": f"{year:04d}-{month:02d}",
                "branchId": "all",
                "amount": _number(amount),
                "qty": _number(qty),
                "stockOh": 0,
                "stockOnOrder": 0,
            }
        )

    for source_sku, source_description, source_branch_code, amount, qty in monthly_branch_rows:
        item = item_for(source_sku, source_description)
        item["points"].append(
            {
                "date": selected_month,
                "branchId": source_branch_code,
                "amount": _number(amount),
                "qty": _number(qty),
                "stockOh": 0,
                "stockOnOrder": 0,
            }
        )

    latest_import = session.scalar(
        select(ImportBatch).order_by(ImportBatch.data_date.desc(), ImportBatch.id.desc()).limit(1)
    )
    return {
        "branches": [
            {
                "id": code,
                "name": (
                    branch_mapping_by_code[code].wa_branch_description
                    or branch_mapping_by_code[code].wa_branch_code
                )
                if code in branch_mapping_by_code
                else name,
            }
            for code, name in branch_rows
        ],
        "dates": (
            [selected_month]
            if grain == "branch_month" and selected_month
            else sorted(
                {value.strftime("%Y-%m") for value in dates}
                if grain == "month"
                else {value.isoformat() for value in dates}
            )
        ),
        "months": available_months,
        "selectedMonth": selected_month,
        "columnTotals": column_totals,
        "items": list(items.values()),
        "meta": {
            "page": page,
            "pageSize": page_size,
            "totalSkus": total_skus,
            "totalPages": max(1, (total_skus + page_size - 1) // page_size),
            "totalBranches": active_branch_count,
        },
        "summary": {
            "amount": _number(total_amount),
            "qty": _number(total_qty),
            "mappingAttention": mapping_attention,
        },
        "latestImport": (
            {
                "dataDate": latest_import.data_date.isoformat(),
                "status": latest_import.status,
                "rowCount": latest_import.row_count,
                "warnings": latest_import.reconciliation_errors.splitlines()
                if latest_import.reconciliation_errors
                else [],
            }
            if latest_import
            else None
        ),
    }

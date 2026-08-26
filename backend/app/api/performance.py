from calendar import monthrange
from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import Integer, cast, distinct, func, or_, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import BranchMapping, ImportBatch, ItemMapping, ModernTrade, SalesInventoryFact
from app.services.performance_export import (
    build_performance_workbook,
    performance_export_filename,
)

router = APIRouter(prefix="/api", tags=["performance"])


def _number(value: Decimal) -> float:
    return float(value)


def _month_bounds(month_key: str) -> tuple[date, date]:
    year, month = (int(part) for part in month_key.split("-"))
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def _selected_branch_ids(branch_id: str | None, branch_ids: str | None) -> list[str]:
    raw_ids = branch_ids or branch_id or ""
    selected: list[str] = []
    for value in raw_ids.split(","):
        normalized = value.strip()
        if normalized and normalized not in selected:
            selected.append(normalized)
    return selected


def _selected_sku_ids(sku_ids: str | None) -> list[str]:
    selected: list[str] = []
    for value in (sku_ids or "").split(","):
        normalized = value.strip()
        if normalized and normalized not in selected:
            selected.append(normalized)
    return selected


@router.get("/performance")
def performance(
    session: Annotated[Session, Depends(get_session)],
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int | None, Query(ge=1, le=1_000_000)] = None,
    branch_id: Annotated[str | None, Query(max_length=30)] = None,
    branch_ids: Annotated[str | None, Query(max_length=3000)] = None,
    sku_ids: Annotated[str | None, Query(max_length=10000)] = None,
    mapping_status: Annotated[Literal["confirmed", "pending", "unmatched"] | None, Query()] = None,
    hide_unmapped: Annotated[bool, Query()] = False,
    search: Annotated[str | None, Query(max_length=200)] = None,
    grain: Annotated[Literal["day", "day_total", "month", "branch_month"], Query()] = "day",
    period_month: Annotated[str | None, Query(max_length=7)] = None,
) -> dict:
    modern_trade = session.scalar(select(ModernTrade).where(ModernTrade.code == "TWD"))
    if modern_trade is None:
        raise HTTPException(status_code=404, detail="ไม่พบ Modern Trade รหัส TWD")
    all_dates = session.scalars(
        select(ImportBatch.data_date)
        .where(
            ImportBatch.modern_trade_id == modern_trade.id,
            ImportBatch.status.in_(("imported", "imported_with_warnings")),
        )
        .order_by(ImportBatch.data_date)
    ).all()
    available_months = sorted({value.strftime("%Y-%m") for value in all_dates})
    min_date = all_dates[0] if all_dates else None
    max_date = all_dates[-1] if all_dates else None
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
    resolved_page_size = page_size or modern_trade.report_page_size
    twd_id = modern_trade.id
    mapping_reference_date = max_date or range_to
    active_mapping_filters = (
        ItemMapping.modern_trade_id == twd_id,
        ItemMapping.effective_from <= mapping_reference_date,
        (
            ItemMapping.effective_to.is_(None)
            | (ItemMapping.effective_to >= mapping_reference_date)
        ),
    )
    active_branch_mapping_filters = (
        BranchMapping.modern_trade_id == twd_id,
        BranchMapping.effective_from <= mapping_reference_date,
        (
            BranchMapping.effective_to.is_(None)
            | (BranchMapping.effective_to >= mapping_reference_date)
        ),
    )
    mapped_skus = select(ItemMapping.source_sku).where(*active_mapping_filters)
    reportable_mapped_skus = mapped_skus.where(ItemMapping.report_status == "active")
    inactive_mapped_skus = mapped_skus.where(ItemMapping.report_status == "inactive")
    filters.append(~SalesInventoryFact.source_sku.in_(inactive_mapped_skus))
    mapped_branches = select(BranchMapping.source_branch_code).where(
        *active_branch_mapping_filters
    )
    if not modern_trade.show_unmatched_items or hide_unmapped:
        filters.append(SalesInventoryFact.source_sku.in_(reportable_mapped_skus))
    if not modern_trade.show_unmatched_branches:
        filters.append(SalesInventoryFact.source_branch_code.in_(mapped_branches))
    selected_branch_ids = _selected_branch_ids(branch_id, branch_ids)
    if selected_branch_ids:
        filters.append(SalesInventoryFact.source_branch_code.in_(selected_branch_ids))
    selected_sku_ids = _selected_sku_ids(sku_ids)
    if selected_sku_ids:
        filters.append(SalesInventoryFact.source_sku.in_(selected_sku_ids))
    if mapping_status:
        if mapping_status == "unmatched":
            filters.append(~SalesInventoryFact.source_sku.in_(reportable_mapped_skus))
        else:
            filters.append(
                SalesInventoryFact.source_sku.in_(
                    reportable_mapped_skus.where(ItemMapping.status == mapping_status)
                )
            )

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
    fact_skus = select(SalesInventoryFact.source_sku).where(*filters)
    mapping_candidate_filters = [
        *active_mapping_filters,
        ItemMapping.report_status == "active",
    ]
    if selected_sku_ids:
        mapping_candidate_filters.append(ItemMapping.source_sku.in_(selected_sku_ids))
    if mapping_status and mapping_status != "unmatched":
        mapping_candidate_filters.append(ItemMapping.status == mapping_status)
    if normalized_search:
        mapping_candidate_filters.append(
            or_(
                ItemMapping.source_sku.icontains(normalized_search, autoescape=True),
                ItemMapping.source_description.icontains(
                    normalized_search, autoescape=True
                ),
                ItemMapping.wa_item_code.icontains(normalized_search, autoescape=True),
                ItemMapping.wa_item_description.icontains(
                    normalized_search, autoescape=True
                ),
            )
        )
    if mapping_status == "unmatched":
        candidate_skus = fact_skus.distinct().subquery()
    else:
        mapping_skus = select(ItemMapping.source_sku).where(*mapping_candidate_filters)
        candidate_skus = fact_skus.union(mapping_skus).subquery()
    total_skus = session.scalar(select(func.count()).select_from(candidate_skus)) or 0
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
        *active_mapping_filters,
        ItemMapping.report_status == "active",
        ItemMapping.status == "confirmed",
    )
    mapping_attention = (
        session.scalar(
            select(func.count())
            .select_from(candidate_skus)
            .where(~candidate_skus.c.source_sku.in_(confirmed_skus))
        )
        or 0
    )
    column_totals: dict[str, dict[str, float]] = {}
    if grain in ("branch_month", "day"):
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
    elif grain == "day_total":
        total_rows = session.execute(
            select(
                SalesInventoryFact.data_date,
                func.coalesce(func.sum(SalesInventoryFact.amount), 0),
                func.coalesce(func.sum(SalesInventoryFact.sales_qty), 0),
            )
            .where(*filters)
            .group_by(SalesInventoryFact.data_date)
            .order_by(SalesInventoryFact.data_date)
        ).all()
        column_totals = {
            data_date.isoformat(): {"amount": _number(amount), "qty": _number(qty)}
            for data_date, amount, qty in total_rows
        }
    skus = session.scalars(
        select(candidate_skus.c.source_sku).order_by(candidate_skus.c.source_sku)
        .offset((page - 1) * resolved_page_size)
        .limit(resolved_page_size)
    ).all()
    facts = []
    daily_rows = []
    monthly_rows = []
    monthly_branch_rows = []
    if grain == "day_total":
        daily_rows = session.execute(
            select(
                SalesInventoryFact.source_sku,
                func.min(SalesInventoryFact.source_description),
                SalesInventoryFact.data_date,
                func.sum(SalesInventoryFact.amount),
                func.sum(SalesInventoryFact.sales_qty),
                func.sum(SalesInventoryFact.stock_on_hand),
                func.sum(SalesInventoryFact.stock_on_order),
            )
            .where(*filters, SalesInventoryFact.source_sku.in_(skus))
            .group_by(SalesInventoryFact.source_sku, SalesInventoryFact.data_date)
            .order_by(SalesInventoryFact.source_sku, SalesInventoryFact.data_date)
        ).all()
    elif grain == "month":
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
    branch_query = select(
        SalesInventoryFact.source_branch_code,
        func.min(SalesInventoryFact.source_branch_name),
    )
    if not modern_trade.show_unmatched_branches:
        branch_query = branch_query.where(
            SalesInventoryFact.source_branch_code.in_(mapped_branches)
        )
    branch_rows = session.execute(
        branch_query.group_by(SalesInventoryFact.source_branch_code).order_by(
            SalesInventoryFact.source_branch_code
        )
    ).all()
    branch_mappings = session.scalars(
        select(BranchMapping)
        .where(*active_branch_mapping_filters)
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
        item = items.get(source_sku)
        if item is None:
            item = {
                "sku": source_sku,
                "twdDescription": source_description
                or (mapping.source_description if mapping else None)
                or "ไม่มีรายละเอียด TWD",
                "waItem": mapping.wa_item_code if mapping else None,
                "waDescription": mapping.wa_item_description if mapping else None,
                "mappingStatus": mapping.status if mapping else "unmatched",
                "itemType": mapping.item_type if mapping else "normal",
                "points": [],
            }
            items[source_sku] = item
        elif source_description:
            item["twdDescription"] = source_description
        return item

    for source_sku in skus:
        item_for(source_sku, None)

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

    aggregate_branch_id = selected_branch_ids[0] if len(selected_branch_ids) == 1 else "all"
    for (
        source_sku,
        source_description,
        data_date,
        amount,
        qty,
        stock_oh,
        stock_on_order,
    ) in daily_rows:
        item = item_for(source_sku, source_description)
        item["points"].append(
            {
                "date": data_date.isoformat(),
                "branchId": aggregate_branch_id,
                "amount": _number(amount),
                "qty": _number(qty),
                "stockOh": _number(stock_oh),
                "stockOnOrder": _number(stock_on_order),
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
        "availableDates": [value.isoformat() for value in all_dates],
        "selectedMonth": selected_month,
        "columnTotals": column_totals,
        "items": list(items.values()),
        "meta": {
            "page": page,
            "pageSize": resolved_page_size,
            "totalSkus": total_skus,
            "totalPages": max(1, (total_skus + resolved_page_size - 1) // resolved_page_size),
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

@router.get("/performance/sku-options")
def sku_options(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    modern_trade = session.scalar(select(ModernTrade).where(ModernTrade.code == "TWD"))
    if modern_trade is None:
        raise HTTPException(status_code=404, detail="ไม่พบ Modern Trade รหัส TWD")

    mapping_reference_date = session.scalar(
        select(func.max(ImportBatch.data_date)).where(
            ImportBatch.modern_trade_id == modern_trade.id,
            ImportBatch.status.in_(("imported", "imported_with_warnings")),
        )
    ) or date.today()
    active_mapping_filters = (
        ItemMapping.modern_trade_id == modern_trade.id,
        ItemMapping.effective_from <= mapping_reference_date,
        (
            ItemMapping.effective_to.is_(None)
            | (ItemMapping.effective_to >= mapping_reference_date)
        ),
    )
    mappings = session.scalars(
        select(ItemMapping)
        .where(
            *active_mapping_filters,
            ItemMapping.report_status == "active",
        )
        .order_by(ItemMapping.source_sku, ItemMapping.effective_from)
    ).all()
    mapping_by_sku = {mapping.source_sku: mapping for mapping in mappings}
    source_by_sku: dict[str, str | None] = {}
    option_skus = set(mapping_by_sku)
    if mapping_by_sku:
        latest_source_rows = session.execute(
            select(
                SalesInventoryFact.source_sku,
                func.min(SalesInventoryFact.source_description),
            )
            .where(
                SalesInventoryFact.data_date == mapping_reference_date,
                SalesInventoryFact.source_sku.in_(tuple(mapping_by_sku)),
            )
            .group_by(SalesInventoryFact.source_sku)
        ).all()
        source_by_sku = {
            sku: description for sku, description in latest_source_rows
        }
    if modern_trade.show_unmatched_items:
        inactive_skus = select(ItemMapping.source_sku).where(
            *active_mapping_filters,
            ItemMapping.report_status == "inactive",
        )
        source_rows = session.execute(
            select(
                SalesInventoryFact.source_sku,
                func.min(SalesInventoryFact.source_description),
            )
            .where(~SalesInventoryFact.source_sku.in_(inactive_skus))
            .group_by(SalesInventoryFact.source_sku)
            .order_by(SalesInventoryFact.source_sku)
        ).all()
        source_by_sku = {sku: description for sku, description in source_rows}
        option_skus.update(source_by_sku)

    return {
        "items": [
            {
                "sku": sku,
                "twdDescription": source_by_sku.get(sku)
                or (mapping_by_sku[sku].source_description if sku in mapping_by_sku else None)
                or "ไม่มีรายละเอียด TWD",
                "waItem": mapping_by_sku[sku].wa_item_code if sku in mapping_by_sku else None,
                "waDescription": mapping_by_sku[sku].wa_item_description
                if sku in mapping_by_sku
                else None,
                "itemType": mapping_by_sku[sku].item_type
                if sku in mapping_by_sku
                else "normal",
            }
            for sku in sorted(option_skus)
        ]
    }

@router.get("/performance/export")
def export_performance(
    session: Annotated[Session, Depends(get_session)],
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    branch_id: Annotated[str | None, Query(max_length=30)] = None,
    branch_ids: Annotated[str | None, Query(max_length=3000)] = None,
    sku_ids: Annotated[str | None, Query(max_length=10000)] = None,
    mapping_status: Annotated[
        Literal["confirmed", "pending", "unmatched"] | None, Query()
    ] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    grain: Annotated[
        Literal["day", "day_total", "month", "branch_month"], Query()
    ] = "day",
    period_month: Annotated[str | None, Query(max_length=7)] = None,
    mode: Annotated[Literal["sales", "inventory"], Query()] = "sales",
    metric: Annotated[
        Literal["amount", "qty", "stockOh", "stockOnOrder"], Query()
    ] = "amount",
    show_descriptions: Annotated[bool, Query()] = True,
) -> StreamingResponse:
    report = performance(
        session=session,
        date_from=date_from,
        date_to=date_to,
        page=1,
        page_size=1_000_000,
        branch_id=branch_id,
        branch_ids=branch_ids,
        sku_ids=sku_ids,
        mapping_status=mapping_status,
        hide_unmapped=False,
        search=search,
        grain=grain,
        period_month=period_month,
    )
    content = build_performance_workbook(
        report,
        mode=mode,
        metric=metric,
        grain=grain,
        show_descriptions=show_descriptions,
        branch_id=branch_id,
        branch_ids=_selected_branch_ids(branch_id, branch_ids),
    )
    filename = performance_export_filename(mode, metric, grain)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )

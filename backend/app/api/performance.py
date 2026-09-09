from calendar import monthrange
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import Integer, case, cast, distinct, func, literal, or_, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.local_time import bangkok_today
from app.models import (
    BranchMapping,
    DailySkuSummary,
    ImportBatch,
    ItemMapping,
    ModernTrade,
    MonthlySalesSummary,
    SalesInventoryFact,
    SkuAnalysisFlag,
)
from app.services.performance_export import (
    build_performance_workbook,
    performance_export_filename,
)

router = APIRouter(prefix="/api", tags=["performance"])
SkuFlagFilter = Literal["all", "flagged", "sho", "pro", "both", "none"]


def _metric_capabilities(mt_code: str) -> dict[str, list[str]]:
    return {
        "sales": ["amount", "qty"],
        "inventory": (
            ["stockOh", "stockOnOrder"]
            if mt_code == "TWD"
            else ["stockOh", "stockValue"]
        ),
    }


def _number(value: Decimal) -> float:
    return float(value)


def _month_bounds(month_key: str) -> tuple[date, date]:
    year, month = (int(part) for part in month_key.split("-"))
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def _normalized_date_ranges(
    date_ranges: list[str] | None,
    date_from: date | None,
    date_to: date | None,
) -> list[tuple[date, date]]:
    if not date_ranges:
        return []
    if date_from is not None or date_to is not None:
        raise HTTPException(
            status_code=422,
            detail="date_range cannot be combined with date_from or date_to",
        )
    if len(date_ranges) > 12:
        raise HTTPException(status_code=422, detail="เลือกช่วงวันที่ได้สูงสุด 12 ช่วง")

    parsed: list[tuple[date, date]] = []
    for index, raw_range in enumerate(date_ranges, start=1):
        parts = [part.strip() for part in raw_range.split(",")]
        if len(parts) != 2 or not all(parts):
            raise HTTPException(
                status_code=422,
                detail=f"ช่วงวันที่ {index} ต้องใช้รูปแบบ YYYY-MM-DD,YYYY-MM-DD",
            )
        try:
            start, end = (date.fromisoformat(part) for part in parts)
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail=f"ช่วงวันที่ {index} ต้องใช้รูปแบบ YYYY-MM-DD,YYYY-MM-DD",
            ) from error
        if start > end:
            raise HTTPException(
                status_code=422,
                detail=f"ช่วงวันที่ {index} วันที่เริ่มต้นต้องไม่เกินวันที่สิ้นสุด",
            )
        parsed.append((start, end))

    parsed.sort(key=lambda value: (value[0], value[1]))
    for index in range(1, len(parsed)):
        if parsed[index][0] <= parsed[index - 1][1]:
            raise HTTPException(
                status_code=422,
                detail=f"ช่วงวันที่ {index} ทับกับช่วงวันที่ {index + 1}",
            )
    return parsed


def _date_in_ranges(value: date, ranges: list[tuple[date, date]]) -> bool:
    return any(start <= value <= end for start, end in ranges)


def _date_range_filter(column, ranges: list[tuple[date, date]]):
    return or_(*(column.between(start, end) for start, end in ranges))


def _previous_three_month_bounds(reference_date: date) -> tuple[date, date]:
    reference_month_index = reference_date.year * 12 + reference_date.month - 1
    first_month_index = reference_month_index - 3
    first_year, first_month_zero = divmod(first_month_index, 12)
    last_month_index = reference_month_index - 1
    last_year, last_month_zero = divmod(last_month_index, 12)
    last_month = last_month_zero + 1
    return (
        date(first_year, first_month_zero + 1, 1),
        date(last_year, last_month, monthrange(last_year, last_month)[1]),
    )


def _turnover_values(stock_on_hand: Decimal, positive_sales_qty: Decimal):
    if stock_on_hand < 0:
        return None
    two_places = Decimal("0.01")
    average_sales = (positive_sales_qty / Decimal("3")).quantize(
        two_places, rounding=ROUND_HALF_UP
    )
    if average_sales == 0:
        return None
    tom = (stock_on_hand / average_sales).quantize(
        two_places, rounding=ROUND_HALF_UP
    )
    tod = (tom * Decimal("30")).quantize(two_places, rounding=ROUND_HALF_UP)
    return tom, tod


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


def _sku_flag_predicate(source_sku, modern_trade_id: int, sku_flag: SkuFlagFilter):
    if sku_flag == "all":
        return None
    matching_flags = select(SkuAnalysisFlag.source_sku).where(
        SkuAnalysisFlag.modern_trade_id == modern_trade_id
    )
    if sku_flag == "flagged":
        return source_sku.in_(
            matching_flags.where(
                or_(
                    SkuAnalysisFlag.is_showroom.is_(True),
                    SkuAnalysisFlag.is_promotion.is_(True),
                )
            )
        )
    if sku_flag == "sho":
        return source_sku.in_(
            matching_flags.where(SkuAnalysisFlag.is_showroom.is_(True))
        )
    if sku_flag == "pro":
        return source_sku.in_(
            matching_flags.where(SkuAnalysisFlag.is_promotion.is_(True))
        )
    if sku_flag == "both":
        return source_sku.in_(
            matching_flags.where(
                SkuAnalysisFlag.is_showroom.is_(True),
                SkuAnalysisFlag.is_promotion.is_(True),
            )
        )
    flagged_skus = matching_flags.where(
        or_(
            SkuAnalysisFlag.is_showroom.is_(True),
            SkuAnalysisFlag.is_promotion.is_(True),
        )
    )
    return ~source_sku.in_(flagged_skus)


def _daily_summary_covers_dates(
    session: Session,
    modern_trade_id: int,
    all_dates: list[date],
) -> bool:
    summary_dates = set(
        session.scalars(
            select(distinct(DailySkuSummary.data_date)).where(
                DailySkuSummary.modern_trade_id == modern_trade_id
            )
        ).all()
    )
    return summary_dates == set(all_dates)


@router.get("/performance")
def performance(
    session: Annotated[Session, Depends(get_session)],
    mt_code: Annotated[Literal["TWD", "HP", "MH"], Query()] = "TWD",
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    date_range: Annotated[list[str] | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int | None, Query(ge=1, le=1_000_000)] = None,
    branch_id: Annotated[str | None, Query(max_length=30)] = None,
    branch_ids: Annotated[str | None, Query(max_length=3000)] = None,
    sku_ids: Annotated[str | None, Query(max_length=10000)] = None,
    sku_flag: Annotated[SkuFlagFilter, Query()] = "all",
    mapping_status: Annotated[Literal["confirmed", "pending", "unmatched"] | None, Query()] = None,
    hide_unmapped: Annotated[bool, Query()] = False,
    search: Annotated[str | None, Query(max_length=200)] = None,
    grain: Annotated[
        Literal["day", "day_total", "month", "branch_month", "branch_range"],
        Query(),
    ] = "day",
    period_month: Annotated[str | None, Query(max_length=7)] = None,
    latest_only: Annotated[bool, Query()] = False,
    sales_basis: Annotated[Literal["net", "gross"], Query()] = "net",
    include_turnover: Annotated[bool, Query()] = False,
    report_mode: Annotated[Literal["sales", "inventory"], Query()] = "sales",
) -> dict:
    modern_trade = session.scalar(select(ModernTrade).where(ModernTrade.code == mt_code))
    if modern_trade is None:
        raise HTTPException(status_code=404, detail=f"ไม่พบ Modern Trade รหัส {mt_code}")
    if sku_flag != "all" and mt_code != "TWD":
        raise HTTPException(
            status_code=422,
            detail="Sho/Pro Prototype รองรับเฉพาะ TWD ใน Phase นี้",
        )
    modern_trade_id = modern_trade.id
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
    selected_ranges = _normalized_date_ranges(date_range, date_from, date_to)
    range_from = (
        selected_ranges[0][0]
        if selected_ranges
        else date_from or min_date or bangkok_today()
    )
    range_to = (
        selected_ranges[-1][1]
        if selected_ranges
        else date_to or max_date or range_from
    )
    selected_snapshot_date = None
    if latest_only:
        eligible_dates = [
            value
            for value in all_dates
            if (
                _date_in_ranges(value, selected_ranges)
                if selected_ranges
                else (date_from is None or value >= date_from)
                and (date_to is None or value <= date_to)
            )
        ]
        selected_snapshot_date = eligible_dates[-1] if eligible_dates else None
        if selected_snapshot_date is not None:
            range_from = selected_snapshot_date
            range_to = selected_snapshot_date
    inventory_month_snapshot_dates: list[date] = []
    if report_mode == "inventory" and grain == "month":
        latest_date_by_month: dict[str, date] = {}
        for value in all_dates:
            if selected_ranges:
                if not _date_in_ranges(value, selected_ranges):
                    continue
            elif (date_from and value < date_from) or (date_to and value > date_to):
                continue
            latest_date_by_month[value.strftime("%Y-%m")] = value
        inventory_month_snapshot_dates = list(latest_date_by_month.values())
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
    requested_page_size = page_size if page_size is not None else modern_trade.report_page_size
    mapping_reference_date = max_date or range_to
    active_mapping_filters = (
        ItemMapping.modern_trade_id == modern_trade_id,
        ItemMapping.effective_from <= mapping_reference_date,
        (
            ItemMapping.effective_to.is_(None)
            | (ItemMapping.effective_to >= mapping_reference_date)
        ),
    )
    active_branch_mapping_filters = (
        BranchMapping.modern_trade_id == modern_trade_id,
        BranchMapping.effective_from <= mapping_reference_date,
        (
            BranchMapping.effective_to.is_(None)
            | (BranchMapping.effective_to >= mapping_reference_date)
        ),
    )
    mapped_skus = select(ItemMapping.source_sku).where(*active_mapping_filters)
    reportable_mapped_skus = mapped_skus.where(ItemMapping.report_status == "active")
    inactive_mapped_skus = mapped_skus.where(ItemMapping.report_status == "inactive")
    mapped_branches = select(BranchMapping.source_branch_code).where(
        *active_branch_mapping_filters
    )
    selected_branch_ids = _selected_branch_ids(branch_id, branch_ids)
    selected_sku_ids = _selected_sku_ids(sku_ids)
    normalized_search = search.strip() if search else ""
    use_daily_summary = (
        grain == "day_total"
        and not latest_only
        and date_from is None
        and date_to is None
        and not selected_ranges
        and not selected_branch_ids
        and not selected_sku_ids
        and mapping_status is None
        and not hide_unmapped
        and not normalized_search
        and not modern_trade.show_unmatched_branches
        and _daily_summary_covers_dates(session, modern_trade_id, all_dates)
    )
    inventory_month_snapshot = report_mode == "inventory" and grain == "month"
    use_monthly_summary = grain in ("month", "branch_month") and not inventory_month_snapshot
    report_model = (
        MonthlySalesSummary
        if use_monthly_summary
        else DailySkuSummary
        if use_daily_summary
        else SalesInventoryFact
    )
    report_date = report_model.month_start if use_monthly_summary else report_model.data_date
    if sales_basis == "gross":
        if use_monthly_summary or use_daily_summary:
            report_amount = report_model.gross_amount
            report_qty = report_model.gross_sales_qty
        else:
            report_amount = case(
                (report_model.amount > 0, report_model.amount), else_=Decimal("0")
            )
            report_qty = case(
                (report_model.sales_qty > 0, report_model.sales_qty),
                else_=Decimal("0"),
            )
    else:
        report_amount = report_model.amount
        report_qty = report_model.sales_qty
    report_stock_oh = getattr(report_model, "stock_on_hand", literal(0))
    report_stock_on_order = getattr(report_model, "stock_on_order", literal(0))
    report_stock_value = getattr(report_model, "stock_value", literal(0))
    filters = [report_model.modern_trade_id == modern_trade_id]
    report_sku_flag_predicate = _sku_flag_predicate(
        report_model.source_sku,
        modern_trade_id,
        sku_flag,
    )
    if report_sku_flag_predicate is not None:
        filters.append(report_sku_flag_predicate)
    filters.append(~report_model.source_sku.in_(inactive_mapped_skus))
    if inventory_month_snapshot:
        filters.append(report_date.in_(inventory_month_snapshot_dates))
    elif latest_only:
        filters.append(
            report_date == selected_snapshot_date
            if selected_snapshot_date is not None
            else report_date.is_(None)
        )
    elif selected_ranges:
        filters.append(_date_range_filter(report_date, selected_ranges))
    else:
        if date_from or grain == "branch_month":
            filters.append(report_date >= range_from)
        if date_to or grain == "branch_month":
            filters.append(report_date <= range_to)
    if not modern_trade.show_unmatched_items or hide_unmapped:
        filters.append(report_model.source_sku.in_(reportable_mapped_skus))
    if not modern_trade.show_unmatched_branches and not use_daily_summary:
        filters.append(report_model.source_branch_code.in_(mapped_branches))
    if selected_branch_ids:
        filters.append(report_model.source_branch_code.in_(selected_branch_ids))
    if selected_sku_ids:
        filters.append(report_model.source_sku.in_(selected_sku_ids))
    if mapping_status:
        if mapping_status == "unmatched":
            filters.append(~report_model.source_sku.in_(reportable_mapped_skus))
        else:
            filters.append(
                report_model.source_sku.in_(
                    reportable_mapped_skus.where(ItemMapping.status == mapping_status)
                )
            )

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
                report_model.source_sku.icontains(normalized_search, autoescape=True),
                report_model.source_description.icontains(normalized_search, autoescape=True),
                report_model.source_sku.in_(wa_matches),
            )
        )
    fact_skus = select(report_model.source_sku).where(*filters)
    mapping_candidate_filters = [
        *active_mapping_filters,
        ItemMapping.report_status == "active",
    ]
    mapping_sku_flag_predicate = _sku_flag_predicate(
        ItemMapping.source_sku,
        modern_trade_id,
        sku_flag,
    )
    if mapping_sku_flag_predicate is not None:
        mapping_candidate_filters.append(mapping_sku_flag_predicate)
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
    elif not modern_trade.show_unmatched_items or hide_unmapped:
        candidate_skus = (
            select(ItemMapping.source_sku)
            .where(*mapping_candidate_filters)
            .distinct()
            .subquery()
        )
    else:
        mapping_skus = select(ItemMapping.source_sku).where(*mapping_candidate_filters)
        candidate_skus = fact_skus.union(mapping_skus).subquery()
    total_skus = session.scalar(select(func.count()).select_from(candidate_skus)) or 0
    resolved_page_size = max(total_skus, 1) if requested_page_size == 0 else requested_page_size
    (
        total_amount,
        total_qty,
        total_stock_oh,
        total_stock_on_order,
        total_stock_value,
    ) = session.execute(
        select(
            func.coalesce(func.sum(report_amount), 0),
            func.coalesce(func.sum(report_qty), 0),
            func.coalesce(func.sum(report_stock_oh), 0),
            func.coalesce(func.sum(report_stock_on_order), 0),
            func.coalesce(func.sum(report_stock_value), 0),
        ).where(*filters)
    ).one()
    active_branch_count = 0
    if use_daily_summary:
        active_branch_filters = [
            MonthlySalesSummary.modern_trade_id == modern_trade_id,
            ~MonthlySalesSummary.source_sku.in_(inactive_mapped_skus),
        ]
        monthly_sku_flag_predicate = _sku_flag_predicate(
            MonthlySalesSummary.source_sku,
            modern_trade_id,
            sku_flag,
        )
        if monthly_sku_flag_predicate is not None:
            active_branch_filters.append(monthly_sku_flag_predicate)
        if not modern_trade.show_unmatched_items:
            active_branch_filters.append(
                MonthlySalesSummary.source_sku.in_(reportable_mapped_skus)
            )
        if not modern_trade.show_unmatched_branches:
            active_branch_filters.append(
                MonthlySalesSummary.source_branch_code.in_(mapped_branches)
            )
        active_branch_count = (
            session.scalar(
                select(
                    func.count(distinct(MonthlySalesSummary.source_branch_code))
                ).where(*active_branch_filters)
            )
            or 0
        )
    else:
        active_branch_count = (
            session.scalar(
                select(func.count(distinct(report_model.source_branch_code))).where(
                    *filters
                )
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
    if grain in ("branch_month", "branch_range", "day"):
        total_rows = session.execute(
            select(
                report_model.source_branch_code,
                func.coalesce(func.sum(report_amount), 0),
                func.coalesce(func.sum(report_qty), 0),
            )
            .where(*filters)
            .group_by(report_model.source_branch_code)
            .order_by(report_model.source_branch_code)
        ).all()
        column_totals = {
            branch_code: {"amount": _number(amount), "qty": _number(qty)}
            for branch_code, amount, qty in total_rows
        }
    elif grain == "month":
        total_year = cast(func.extract("year", report_date), Integer)
        total_month = cast(func.extract("month", report_date), Integer)
        total_rows = session.execute(
            select(
                total_year,
                total_month,
                func.coalesce(func.sum(report_amount), 0),
                func.coalesce(func.sum(report_qty), 0),
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
                report_date,
                func.coalesce(func.sum(report_amount), 0),
                func.coalesce(func.sum(report_qty), 0),
            )
            .where(*filters)
            .group_by(report_date)
            .order_by(report_date)
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
    turnover_by_sku: dict[str, tuple[Decimal, Decimal]] = {}
    average_tom = None
    average_tod = None
    turnover_reference_date = None
    if include_turnover and mt_code == "TWD":
        eligible_reference_dates = [
            value
            for value in all_dates
            if (
                _date_in_ranges(value, selected_ranges)
                if selected_ranges
                else (date_from is None or value >= date_from)
                and (date_to is None or value <= date_to)
            )
        ]
        turnover_reference_date = (
            eligible_reference_dates[-1] if eligible_reference_dates else None
        )
        if turnover_reference_date is not None:
            turnover_skus = select(candidate_skus.c.source_sku)
            sales_from, sales_to = _previous_three_month_bounds(
                turnover_reference_date
            )
            use_turnover_summary = (
                not selected_branch_ids
                and _daily_summary_covers_dates(session, modern_trade_id, all_dates)
            )
            turnover_model = (
                DailySkuSummary if use_turnover_summary else SalesInventoryFact
            )
            stock_filters = [
                turnover_model.modern_trade_id == modern_trade_id,
                turnover_model.data_date == turnover_reference_date,
                turnover_model.source_sku.in_(turnover_skus),
            ]
            sales_filters = [
                turnover_model.modern_trade_id == modern_trade_id,
                turnover_model.data_date.between(sales_from, sales_to),
                turnover_model.source_sku.in_(turnover_skus),
            ]
            sales_qty = (
                DailySkuSummary.gross_sales_qty
                if use_turnover_summary
                else SalesInventoryFact.sales_qty
            )
            if not use_turnover_summary:
                sales_filters.append(SalesInventoryFact.sales_qty > 0)
            if not use_turnover_summary and not modern_trade.show_unmatched_branches:
                stock_filters.append(
                    SalesInventoryFact.source_branch_code.in_(mapped_branches)
                )
                sales_filters.append(
                    SalesInventoryFact.source_branch_code.in_(mapped_branches)
                )
            if not use_turnover_summary and selected_branch_ids:
                stock_filters.append(
                    SalesInventoryFact.source_branch_code.in_(selected_branch_ids)
                )
                sales_filters.append(
                    SalesInventoryFact.source_branch_code.in_(selected_branch_ids)
                )
            stock_rows = session.execute(
                select(
                    turnover_model.source_sku,
                    func.sum(turnover_model.stock_on_hand),
                )
                .where(*stock_filters)
                .group_by(turnover_model.source_sku)
            ).all()
            sales_rows = session.execute(
                select(
                    turnover_model.source_sku,
                    func.sum(sales_qty),
                )
                .where(*sales_filters)
                .group_by(turnover_model.source_sku)
            ).all()
            sales_by_sku = {sku: qty for sku, qty in sales_rows}
            for sku, stock_on_hand in stock_rows:
                values = _turnover_values(
                    stock_on_hand,
                    sales_by_sku.get(sku, Decimal("0")),
                )
                if values is not None:
                    turnover_by_sku[sku] = values
            if turnover_by_sku:
                two_places = Decimal("0.01")
                average_tom = (
                    sum(value[0] for value in turnover_by_sku.values())
                    / Decimal(len(turnover_by_sku))
                ).quantize(two_places, rounding=ROUND_HALF_UP)
                average_tod = (
                    sum(value[1] for value in turnover_by_sku.values())
                    / Decimal(len(turnover_by_sku))
                ).quantize(two_places, rounding=ROUND_HALF_UP)
    facts = []
    daily_rows = []
    monthly_rows = []
    monthly_branch_rows = []
    branch_range_rows = []
    if grain == "day_total":
        daily_rows = session.execute(
            select(
                report_model.source_sku,
                func.min(report_model.source_description),
                report_date,
                func.sum(report_amount),
                func.sum(report_qty),
                func.sum(report_model.stock_on_hand),
                func.sum(report_model.stock_on_order),
                func.sum(report_model.stock_value),
            )
            .where(*filters, report_model.source_sku.in_(skus))
            .group_by(report_model.source_sku, report_date)
            .order_by(report_model.source_sku, report_date)
        ).all()
    elif grain == "month":
        year_part = cast(func.extract("year", report_date), Integer)
        month_part = cast(func.extract("month", report_date), Integer)
        monthly_rows = session.execute(
            select(
                report_model.source_sku,
                func.min(report_model.source_description),
                year_part,
                month_part,
                func.sum(report_amount),
                func.sum(report_qty),
                func.sum(report_stock_oh),
                func.sum(report_stock_on_order),
                func.sum(report_stock_value),
            )
            .where(*filters, report_model.source_sku.in_(skus))
            .group_by(report_model.source_sku, year_part, month_part)
            .order_by(report_model.source_sku, year_part, month_part)
        ).all()
    elif grain == "branch_month":
        monthly_branch_rows = session.execute(
            select(
                report_model.source_sku,
                func.min(report_model.source_description),
                report_model.source_branch_code,
                func.sum(report_amount),
                func.sum(report_qty),
            )
            .where(*filters, report_model.source_sku.in_(skus))
            .group_by(report_model.source_sku, report_model.source_branch_code)
            .order_by(report_model.source_sku, report_model.source_branch_code)
        ).all()
    elif grain == "branch_range":
        branch_range_rows = session.execute(
            select(
                SalesInventoryFact.source_sku,
                func.min(SalesInventoryFact.source_description),
                SalesInventoryFact.source_branch_code,
                func.sum(report_amount),
                func.sum(report_qty),
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
    if modern_trade.show_unmatched_branches:
        branch_report_model = (
            MonthlySalesSummary if use_daily_summary else SalesInventoryFact
        )
        branch_query = select(
            branch_report_model.source_branch_code,
            func.min(branch_report_model.source_branch_name),
        ).where(branch_report_model.modern_trade_id == modern_trade_id)
        branch_rows = session.execute(
            branch_query.group_by(branch_report_model.source_branch_code).order_by(
                branch_report_model.source_branch_code
            )
        ).all()
    else:
        branch_rows = session.execute(
            select(
                MonthlySalesSummary.source_branch_code,
                func.min(MonthlySalesSummary.source_branch_name),
            )
            .where(
                MonthlySalesSummary.modern_trade_id == modern_trade_id,
                MonthlySalesSummary.source_branch_code.in_(mapped_branches),
            )
            .group_by(MonthlySalesSummary.source_branch_code)
            .order_by(MonthlySalesSummary.source_branch_code)
        ).all()
        if not branch_rows:
            branch_rows = session.execute(
                select(
                    SalesInventoryFact.source_branch_code,
                    func.min(SalesInventoryFact.source_branch_name),
                )
                .where(
                    SalesInventoryFact.modern_trade_id == modern_trade_id,
                    SalesInventoryFact.source_branch_code.in_(mapped_branches),
                )
                .group_by(SalesInventoryFact.source_branch_code)
                .order_by(SalesInventoryFact.source_branch_code)
            ).all()
    branch_mappings = session.scalars(
        select(BranchMapping)
        .where(*active_branch_mapping_filters)
        .order_by(BranchMapping.effective_from)
    ).all()
    branch_mapping_by_code = {
        mapping.source_branch_code: mapping for mapping in branch_mappings
    }
    dates = (
        [date.fromisoformat(f"{value}-01") for value in available_months]
        if use_monthly_summary
        else session.scalars(
            select(distinct(report_date))
            .where(*filters)
            .order_by(report_date)
        ).all()
    )
    mappings = session.scalars(
        select(ItemMapping)
        .where(
            ItemMapping.source_sku.in_(skus),
            *active_mapping_filters,
        )
        .order_by(ItemMapping.effective_from)
    ).all()
    mapping_by_sku = {mapping.source_sku: mapping for mapping in mappings}
    analysis_flags_by_sku = {}
    if mt_code == "TWD" and skus:
        analysis_flags = session.scalars(
            select(SkuAnalysisFlag).where(
                SkuAnalysisFlag.modern_trade_id == modern_trade_id,
                SkuAnalysisFlag.source_sku.in_(skus),
            )
        ).all()
        analysis_flags_by_sku = {
            analysis_flag.source_sku: analysis_flag
            for analysis_flag in analysis_flags
        }

    items: dict[str, dict] = {}

    def item_for(source_sku: str, source_description: str | None) -> dict:
        mapping = mapping_by_sku.get(source_sku)
        item = items.get(source_sku)
        if item is None:
            item = {
                "sku": source_sku,
                "twdDescription": source_description
                or (mapping.source_description if mapping else None)
                or f"ไม่มีรายละเอียด {mt_code}",
                "waItem": mapping.wa_item_code if mapping else None,
                "waDescription": mapping.wa_item_description if mapping else None,
                "mappingStatus": mapping.status if mapping else "unmatched",
                "itemType": mapping.item_type if mapping else "normal",
                "points": [],
            }
            if mt_code == "TWD":
                analysis_flag = analysis_flags_by_sku.get(source_sku)
                item["isSho"] = bool(
                    analysis_flag and analysis_flag.is_showroom
                )
                item["isPro"] = bool(
                    analysis_flag and analysis_flag.is_promotion
                )
            if include_turnover and mt_code == "TWD":
                item["tom"] = (
                    _number(turnover_by_sku[source_sku][0])
                    if source_sku in turnover_by_sku
                    else None
                )
                item["tod"] = (
                    _number(turnover_by_sku[source_sku][1])
                    if source_sku in turnover_by_sku
                    else None
                )
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
                "amount": _number(
                    fact.amount
                    if sales_basis == "net" or fact.amount > 0
                    else Decimal("0")
                ),
                "qty": _number(
                    fact.sales_qty
                    if sales_basis == "net" or fact.sales_qty > 0
                    else Decimal("0")
                ),
                "stockOh": _number(fact.stock_on_hand),
                "stockOnOrder": _number(fact.stock_on_order),
                "stockValue": _number(fact.stock_value),
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
        stock_value,
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
                "stockValue": _number(stock_value),
            }
        )

    for (
        source_sku,
        source_description,
        year,
        month,
        amount,
        qty,
        stock_oh,
        stock_on_order,
        stock_value,
    ) in monthly_rows:
        item = item_for(source_sku, source_description)
        item["points"].append(
            {
                "date": f"{year:04d}-{month:02d}",
                "branchId": "all",
                "amount": _number(amount),
                "qty": _number(qty),
                "stockOh": _number(stock_oh),
                "stockOnOrder": _number(stock_on_order),
                "stockValue": _number(stock_value),
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
                "stockValue": 0,
            }
        )

    for source_sku, source_description, source_branch_code, amount, qty in branch_range_rows:
        item = item_for(source_sku, source_description)
        item["points"].append(
            {
                "date": range_to.isoformat(),
                "branchId": source_branch_code,
                "amount": _number(amount),
                "qty": _number(qty),
                "stockOh": 0,
                "stockOnOrder": 0,
                "stockValue": 0,
            }
        )

    latest_import = session.scalar(
        select(ImportBatch)
        .where(ImportBatch.modern_trade_id == modern_trade_id)
        .order_by(ImportBatch.data_date.desc(), ImportBatch.id.desc())
        .limit(1)
    )
    return {
        "mtCode": mt_code,
        "mtName": modern_trade.name,
        "metricCapabilities": _metric_capabilities(mt_code),
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
        "selectedDateRanges": [
            {"from": start.isoformat(), "to": end.isoformat()}
            for start, end in selected_ranges
        ],
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
        "inventorySummary": {
            "stockOh": _number(total_stock_oh),
            "stockOnOrder": _number(total_stock_on_order),
            "stockValue": _number(total_stock_value),
            **(
                {
                    "averageTom": _number(average_tom)
                    if average_tom is not None
                    else None,
                    "averageTod": _number(average_tod)
                    if average_tod is not None
                    else None,
                    "turnoverSkuCount": len(turnover_by_sku),
                    "turnoverReferenceDate": turnover_reference_date.isoformat()
                    if turnover_reference_date
                    else None,
                }
                if include_turnover and mt_code == "TWD"
                else {}
            ),
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
    mt_code: Annotated[Literal["TWD", "HP", "MH"], Query()] = "TWD",
) -> dict:
    modern_trade = session.scalar(select(ModernTrade).where(ModernTrade.code == mt_code))
    if modern_trade is None:
        raise HTTPException(status_code=404, detail=f"ไม่พบ Modern Trade รหัส {mt_code}")

    mapping_reference_date = session.scalar(
        select(func.max(ImportBatch.data_date)).where(
            ImportBatch.modern_trade_id == modern_trade.id,
            ImportBatch.status.in_(("imported", "imported_with_warnings")),
        )
    ) or bangkok_today()
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
                SalesInventoryFact.modern_trade_id == modern_trade.id,
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
            .where(
                SalesInventoryFact.modern_trade_id == modern_trade.id,
                ~SalesInventoryFact.source_sku.in_(inactive_skus),
            )
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
                or f"ไม่มีรายละเอียด {mt_code}",
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
    mt_code: Annotated[Literal["TWD", "HP", "MH"], Query()] = "TWD",
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    date_range: Annotated[list[str] | None, Query()] = None,
    branch_id: Annotated[str | None, Query(max_length=30)] = None,
    branch_ids: Annotated[str | None, Query(max_length=3000)] = None,
    sku_ids: Annotated[str | None, Query(max_length=10000)] = None,
    sku_flag: Annotated[SkuFlagFilter, Query()] = "all",
    mapping_status: Annotated[
        Literal["confirmed", "pending", "unmatched"] | None, Query()
    ] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    grain: Annotated[
        Literal["day", "day_total", "month", "branch_month", "branch_range"], Query()
    ] = "day",
    period_month: Annotated[str | None, Query(max_length=7)] = None,
    mode: Annotated[Literal["sales", "inventory"], Query()] = "sales",
    metric: Annotated[
        Literal["amount", "qty", "stockOh", "stockOnOrder", "stockValue"], Query()
    ] = "amount",
    show_descriptions: Annotated[bool, Query()] = True,
    latest_only: Annotated[bool, Query()] = False,
    sales_basis: Annotated[Literal["net", "gross"], Query()] = "net",
) -> StreamingResponse:
    if metric not in _metric_capabilities(mt_code)[mode]:
        raise HTTPException(
            status_code=422,
            detail=f"Metric {metric} ไม่มีในข้อมูล {mt_code} สำหรับโหมด {mode}",
        )
    report = performance(
        session=session,
        mt_code=mt_code,
        date_from=date_from,
        date_to=date_to,
        date_range=date_range,
        page=1,
        page_size=1_000_000,
        branch_id=branch_id,
        branch_ids=branch_ids,
        sku_ids=sku_ids,
        sku_flag=sku_flag,
        mapping_status=mapping_status,
        hide_unmapped=False,
        search=search,
        grain=grain,
        period_month=period_month,
        latest_only=latest_only,
        sales_basis=sales_basis,
        include_turnover=mode == "inventory",
        report_mode=mode,
    )
    content = build_performance_workbook(
        report,
        mode=mode,
        metric=metric,
        grain=grain,
        show_descriptions=show_descriptions,
        branch_id=branch_id,
        branch_ids=_selected_branch_ids(branch_id, branch_ids),
        sales_basis=sales_basis,
        mt_code=mt_code,
    )
    filename = performance_export_filename(
        mode, metric, grain, sales_basis=sales_basis, mt_code=mt_code
    )
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )

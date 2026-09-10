from calendar import monthrange
from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, distinct, func, select
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.database import get_session
from app.models import BranchMapping, ImportBatch, ModernTrade, MonthlySalesSummary
from app.services.dashboard_export import (
    build_dashboard_workbook,
    dashboard_export_filename,
)

router = APIRouter(prefix="/api/dashboards", tags=["dashboards"])
AVAILABLE_STATUSES = ("imported", "imported_with_warnings")
Period = Literal["ytd", "h1", "h2", "full"]


def _number(value: Decimal | int | float | None) -> float:
    return float(value or 0)


def _change(current: Decimal, previous: Decimal) -> float | None:
    if previous == 0:
        return None
    return float(((current - previous) / previous) * 100)


def _period_months(period: Period, selected_year: int, latest_date: date) -> list[int]:
    start, end = {
        "ytd": (1, 12),
        "h1": (1, 6),
        "h2": (7, 12),
        "full": (1, 12),
    }[period]
    if selected_year == latest_date.year and period != "full":
        end = min(end, latest_date.month)
    return list(range(start, end + 1)) if end >= start else []


def _dashboard(
    code: str,
    session: Annotated[Session, Depends(get_session)],
    year: Annotated[int | None, Query(ge=2025, le=9999)] = None,
    period: Annotated[Period, Query()] = "ytd",
) -> dict:
    modern_trade = session.execute(
        select(ModernTrade.id, ModernTrade.code, ModernTrade.name).where(
            ModernTrade.code == code
        )
    ).one_or_none()
    if modern_trade is None:
        raise HTTPException(status_code=404, detail=f"ไม่พบ Modern Trade รหัส {code}")

    batch_filter = (
        ImportBatch.modern_trade_id == modern_trade.id,
        ImportBatch.status.in_(AVAILABLE_STATUSES),
    )
    latest_date = session.scalar(select(func.max(ImportBatch.data_date)).where(*batch_filter))
    if latest_date is None:
        return {
            "meta": {
                "mtCode": modern_trade.code,
                "mtName": modern_trade.name,
                "year": year,
                "previousYear": year - 1 if year else None,
                "period": period,
                "latestDataDate": None,
                "availableYears": [],
                "loadedDays": 0,
                "expectedDays": 0,
                "completenessPercent": 0,
            },
            "summary": None,
            "monthly": [],
            "topBranches": [],
            "topSkus": [],
        }

    batch_year = func.extract("year", ImportBatch.data_date)
    available_years = [
        int(value)
        for value in session.scalars(
            select(batch_year)
            .where(*batch_filter)
            .distinct()
            .order_by(batch_year)
        ).all()
    ]
    selected_year = year or latest_date.year
    if selected_year not in available_years:
        raise HTTPException(status_code=422, detail=f"ปีที่เลือกยังไม่มีข้อมูล {code}")

    months = _period_months(period, selected_year, latest_date)
    previous_year = selected_year - 1
    summary_year = func.extract("year", MonthlySalesSummary.month_start)
    summary_month = func.extract("month", MonthlySalesSummary.month_start)
    summary_filters = (
        MonthlySalesSummary.modern_trade_id == modern_trade.id,
        summary_year.in_((selected_year, previous_year)),
        summary_month.in_(months or [-1]),
    )
    monthly_rows = session.execute(
        select(
            summary_year,
            summary_month,
            func.sum(MonthlySalesSummary.amount),
            func.sum(MonthlySalesSummary.sales_qty),
        )
        .where(*summary_filters)
        .group_by(summary_year, summary_month)
    ).all()
    monthly_amount = {
        (int(row_year), int(month)): amount
        for row_year, month, amount, _ in monthly_rows
    }
    monthly_qty = {
        (int(row_year), int(month)): qty
        for row_year, month, _, qty in monthly_rows
    }

    current_amount_sum = func.sum(
        case((summary_year == selected_year, MonthlySalesSummary.amount), else_=0)
    )
    previous_amount_sum = func.sum(
        case((summary_year == previous_year, MonthlySalesSummary.amount), else_=0)
    )
    current_qty_sum = func.sum(
        case((summary_year == selected_year, MonthlySalesSummary.sales_qty), else_=0)
    )
    previous_qty_sum = func.sum(
        case((summary_year == previous_year, MonthlySalesSummary.sales_qty), else_=0)
    )

    branch_rows = session.execute(
        select(
            MonthlySalesSummary.source_branch_code,
            func.max(MonthlySalesSummary.source_branch_name),
            current_amount_sum.label("current_amount"),
            previous_amount_sum.label("previous_amount"),
            current_qty_sum.label("current_qty"),
            previous_qty_sum.label("previous_qty"),
        )
        .where(*summary_filters)
        .group_by(MonthlySalesSummary.source_branch_code)
        .order_by(current_amount_sum.desc())
        .limit(10)
    ).all()
    sku_rows = session.execute(
        select(
            MonthlySalesSummary.source_sku,
            func.max(MonthlySalesSummary.source_description),
            current_amount_sum.label("current_amount"),
            previous_amount_sum.label("previous_amount"),
            current_qty_sum.label("current_qty"),
            previous_qty_sum.label("previous_qty"),
        )
        .where(*summary_filters)
        .group_by(MonthlySalesSummary.source_sku)
        .order_by(current_amount_sum.desc())
        .limit(15)
    ).all()
    branch_codes = [row[0] for row in branch_rows]
    branch_mappings = session.scalars(
        select(BranchMapping)
        .where(
            BranchMapping.modern_trade_id == modern_trade.id,
            BranchMapping.source_branch_code.in_(branch_codes or [""]),
            BranchMapping.effective_from <= latest_date,
            (
                BranchMapping.effective_to.is_(None)
                | (BranchMapping.effective_to >= latest_date)
            ),
        )
        .order_by(BranchMapping.effective_from)
    ).all()
    branch_mapping_by_code = {
        mapping.source_branch_code: mapping for mapping in branch_mappings
    }

    monthly = []
    prior_current_amount: Decimal | None = None
    for month in months:
        current_available = (
            selected_year != latest_date.year or month <= latest_date.month
        )
        current_amount = monthly_amount.get((selected_year, month), Decimal(0))
        previous_amount = monthly_amount.get((previous_year, month), Decimal(0))
        current_qty = monthly_qty.get((selected_year, month), Decimal(0))
        previous_qty = monthly_qty.get((previous_year, month), Decimal(0))
        monthly.append(
            {
                "month": month,
                "monthKey": f"{selected_year}-{month:02d}",
                "currentAvailable": current_available,
                "currentAmount": _number(current_amount),
                "previousAmount": _number(previous_amount),
                "amountYoY": (
                    _change(current_amount, previous_amount)
                    if current_available
                    else None
                ),
                "amountMoM": (
                    _change(current_amount, prior_current_amount)
                    if current_available and prior_current_amount is not None
                    else None
                ),
                "currentQty": _number(current_qty),
                "previousQty": _number(previous_qty),
                "qtyYoY": (
                    _change(current_qty, previous_qty) if current_available else None
                ),
            }
        )
        if current_available:
            prior_current_amount = current_amount

    current_amount = sum(
        (monthly_amount.get((selected_year, month), Decimal(0)) for month in months),
        Decimal(0),
    )
    previous_amount = sum(
        (monthly_amount.get((previous_year, month), Decimal(0)) for month in months),
        Decimal(0),
    )
    current_qty = sum(
        (monthly_qty.get((selected_year, month), Decimal(0)) for month in months),
        Decimal(0),
    )
    previous_qty = sum(
        (monthly_qty.get((previous_year, month), Decimal(0)) for month in months),
        Decimal(0),
    )

    def ranking_item(identity: str, name: str | None, values: tuple, sku: bool) -> dict:
        current, previous, current_qty_value, previous_qty_value = values
        item = {
            "currentAmount": _number(current),
            "previousAmount": _number(previous),
            "currentQty": _number(current_qty_value),
            "previousQty": _number(previous_qty_value),
            "amountYoY": _change(current, previous),
            "qtyYoY": _change(current_qty_value, previous_qty_value),
        }
        if sku:
            return {"sku": identity, "description": name or "ไม่ระบุชื่อสินค้า", **item}
        mapping = branch_mapping_by_code.get(identity)
        branch_name = (
            mapping.wa_branch_description
            if mapping and mapping.wa_branch_description
            else name or identity
        )
        mapped_code = mapping.wa_branch_code if mapping else None
        display_name = f"{identity} - {branch_name}"
        if mapped_code:
            display_name += f" ({mapped_code})"
        return {
            "branchCode": identity,
            "branchName": branch_name,
            "mappedBranchCode": mapped_code,
            "displayName": display_name,
            **item,
        }

    top_branches = [
        ranking_item(code, name, (current, previous, current_qty_value, previous_qty_value), False)
        for code, name, current, previous, current_qty_value, previous_qty_value in branch_rows
    ]
    top_skus = [
        ranking_item(code, name, (current, previous, current_qty_value, previous_qty_value), True)
        for code, name, current, previous, current_qty_value, previous_qty_value in sku_rows
    ]

    if months:
        range_from = date(selected_year, months[0], 1)
        period_end = date(
            selected_year,
            months[-1],
            monthrange(selected_year, months[-1])[1],
        )
        range_to = (
            min(latest_date, period_end)
            if selected_year == latest_date.year and period != "full"
            else period_end
        )
        loaded_days = session.scalar(
            select(func.count(distinct(ImportBatch.data_date))).where(
                *batch_filter,
                ImportBatch.data_date >= range_from,
                ImportBatch.data_date <= range_to,
            )
        ) or 0
        expected_days = (range_to - range_from).days + 1
    else:
        range_from = None
        range_to = None
        loaded_days = 0
        expected_days = 0

    return {
        "meta": {
            "mtCode": modern_trade.code,
            "mtName": modern_trade.name,
            "year": selected_year,
            "previousYear": previous_year,
            "period": period,
            "rangeFrom": range_from,
            "rangeTo": range_to,
            "latestDataDate": latest_date,
            "availableYears": available_years,
            "loadedDays": loaded_days,
            "expectedDays": expected_days,
            "completenessPercent": round((loaded_days / expected_days) * 100, 1)
            if expected_days
            else 0,
        },
        "summary": {
            "currentAmount": _number(current_amount),
            "previousAmount": _number(previous_amount),
            "amountYoY": _change(current_amount, previous_amount),
            "currentQty": _number(current_qty),
            "previousQty": _number(previous_qty),
            "qtyYoY": _change(current_qty, previous_qty),
        },
        "monthly": monthly,
        "topBranches": top_branches,
        "topSkus": top_skus,
    }


@router.get("/twd")
def twd_dashboard(
    session: Annotated[Session, Depends(get_session)],
    year: Annotated[int | None, Query(ge=2025, le=9999)] = None,
    period: Annotated[Period, Query()] = "ytd",
) -> dict:
    return _dashboard("TWD", session, year, period)


@router.get("/{code}")
def modern_trade_dashboard(
    code: str,
    session: Annotated[Session, Depends(get_session)],
    year: Annotated[int | None, Query(ge=2025, le=9999)] = None,
    period: Annotated[Period, Query()] = "ytd",
) -> dict:
    normalized = code.strip().upper()
    if normalized not in {"HP", "MH"}:
        raise HTTPException(status_code=404, detail=f"ไม่รองรับ Dashboard {normalized}")
    return _dashboard(normalized, session, year, period)


@router.get("/{code}/export")
def export_modern_trade_dashboard(
    code: str,
    session: Annotated[Session, Depends(get_session)],
    year: Annotated[int | None, Query(ge=2025, le=9999)] = None,
    period: Annotated[Period, Query()] = "ytd",
    metric: Annotated[Literal["amount", "qty"], Query()] = "amount",
) -> StreamingResponse:
    normalized = code.strip().upper()
    if normalized not in {"TWD", "HP", "MH"}:
        raise HTTPException(status_code=404, detail=f"ไม่รองรับ Dashboard {normalized}")
    report = _dashboard(normalized, session, year, period)
    selected_year = report["meta"]["year"]
    if selected_year is None:
        raise HTTPException(status_code=422, detail=f"ยังไม่มีข้อมูล Dashboard {normalized}")
    content = build_dashboard_workbook(report, metric=metric)
    filename = dashboard_export_filename(
        normalized,
        selected_year,
        period,
        metric,
    )
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )

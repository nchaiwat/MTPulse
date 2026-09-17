from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DailySkuSummary, ImportBatch, ModernTrade, MonthlySalesSummary
from app.modern_trade_registry import active_modern_trade_codes
from app.sales_grain import SALES_GRAIN_DAILY
from app.services.sale_out import (
    ACTIVE_CUTOFF_KEY,
    AVAILABLE_BATCH_STATUSES,
    average_price,
    comparison_period_end,
    growth_percent,
)
from app.services.telegram import setting_value

SalesBasis = Literal["net", "gross"]
Metric = Literal["amount", "qty", "average_price"]
DataState = Literal["value", "zero", "missing", "future", "unavailable", "incomplete"]


class SaleOutReportError(ValueError):
    pass


@dataclass(frozen=True)
class Totals:
    amount: Decimal = Decimal("0")
    qty: Decimal = Decimal("0")
    gross_amount: Decimal = Decimal("0")
    gross_qty: Decimal = Decimal("0")

    def __add__(self, other: Totals) -> Totals:
        return Totals(
            amount=self.amount + other.amount,
            qty=self.qty + other.qty,
            gross_amount=self.gross_amount + other.gross_amount,
            gross_qty=self.gross_qty + other.gross_qty,
        )


@dataclass(frozen=True)
class MetricResult:
    state: DataState
    value: Decimal | None
    totals: Totals = Totals()


@dataclass
class SaleOutCube:
    monthly: dict[tuple[int, date], Totals]
    daily: dict[tuple[int, date], Totals]
    valid_days: dict[int, set[date]]
    latest_source: dict[int, date]
    latest_daily: dict[int, date]


def _totals(values: tuple[Decimal | None, ...]) -> Totals:
    return Totals(*(value or Decimal("0") for value in values))


def _load_cube(
    session: Session,
    modern_trade_ids: list[int],
    first_year: int,
    last_year: int,
) -> SaleOutCube:
    if not modern_trade_ids:
        return SaleOutCube({}, {}, {}, {}, {})
    range_from = date(first_year, 1, 1)
    range_to = date(last_year, 12, 31)
    monthly_rows = session.execute(
        select(
            MonthlySalesSummary.modern_trade_id,
            MonthlySalesSummary.month_start,
            func.sum(MonthlySalesSummary.amount),
            func.sum(MonthlySalesSummary.sales_qty),
            func.sum(MonthlySalesSummary.gross_amount),
            func.sum(MonthlySalesSummary.gross_sales_qty),
        )
        .where(
            MonthlySalesSummary.modern_trade_id.in_(modern_trade_ids),
            MonthlySalesSummary.month_start >= range_from,
            MonthlySalesSummary.month_start <= range_to,
        )
        .group_by(
            MonthlySalesSummary.modern_trade_id,
            MonthlySalesSummary.month_start,
        )
    ).all()
    daily_rows = session.execute(
        select(
            DailySkuSummary.modern_trade_id,
            DailySkuSummary.data_date,
            func.sum(DailySkuSummary.amount),
            func.sum(DailySkuSummary.sales_qty),
            func.sum(DailySkuSummary.gross_amount),
            func.sum(DailySkuSummary.gross_sales_qty),
        )
        .where(
            DailySkuSummary.modern_trade_id.in_(modern_trade_ids),
            DailySkuSummary.data_date >= range_from,
            DailySkuSummary.data_date <= range_to,
        )
        .group_by(DailySkuSummary.modern_trade_id, DailySkuSummary.data_date)
    ).all()
    batches = session.scalars(
        select(ImportBatch)
        .where(ImportBatch.modern_trade_id.in_(modern_trade_ids))
        .order_by(ImportBatch.data_date)
    ).all()
    valid_days = {modern_trade_id: set() for modern_trade_id in modern_trade_ids}
    latest_source: dict[int, date] = {}
    latest_daily: dict[int, date] = {}
    for batch in batches:
        latest_source[batch.modern_trade_id] = max(
            latest_source.get(batch.modern_trade_id, batch.data_date),
            batch.data_date,
        )
        valid = (
            batch.status in AVAILABLE_BATCH_STATUSES
            and batch.sales_grain == SALES_GRAIN_DAILY
            and (
                not batch.reconciliation_errors
                or batch.warning_resolution == "acknowledged"
            )
        )
        if not valid:
            continue
        latest_daily[batch.modern_trade_id] = max(
            latest_daily.get(batch.modern_trade_id, batch.data_date),
            batch.data_date,
        )
        valid_days[batch.modern_trade_id].add(batch.data_date)
    return SaleOutCube(
        monthly={
            (modern_trade_id, month_start): _totals(values)
            for modern_trade_id, month_start, *values in monthly_rows
        },
        daily={
            (modern_trade_id, data_date): _totals(values)
            for modern_trade_id, data_date, *values in daily_rows
        },
        valid_days=valid_days,
        latest_source=latest_source,
        latest_daily=latest_daily,
    )


def _metric_value(totals: Totals, basis: SalesBasis, metric: Metric) -> Decimal | None:
    amount = totals.gross_amount if basis == "gross" else totals.amount
    qty = totals.gross_qty if basis == "gross" else totals.qty
    if metric == "amount":
        return amount
    if metric == "qty":
        return qty
    return average_price(amount, qty)


def _month_end(value: date) -> date:
    return value.replace(day=monthrange(value.year, value.month)[1])


def _next_month(value: date) -> date:
    return date(value.year + (value.month == 12), value.month % 12 + 1, 1)


def _range_result(
    modern_trade: ModernTrade,
    cube: SaleOutCube,
    range_from: date,
    range_to: date,
    basis: SalesBasis,
    metric: Metric,
) -> MetricResult:
    start_date = modern_trade.sale_out_start_date
    if start_date is None or start_date > range_to:
        return MetricResult("unavailable", None)
    effective_from = max(range_from, start_date)
    expected_days = (range_to - effective_from).days + 1
    covered_days = sum(
        1
        for offset in range(expected_days)
        if effective_from + timedelta(days=offset)
        in cube.valid_days.get(modern_trade.id, set())
    )
    if covered_days == 0:
        return MetricResult("missing", None)
    if covered_days < expected_days:
        return MetricResult("incomplete", None)
    totals = Totals()
    cursor = effective_from
    while cursor <= range_to:
        segment_end = min(_month_end(cursor), range_to)
        if cursor.day == 1 and segment_end == _month_end(cursor):
            totals += cube.monthly.get(
                (modern_trade.id, cursor.replace(day=1)),
                Totals(),
            )
        else:
            day = cursor
            while day <= segment_end:
                totals += cube.daily.get((modern_trade.id, day), Totals())
                day += timedelta(days=1)
        cursor = _next_month(cursor)
    value = _metric_value(totals, basis, metric)
    if value is None:
        return MetricResult("unavailable", None, totals)
    return MetricResult("zero" if value == 0 else "value", value, totals)


def _total_result(results: list[MetricResult], basis: SalesBasis, metric: Metric) -> MetricResult:
    applicable = [
        result
        for result in results
        if result.state != "unavailable" or result.totals != Totals()
    ]
    if not applicable:
        return MetricResult("unavailable", None)
    if any(result.state == "missing" for result in applicable):
        return MetricResult("missing", None)
    if any(result.state == "incomplete" for result in applicable):
        return MetricResult("incomplete", None)
    totals = sum((result.totals for result in applicable), Totals())
    value = _metric_value(totals, basis, metric)
    if value is None:
        return MetricResult("unavailable", None, totals)
    return MetricResult("zero" if value == 0 else "value", value, totals)


def _payload(result: MetricResult) -> dict:
    return {
        "state": result.state,
        "value": float(result.value) if result.value is not None else None,
    }


def _difference(comparison: MetricResult, base: MetricResult) -> float | None:
    if comparison.value is None or base.value is None:
        return None
    return float(comparison.value - base.value)


def _growth(comparison: MetricResult, base: MetricResult) -> float | None:
    if comparison.value is None or base.value is None:
        return None
    value = growth_percent(comparison.value, base.value)
    return float(value) if value is not None else None


def _included(modern_trades: list[ModernTrade]) -> list[ModernTrade]:
    return [
        modern_trade
        for modern_trade in modern_trades
        if modern_trade.sale_out_include_in_total
        and modern_trade.sale_out_start_date is not None
    ]


def _total_for_range(
    modern_trades: list[ModernTrade],
    cube: SaleOutCube,
    range_from: date,
    range_to: date,
    basis: SalesBasis,
    metric: Metric,
) -> MetricResult:
    return _total_result(
        [
            _range_result(modern_trade, cube, range_from, range_to, basis, metric)
            for modern_trade in _included(modern_trades)
        ],
        basis,
        metric,
    )


def _period_row(
    code: str,
    range_start_month: int,
    range_end_month: int,
    modern_trades: list[ModernTrade],
    cube: SaleOutCube,
    base_year: int,
    comparison_year: int,
    cutoff: date,
    basis: SalesBasis,
    metric: Metric,
) -> dict:
    cutoff_month = cutoff.month
    base_start = date(base_year, range_start_month, 1)
    if code == "QTD":
        base_end = comparison_period_end(cutoff, base_year)
        comparison_end = comparison_period_end(cutoff, comparison_year)
    else:
        base_end = date(
            base_year,
            range_end_month,
            monthrange(base_year, range_end_month)[1],
        )
        comparison_end = date(
            comparison_year,
            range_end_month,
            monthrange(comparison_year, range_end_month)[1],
        )
    base = _total_for_range(
        modern_trades,
        cube,
        base_start,
        base_end,
        basis,
        metric,
    )
    mapped_cutoff = comparison_period_end(cutoff, comparison_year)
    if range_start_month > cutoff_month or (
        code != "QTD" and comparison_end > mapped_cutoff
    ):
        future = MetricResult("future", None)
        return {
            "code": code,
            "base": _payload(base),
            "comparison": _payload(future),
            "growthPercent": None,
        }
    comparison = _total_for_range(
        modern_trades,
        cube,
        date(comparison_year, range_start_month, 1),
        comparison_end,
        basis,
        metric,
    )
    return {
        "code": code,
        "base": _payload(base),
        "comparison": _payload(comparison),
        "growthPercent": _growth(comparison, base),
    }


def build_sale_out_report(
    session: Session,
    *,
    base_year: int,
    comparison_year: int,
    cutoff: date | None,
    sales_basis: SalesBasis,
    metric: Metric,
    mt_codes: list[str] | None,
) -> dict:
    if base_year == comparison_year:
        raise SaleOutReportError("ปีฐานและปีเปรียบเทียบต้องไม่ซ้ำกัน")
    active_value = setting_value(session, ACTIVE_CUTOFF_KEY)
    if not active_value:
        raise SaleOutReportError("ยังไม่มี Active Common Cut-off สำหรับ Sale Out")
    active_cutoff = date.fromisoformat(active_value)
    selected_cutoff = cutoff or active_cutoff
    if selected_cutoff > active_cutoff:
        raise SaleOutReportError("Historical Cut-off ต้องไม่เกิน Active Common Cut-off")

    supported_codes = active_modern_trade_codes("settings")
    explicit_codes = mt_codes is not None
    requested_codes = (
        [code.strip().upper() for code in mt_codes]
        if explicit_codes
        else sorted(supported_codes)
    )
    invalid_codes = sorted(set(requested_codes) - supported_codes)
    if invalid_codes:
        raise SaleOutReportError(
            f"ไม่รองรับ Modern Trade รหัส {', '.join(invalid_codes)}"
        )
    modern_trades = session.scalars(
        select(ModernTrade)
        .where(ModernTrade.code.in_(requested_codes))
        .order_by(ModernTrade.code)
    ).all()
    found_codes = {modern_trade.code for modern_trade in modern_trades}
    missing_codes = sorted(set(requested_codes) - found_codes)
    if explicit_codes and missing_codes:
        raise SaleOutReportError(f"ไม่พบ Modern Trade รหัส {', '.join(missing_codes)}")

    comparison_end = comparison_period_end(selected_cutoff, comparison_year)
    base_end = comparison_period_end(selected_cutoff, base_year)
    previous_month_end = comparison_end.replace(day=1) - timedelta(days=1)
    previous_month_start = previous_month_end.replace(day=1)
    if comparison_end.day < monthrange(comparison_year, comparison_end.month)[1]:
        previous_month_end = previous_month_end.replace(
            day=min(comparison_end.day, previous_month_end.day)
        )
    first_year = min(base_year, comparison_year, previous_month_end.year)
    last_year = max(base_year, comparison_year)
    cube = _load_cube(
        session,
        [modern_trade.id for modern_trade in modern_trades],
        first_year,
        last_year,
    )

    base_ytd = _total_for_range(
        modern_trades, cube, date(base_year, 1, 1), base_end, sales_basis, metric
    )
    comparison_ytd = _total_for_range(
        modern_trades,
        cube,
        date(comparison_year, 1, 1),
        comparison_end,
        sales_basis,
        metric,
    )

    monthly: list[dict] = []
    member_monthly: dict[str, list[dict]] = {
        modern_trade.code: [] for modern_trade in modern_trades
    }
    for month in range(1, 13):
        base_month_from = date(base_year, month, 1)
        base_month_to = _month_end(base_month_from)
        comparison_month_from = date(comparison_year, month, 1)
        if month > selected_cutoff.month:
            comparison_total = MetricResult("future", None)
            comparison_members = {
                modern_trade.code: MetricResult("future", None)
                for modern_trade in modern_trades
            }
        else:
            comparison_month_to = (
                comparison_end
                if month == selected_cutoff.month
                else _month_end(comparison_month_from)
            )
            comparison_members = {
                modern_trade.code: (
                    _range_result(
                        modern_trade,
                        cube,
                        comparison_month_from,
                        comparison_month_to,
                        sales_basis,
                        metric,
                    )
                    if modern_trade.sale_out_include_in_total
                    else MetricResult("unavailable", None)
                )
                for modern_trade in modern_trades
            }
            comparison_total = _total_result(
                [
                    comparison_members[modern_trade.code]
                    for modern_trade in _included(modern_trades)
                ],
                sales_basis,
                metric,
            )
        base_members = {
            modern_trade.code: (
                _range_result(
                    modern_trade,
                    cube,
                    base_month_from,
                    base_month_to,
                    sales_basis,
                    metric,
                )
                if modern_trade.sale_out_include_in_total
                else MetricResult("unavailable", None)
            )
            for modern_trade in modern_trades
        }
        base_total = _total_result(
            [base_members[modern_trade.code] for modern_trade in _included(modern_trades)],
            sales_basis,
            metric,
        )
        monthly.append(
            {
                "month": month,
                "base": _payload(base_total),
                "comparison": _payload(comparison_total),
                "growthPercent": _growth(comparison_total, base_total),
            }
        )
        for modern_trade in modern_trades:
            base_member = base_members[modern_trade.code]
            comparison_member = comparison_members[modern_trade.code]
            member_monthly[modern_trade.code].append(
                {
                    "month": month,
                    "base": _payload(base_member),
                    "comparison": _payload(comparison_member),
                    "growthPercent": _growth(comparison_member, base_member),
                }
            )

    modern_trade_rows = []
    for modern_trade in modern_trades:
        included = modern_trade.sale_out_include_in_total
        member_base = (
            _range_result(
                modern_trade,
                cube,
                date(base_year, 1, 1),
                base_end,
                sales_basis,
                metric,
            )
            if included
            else MetricResult("unavailable", None)
        )
        member_comparison = (
            _range_result(
                modern_trade,
                cube,
                date(comparison_year, 1, 1),
                comparison_end,
                sales_basis,
                metric,
            )
            if included
            else MetricResult("unavailable", None)
        )
        member_latest = (
            _range_result(
                modern_trade,
                cube,
                comparison_end.replace(day=1),
                comparison_end,
                sales_basis,
                metric,
            )
            if included
            else MetricResult("unavailable", None)
        )
        member_yoy_end = comparison_period_end(comparison_end, base_year)
        member_yoy = (
            _range_result(
                modern_trade,
                cube,
                member_yoy_end.replace(day=1),
                member_yoy_end,
                sales_basis,
                metric,
            )
            if included
            else MetricResult("unavailable", None)
        )
        member_mom = (
            _range_result(
                modern_trade,
                cube,
                previous_month_start,
                previous_month_end,
                sales_basis,
                metric,
            )
            if included
            else MetricResult("unavailable", None)
        )
        status = (
            "excluded"
            if not included
            else "missing_start_date"
            if modern_trade.sale_out_start_date is None
            else member_comparison.state
            if member_comparison.state in {"missing", "incomplete", "unavailable"}
            else "ready"
        )
        modern_trade_rows.append(
            {
                "code": modern_trade.code,
                "name": modern_trade.name,
                "status": status,
                "includedInTotal": included,
                "startDate": modern_trade.sale_out_start_date,
                "latestSourceDate": cube.latest_source.get(modern_trade.id),
                "latestDailyDate": cube.latest_daily.get(modern_trade.id),
                "baseYtd": _payload(member_base),
                "comparisonYtd": _payload(member_comparison),
                "difference": _difference(member_comparison, member_base),
                "growthPercent": _growth(member_comparison, member_base),
                "latestMonth": _payload(member_latest),
                "momPercent": _growth(member_latest, member_mom),
                "yoyPercent": _growth(member_latest, member_yoy),
                "monthly": member_monthly[modern_trade.code],
            }
        )

    latest_month_start = comparison_end.replace(day=1)
    latest_month = _total_for_range(
        modern_trades,
        cube,
        latest_month_start,
        comparison_end,
        sales_basis,
        metric,
    )
    yoy_end = comparison_period_end(comparison_end, base_year)
    yoy = _total_for_range(
        modern_trades,
        cube,
        yoy_end.replace(day=1),
        yoy_end,
        sales_basis,
        metric,
    )
    mom = _total_for_range(
        modern_trades,
        cube,
        previous_month_start,
        previous_month_end,
        sales_basis,
        metric,
    )

    quarter_start = ((selected_cutoff.month - 1) // 3) * 3 + 1
    periods = [
        _period_row(
            "Q1", 1, 3, modern_trades, cube, base_year, comparison_year,
            selected_cutoff, sales_basis, metric,
        ),
        _period_row(
            "Q2", 4, 6, modern_trades, cube, base_year, comparison_year,
            selected_cutoff, sales_basis, metric,
        ),
        _period_row(
            "H1", 1, 6, modern_trades, cube, base_year, comparison_year,
            selected_cutoff, sales_basis, metric,
        ),
        _period_row(
            "QTD", quarter_start, selected_cutoff.month, modern_trades, cube,
            base_year, comparison_year, selected_cutoff, sales_basis, metric,
        ),
        {
            "code": "YTD",
            "base": _payload(base_ytd),
            "comparison": _payload(comparison_ytd),
            "growthPercent": _growth(comparison_ytd, base_ytd),
        },
    ]
    included_rows = [row for row in modern_trade_rows if row["includedInTotal"]]
    complete_rows = [
        row
        for row in included_rows
        if row["baseYtd"]["state"] in {"value", "zero"}
        and row["comparisonYtd"]["state"] in {"value", "zero"}
    ]
    available_years = sorted(
        {
            covered_date.year
            for covered_dates in cube.valid_days.values()
            for covered_date in covered_dates
        }
    )
    return {
        "meta": {
            "baseYear": base_year,
            "comparisonYear": comparison_year,
            "cutoff": selected_cutoff,
            "activeCutoff": active_cutoff,
            "salesBasis": sales_basis,
            "metric": metric,
            "mtCodes": [modern_trade.code for modern_trade in modern_trades],
            "availableYears": available_years,
        },
        "kpis": {
            "baseYtd": _payload(base_ytd),
            "comparisonYtd": _payload(comparison_ytd),
            "difference": _difference(comparison_ytd, base_ytd),
            "growthPercent": _growth(comparison_ytd, base_ytd),
            "latestMonth": _payload(latest_month),
            "momPercent": _growth(latest_month, mom),
            "yoyPercent": _growth(latest_month, yoy),
            "dataCompletenessPercent": (
                round(len(complete_rows) / len(included_rows) * 100, 1)
                if included_rows
                else 0.0
            ),
        },
        "monthly": monthly,
        "modernTrades": modern_trade_rows,
        "periods": periods,
    }

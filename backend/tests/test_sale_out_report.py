from calendar import monthrange
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.api.sale_out import get_sale_out_report
from app.database import Base
from app.models import (
    DailySkuSummary,
    ImportBatch,
    ModernTrade,
    MonthlySalesSummary,
    SystemSetting,
)
from app.services.sale_out import ACTIVE_CUTOFF_KEY
from app.services.sale_out_report import build_sale_out_report


def _batch(batch_id: int, mt_id: int, data_date: date) -> ImportBatch:
    return ImportBatch(
        id=batch_id,
        modern_trade_id=mt_id,
        status="imported",
        data_date=data_date,
        sales_grain="daily",
        source_path=f"{batch_id}.xlsx",
        source_filename=f"{batch_id}.xlsx",
        checksum_sha256=f"{batch_id:064d}",
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


def _month(
    year: int,
    *,
    mt_id: int = 1,
    amount: int,
    qty: int,
    gross_amount: int,
    gross_qty: int,
) -> MonthlySalesSummary:
    return MonthlySalesSummary(
        modern_trade_id=mt_id,
        month_start=date(year, 1, 1),
        source_sku="SKU-1",
        source_branch_code="B1",
        source_branch_name="Branch 1",
        source_description="Item 1",
        amount=amount,
        sales_qty=qty,
        gross_amount=gross_amount,
        gross_sales_qty=gross_qty,
    )


def _day(
    data_date: date,
    *,
    mt_id: int = 1,
    amount: int,
    qty: int,
    gross_amount: int,
    gross_qty: int,
) -> DailySkuSummary:
    return DailySkuSummary(
        modern_trade_id=mt_id,
        data_date=data_date,
        source_sku="SKU-1",
        source_description="Item 1",
        amount=amount,
        sales_qty=qty,
        gross_amount=gross_amount,
        gross_sales_qty=gross_qty,
        stock_on_hand=0,
        stock_on_order=0,
        stock_value=0,
    )


def _seed_report_data(session: Session) -> None:
    session.add_all(
        [
            ModernTrade(
                id=1,
                code="TWD",
                name="Thai Watsadu",
                sale_out_start_date=date(2025, 1, 1),
                sale_out_include_in_total=True,
            ),
            ModernTrade(
                id=2,
                code="DH",
                name="DoHome",
                sale_out_start_date=date(2025, 1, 1),
                sale_out_include_in_total=False,
            ),
            SystemSetting(
                key=ACTIVE_CUTOFF_KEY,
                value="2026-02-02",
                updated_by="test",
            ),
            _month(2025, amount=100, qty=10, gross_amount=100, gross_qty=10),
            _month(2026, amount=150, qty=15, gross_amount=150, gross_qty=15),
            _day(
                date(2026, 1, 1),
                amount=10,
                qty=1,
                gross_amount=10,
                gross_qty=1,
            ),
            _day(
                date(2026, 1, 2),
                amount=10,
                qty=1,
                gross_amount=10,
                gross_qty=1,
            ),
            _day(
                date(2025, 2, 1),
                amount=10,
                qty=1,
                gross_amount=10,
                gross_qty=1,
            ),
            _day(
                date(2025, 2, 2),
                amount=-5,
                qty=-1,
                gross_amount=0,
                gross_qty=0,
            ),
            _day(
                date(2026, 2, 1),
                amount=20,
                qty=2,
                gross_amount=20,
                gross_qty=2,
            ),
            _day(
                date(2026, 2, 2),
                amount=-4,
                qty=-1,
                gross_amount=0,
                gross_qty=0,
            ),
        ]
    )
    batch_id = 1
    for year in (2025, 2026):
        for month in (1, 2):
            last_day = monthrange(year, month)[1] if month == 1 else 2
            for day in range(1, last_day + 1):
                session.add(_batch(batch_id, 1, date(year, month, day)))
                batch_id += 1
    session.commit()


def test_sale_out_report_uses_monthly_for_complete_and_daily_for_partial_months() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_report_data(session)

        report = build_sale_out_report(
            session,
            base_year=2025,
            comparison_year=2026,
            cutoff=None,
            sales_basis="gross",
            metric="amount",
            mt_codes=None,
        )

    assert report["meta"]["cutoff"] == date(2026, 2, 2)
    assert report["meta"]["activeCutoff"] == date(2026, 2, 2)
    assert report["kpis"]["baseYtd"] == {"state": "value", "value": 110.0}
    assert report["kpis"]["comparisonYtd"] == {
        "state": "value",
        "value": 170.0,
    }
    assert report["kpis"]["difference"] == 60.0
    assert report["kpis"]["growthPercent"] == pytest.approx(54.5454545)
    assert report["monthly"][0]["base"]["value"] == 100.0
    assert report["monthly"][0]["comparison"]["value"] == 150.0
    assert report["monthly"][1]["comparison"]["value"] == 20.0
    assert report["monthly"][2]["comparison"] == {
        "state": "future",
        "value": None,
    }
    assert [row["code"] for row in report["modernTrades"]] == ["DH", "TWD"]
    assert report["modernTrades"][0]["status"] == "excluded"
    assert report["kpis"]["momPercent"] == 0.0
    assert report["kpis"]["yoyPercent"] == 100.0
    twd = report["modernTrades"][1]
    assert twd["momPercent"] == 0.0
    assert twd["yoyPercent"] == 100.0
    q1 = next(row for row in report["periods"] if row["code"] == "Q1")
    assert q1["comparison"]["state"] == "future"


def test_sale_out_report_supports_net_qty_average_and_fixed_global_cutoff() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_report_data(session)

        net = build_sale_out_report(
            session,
            base_year=2025,
            comparison_year=2026,
            cutoff=date(2026, 2, 1),
            sales_basis="net",
            metric="amount",
            mt_codes=["TWD"],
        )
        average = build_sale_out_report(
            session,
            base_year=2025,
            comparison_year=2026,
            cutoff=None,
            sales_basis="gross",
            metric="average_price",
            mt_codes=["TWD"],
        )
        qty = build_sale_out_report(
            session,
            base_year=2025,
            comparison_year=2026,
            cutoff=None,
            sales_basis="gross",
            metric="qty",
            mt_codes=["TWD"],
        )

    assert net["meta"]["activeCutoff"] == date(2026, 2, 2)
    assert net["meta"]["cutoff"] == date(2026, 2, 1)
    assert net["kpis"]["baseYtd"]["value"] == 110.0
    assert net["kpis"]["comparisonYtd"]["value"] == 170.0
    assert average["kpis"]["baseYtd"]["value"] == 10.0
    assert average["kpis"]["comparisonYtd"]["value"] == 10.0
    assert qty["kpis"]["baseYtd"]["value"] == 11.0
    assert qty["kpis"]["comparisonYtd"]["value"] == 17.0


def test_sale_out_report_returns_zero_missing_and_unavailable_as_distinct_states() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_report_data(session)
        january = session.query(MonthlySalesSummary).filter_by(month_start=date(2025, 1, 1)).one()
        january.amount = Decimal("0")
        january.gross_amount = Decimal("0")
        session.commit()

        report = build_sale_out_report(
            session,
            base_year=2025,
            comparison_year=2026,
            cutoff=None,
            sales_basis="gross",
            metric="amount",
            mt_codes=["TWD", "DH"],
        )

    assert report["monthly"][0]["base"] == {"state": "zero", "value": 0.0}
    assert report["monthly"][2]["base"]["state"] == "missing"
    assert report["modernTrades"][0]["baseYtd"]["state"] == "unavailable"


def test_sale_out_api_rejects_invalid_year_cutoff_and_mt() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_report_data(session)

        with pytest.raises(HTTPException, match="ปีฐาน") as same_year:
            get_sale_out_report(
                session=session,
                base_year=2026,
                comparison_year=2026,
                cutoff=None,
                sales_basis="gross",
                metric="amount",
                mt_code=None,
            )
        assert same_year.value.status_code == 422

        with pytest.raises(HTTPException, match="Cut-off"):
            get_sale_out_report(
                session=session,
                base_year=2025,
                comparison_year=2026,
                cutoff=date(2026, 2, 3),
                sales_basis="gross",
                metric="amount",
                mt_code=None,
            )

        with pytest.raises(HTTPException, match="XYZ"):
            get_sale_out_report(
                session=session,
                base_year=2025,
                comparison_year=2026,
                cutoff=None,
                sales_basis="gross",
                metric="amount",
                mt_code=["XYZ"],
            )


def test_sale_out_report_uses_bounded_summary_queries_not_one_query_per_mt() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_report_data(session)
        statements: list[str] = []

        def record_statement(*args: object) -> None:
            statements.append(str(args[2]))

        event.listen(engine, "before_cursor_execute", record_statement)
        try:
            build_sale_out_report(
                session,
                base_year=2025,
                comparison_year=2026,
                cutoff=None,
                sales_basis="gross",
                metric="amount",
                mt_codes=None,
            )
        finally:
            event.remove(engine, "before_cursor_execute", record_statement)

    assert len(statements) <= 6


def test_mt_filter_changes_members_not_global_cutoff() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_report_data(session)
        session.add_all(
            [
                ModernTrade(
                    id=3,
                    code="HP",
                    name="HomePro",
                    sale_out_start_date=date(2025, 1, 1),
                    sale_out_include_in_total=True,
                ),
                _month(
                    2025,
                    mt_id=3,
                    amount=50,
                    qty=5,
                    gross_amount=50,
                    gross_qty=5,
                ),
                _month(
                    2026,
                    mt_id=3,
                    amount=70,
                    qty=7,
                    gross_amount=70,
                    gross_qty=7,
                ),
                _day(
                    date(2025, 2, 1),
                    mt_id=3,
                    amount=15,
                    qty=1,
                    gross_amount=15,
                    gross_qty=1,
                ),
                _day(
                    date(2025, 2, 2),
                    mt_id=3,
                    amount=15,
                    qty=1,
                    gross_amount=15,
                    gross_qty=1,
                ),
                _day(
                    date(2026, 2, 1),
                    mt_id=3,
                    amount=25,
                    qty=2,
                    gross_amount=25,
                    gross_qty=2,
                ),
                _day(
                    date(2026, 2, 2),
                    mt_id=3,
                    amount=25,
                    qty=2,
                    gross_amount=25,
                    gross_qty=2,
                ),
            ]
        )
        batch_id = 1_000
        for year in (2025, 2026):
            for month in (1, 2):
                last_day = monthrange(year, month)[1] if month == 1 else 2
                for day in range(1, last_day + 1):
                    session.add(_batch(batch_id, 3, date(year, month, day)))
                    batch_id += 1
        session.commit()

        all_modern_trades = build_sale_out_report(
            session,
            base_year=2025,
            comparison_year=2026,
            cutoff=None,
            sales_basis="gross",
            metric="amount",
            mt_codes=None,
        )
        twd_only = build_sale_out_report(
            session,
            base_year=2025,
            comparison_year=2026,
            cutoff=None,
            sales_basis="gross",
            metric="amount",
            mt_codes=["TWD"],
        )

    assert all_modern_trades["kpis"]["baseYtd"]["value"] == 190.0
    assert all_modern_trades["kpis"]["comparisonYtd"]["value"] == 290.0
    assert twd_only["kpis"]["baseYtd"]["value"] == 110.0
    assert twd_only["kpis"]["comparisonYtd"]["value"] == 170.0
    assert all_modern_trades["meta"]["cutoff"] == twd_only["meta"]["cutoff"]


def test_sale_out_start_date_is_an_absolute_full_date_boundary() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_report_data(session)
        twd = session.get(ModernTrade, 1)
        assert twd is not None
        twd.sale_out_start_date = date(2025, 2, 1)
        session.commit()

        report = build_sale_out_report(
            session,
            base_year=2025,
            comparison_year=2026,
            cutoff=None,
            sales_basis="gross",
            metric="amount",
            mt_codes=["TWD"],
        )

    assert report["monthly"][0]["base"]["state"] == "unavailable"
    assert report["kpis"]["baseYtd"]["value"] == 10.0
    assert report["kpis"]["comparisonYtd"]["value"] == 170.0

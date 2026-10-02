from datetime import date
from decimal import Decimal
from itertools import count
from unittest.mock import patch

from fastapi.routing import APIRoute
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.sale_out_settings import (
    SaleOutModernTradeUpdate,
    get_sale_out_settings,
    update_sale_out_modern_trade,
)
from app.api.sale_out_settings import (
    router as sale_out_settings_router,
)
from app.auth import require_system_admin
from app.database import Base
from app.models import (
    AuditEvent,
    BranchMapping,
    DailySkuSummary,
    ImportBatch,
    ModernTrade,
    SalesInventoryFact,
)
from app.services.daily_sku_summary import refresh_daily_sku_summary
from app.services.sale_out import (
    average_price,
    comparison_period_end,
    evaluate_common_cutoff,
    growth_percent,
    refresh_common_cutoff,
    set_cutoff_auto_advance,
    set_cutoff_frozen,
)


def _batch(
    batch_id: int,
    mt_id: int,
    data_date: date,
    *,
    grain: str = "daily",
    status: str = "imported",
    warnings: str | None = None,
    resolution: str | None = None,
) -> ImportBatch:
    return ImportBatch(
        id=batch_id,
        modern_trade_id=mt_id,
        status=status,
        data_date=data_date,
        sales_grain=grain,
        sales_window_days=30 if grain == "rolling_30d" else None,
        source_path=f"{batch_id}.xlsx",
        source_filename=f"{batch_id}.xlsx",
        checksum_sha256=f"{batch_id:064d}",
        row_count=1,
        store_count=1,
        sku_count=1,
        negative_row_count=0,
        source_amount=100,
        amount=100,
        sales_qty=1,
        stock_on_hand=0,
        reported_stock_on_hand=0,
        stock_on_order=0,
        reconciliation_errors=warnings,
        warning_resolution=resolution,
    )


def test_sale_out_metric_math_uses_comparable_dates_and_weighted_average() -> None:
    assert comparison_period_end(date(2024, 2, 29), 2023) == date(2023, 2, 28)
    assert comparison_period_end(date(2026, 9, 14), 2025) == date(2025, 9, 14)
    assert growth_percent(Decimal("120"), Decimal("100")) == Decimal("20")
    assert growth_percent(Decimal("0"), Decimal("0")) is None
    assert average_price(Decimal("300"), Decimal("4")) == Decimal("75")
    assert average_price(Decimal("300"), Decimal("0")) is None


def test_sale_out_gross_and_net_contract_uses_shared_positive_sale_predicate() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    data_date = date(2026, 8, 3)
    with Session(engine) as session:
        session.add_all(
            [
                ModernTrade(id=1, code="TWD", name="Thai Watsadu"),
                BranchMapping(
                    id=1,
                    modern_trade_id=1,
                    source_branch_code="B1",
                    wa_branch_code="WA-B1",
                    status="confirmed",
                    effective_from=data_date,
                    changed_by="test",
                ),
                _batch(1, 1, data_date),
                SalesInventoryFact(
                    id=1,
                    modern_trade_id=1,
                    batch_id=1,
                    data_date=data_date,
                    source_branch_code="B1",
                    source_branch_name="Branch 1",
                    source_sku="SKU-2",
                    source_description="Item 2",
                    source_amount=100,
                    amount=100,
                    sales_qty=2,
                    stock_on_hand=0,
                    stock_on_order=0,
                ),
                SalesInventoryFact(
                    id=2,
                    modern_trade_id=1,
                    batch_id=1,
                    data_date=data_date,
                    source_branch_code="B1",
                    source_branch_name="Branch 1",
                    source_sku="SKU-1",
                    source_description="Item 1",
                    source_amount=-20,
                    amount=-20,
                    sales_qty=-1,
                    stock_on_hand=0,
                    stock_on_order=0,
                ),
            ]
        )
        session.flush()
        refresh_daily_sku_summary(session, 1, data_date)
        summaries = session.scalars(select(DailySkuSummary)).all()

    net_amount = sum((row.amount for row in summaries), Decimal("0"))
    net_qty = sum((row.sales_qty for row in summaries), Decimal("0"))
    gross_amount = sum((row.gross_amount for row in summaries), Decimal("0"))
    gross_qty = sum((row.gross_sales_qty for row in summaries), Decimal("0"))
    assert net_amount == Decimal("80")
    assert net_qty == Decimal("1")
    assert gross_amount == Decimal("100")
    assert gross_qty == Decimal("2")
    assert average_price(gross_amount, gross_qty) == Decimal("50")


def test_common_cutoff_requires_contiguous_daily_coverage_and_ignores_rolling() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                ModernTrade(
                    id=1,
                    code="GH",
                    name="Global House",
                    sale_out_start_date=date(2026, 8, 1),
                    sale_out_include_in_total=True,
                ),
                ModernTrade(
                    id=2,
                    code="TA",
                    name="Thai-Aust",
                    sale_out_start_date=date(2026, 8, 1),
                    sale_out_include_in_total=True,
                ),
                ModernTrade(
                    id=3,
                    code="HH",
                    name="HomeHub",
                    sale_out_start_date=date(2026, 8, 1),
                    sale_out_include_in_total=True,
                ),
                ModernTrade(
                    id=4,
                    code="DH",
                    name="DoHome",
                    sale_out_start_date=date(2025, 1, 1),
                    sale_out_include_in_total=False,
                ),
                _batch(1, 1, date(2026, 8, 1)),
                _batch(2, 1, date(2026, 8, 2)),
                _batch(3, 1, date(2026, 8, 3)),
                _batch(4, 1, date(2026, 8, 4), grain="rolling_30d"),
                _batch(5, 2, date(2026, 8, 1)),
                _batch(6, 2, date(2026, 8, 2)),
                _batch(7, 2, date(2026, 8, 3)),
                _batch(8, 2, date(2026, 8, 4), warnings="ยอดไม่ตรง"),
                _batch(9, 3, date(2026, 8, 1)),
                _batch(10, 3, date(2026, 8, 2)),
                _batch(11, 3, date(2026, 8, 3)),
            ]
        )
        for batch_id in (9, 10, 11):
            zero_batch = session.get(ImportBatch, batch_id)
            assert zero_batch is not None
            zero_batch.source_amount = 0
            zero_batch.amount = 0
            zero_batch.sales_qty = 0
        session.commit()

        evaluation = evaluate_common_cutoff(session)

    assert evaluation.candidate_date == date(2026, 8, 3)
    assert {member.code: member.covered_through for member in evaluation.members} == {
        "GH": date(2026, 8, 3),
        "HH": date(2026, 8, 3),
        "TA": date(2026, 8, 3),
    }
    members = {member.code: member for member in evaluation.members}
    assert members["GH"].latest_source_date == date(2026, 8, 4)
    assert members["TA"].blocking_date == date(2026, 8, 4)
    assert "DH" not in members


def test_cutoff_advances_never_regresses_and_freeze_is_audited() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            ModernTrade(
                id=1,
                code="TWD",
                name="Thai Watsadu",
                sale_out_start_date=date(2026, 8, 1),
                sale_out_include_in_total=True,
            )
        )
        session.add_all([_batch(day, 1, date(2026, 8, day)) for day in range(1, 4)])
        session.commit()

        audit_ids = count(1)
        with patch(
            "app.services.sale_out.AuditEvent",
            side_effect=lambda **values: AuditEvent(id=next(audit_ids), **values),
        ):
            first = refresh_common_cutoff(session, actor="admin")
            assert first.active_date == date(2026, 8, 3)
            assert first.advanced is True

            set_cutoff_frozen(session, frozen=True, actor="admin")
            session.add(_batch(4, 1, date(2026, 8, 4)))
            session.commit()
            frozen = refresh_common_cutoff(session, actor="admin")
            assert frozen.active_date == date(2026, 8, 3)
            assert frozen.candidate_date == date(2026, 8, 4)
            assert frozen.advanced is False

            set_cutoff_frozen(session, frozen=False, actor="admin")
            advanced = refresh_common_cutoff(session, actor="admin")
            assert advanced.active_date == date(2026, 8, 4)

            session.delete(session.get(ImportBatch, 4))
            session.commit()
            regressed_source = refresh_common_cutoff(session, actor="admin")
            assert regressed_source.active_date == date(2026, 8, 4)
            assert regressed_source.candidate_date == date(2026, 8, 3)
            assert regressed_source.advanced is False

            set_cutoff_auto_advance(session, enabled=False, actor="admin")
            session.add(_batch(5, 1, date(2026, 8, 4)))
            session.commit()
            disabled = refresh_common_cutoff(session, actor="admin")
            assert disabled.active_date == date(2026, 8, 4)
            assert disabled.auto_advance_enabled is False

            set_cutoff_auto_advance(session, enabled=True, actor="admin")

        actions = session.scalars(
            select(AuditEvent.action)
            .where(AuditEvent.entity_id == "sale_out_common_cutoff")
            .order_by(AuditEvent.id)
        ).all()

    assert actions == [
        "advance",
        "freeze",
        "unfreeze",
        "advance",
        "disable_auto_advance",
        "enable_auto_advance",
    ]


def test_sale_out_settings_update_is_per_mt_and_audited() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                ModernTrade(id=1, code="TWD", name="Thai Watsadu"),
                ModernTrade(id=2, code="DH", name="DoHome"),
            ]
        )
        session.commit()
        with patch(
            "app.api.sale_out_settings.AuditEvent",
            side_effect=lambda **values: AuditEvent(id=1, **values),
        ):
            result = update_sale_out_modern_trade(
                "DH",
                SaleOutModernTradeUpdate(
                    start_date=date(2025, 1, 1),
                    include_in_total=False,
                ),
                session,
                "system-admin",
            )

        assert result["code"] == "DH"
        assert result["startDate"] == date(2025, 1, 1)
        assert result["includeInTotal"] is False
        assert session.get(ModernTrade, 1).sale_out_start_date is None
        audit = session.scalar(select(AuditEvent))
        assert audit is not None
        assert audit.actor == "system-admin"

        settings = get_sale_out_settings(session)
        assert [row["code"] for row in settings["modernTrades"]] == ["DH", "TWD"]
        assert settings["cutoff"]["activeDate"] is None


def test_sale_out_mutations_require_system_admin_but_settings_read_does_not() -> None:
    routes = [
        route for route in sale_out_settings_router.routes if isinstance(route, APIRoute)
    ]
    for route in routes:
        dependencies = {dependency.call for dependency in route.dependant.dependencies}
        if route.methods & {"PATCH", "POST"}:
            assert require_system_admin in dependencies
        elif route.methods == {"GET"}:
            assert require_system_admin not in dependencies

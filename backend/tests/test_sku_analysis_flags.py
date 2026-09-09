from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.api.performance as performance_api
import app.api.sku_analysis_flags as sku_analysis_flags_api
from app.api.performance import export_performance, performance
from app.api.sku_analysis_flags import SkuAnalysisFlagUpdate, update_sku_analysis_flag
from app.database import Base
from app.models import (
    AuditEvent,
    BranchMapping,
    ImportBatch,
    ItemMapping,
    ModernTrade,
    SalesInventoryFact,
    SkuAnalysisFlag,
)
from app.services.daily_sku_summary import refresh_daily_sku_summary
from app.services.monthly_sales_summary import refresh_monthly_sales_summary


def _seed(session: Session) -> None:
    session.add_all(
        [
            ModernTrade(id=1, code="TWD", name="Thai Watsadu"),
            ModernTrade(id=2, code="HP", name="HomePro"),
            ItemMapping(
                id=1,
                modern_trade_id=1,
                source_sku="SKU-A",
                source_description="Item A",
                wa_item_code="WA-A",
                wa_item_description="WA Item A",
                status="confirmed",
                item_type="normal",
                report_status="active",
                effective_from=date(2026, 1, 1),
                changed_by="test",
            ),
            ItemMapping(
                id=2,
                modern_trade_id=2,
                source_sku="SKU-A",
                source_description="Item A at HP",
                wa_item_code="WA-A",
                wa_item_description="WA Item A",
                status="confirmed",
                item_type="normal",
                report_status="active",
                effective_from=date(2026, 1, 1),
                changed_by="test",
            ),
        ]
    )
    session.commit()


def test_flag_scope_is_unique_per_modern_trade_and_source_sku() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
        session.add_all(
            [
                SkuAnalysisFlag(
                    modern_trade_id=1,
                    source_sku="SKU-A",
                    is_showroom=True,
                    updated_by="test",
                ),
                SkuAnalysisFlag(
                    modern_trade_id=2,
                    source_sku="SKU-A",
                    is_promotion=True,
                    updated_by="test",
                ),
            ]
        )
        session.commit()

        session.add(
            SkuAnalysisFlag(
                modern_trade_id=1,
                source_sku="SKU-A",
                updated_by="duplicate",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_partial_updates_do_not_overwrite_the_other_flag_and_are_audited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    audit_ids = iter(range(1, 10))
    monkeypatch.setattr(
        sku_analysis_flags_api,
        "AuditEvent",
        lambda **values: AuditEvent(id=next(audit_ids), **values),
    )
    with Session(engine) as session:
        _seed(session)

        sho_result = update_sku_analysis_flag(
            mt_code="TWD",
            source_sku="SKU-A",
            request=SkuAnalysisFlagUpdate(flag="sho", enabled=True),
            session=session,
        )
        pro_result = update_sku_analysis_flag(
            mt_code="TWD",
            source_sku="SKU-A",
            request=SkuAnalysisFlagUpdate(flag="pro", enabled=True),
            session=session,
        )

        assert sho_result["isSho"] is True
        assert sho_result["isPro"] is False
        assert pro_result["isSho"] is True
        assert pro_result["isPro"] is True
        assert session.scalar(select(SkuAnalysisFlag)).updated_by == "performance-user"
        audits = session.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity_type == "sku_analysis_flag")
            .order_by(AuditEvent.id)
        ).all()
        assert [audit.action for audit in audits] == ["set_sho", "set_pro"]


def test_flag_survives_mapping_inactive_and_reactivate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    audit_ids = iter(range(1, 10))
    monkeypatch.setattr(
        sku_analysis_flags_api,
        "AuditEvent",
        lambda **values: AuditEvent(id=next(audit_ids), **values),
    )
    with Session(engine) as session:
        _seed(session)
        update_sku_analysis_flag(
            mt_code="TWD",
            source_sku="SKU-A",
            request=SkuAnalysisFlagUpdate(flag="sho", enabled=True),
            session=session,
        )
        mapping = session.get(ItemMapping, 1)
        mapping.report_status = "inactive"
        session.commit()
        mapping.report_status = "active"
        session.commit()

        flag = session.scalar(
            select(SkuAnalysisFlag).where(
                SkuAnalysisFlag.modern_trade_id == 1,
                SkuAnalysisFlag.source_sku == "SKU-A",
            )
        )
        assert flag is not None
        assert flag.is_showroom is True


def test_phase_one_endpoint_rejects_other_modern_trades() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
        with pytest.raises(HTTPException) as exc_info:
            update_sku_analysis_flag(
                mt_code="HP",
                source_sku="SKU-A",
                request=SkuAnalysisFlagUpdate(flag="sho", enabled=True),
                session=session,
            )

    assert exc_info.value.status_code == 422


def _seed_performance_scope(session: Session) -> None:
    _seed(session)
    session.add_all(
        [
            BranchMapping(
                id=10,
                modern_trade_id=1,
                source_branch_code="B1",
                source_branch_description="Branch 1",
                wa_branch_code="WA-B1",
                wa_branch_description="Branch 1",
                status="confirmed",
                effective_from=date(2026, 1, 1),
                changed_by="test",
            ),
            *[
                ItemMapping(
                    id=index + 1,
                    modern_trade_id=1,
                    source_sku=sku,
                    source_description=f"Item {sku}",
                    wa_item_code=f"WA-{sku}",
                    wa_item_description=f"WA Item {sku}",
                    status="confirmed",
                    item_type="normal",
                    report_status="active",
                    effective_from=date(2026, 1, 1),
                    changed_by="test",
                )
                for index, sku in enumerate(["SKU-B", "SKU-C", "SKU-D", "SKU-E"], start=2)
            ],
            ImportBatch(
                id=10,
                modern_trade_id=1,
                status="imported",
                data_date=date(2026, 5, 1),
                source_path="prior.xlsx",
                source_filename="prior.xlsx",
                checksum_sha256="a" * 64,
                row_count=5,
                store_count=1,
                sku_count=5,
                negative_row_count=0,
                source_amount=0,
                amount=0,
                sales_qty=15,
                stock_on_hand=0,
                reported_stock_on_hand=0,
                stock_on_order=0,
            ),
            ImportBatch(
                id=11,
                modern_trade_id=1,
                status="imported",
                data_date=date(2026, 8, 31),
                source_path="current.xlsx",
                source_filename="current.xlsx",
                checksum_sha256="b" * 64,
                row_count=5,
                store_count=1,
                sku_count=5,
                negative_row_count=0,
                source_amount=1500,
                amount=1500,
                sales_qty=15,
                stock_on_hand=150,
                reported_stock_on_hand=150,
                stock_on_order=0,
            ),
        ]
    )
    for index, sku in enumerate(["SKU-A", "SKU-B", "SKU-C", "SKU-D", "SKU-E"], start=1):
        session.add_all(
            [
                SalesInventoryFact(
                    id=index,
                    modern_trade_id=1,
                    batch_id=10,
                    data_date=date(2026, 5, 1),
                    source_branch_code="B1",
                    source_branch_name="Branch 1",
                    source_sku=sku,
                    source_description=f"Item {sku}",
                    source_amount=0,
                    amount=0,
                    sales_qty=3,
                    stock_on_hand=0,
                    stock_on_order=0,
                ),
                SalesInventoryFact(
                    id=index + 10,
                    modern_trade_id=1,
                    batch_id=11,
                    data_date=date(2026, 8, 31),
                    source_branch_code="B1",
                    source_branch_name="Branch 1",
                    source_sku=sku,
                    source_description=f"Item {sku}",
                    source_amount=index * 100,
                    amount=index * 100,
                    sales_qty=index,
                    stock_on_hand=index * 10,
                    stock_on_order=0,
                ),
            ]
        )
    session.add_all(
        [
            SkuAnalysisFlag(
                id=10,
                modern_trade_id=1,
                source_sku="SKU-A",
                is_showroom=True,
                updated_by="test",
            ),
            SkuAnalysisFlag(
                id=11,
                modern_trade_id=1,
                source_sku="SKU-B",
                is_promotion=True,
                updated_by="test",
            ),
            SkuAnalysisFlag(
                id=12,
                modern_trade_id=1,
                source_sku="SKU-C",
                is_showroom=True,
                is_promotion=True,
                updated_by="test",
            ),
            SkuAnalysisFlag(
                id=13,
                modern_trade_id=1,
                source_sku="SKU-D",
                updated_by="test",
            ),
        ]
    )
    session.commit()


@pytest.mark.parametrize(
    ("sku_flag", "expected_skus", "expected_amount", "expected_average_tom"),
    [
        ("all", {"SKU-A", "SKU-B", "SKU-C", "SKU-D", "SKU-E"}, 1500.0, 30.0),
        ("flagged", {"SKU-A", "SKU-B", "SKU-C"}, 600.0, 20.0),
        ("sho", {"SKU-A", "SKU-C"}, 400.0, 20.0),
        ("pro", {"SKU-B", "SKU-C"}, 500.0, 25.0),
        ("both", {"SKU-C"}, 300.0, 30.0),
        ("none", {"SKU-D", "SKU-E"}, 900.0, 45.0),
    ],
)
def test_performance_flag_filter_scopes_items_summary_pagination_and_turnover(
    sku_flag: str,
    expected_skus: set[str],
    expected_amount: float,
    expected_average_tom: float,
) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_performance_scope(session)
        report = performance(
            session=session,
            mt_code="TWD",
            date_from=date(2026, 8, 31),
            date_to=date(2026, 8, 31),
            page=1,
            page_size=1,
            grain="day",
            include_turnover=True,
            sku_flag=sku_flag,
        )

    assert report["meta"]["totalSkus"] == len(expected_skus)
    assert report["meta"]["totalPages"] == len(expected_skus)
    assert report["meta"]["totalBranches"] == 1
    assert report["summary"]["amount"] == expected_amount
    assert report["inventorySummary"]["averageTom"] == expected_average_tom
    assert report["inventorySummary"]["averageTod"] == expected_average_tom * 30
    assert report["inventorySummary"]["turnoverSkuCount"] == len(expected_skus)
    assert len(report["items"]) == 1
    assert report["items"][0]["sku"] == sorted(expected_skus)[0]
    expected_flags = {
        "SKU-A": (True, False),
        "SKU-B": (False, True),
        "SKU-C": (True, True),
        "SKU-D": (False, False),
        "SKU-E": (False, False),
    }
    assert (
        report["items"][0]["isSho"],
        report["items"][0]["isPro"],
    ) == expected_flags[report["items"][0]["sku"]]


def test_phase_one_performance_filter_rejects_other_modern_trades() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
        with pytest.raises(HTTPException) as exc_info:
            performance(session=session, mt_code="HP", sku_flag="sho")

    assert exc_info.value.status_code == 422


def test_flag_filter_applies_to_daily_and_monthly_summary_fast_paths() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_performance_scope(session)
        for data_date in (date(2026, 5, 1), date(2026, 8, 31)):
            refresh_daily_sku_summary(session, 1, data_date)
            refresh_monthly_sales_summary(session, 1, data_date)
        session.commit()

        daily_report = performance(
            session=session,
            mt_code="TWD",
            grain="day_total",
            sku_flag="both",
        )
        monthly_report = performance(
            session=session,
            mt_code="TWD",
            date_from=date(2026, 8, 1),
            date_to=date(2026, 8, 31),
            grain="month",
            sku_flag="pro",
        )

    assert daily_report["meta"]["totalSkus"] == 1
    assert daily_report["summary"]["amount"] == 300.0
    assert [item["sku"] for item in daily_report["items"]] == ["SKU-C"]
    assert daily_report["items"][0]["isSho"] is True
    assert daily_report["items"][0]["isPro"] is True
    assert monthly_report["meta"]["totalSkus"] == 2
    assert monthly_report["summary"]["amount"] == 500.0
    assert [item["sku"] for item in monthly_report["items"]] == ["SKU-B", "SKU-C"]


def test_export_forwards_the_same_flag_filter_to_performance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def fake_performance(**kwargs):
        captured.update(kwargs)
        return {"items": [], "dates": [], "branches": []}

    monkeypatch.setattr(performance_api, "performance", fake_performance)
    monkeypatch.setattr(
        performance_api,
        "build_performance_workbook",
        lambda *args, **kwargs: b"xlsx",
    )

    response = export_performance(session=None, sku_flag="both")

    assert response.status_code == 200
    assert captured["sku_flag"] == "both"

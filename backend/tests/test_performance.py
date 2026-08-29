from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.performance import _month_bounds, _selected_branch_ids, performance, sku_options
from app.database import Base
from app.models import (
    BranchMapping,
    ImportBatch,
    ItemMapping,
    ModernTrade,
    SalesInventoryFact,
)
from app.services.monthly_sales_summary import refresh_monthly_sales_summary


def test_month_bounds_supports_leap_year() -> None:
    assert _month_bounds("2024-02") == (date(2024, 2, 1), date(2024, 2, 29))


def test_month_bounds_rejects_invalid_month() -> None:
    with pytest.raises(ValueError):
        _month_bounds("2026-13")


def test_selected_branch_ids_supports_multi_select_and_legacy_parameter() -> None:
    assert _selected_branch_ids(None, "60016, 60923,60016") == ["60016", "60923"]
    assert _selected_branch_ids("60020", None) == ["60020"]
    assert _selected_branch_ids("60020", "60016,60923") == ["60016", "60923"]
    assert _selected_branch_ids(None, None) == []


def test_performance_search_includes_mapping_without_facts() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ModernTrade(id=1, code="TWD", name="Thai Watsadu"))
        session.add(
            ItemMapping(
                id=1,
                modern_trade_id=1,
                source_sku="060358971",
                source_description="สินค้าใหม่",
                wa_item_code="FAE09-W6612-100100",
                wa_item_description="รายละเอียดสินค้าใหม่",
                status="pending",
                effective_from=date(2026, 8, 16),
                effective_to=None,
                changed_by="test",
            )
        )
        session.commit()

        result = performance(
            session,
            date_from=date(2026, 8, 16),
            date_to=date(2026, 8, 17),
            page=1,
            page_size=25,
            branch_id=None,
            mapping_status=None,
            hide_unmapped=True,
            search="060358971",
            grain="branch_month",
            period_month="2026-08",
        )

    assert result["meta"]["totalSkus"] == 1
    assert result["items"] == [
        {
            "sku": "060358971",
            "twdDescription": "สินค้าใหม่",
            "waItem": "FAE09-W6612-100100",
            "waDescription": "รายละเอียดสินค้าใหม่",
            "mappingStatus": "pending",
            "itemType": "normal",
            "points": [],
        }
    ]
    assert result["summary"]["amount"] == 0
    assert result["summary"]["qty"] == 0


def test_performance_uses_fact_description_when_mapping_description_is_missing() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ModernTrade(id=1, code="TWD", name="Thai Watsadu"))
        session.add(
            ImportBatch(
                id=1,
                modern_trade_id=1,
                status="imported",
                data_date=date(2026, 8, 17),
                source_path="test.xls",
                source_filename="test.xls",
                checksum_sha256="0" * 64,
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
            )
        )
        session.add_all(
            [
                ItemMapping(
                    id=1,
                    modern_trade_id=1,
                    source_sku="060277546",
                    source_description=None,
                    wa_item_code="FA09-W0112-080050",
                    wa_item_description="รายละเอียด WA",
                    status="confirmed",
                    effective_from=date(2026, 8, 1),
                    changed_by="test",
                ),
                BranchMapping(
                    id=1,
                    modern_trade_id=1,
                    source_branch_code="60016",
                    source_branch_description="สาขาต้นทาง",
                    wa_branch_code="CTW-0048",
                    wa_branch_description="ภูเก็ต เฟสติวัล",
                    status="confirmed",
                    effective_from=date(2026, 8, 1),
                    changed_by="test",
                ),
                SalesInventoryFact(
                    modern_trade_id=1,
                    id=1,
                    batch_id=1,
                    data_date=date(2026, 8, 17),
                    source_branch_code="60016",
                    source_branch_name="สาขาต้นทาง",
                    source_sku="060277546",
                    source_description="หน้าต่างบานเลื่อน อลูมิเนียม WINDOW ASIA",
                    source_amount=100,
                    amount=100,
                    sales_qty=1,
                    stock_on_hand=0,
                    stock_on_order=0,
                ),
            ]
        )
        session.commit()
        refresh_monthly_sales_summary(session, 1, date(2026, 8, 17))
        session.commit()

        result = performance(
            session,
            date_from=None,
            date_to=None,
            page=1,
            page_size=25,
            branch_id=None,
            mapping_status=None,
            hide_unmapped=False,
            search="060277546",
            grain="branch_month",
            period_month="2026-08",
        )

    assert result["items"][0]["twdDescription"] == ("หน้าต่างบานเลื่อน อลูมิเนียม WINDOW ASIA")


def test_branch_month_uses_current_mapping_for_historical_facts() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ModernTrade(id=1, code="TWD", name="Thai Watsadu"))
        session.add_all(
            [
                ImportBatch(
                    id=1,
                    modern_trade_id=1,
                    status="imported",
                    data_date=date(2026, 7, 26),
                    source_path="july.xlsx",
                    source_filename="july.xlsx",
                    checksum_sha256="1" * 64,
                    row_count=1,
                    store_count=1,
                    sku_count=1,
                    negative_row_count=0,
                    source_amount=100,
                    amount=100,
                    sales_qty=2,
                    stock_on_hand=0,
                    reported_stock_on_hand=0,
                    stock_on_order=0,
                ),
                ImportBatch(
                    id=2,
                    modern_trade_id=1,
                    status="imported",
                    data_date=date(2026, 8, 16),
                    source_path="august.xlsx",
                    source_filename="august.xlsx",
                    checksum_sha256="2" * 64,
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
                ),
                ItemMapping(
                    id=1,
                    modern_trade_id=1,
                    source_sku="HISTORICAL-ITEM",
                    source_description="สินค้ากรกฎาคม",
                    wa_item_code="WA-ITEM",
                    wa_item_description="สินค้า WA",
                    status="confirmed",
                    effective_from=date(2026, 8, 16),
                    changed_by="test",
                ),
                BranchMapping(
                    id=1,
                    modern_trade_id=1,
                    source_branch_code="HISTORICAL-BRANCH",
                    source_branch_description="สาขาต้นทาง",
                    wa_branch_code="WA-BRANCH",
                    wa_branch_description="สาขา WA",
                    status="confirmed",
                    effective_from=date(2026, 8, 16),
                    changed_by="test",
                ),
                SalesInventoryFact(
                    modern_trade_id=1,
                    id=1,
                    batch_id=1,
                    data_date=date(2026, 7, 26),
                    source_branch_code="HISTORICAL-BRANCH",
                    source_branch_name="สาขาต้นทาง",
                    source_sku="HISTORICAL-ITEM",
                    source_description="สินค้ากรกฎาคม",
                    source_amount=100,
                    amount=100,
                    sales_qty=2,
                    stock_on_hand=0,
                    stock_on_order=0,
                ),
                SalesInventoryFact(
                    modern_trade_id=1,
                    id=2,
                    batch_id=2,
                    data_date=date(2026, 8, 16),
                    source_branch_code="HISTORICAL-BRANCH",
                    source_branch_name="สาขาต้นทาง",
                    source_sku="HISTORICAL-ITEM",
                    source_description="สินค้ากรกฎาคม",
                    source_amount=0,
                    amount=0,
                    sales_qty=0,
                    stock_on_hand=0,
                    stock_on_order=0,
                ),
            ]
        )
        session.commit()
        refresh_monthly_sales_summary(session, 1, date(2026, 7, 26))
        refresh_monthly_sales_summary(session, 1, date(2026, 8, 16))
        session.commit()

        result = performance(
            session,
            date_from=None,
            date_to=None,
            page=1,
            page_size=25,
            branch_id=None,
            mapping_status=None,
            hide_unmapped=False,
            search=None,
            grain="branch_month",
            period_month="2026-07",
        )
        day_result = performance(
            session,
            date_from=date(2026, 7, 26),
            date_to=date(2026, 7, 26),
            page=1,
            page_size=25,
            branch_id=None,
            mapping_status=None,
            hide_unmapped=False,
            search=None,
            grain="day",
            period_month=None,
        )
        branch_range_result = performance(
            session,
            date_from=date(2026, 7, 26),
            date_to=date(2026, 8, 16),
            page=1,
            page_size=25,
            branch_id=None,
            mapping_status=None,
            hide_unmapped=False,
            search=None,
            grain="branch_range",
            period_month=None,
        )

    assert result["meta"]["totalSkus"] == 1
    assert result["meta"]["totalBranches"] == 1
    assert result["summary"] == {"amount": 100.0, "qty": 2.0, "mappingAttention": 0}
    assert result["columnTotals"] == {"HISTORICAL-BRANCH": {"amount": 100.0, "qty": 2.0}}
    assert day_result["dates"] == ["2026-07-26"]
    assert day_result["columnTotals"] == {"HISTORICAL-BRANCH": {"amount": 100.0, "qty": 2.0}}
    assert branch_range_result["dates"] == ["2026-07-26", "2026-08-16"]
    assert branch_range_result["columnTotals"] == {
        "HISTORICAL-BRANCH": {"amount": 100.0, "qty": 2.0}
    }
    assert branch_range_result["items"][0]["points"] == [
        {
            "date": "2026-08-16",
            "branchId": "HISTORICAL-BRANCH",
            "amount": 100.0,
            "qty": 2.0,
            "stockOh": 0,
            "stockOnOrder": 0,
        }
    ]


def test_performance_unmatched_visibility_controls_rows_and_every_total() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        modern_trade = ModernTrade(id=1, code="TWD", name="Thai Watsadu")
        session.add(modern_trade)
        session.add(
            ImportBatch(
                id=1,
                modern_trade_id=1,
                status="imported",
                data_date=date(2026, 8, 17),
                source_path="test.xlsx",
                source_filename="test.xlsx",
                checksum_sha256="0" * 64,
                row_count=4,
                store_count=2,
                sku_count=2,
                negative_row_count=0,
                source_amount=1000,
                amount=1000,
                sales_qty=4,
                stock_on_hand=0,
                reported_stock_on_hand=0,
                stock_on_order=0,
            )
        )
        session.add_all(
            [
                ItemMapping(
                    id=10,
                    modern_trade_id=1,
                    source_sku="MAPPED-ITEM",
                    source_description="Mapped item",
                    wa_item_code="WA-ITEM",
                    wa_item_description="Mapped item",
                    status="confirmed",
                    effective_from=date(2026, 8, 1),
                    changed_by="test",
                ),
                BranchMapping(
                    id=20,
                    modern_trade_id=1,
                    source_branch_code="MAPPED-BRANCH",
                    source_branch_description="Mapped source branch",
                    wa_branch_code="WA-BRANCH",
                    wa_branch_description="สาขาที่ Mapping",
                    status="confirmed",
                    effective_from=date(2026, 8, 1),
                    changed_by="test",
                ),
            ]
        )

        def fact(fact_id: int, sku: str, branch: str, amount: int) -> SalesInventoryFact:
            return SalesInventoryFact(
                modern_trade_id=1,
                id=fact_id,
                batch_id=1,
                data_date=date(2026, 8, 17),
                source_branch_code=branch,
                source_branch_name=branch,
                source_sku=sku,
                source_description=sku,
                source_amount=amount,
                amount=amount,
                sales_qty=1,
                stock_on_hand=0,
                stock_on_order=0,
            )

        session.add_all(
            [
                fact(1, "MAPPED-ITEM", "MAPPED-BRANCH", 100),
                fact(2, "UNMATCHED-ITEM", "MAPPED-BRANCH", 200),
                fact(3, "MAPPED-ITEM", "UNMATCHED-BRANCH", 300),
                fact(4, "UNMATCHED-ITEM", "UNMATCHED-BRANCH", 400),
            ]
        )
        session.commit()

        def report() -> dict:
            return performance(
                session,
                date_from=date(2026, 8, 17),
                date_to=date(2026, 8, 17),
                page=1,
                page_size=25,
                branch_id=None,
                mapping_status=None,
                hide_unmapped=False,
                search=None,
                grain="day",
                period_month=None,
            )

        hidden = report()
        modern_trade.show_unmatched_items = True
        modern_trade.show_unmatched_branches = True
        session.commit()
        shown = report()
        modern_trade.report_page_size = 50
        session.commit()
        selected = performance(
            session,
            date_from=date(2026, 8, 17),
            date_to=date(2026, 8, 17),
            page=1,
            page_size=None,
            branch_id=None,
            branch_ids="MAPPED-BRANCH,DOES-NOT-EXIST",
            mapping_status=None,
            hide_unmapped=False,
            search=None,
            grain="day",
            period_month=None,
        )
        modern_trade.report_page_size = 0
        session.commit()
        all_skus = performance(
            session,
            date_from=date(2026, 8, 17),
            date_to=date(2026, 8, 17),
            page=1,
            page_size=None,
            branch_id=None,
            branch_ids=None,
            mapping_status=None,
            hide_unmapped=False,
            search=None,
            grain="day",
            period_month=None,
        )

    assert hidden["summary"] == {"amount": 100.0, "qty": 1.0, "mappingAttention": 0}
    assert hidden["meta"]["totalSkus"] == 1
    assert hidden["meta"]["totalBranches"] == 1
    assert hidden["branches"] == [{"id": "MAPPED-BRANCH", "name": "สาขาที่ Mapping"}]

    assert shown["summary"] == {"amount": 1000.0, "qty": 4.0, "mappingAttention": 1}
    assert shown["meta"]["totalSkus"] == 2
    assert shown["meta"]["totalBranches"] == 2
    assert {branch["id"] for branch in shown["branches"]} == {
        "MAPPED-BRANCH",
        "UNMATCHED-BRANCH",
    }
    assert {item["sku"] for item in shown["items"]} == {
        "MAPPED-ITEM",
        "UNMATCHED-ITEM",
    }
    assert selected["summary"]["amount"] == 300.0
    assert selected["columnTotals"] == {"MAPPED-BRANCH": {"amount": 300.0, "qty": 2.0}}
    assert selected["meta"]["pageSize"] == 50
    assert all_skus["meta"]["pageSize"] == 2
    assert all_skus["meta"]["totalPages"] == 1
    assert len(all_skus["items"]) == 2


def test_inactive_item_is_excluded_globally_and_multi_sku_filter_is_consistent() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ModernTrade(id=1, code="TWD", name="Thai Watsadu"))
        session.add(
            ImportBatch(
                id=1,
                modern_trade_id=1,
                status="imported",
                data_date=date(2026, 8, 17),
                source_path="test.xlsx",
                source_filename="test.xlsx",
                checksum_sha256="3" * 64,
                row_count=3,
                store_count=1,
                sku_count=3,
                negative_row_count=0,
                source_amount=600,
                amount=600,
                sales_qty=6,
                stock_on_hand=0,
                reported_stock_on_hand=0,
                stock_on_order=0,
            )
        )
        session.add(
            BranchMapping(
                id=1,
                modern_trade_id=1,
                source_branch_code="60016",
                source_branch_description="สาขาต้นทาง",
                wa_branch_code="CTW-0048",
                wa_branch_description="ภูเก็ต เฟสติวัล",
                status="confirmed",
                effective_from=date(2026, 8, 1),
                changed_by="test",
            )
        )
        session.add_all(
            [
                ItemMapping(
                    id=1,
                    modern_trade_id=1,
                    source_sku="NORMAL",
                    source_description="สินค้าปกติ",
                    wa_item_code="WA-NORMAL",
                    wa_item_description="สินค้าปกติ WA",
                    status="confirmed",
                    item_type="normal",
                    report_status="active",
                    effective_from=date(2026, 8, 1),
                    changed_by="test",
                ),
                ItemMapping(
                    id=2,
                    modern_trade_id=1,
                    source_sku="TRIAL",
                    source_description="สินค้าทดลอง",
                    wa_item_code="WA-TRIAL",
                    wa_item_description="สินค้าทดลอง WA",
                    status="confirmed",
                    item_type="trial",
                    report_status="active",
                    effective_from=date(2026, 8, 1),
                    changed_by="test",
                ),
                ItemMapping(
                    id=3,
                    modern_trade_id=1,
                    source_sku="HIDDEN",
                    source_description="สินค้าที่ซ่อน",
                    wa_item_code="WA-HIDDEN",
                    wa_item_description="สินค้าที่ซ่อน WA",
                    status="confirmed",
                    item_type="trial",
                    report_status="inactive",
                    effective_from=date(2026, 8, 1),
                    changed_by="test",
                ),
            ]
        )

        def fact(fact_id: int, sku: str, amount: int, qty: int) -> SalesInventoryFact:
            return SalesInventoryFact(
                modern_trade_id=1,
                id=fact_id,
                batch_id=1,
                data_date=date(2026, 8, 17),
                source_branch_code="60016",
                source_branch_name="สาขาต้นทาง",
                source_sku=sku,
                source_description=sku,
                source_amount=amount,
                amount=amount,
                sales_qty=qty,
                stock_on_hand=0,
                stock_on_order=0,
            )

        session.add_all(
            [fact(1, "NORMAL", 100, 1), fact(2, "TRIAL", 200, 2), fact(3, "HIDDEN", 300, 3)]
        )
        session.commit()

        all_active = performance(
            session=session,
            date_from=date(2026, 8, 17),
            date_to=date(2026, 8, 17),
            page=1,
            page_size=25,
            branch_id=None,
            branch_ids=None,
            sku_ids=None,
            mapping_status=None,
            hide_unmapped=False,
            search=None,
            grain="day",
            period_month=None,
        )
        selected = performance(
            session=session,
            date_from=date(2026, 8, 17),
            date_to=date(2026, 8, 17),
            page=1,
            page_size=25,
            branch_id=None,
            branch_ids=None,
            sku_ids="TRIAL,HIDDEN",
            mapping_status=None,
            hide_unmapped=False,
            search=None,
            grain="day",
            period_month=None,
        )
        options = sku_options(session=session)

    assert all_active["summary"]["amount"] == 300.0
    assert all_active["summary"]["qty"] == 3.0
    assert {item["sku"] for item in all_active["items"]} == {"NORMAL", "TRIAL"}
    assert (
        next(item for item in all_active["items"] if item["sku"] == "TRIAL")["itemType"] == "trial"
    )
    assert selected["summary"]["amount"] == 200.0
    assert [item["sku"] for item in selected["items"]] == ["TRIAL"]
    assert {item["sku"] for item in options["items"]} == {"NORMAL", "TRIAL"}


def test_sku_options_uses_latest_fact_description_when_mapping_description_is_missing() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ModernTrade(id=1, code="TWD", name="Thai Watsadu"))
        session.add(
            ImportBatch(
                id=1,
                modern_trade_id=1,
                status="imported",
                data_date=date(2026, 8, 23),
                source_path="latest.xlsx",
                source_filename="latest.xlsx",
                checksum_sha256="4" * 64,
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
            )
        )
        session.add(
            ItemMapping(
                id=1,
                modern_trade_id=1,
                source_sku="060385494",
                source_description=None,
                wa_item_code="FA09-W0319-240110",
                wa_item_description="WA description",
                status="confirmed",
                effective_from=date(2026, 8, 1),
                changed_by="test",
            )
        )
        session.add(
            SalesInventoryFact(
                modern_trade_id=1,
                id=1,
                batch_id=1,
                data_date=date(2026, 8, 23),
                source_branch_code="60016",
                source_branch_name="Source branch",
                source_sku="060385494",
                source_description="WINDOW ASIA sliding window",
                source_amount=100,
                amount=100,
                sales_qty=1,
                stock_on_hand=0,
                stock_on_order=0,
            )
        )
        session.commit()

        result = sku_options(session=session)

    assert result["items"] == [
        {
            "sku": "060385494",
            "twdDescription": "WINDOW ASIA sliding window",
            "waItem": "FA09-W0319-240110",
            "waDescription": "WA description",
            "itemType": "normal",
        }
    ]

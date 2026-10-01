from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from test_sale_out_report import _batch

from app.database import Base
from app.models import BranchMapping, ItemMapping, ModernTrade, SalesInventoryFact
from app.services.daily_sku_summary import refresh_daily_sku_summary
from app.services.monthly_sales_summary import refresh_monthly_sales_summary
from app.services.sale_out_report import _growth, _load_cube, _range_result, _total_result


@pytest.mark.parametrize("code", ["TWD", "HP", "MH", "HH", "GH", "DH", "TA"])
@pytest.mark.parametrize(
    "items,branches,expected",
    [
        (False, False, 100),
        (True, False, 300),
        (False, True, 400),
        (True, True, 600),
    ],
)
def test_partial_respects_report_mapping_and_valid_days(code, items, branches, expected):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        mt = ModernTrade(
            id=1,
            code=code,
            name=code,
            sale_out_start_date=date(2025, 3, 1),
            show_unmatched_items=items,
            show_unmatched_branches=branches,
        )
        s.add(mt)
        s.add(
            ItemMapping(
                id=1,
                modern_trade_id=1,
                source_sku="A",
                wa_item_code="WA",
                status="confirmed",
                effective_from=date(2025, 1, 1),
                changed_by="test",
            )
        )
        s.add(
            BranchMapping(
                id=1,
                modern_trade_id=1,
                source_branch_code="B1",
                source_branch_description="B1",
                wa_branch_code="WA",
                status="confirmed",
                effective_from=date(2025, 1, 1),
                changed_by="test",
            )
        )
        for day in [1, 2]:
            batch = _batch(day, 1, date(2025, 3, day))
            if day == 2:
                batch.reconciliation_errors = "unresolved"
            s.add(batch)
            for i, (sku, branch, amount) in enumerate(
                [("A", "B1", 100), ("U", "B1", 200), ("A", "U", 300)]
            ):
                s.add(
                    SalesInventoryFact(
                        id=day * 10 + i,
                        batch_id=day,
                        modern_trade_id=1,
                        data_date=batch.data_date,
                        source_sku=sku,
                        source_description=sku,
                        source_branch_code=branch,
                        source_branch_name=branch,
                        amount=amount,
                        source_amount=amount,
                        sales_qty=amount / 10,
                        stock_on_hand=0,
                        stock_on_order=0,
                    )
                )
        s.commit()
        for day in [1, 2]:
            refresh_daily_sku_summary(s, 1, date(2025, 3, day))
        refresh_monthly_sales_summary(s, 1, date(2025, 3, 1))
        s.commit()
        cube = _load_cube(s, [1], 2025, 2026)
        args = (mt, cube, date(2025, 3, 1), date(2025, 3, 31), "gross", "amount")
        assert _range_result(*args).value is None
        cube.show_partial = True
        result = _range_result(*args)
        assert result.state == "incomplete"
        assert result.value == expected  # Unresolved day is not included.
        assert (result.covered_days, result.expected_days) == (1, 31)
        assert _growth(result, result) is None
        missing = _range_result(mt, cube, date(2025, 4, 1), date(2025, 4, 30), "gross", "amount")
        total = _total_result([result, missing], "gross", "amount")
        assert total.state == "incomplete" and total.value == expected
        assert (total.covered_days, total.expected_days) == (1, 61)
        assert _total_result([missing], "gross", "amount").value is None

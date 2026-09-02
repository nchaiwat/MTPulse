from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.dashboards import twd_dashboard
from app.database import Base
from app.models import BranchMapping, ImportBatch, ModernTrade, MonthlySalesSummary


def _batch(batch_id: int, mt_id: int, data_date: date) -> ImportBatch:
    return ImportBatch(
        id=batch_id,
        modern_trade_id=mt_id,
        status="imported",
        data_date=data_date,
        source_path=f"{batch_id}.xls",
        source_filename=f"{batch_id}.xls",
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
    )


def _summary(
    mt_id: int,
    year: int,
    month: int,
    branch: str,
    sku: str,
    amount: int,
    qty: int,
) -> MonthlySalesSummary:
    return MonthlySalesSummary(
        modern_trade_id=mt_id,
        month_start=date(year, month, 1),
        source_sku=sku,
        source_branch_code=branch,
        source_branch_name=f"สาขา {branch}",
        source_description=f"สินค้า {sku}",
        amount=amount,
        sales_qty=qty,
    )


def test_twd_dashboard_compares_same_h1_months_and_does_not_mix_mt() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                ModernTrade(id=1, code="TWD", name="ไทวัสดุ"),
                ModernTrade(id=2, code="TA", name="Test MT"),
                _batch(1, 1, date(2025, 6, 30)),
                _batch(2, 1, date(2026, 6, 30)),
                _summary(1, 2025, 1, "B1", "SKU1", 100, 10),
                _summary(1, 2026, 1, "B1", "SKU1", 120, 12),
                _summary(1, 2025, 2, "B2", "SKU2", 200, 20),
                _summary(1, 2026, 2, "B2", "SKU2", 300, 25),
                BranchMapping(
                    id=1,
                    modern_trade_id=1,
                    source_branch_code="B2",
                    source_branch_description="Source B2",
                    wa_branch_code="CTW-0048",
                    wa_branch_description="ภูเก็ต เฟสติวัล",
                    status="confirmed",
                    effective_from=date(2025, 1, 1),
                    changed_by="test",
                ),
                _summary(2, 2026, 1, "B9", "SKU9", 9999, 999),
            ]
        )
        session.commit()

        result = twd_dashboard(session=session, year=2026, period="h1")

    assert result["summary"] == {
        "currentAmount": 420.0,
        "previousAmount": 300.0,
        "amountYoY": 40.0,
        "currentQty": 37.0,
        "previousQty": 30.0,
        "qtyYoY": pytest.approx(23.3333333333),
    }
    assert [row["month"] for row in result["monthly"]] == [1, 2, 3, 4, 5, 6]
    assert result["monthly"][0]["amountMoM"] is None
    assert result["monthly"][1]["amountMoM"] == 150.0
    assert result["topBranches"][0]["branchCode"] == "B2"
    assert result["topBranches"][0]["displayName"] == "B2 - ภูเก็ต เฟสติวัล (CTW-0048)"
    assert result["topSkus"][0]["sku"] == "SKU2"
    assert all(row["branchCode"] != "B9" for row in result["topBranches"])


def test_twd_dashboard_returns_empty_contract_without_imports() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ModernTrade(id=1, code="TWD", name="ไทวัสดุ"))
        session.commit()
        result = twd_dashboard(session=session)

    assert result["summary"] is None
    assert result["monthly"] == []
    assert result["meta"]["latestDataDate"] is None


def test_twd_dashboard_rejects_year_without_data() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                ModernTrade(id=1, code="TWD", name="ไทวัสดุ"),
                _batch(1, 1, date(2026, 6, 30)),
            ]
        )
        session.commit()
        with pytest.raises(HTTPException) as error:
            twd_dashboard(session=session, year=2025, period="ytd")

    assert error.value.status_code == 422

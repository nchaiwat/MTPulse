from datetime import UTC, datetime
from io import BytesIO

import openpyxl

from app.services.dashboard_export import (
    build_dashboard_workbook,
    dashboard_export_filename,
)


def _dashboard() -> dict:
    return {
        "meta": {
            "mtCode": "TWD",
            "mtName": "ไทวัสดุ",
            "year": 2026,
            "previousYear": 2025,
            "period": "ytd",
            "latestDataDate": "2026-08-31",
            "loadedDays": 172,
            "expectedDays": 243,
            "completenessPercent": 70.8,
        },
        "summary": {
            "currentAmount": 193_678_540,
            "previousAmount": 255_778_931,
            "amountYoY": -24.3,
            "currentQty": 72_187,
            "previousQty": 96_585,
            "qtyYoY": -25.3,
        },
        "monthly": [
            {
                "month": 1,
                "monthKey": "2026-01",
                "currentAmount": 25_000_000,
                "previousAmount": 36_000_000,
                "amountYoY": -30.6,
                "amountMoM": None,
                "currentQty": 10_000,
                "previousQty": 14_000,
                "qtyYoY": -28.6,
            }
        ],
        "topBranches": [
            {
                "branchCode": "60919",
                "displayName": "60919 - สุขาภิบาล 3 (CTW-0051)",
                "currentAmount": 5_000_000,
                "previousAmount": 8_000_000,
                "amountYoY": -37.5,
                "currentQty": 2_000,
                "previousQty": 3_000,
                "qtyYoY": -33.3,
            }
        ],
        "topSkus": [
            {
                "sku": "060277546",
                "description": "สินค้า A",
                "currentAmount": 1_200_000,
                "previousAmount": 1_000_000,
                "amountYoY": 20,
                "currentQty": 500,
                "previousQty": 450,
                "qtyYoY": 11.1,
            }
        ],
    }


def test_dashboard_workbook_matches_visible_summary_and_sections() -> None:
    content = build_dashboard_workbook(_dashboard(), metric="amount")
    workbook = openpyxl.load_workbook(BytesIO(content), data_only=False)
    sheet = workbook["Dashboard"]

    assert sheet["A1"].value == "TWD Sales Dashboard"
    assert "Year: 2026 | Period: YTD | Metric: Amount" in sheet["A2"].value
    assert sheet["A5"].value == 193_678_540
    assert sheet["C5"].value == -0.243
    assert sheet["A8"].value == "Monthly Performance"
    assert sheet["A10"].value == "2026-01"
    assert sheet["A13"].value == "Top 10 Branches"
    assert sheet["B15"].value == "60919"
    assert sheet["A18"].value == "Top 15 SKU"
    assert sheet["B20"].value == "060277546"
    assert sheet.freeze_panes == "A10"
    assert sheet.auto_filter.ref == "A9:H10"
    workbook.close()


def test_dashboard_export_filename_contains_active_filters() -> None:
    assert dashboard_export_filename(
        "TWD",
        2026,
        "h1",
        "qty",
        datetime(2026, 9, 9, 1, 2, 3, tzinfo=UTC),
    ) == "TWD_Dashboard_2026_H1_Qty_20260909_080203.xlsx"

from datetime import datetime
from io import BytesIO

import openpyxl

from app.services.performance_export import (
    build_performance_workbook,
    performance_export_filename,
)


def _report() -> dict:
    return {
        "dates": ["2026-08-17"],
        "selectedMonth": "2026-08",
        "branches": [
            {"id": "60016", "name": "ภูเก็ต เฟสติวัล"},
            {"id": "60926", "name": "ลำปาง"},
        ],
        "items": [
            {
                "sku": "060277546",
                "twdDescription": "สินค้าไทยหนึ่ง",
                "waItem": "FA09-W0112-080050",
                "waDescription": "สินค้า WA หนึ่ง",
                "points": [
                    {
                        "date": "2026-08-17",
                        "branchId": "60016",
                        "amount": 100.5,
                        "qty": 2,
                        "stockOh": 7,
                        "stockOnOrder": 1,
                    },
                    {
                        "date": "2026-08-17",
                        "branchId": "60926",
                        "amount": 50,
                        "qty": 1,
                        "stockOh": 3,
                        "stockOnOrder": 0,
                    },
                ],
            },
            {
                "sku": "060277547",
                "twdDescription": "สินค้าไทยสอง",
                "waItem": "FA09-W0112-100110",
                "waDescription": "สินค้า WA สอง",
                "points": [
                    {
                        "date": "2026-08-17",
                        "branchId": "60926",
                        "amount": -25,
                        "qty": -1,
                        "stockOh": 4,
                        "stockOnOrder": 2,
                    },
                ],
            },
        ],
    }


def test_performance_workbook_contains_all_rows_formulas_and_branch_headers() -> None:
    content = build_performance_workbook(
        _report(),
        mode="sales",
        metric="amount",
        grain="day",
        show_descriptions=True,
        branch_id=None,
    )
    workbook = openpyxl.load_workbook(BytesIO(content), data_only=False)
    sheet = workbook["Report"]

    assert sheet["A5"].value == "TWD SKU"
    assert sheet["B5"].value == "TWD Description"
    assert sheet["E5"].value == "TOTAL"
    assert sheet["F5"].value == "60016 - ภูเก็ต เฟสติวัล"
    assert sheet["G5"].value == "60926 - ลำปาง"
    assert sheet["A6"].value == "060277546"
    assert sheet["A7"].value == "060277547"
    assert sheet["E6"].value == "=SUM(F6:G6)"
    assert sheet["E4"].value == "=SUM(E6:E7)"
    assert sheet["F6"].value == 100.5
    assert sheet["G6"].value == 50
    assert sheet["G7"].value == -25
    assert sheet.freeze_panes == "F6"
    assert sheet.auto_filter.ref == "A5:G7"
    workbook.close()


def test_performance_workbook_can_hide_description_columns() -> None:
    content = build_performance_workbook(
        _report(),
        mode="sales",
        metric="qty",
        grain="day",
        show_descriptions=False,
        branch_id=None,
    )
    workbook = openpyxl.load_workbook(BytesIO(content), data_only=False)
    sheet = workbook["Report"]

    assert [sheet.cell(5, column).value for column in range(1, 6)] == [
        "TWD SKU",
        "WA Item",
        "TOTAL",
        "60016 - ภูเก็ต เฟสติวัล",
        "60926 - ลำปาง",
    ]
    assert sheet["C6"].value == "=SUM(D6:E6)"
    workbook.close()




def test_performance_workbook_keeps_backend_aggregate_for_selected_branches() -> None:
    report = _report()
    report["items"] = [
        {
            **report["items"][0],
            "points": [
                {
                    "date": "2026-08-17",
                    "branchId": "all",
                    "amount": 150.5,
                    "qty": 3,
                    "stockOh": 0,
                    "stockOnOrder": 0,
                }
            ],
        }
    ]
    content = build_performance_workbook(
        report,
        mode="sales",
        metric="amount",
        grain="day_total",
        show_descriptions=False,
        branch_ids=["60016", "60926"],
    )
    workbook = openpyxl.load_workbook(BytesIO(content), data_only=False)
    sheet = workbook["Report"]

    assert sheet["D5"].value == "17/08/2026"
    assert sheet["D6"].value == 150.5
    assert sheet["C6"].value == "=SUM(D6:D6)"
    workbook.close()

def test_performance_export_filename_has_view_and_unique_timestamp() -> None:
    filename = performance_export_filename(
        "sales",
        "amount",
        "day",
        datetime(2026, 8, 25, 12, 34, 56),
    )

    assert filename == "TWD_Sales_Amount_Branch_20260825_123456.xlsx"
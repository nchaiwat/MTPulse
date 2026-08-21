from pathlib import Path

import openpyxl

from app.services.mapping_import import extract_mapping_workbook


def test_extract_mapping_workbook_deduplicates_and_excludes_conflicts(tmp_path: Path) -> None:
    path = tmp_path / "mapping.xlsx"
    workbook = openpyxl.Workbook()
    item_sheet = workbook.active
    item_sheet.title = "BP 22.1.26"
    item_sheet.append(["BP Code", "BP Name", "Item No.", "Description", "Catalog"])
    item_sheet.append(["CTW-0001", "A", "WA-001", "สินค้า 1", 60424005])
    item_sheet.append(["CTW-0002", "B", "WA-001", "สินค้า 1", 60424005])
    item_sheet.append(["CTW-0001", "A", "WA-002", "สินค้า 2", 60424006])
    item_sheet.append(["CTW-0002", "B", "WA-003", "สินค้า 3", 60424006])
    item_sheet.append(["CDH-0001", "C", "OTHER", "ไม่ใช่ TWD", 60424007])
    branch_sheet = workbook.create_sheet("สาขา")
    branch_sheet.append(["Store", "Code", "Name", "WA BP"])
    branch_sheet.append(["60920-Bangna", 60920, "บางนา", "CTW-0001"])
    branch_sheet.append(["30000-New", 30000, "New", None])
    workbook.save(path)

    extract = extract_mapping_workbook(path)

    assert extract.raw_item_rows == 4
    assert extract.duplicate_item_rows == 1
    assert extract.item_conflicts == ("060424006",)
    assert [(item.source_sku, item.wa_item_code) for item in extract.items] == [
        ("060424005", "WA-001")
    ]
    assert [(branch.source_branch_code, branch.wa_branch_code) for branch in extract.branches] == [
        ("60920", "CTW-0001")
    ]
    assert extract.unresolved_branch_rows == 1

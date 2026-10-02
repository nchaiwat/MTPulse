from datetime import date
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.importers.dh import extract_dh_pair
from app.services.dh_pricing import DhPrice, DhPricingError, price_dh_pair


def _save_sale(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(
        [
            "รหัสสินค้า",
            "ชื่อสินค้า",
            "ชื่อผู้ดูแลขาย",
            "บางนา-ตราด",
            "To go สาทร",
            "รวม",
        ]
    )
    sheet.append(["00123", "สินค้า A", "OWNER", 2, 0, 2])
    sheet.append(["00456", "สินค้า B", "OWNER", -1, 3, 2])
    sheet.append([None, None, None, 0, 600, 4])
    workbook.save(path)


def _save_stock(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(
        [
            "รหัสสาขา",
            "ชื่อสาขา",
            "รหัสสินค้า",
            "ชื่อสินค้า",
            "หน่วย",
            "ชื่อหน่วย",
            "สต็อกคงเหลือ",
            "จำนวนขาย",
        ]
    )
    sheet.append(["BN", "บางนา-ตราด", "00123", "สินค้า A", "EA", "ชิ้น", 10, 2])
    sheet.append(["BN", "บางนา-ตราด", "00456", "สินค้า B", "EA", "ชิ้น", 5, -1])
    workbook.save(path)


def _pair(tmp_path: Path):
    sale = tmp_path / "รายงานยอดขาย06-01-2025_06-01-2025.xlsx"
    stock = tmp_path / "รายงานสต็อคAll07-01-2025_07-01-2025.xlsx"
    _save_sale(sale)
    _save_stock(stock)
    return extract_dh_pair(stock, sale)


def test_dh_pricing_uses_effective_ex_vat_price_per_sku(tmp_path: Path) -> None:
    priced = price_dh_pair(
        _pair(tmp_path),
        (
            DhPrice("00123", 100, date(2025, 1, 1), date(2025, 1, 5)),
            DhPrice("00123", 120, date(2025, 1, 6)),
            DhPrice("00456", 200, date(2025, 1, 1)),
        ),
    )

    rows = {(row.branch_code, row.sku): row for row in priced.rows}
    assert rows[("BN", "00123")].unit_price_ex_vat == 120
    assert rows[("BN", "00123")].amount == 240
    assert rows[("BN", "00456")].amount == -200
    assert sum(row.amount for row in priced.rows) == 640
    assert priced.summary.source_footer_amount == 600
    assert priced.summary.derived_amount == 640
    assert priced.reconciliation_errors == (
        "Amount สาขา บางนา-ตราด จาก Qty × ราคา 40.000000000000 "
        "ไม่ตรงกับ Footer 0E-12",
        "Amount รวมจาก Qty × ราคา 640.000000000000 "
        "ไม่ตรงกับ Footer 600.000000000000",
    )


def test_dh_pricing_rejects_missing_or_zero_price(tmp_path: Path) -> None:
    pair = _pair(tmp_path)

    with pytest.raises(DhPricingError, match="00456"):
        price_dh_pair(pair, (DhPrice("00123", 100, date(2025, 1, 1)),))

    with pytest.raises(DhPricingError, match="ต้องมากกว่า 0"):
        price_dh_pair(
            pair,
            (
                DhPrice("00123", 100, date(2025, 1, 1), date(2025, 1, 10)),
                DhPrice("00456", 0, date(2025, 1, 1)),
            ),
        )


def test_dh_pricing_rejects_overlapping_effective_prices(tmp_path: Path) -> None:
    with pytest.raises(DhPricingError, match="มากกว่าหนึ่งราคา"):
        price_dh_pair(
            _pair(tmp_path),
            (
                DhPrice("00123", 100, date(2025, 1, 1)),
                DhPrice("00123", 120, date(2025, 1, 5)),
                DhPrice("00456", 200, date(2025, 1, 1)),
            ),
        )


def test_dh_pricing_fingerprint_changes_when_effective_price_changes(
    tmp_path: Path,
) -> None:
    pair = _pair(tmp_path)
    first = price_dh_pair(
        pair,
        (
            DhPrice("00123", 120, date(2025, 1, 1)),
            DhPrice("00456", 200, date(2025, 1, 1)),
        ),
    )
    corrected = price_dh_pair(
        pair,
        (
            DhPrice("00123", 121, date(2025, 1, 1)),
            DhPrice("00456", 200, date(2025, 1, 1)),
        ),
    )

    assert first.business_fingerprint != corrected.business_fingerprint

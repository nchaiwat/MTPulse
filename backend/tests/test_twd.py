from decimal import Decimal
from pathlib import Path

import pytest

from app.importers.twd import calculate_amount, extract_twd_file
from app.models import ImportBatch

SAMPLE_DIR = Path(__file__).parents[2] / ".tmp" / "twd-samples"


def test_calculate_amount_uses_decimal() -> None:
    assert calculate_amount(Decimal("107")) == Decimal("100.000000000000")


def test_import_status_values_fit_database_column() -> None:
    status_length = ImportBatch.__table__.c.status.type.length
    assert status_length is not None
    assert (
        max(map(len, ("imported", "imported_with_warnings", "failed", "duplicate")))
        <= status_length
    )


@pytest.mark.parametrize(
    (
        "filename",
        "period",
        "rows",
        "source_amount",
        "qty",
        "stock_oh",
        "reported_stock_oh",
        "stock_order",
        "negative",
    ),
    [
        (
            "twd-2026-08-16.xls",
            "2026-08-16",
            12560,
            "1101053.72",
            "353",
            "77790",
            "77265",
            "5902",
            4,
        ),
        (
            "twd-2026-08-17.xls",
            "2026-08-17",
            12561,
            "864345.32",
            "345",
            "77941",
            "77416",
            "6338",
            2,
        ),
    ],
)
def test_real_twd_samples_reconcile(
    filename, period, rows, source_amount, qty, stock_oh, reported_stock_oh, stock_order, negative
) -> None:
    path = SAMPLE_DIR / filename
    if not path.exists():
        pytest.skip("ไฟล์ตัวอย่างจาก NAS ไม่มีใน workspace")
    extract = extract_twd_file(path)
    summary = extract.summary
    assert extract.data_date.isoformat() == period
    assert (summary.row_count, summary.store_count, summary.sku_count) == (rows, 102, 2043)
    assert summary.source_amount == Decimal(source_amount)
    assert summary.sales_qty == Decimal(qty)
    assert summary.stock_on_hand == Decimal(stock_oh)
    assert extract.reported_summary.stock_on_hand == Decimal(reported_stock_oh)
    assert summary.stock_on_order == Decimal(stock_order)
    assert summary.negative_row_count == negative
    assert extract.reconciliation_errors == (
        f"Stock On Hand: calculated={Decimal(stock_oh):.1f}, source={Decimal(reported_stock_oh)}",
    )
    assert extract.rows[0].description
    assert any("\u0e00" <= character <= "\u0e7f" for character in extract.rows[0].description)

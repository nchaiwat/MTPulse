from datetime import UTC, datetime

from app.services.automatic_import import SourceCandidate
from app.services.hh_automatic_import import list_hh_pairs


def _candidate(path: str, filename: str) -> SourceCandidate:
    return SourceCandidate(
        path=path,
        filename=filename,
        size_bytes=100,
        modified_at=datetime(2026, 9, 11, tzinfo=UTC),
    )


def test_list_hh_pairs_groups_stock_and_sales_by_day_folder() -> None:
    pairs = list_hh_pairs(
        [
            _candidate(r"\\server\HomeHub\2026-09-10\StockReport.xlsx", "StockReport.xlsx"),
            _candidate(r"\\server\HomeHub\2026-09-10\SaleReport.xlsx", "SaleReport.xlsx"),
            _candidate(r"\\server\HomeHub\2026-09-11\StockReport.xlsx", "StockReport.xlsx"),
            _candidate(r"\\server\HomeHub\2026-09-11\notes.xlsx", "notes.xlsx"),
        ]
    )

    assert len(pairs) == 2
    assert pairs[0].inventory is not None and pairs[0].sales is not None
    assert pairs[1].inventory is not None and pairs[1].sales is None


def test_hh_pairing_does_not_use_sku_or_filename_length_patterns() -> None:
    pairs = list_hh_pairs(
        [
            _candidate(r"\\server\HomeHub\day\StockReport.xlsx", "StockReport.xlsx"),
            _candidate(r"\\server\HomeHub\day\SaleReport.xlsx", "SaleReport.xlsx"),
        ]
    )
    assert len(pairs) == 1
    assert pairs[0].key.endswith(r"homehub\day")

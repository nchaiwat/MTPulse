import csv
import io
from datetime import UTC, datetime
from decimal import Decimal
from itertools import count
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.importers.hp_mh import HpMhFormatError, extract_hp_mh_pair
from app.models import (
    AuditEvent,
    ImportBatch,
    ImportRun,
    InventoryCoverage,
    ModernTrade,
    SalesInventoryFact,
    SkuInterest,
    SourceFile,
)
from app.services import hp_mh_import
from app.services.automatic_import import SourceCandidate, run_payload
from app.services.hp_mh_automatic_import import list_hp_mh_pairs


def _zip_csv(path: Path, member: str, rows: list[list[object]]) -> None:
    lines = []
    for row in rows:
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="")
        writer.writerow(row)
        lines.append(output.getvalue())
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr(member, "\ufeff" + "\n".join(lines))


def _pair(tmp_path: Path, *, renamed: bool = False) -> tuple[Path, Path]:
    suffix = "_renamed" if renamed else ""
    inventory = tmp_path / f"VRM_InventoryData_20260906_070129{suffix}.zip"
    sales = tmp_path / f"VRM_SalesData_20260906_070052{suffix}.zip"
    _zip_csv(
        inventory,
        "VRM_InventoryData_20260906.csv",
        [
            ["Last Update : 06/09/2026", "Output : Onhand"],
            [
                "ARTNO",
                "ARTNAME",
                "S001 QTY",
                "S001 AMT",
                "M026 QTY",
                "M026 AMT",
                "DC01 QTY",
                "DC01 AMT",
            ],
            ["100", "Window A", '="2"', '="214"', "0", "0", "8", "856"],
            ["200", "Door B", "0", "0", "3", "321", "0", "0"],
        ],
    )
    _zip_csv(
        sales,
        "VRM_SalesData_20260906.csv",
        [
            ["Period : 2026-09-06 - 2026-09-06", "Option : Billing(QTY&Amount)"],
            ["PERIODDATE", "SITENO", "ARTNO", "ARTNAME", "QTY", "VALUE"],
            ["2026-09-06", "S001", "100", "Window A", "1", "107"],
            ["2026-09-06", "S001", "100", "Window A", "-1", "-107"],
            ["2026-09-06", "M026", "200", "Door B", "2", "214"],
            ["2026-09-06", "DC01", "999", "Ignored", "9", "963"],
        ],
    )
    return inventory, sales


def test_extract_hp_mh_pair_splits_branches_and_preserves_source_metrics(tmp_path) -> None:
    inventory, sales = _pair(tmp_path)

    extract = extract_hp_mh_pair(inventory, sales)

    assert extract.data_date.isoformat() == "2026-09-06"
    assert extract.ignored_branch_codes == ("DC01",)
    assert extract.hp.sale_skus == frozenset({"100"})
    assert extract.mh.sale_skus == frozenset({"200"})
    assert extract.hp.inventory_skus == frozenset({"100", "200"})
    assert extract.mh.inventory_skus == frozenset({"100", "200"})
    assert extract.hp.summary.source_amount == Decimal("0")
    assert extract.hp.summary.sales_qty == Decimal("0")
    assert extract.hp.summary.stock_on_hand == Decimal("2")
    assert extract.hp.summary.stock_value == Decimal("214")
    assert extract.hp.rows[0].branch_name == "S001"
    assert extract.mh.summary.source_amount == Decimal("214")
    assert extract.mh.summary.amount == Decimal("200.000000000000")
    assert extract.mh.summary.sales_qty == Decimal("2")
    assert extract.mh.summary.stock_on_hand == Decimal("3")
    assert extract.mh.summary.stock_value == Decimal("321")


def test_extract_legacy_row_inventory_preserves_opaque_skus(tmp_path) -> None:
    inventory = tmp_path / "VRM_InventoryData_20250102.zip"
    sales = tmp_path / "VRM_SalesData_20250102.zip"
    _zip_csv(
        inventory,
        "VRM_InventoryData_20250102.csv",
        [
            ["Last Update : 02/01/2025", "Output : Onhand"],
            ["PERIODDATE", "ARTNO", "ARTDESC", "SITENO", "SITENAME", "ONHANDQTY", "ONHANDVALUE"],
            ["02/01/2025", "00001", "Window A", "S001", "HomePro A", "2", "214"],
            ["02/01/2025", "12345678901", "Door B", "M026", "MegaHome B", "3", "321"],
        ],
    )
    _zip_csv(
        sales,
        "VRM_SalesData_20250102.csv",
        [
            ["Period : 2025-01-02 - 2025-01-02"],
            ["PERIODDATE", "SITENO", "SITENAME", "ARTNO", "ARTDESC", "QTY", "VALUE"],
            ["02/01/2025", "S001", "HomePro A", "00001", "Window A", "1", "107"],
            ["02/01/2025", "M026", "MegaHome B", "12345678901", "Door B", "2", "214"],
        ],
    )

    extract = extract_hp_mh_pair(inventory, sales)

    assert extract.hp.sale_skus == frozenset({"00001"})
    assert extract.hp.inventory_skus == frozenset({"00001"})
    assert extract.hp.rows[0].sku == "00001"
    assert extract.hp.summary.stock_on_hand == Decimal("2")
    assert extract.mh.sale_skus == frozenset({"12345678901"})
    assert extract.mh.inventory_skus == frozenset({"12345678901"})
    assert extract.mh.rows[0].sku == "12345678901"
    assert extract.mh.summary.stock_on_hand == Decimal("3")


def test_inventory_uses_ean_to_match_sales_sku_without_length_normalization(tmp_path) -> None:
    inventory = tmp_path / "VRM_InventoryData_20260909.zip"
    sales = tmp_path / "VRM_SalesData_20260909.zip"
    _zip_csv(
        inventory,
        "VRM_InventoryData_20260909.csv",
        [
            ["Last Update : 09/09/2026", "Output : Onhand"],
            ["ARTNO", "ARTDESC", "ARTEAN", "S001 QTY", "S001 AMT", "M026 QTY", "M026 AMT"],
            ["000000000009999999", "Window A", "2400000156673", "10", "1000", "0", "0"],
            ["INVENTORY-CODE-B", "Door B", "2900002724660", "0", "0", "6", "600"],
        ],
    )
    _zip_csv(
        sales,
        "VRM_SalesData_20260909.csv",
        [
            ["Period : 2026-09-09 - 2026-09-09"],
            ["PERIODDATE", "SITENO", "ARTNO", "ARTDESC", "ARTEAN", "QTY", "VALUE"],
            ["09/09/2026", "S001", "00001", "Window A", "2400000156673", "2", "200"],
            ["09/09/2026", "M026", "1128033", "Door B", "2900002724660", "3", "300"],
        ],
    )

    extract = extract_hp_mh_pair(inventory, sales)

    assert extract.hp.inventory_skus == frozenset({"00001", "INVENTORY-CODE-B"})
    assert extract.mh.inventory_skus == frozenset({"000000000009999999", "1128033"})
    hp_row = next(row for row in extract.hp.rows if row.sku == "00001")
    mh_row = next(row for row in extract.mh.rows if row.sku == "1128033")
    assert hp_row.stock_on_hand == Decimal("10")
    assert hp_row.sales_qty == Decimal("2")
    assert mh_row.stock_on_hand == Decimal("6")
    assert mh_row.sales_qty == Decimal("3")


def test_business_fingerprint_ignores_zip_filename(tmp_path) -> None:
    first = extract_hp_mh_pair(*_pair(tmp_path))
    second_dir = tmp_path / "second"
    second_dir.mkdir()
    second = extract_hp_mh_pair(*_pair(second_dir, renamed=True))

    assert first.business_fingerprint == second.business_fingerprint
    assert first.inventory_checksum == second.inventory_checksum
    assert first.sales_checksum == second.sales_checksum


def test_pair_requires_matching_internal_dates(tmp_path) -> None:
    inventory, sales = _pair(tmp_path)
    _zip_csv(
        sales,
        "VRM_SalesData_20260907.csv",
        [
            ["Period : 2026-09-07 - 2026-09-07"],
            ["PERIODDATE", "SITENO", "ARTNO", "QTY", "VALUE"],
            ["2026-09-07", "S001", "100", "1", "107"],
        ],
    )

    with pytest.raises(HpMhFormatError, match="วันที่ข้อมูล Inventory และ Sale Out ไม่ตรงกัน"):
        extract_hp_mh_pair(inventory, sales)


def test_pair_ignores_sales_outside_inventory_date_with_warning(tmp_path) -> None:
    inventory, sales = _pair(tmp_path)
    _zip_csv(
        sales,
        "VRM_SalesData_20260906.csv",
        [
            ["Period : 2026-09-06 - 2026-09-07"],
            ["PERIODDATE", "SITENO", "ARTNO", "QTY", "VALUE"],
            ["2026-09-06", "S001", "00001", "1", "107"],
            ["2026-09-07", "S001", "00001", "2", "214"],
        ],
    )

    extract = extract_hp_mh_pair(inventory, sales)

    assert extract.data_date.isoformat() == "2026-09-06"
    assert extract.hp.summary.sales_qty == Decimal("1")
    assert any("06/09/2026" in warning for warning in extract.reconciliation_errors)


def test_zero_byte_zip_is_skipped_as_format_error(tmp_path) -> None:
    inventory, sales = _pair(tmp_path)
    inventory.write_bytes(b"")

    with pytest.raises(HpMhFormatError, match="0 bytes"):
        extract_hp_mh_pair(inventory, sales)


def test_pairing_selects_latest_generation_and_marks_older_superseded() -> None:
    timestamp = datetime(2026, 9, 7, tzinfo=UTC)

    def candidate(filename: str) -> SourceCandidate:
        return SourceCandidate(
            path=rf"\\server\share\HP_MH\2026-09-07\{filename}",
            filename=filename,
            size_bytes=100,
            modified_at=timestamp,
        )

    old_inventory = candidate("VRM_0000003970_InventoryData_20260906_20260907_070100.zip")
    new_inventory = candidate("VRM_0000003970_InventoryData_20260906_20260907_070129.zip")
    sales = candidate("VRM_0000003970_SalesData_20260906_20260907_070052.zip")

    pairs = list_hp_mh_pairs([new_inventory, old_inventory, sales])

    assert len(pairs) == 1
    assert pairs[0].inventory == new_inventory
    assert pairs[0].sales == sales
    assert pairs[0].superseded == (("inventory", old_inventory),)


def test_shared_run_progress_counts_pairs_instead_of_physical_files() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime(2026, 9, 7, tzinfo=UTC)
    with Session(engine) as session:
        mt = ModernTrade(
            id=1,
            code="HP",
            name="HomePro",
            source_group_code="HP_MH",
        )
        run = ImportRun(
            id=1,
            modern_trade_id=1,
            trigger="manual",
            mode="import",
            status="running",
            requested_by="admin",
            found_count=1,
        )
        session.add_all([mt, run])
        session.add_all(
            [
                SourceFile(
                    modern_trade_id=1,
                    source_path=rf"\\server\share\HP_MH\day\{kind}.zip",
                    source_filename=f"{kind}.zip",
                    size_bytes=100,
                    modified_at=now,
                    status="imported",
                    source_kind=kind,
                    pair_key=r"\\server\share\hp_mh\day",
                    last_seen_run_id=1,
                    last_seen_at=now,
                )
                for kind in ("inventory", "sales")
            ]
        )
        session.commit()

        progress = run_payload(run, mt, session=session)["progress"]

    assert progress is not None
    assert progress["processed"] == 1
    assert progress["total"] == 1
    assert progress["percent"] == 100
    assert progress["counts"]["imported"] == 1


def test_corrected_pair_replaces_both_mts_and_writes_one_audit(tmp_path, monkeypatch) -> None:
    audit_ids = count(1)
    batch_ids = count(1)
    fact_ids = count(1)
    coverage_ids = count(1)
    monkeypatch.setattr(
        hp_mh_import,
        "AuditEvent",
        lambda **values: AuditEvent(id=next(audit_ids), **values),
    )
    monkeypatch.setattr(
        hp_mh_import,
        "_new_import_batch",
        lambda **values: ImportBatch(id=next(batch_ids), **values),
    )
    monkeypatch.setattr(
        hp_mh_import,
        "_new_fact",
        lambda **values: SalesInventoryFact(id=next(fact_ids), **values),
    )
    monkeypatch.setattr(
        hp_mh_import,
        "_new_coverage",
        lambda **values: InventoryCoverage(id=next(coverage_ids), **values),
    )
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    first = extract_hp_mh_pair(*_pair(tmp_path))
    corrected_dir = tmp_path / "corrected"
    corrected_dir.mkdir()
    inventory, sales = _pair(corrected_dir, renamed=True)
    _zip_csv(
        sales,
        "VRM_SalesData_20260906.csv",
        [
            ["Period : 2026-09-06 - 2026-09-06"],
            ["PERIODDATE", "SITENO", "ARTNO", "ARTNAME", "QTY", "VALUE"],
            ["2026-09-06", "S001", "100", "Window A", "2", "214"],
            ["2026-09-06", "M026", "200", "Door B", "3", "321"],
        ],
    )
    corrected = extract_hp_mh_pair(inventory, sales)

    with Session(engine) as session:
        session.add_all(
            [
                ModernTrade(id=1, code="HP", name="HomePro"),
                ModernTrade(id=2, code="MH", name="MegaHome"),
                SkuInterest(
                    id=1,
                    modern_trade_id=1,
                    source_sku="100",
                    status="active",
                    first_seen_date=first.data_date,
                    last_seen_date=first.data_date,
                ),
                SkuInterest(
                    id=2,
                    modern_trade_id=2,
                    source_sku="200",
                    status="active",
                    first_seen_date=first.data_date,
                    last_seen_date=first.data_date,
                ),
            ]
        )
        session.commit()
        hp_mh_import.import_hp_mh_pair(session, first, actor="admin")
        session.commit()
        first_ids = {
            batch.modern_trade_id: batch.id for batch in session.scalars(select(ImportBatch))
        }

        batches = hp_mh_import.import_hp_mh_pair(session, corrected, actor="admin")
        session.commit()
        audit = session.scalar(select(AuditEvent).where(AuditEvent.action == "corrected_reimport"))
        corrected_ids = {batch.id for batch in batches.values()}
        corrected_fingerprints = {batch.business_fingerprint for batch in batches.values()}

    assert corrected_ids == set(first_ids.values())
    assert corrected_fingerprints == {corrected.business_fingerprint}
    assert audit is not None
    assert audit.entity_id == "2026-09-06"
    assert audit.actor == "admin"

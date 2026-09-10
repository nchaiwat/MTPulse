from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base
from app.models import ManualUploadBatch, ManualUploadFile
from app.services import manual_upload_detection
from app.services.manual_upload_contracts import (
    MAX_FOLDER_FILES,
    MAX_UPLOAD_BYTES,
    ManualUploadContractError,
    validate_upload_batch_request,
    validate_upload_file_contract,
)
from app.services.manual_upload_detection import detect_upload_batch, detect_upload_file


def test_user_can_upload_one_file_but_cannot_use_folder_mode() -> None:
    validate_upload_batch_request(source_mode="single", file_count=1, is_admin=False)

    with pytest.raises(ManualUploadContractError, match="Admin"):
        validate_upload_batch_request(source_mode="folder", file_count=1, is_admin=False)


def test_admin_folder_limit_is_200_files() -> None:
    validate_upload_batch_request(
        source_mode="folder",
        file_count=MAX_FOLDER_FILES,
        is_admin=True,
    )

    with pytest.raises(ManualUploadContractError, match="200"):
        validate_upload_batch_request(
            source_mode="folder",
            file_count=MAX_FOLDER_FILES + 1,
            is_admin=True,
        )


def test_single_mode_rejects_multiple_files() -> None:
    with pytest.raises(ManualUploadContractError, match="ครั้งละ 1 ไฟล์"):
        validate_upload_batch_request(source_mode="single", file_count=2, is_admin=True)


def test_upload_file_contract_enforces_size_and_direct_folder_level() -> None:
    validate_upload_file_contract(size_bytes=MAX_UPLOAD_BYTES, relative_depth=1)

    with pytest.raises(ManualUploadContractError, match="25 MB"):
        validate_upload_file_contract(size_bytes=MAX_UPLOAD_BYTES + 1, relative_depth=1)
    with pytest.raises(ManualUploadContractError, match="ระดับแรก"):
        validate_upload_file_contract(size_bytes=1, relative_depth=2)


def _zip_with_member(path, member: str) -> None:
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr(member, "header\n")


def test_hp_mh_detection_uses_archive_contract_not_outer_filename(tmp_path) -> None:
    source = tmp_path / "looks-like-twd.zip"
    _zip_with_member(source, "VRM_InventoryData_20260909.csv")

    result = detect_upload_file(source)

    assert result.status == "detected"
    assert result.source_group_code == "HP_MH"
    assert result.mt_codes == ("HP", "MH")
    assert result.source_kind == "inventory"


def test_hp_mh_shared_source_is_one_group_not_mixed_mt(tmp_path) -> None:
    inventory = tmp_path / "inventory.zip"
    sales = tmp_path / "sales.zip"
    _zip_with_member(inventory, "InventoryData.csv")
    _zip_with_member(sales, "SalesData.csv")

    result = detect_upload_batch([inventory, sales])

    assert result.status == "detected"
    assert result.source_group_code == "HP_MH"
    assert result.mt_codes == ("HP", "MH")


def test_batch_rejects_multiple_source_groups(tmp_path, monkeypatch) -> None:
    twd = tmp_path / "twd.xlsx"
    twd.write_bytes(b"not parsed because importer is wrapped")
    hp_mh = tmp_path / "hp-mh.zip"
    _zip_with_member(hp_mh, "SalesData.csv")
    monkeypatch.setattr(
        manual_upload_detection,
        "extract_twd_file",
        lambda _path: SimpleNamespace(data_date=date(2026, 9, 9)),
    )

    result = detect_upload_batch([twd, hp_mh])

    assert result.status == "conflict"
    assert "มากกว่าหนึ่ง" in (result.reason or "")


def test_hp_mh_pair_validation_wraps_existing_strict_importer(tmp_path, monkeypatch) -> None:
    inventory = tmp_path / "any-inventory-name.zip"
    sales = tmp_path / "any-sales-name.zip"
    monkeypatch.setattr(
        manual_upload_detection,
        "extract_hp_mh_pair",
        lambda *_paths: SimpleNamespace(data_date=date(2026, 9, 9)),
    )

    result = manual_upload_detection.validate_hp_mh_pair(inventory, sales)

    assert result.status == "detected"
    assert result.source_group_code == "HP_MH"
    assert result.mt_codes == ("HP", "MH")


def test_unknown_file_requires_review(tmp_path) -> None:
    source = tmp_path / "unknown.txt"
    source.write_text("unknown", encoding="utf-8")

    result = detect_upload_batch([source])

    assert result.status == "needs_review"
    assert result.source_group_code is None


def test_upload_file_idempotency_is_scoped_to_batch() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime(2026, 9, 10, tzinfo=UTC)
    with Session(engine) as session:
        batch = ManualUploadBatch(
            status="uploading",
            source_mode="folder",
            requested_by="admin",
            expires_at=now + timedelta(days=7),
        )
        session.add(batch)
        session.flush()
        values = {
            "upload_batch_id": batch.id,
            "display_filename": "source.zip",
            "size_bytes": 100,
            "idempotency_key": "same-file",
            "status": "uploaded",
            "expires_at": now + timedelta(days=7),
        }
        session.add_all([ManualUploadFile(**values), ManualUploadFile(**values)])

        with pytest.raises(IntegrityError):
            session.commit()

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from zipfile import BadZipFile, ZipFile

from app.importers.hh import HhFormatError, extract_hh_pair, inspect_hh_workbook
from app.importers.hp_mh import HpMhFormatError, extract_hp_mh_pair
from app.importers.twd import TwdFormatError, extract_twd_file

DetectionStatus = Literal["detected", "needs_review", "conflict", "unsupported"]


@dataclass(frozen=True)
class UploadDetection:
    status: DetectionStatus
    source_group_code: str | None
    mt_codes: tuple[str, ...]
    source_kind: str | None
    evidence: tuple[str, ...]
    reason: str | None = None


@dataclass(frozen=True)
class UploadBatchDetection:
    status: DetectionStatus
    source_group_code: str | None
    mt_codes: tuple[str, ...]
    files: tuple[UploadDetection, ...]
    reason: str | None = None


def _detect_twd_workbook(path: Path) -> UploadDetection:
    try:
        extract = extract_twd_file(path)
    except (TwdFormatError, OSError, ValueError) as exc:
        return _unsupported(f"โครงสร้าง Excel ไม่ตรงกับ TWD: {exc}")
    return UploadDetection(
        status="detected",
        source_group_code="TWD",
        mt_codes=("TWD",),
        source_kind="workbook",
        evidence=(
            "ผ่าน Strict Validation ของ TWD importer",
            f"Data date {extract.data_date.isoformat()}",
        ),
    )


def _detect_excel_workbook(path: Path) -> UploadDetection:
    twd = _detect_twd_workbook(path)
    if twd.status == "detected":
        return twd
    try:
        kind, data_date = inspect_hh_workbook(path)
    except (HhFormatError, OSError, ValueError):
        return twd
    return UploadDetection(
        status="detected",
        source_group_code="HH",
        mt_codes=("HH",),
        source_kind=kind,
        evidence=(
            "ผ่าน Strict Validation ของ HH workbook",
            f"Data date {data_date.isoformat()}",
        ),
    )


def detect_upload_batch(paths: list[str | Path]) -> UploadBatchDetection:
    detections = tuple(detect_upload_file(path) for path in paths)
    detected = [item for item in detections if item.status == "detected"]
    groups = {item.source_group_code for item in detected if item.source_group_code}
    if len(groups) > 1:
        return UploadBatchDetection(
            status="conflict",
            source_group_code=None,
            mt_codes=(),
            files=detections,
            reason="พบข้อมูลมากกว่าหนึ่ง Modern Trade/Source Group ใน Folder เดียว",
        )
    if not groups:
        return UploadBatchDetection(
            status="needs_review",
            source_group_code=None,
            mt_codes=(),
            files=detections,
            reason="ยังไม่พบไฟล์ที่ระบบระบุ Modern Trade ได้",
        )
    group = next(iter(groups))
    mt_codes = tuple(dict.fromkeys(code for item in detected for code in item.mt_codes))
    return UploadBatchDetection(
        status="detected",
        source_group_code=group,
        mt_codes=mt_codes,
        files=detections,
    )


def validate_hp_mh_pair(
    inventory_path: str | Path,
    sales_path: str | Path,
) -> UploadDetection:
    try:
        extract = extract_hp_mh_pair(inventory_path, sales_path)
    except (HpMhFormatError, OSError, ValueError) as exc:
        return UploadDetection(
            status="conflict",
            source_group_code="HP_MH",
            mt_codes=("HP", "MH"),
            source_kind="pair",
            evidence=(),
            reason=f"คู่ไฟล์ HP/MH ไม่ผ่าน Strict Validation: {exc}",
        )
    return UploadDetection(
        status="detected",
        source_group_code="HP_MH",
        mt_codes=("HP", "MH"),
        source_kind="pair",
        evidence=(
            "ผ่าน Strict Validation ของ HP/MH pair importer",
            f"Data date {extract.data_date.isoformat()}",
        ),
    )


def validate_hh_pair(
    inventory_path: str | Path,
    sales_path: str | Path,
) -> UploadDetection:
    try:
        extract = extract_hh_pair(inventory_path, sales_path)
    except (HhFormatError, OSError, ValueError) as exc:
        return UploadDetection(
            status="conflict",
            source_group_code="HH",
            mt_codes=("HH",),
            source_kind="pair",
            evidence=(),
            reason=f"คู่ไฟล์ HH ไม่ผ่าน Strict Validation: {exc}",
        )
    return UploadDetection(
        status="detected",
        source_group_code="HH",
        mt_codes=("HH",),
        source_kind="pair",
        evidence=(
            "ผ่าน Strict Validation ของ HH pair importer",
            f"Data date {extract.data_date.isoformat()}",
        ),
    )


def _detect_hp_mh_archive(path: Path) -> UploadDetection:
    try:
        with ZipFile(path) as archive:
            members = [
                Path(name).name.lower()
                for name in archive.namelist()
                if not name.endswith("/") and Path(name).suffix.lower() == ".csv"
            ]
    except (BadZipFile, OSError) as exc:
        return _unsupported(f"เปิด ZIP ไม่สำเร็จ: {exc}")
    if len(members) != 1:
        return _unsupported(f"ZIP ต้องมี CSV หนึ่งไฟล์ แต่พบ {len(members)} ไฟล์")
    member = members[0]
    if "inventorydata" in member:
        source_kind = "inventory"
    elif "salesdata" in member:
        source_kind = "sales"
    else:
        return _unsupported("ชื่อข้อมูลภายใน ZIP ไม่ใช่ InventoryData หรือ SalesData")
    return UploadDetection(
        status="detected",
        source_group_code="HP_MH",
        mt_codes=("HP", "MH"),
        source_kind=source_kind,
        evidence=(f"พบ {source_kind} CSV ตามสัญญา HP/MH ภายใน ZIP",),
    )


Detector = Callable[[Path], UploadDetection]
DETECTOR_REGISTRY: dict[str, Detector] = {
    ".xls": _detect_twd_workbook,
    ".xlsx": _detect_excel_workbook,
    ".zip": _detect_hp_mh_archive,
}


def detect_upload_file(source_path: str | Path) -> UploadDetection:
    path = Path(source_path)
    suffix = path.suffix.lower()
    detector = DETECTOR_REGISTRY.get(suffix)
    if detector is None:
        return _unsupported(f"ไม่รองรับไฟล์ชนิด {suffix or 'ไม่มีนามสกุล'}")
    return detector(path)


def _unsupported(reason: str) -> UploadDetection:
    return UploadDetection(
        status="unsupported",
        source_group_code=None,
        mt_codes=(),
        source_kind=None,
        evidence=(),
        reason=reason,
    )

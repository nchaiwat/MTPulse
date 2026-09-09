from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from app.importers.twd import STORAGE_SCALE, calculate_amount, sha256_file

BRANCH_PATTERN = re.compile(r"(?<![A-Z0-9])([A-Z]{1,2}\d{2,3})(?![A-Z0-9])", re.I)
DATE_PATTERN = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})\b")


class HpMhFormatError(ValueError):
    """Raised when a HP/MH ZIP pair violates the agreed source contract."""


@dataclass(frozen=True)
class HpMhRow:
    branch_code: str
    branch_name: str
    sku: str
    description: str | None
    source_amount: Decimal
    amount: Decimal
    sales_qty: Decimal
    stock_on_hand: Decimal
    stock_value: Decimal


@dataclass(frozen=True)
class HpMhSummary:
    row_count: int
    store_count: int
    sku_count: int
    negative_row_count: int
    source_amount: Decimal
    amount: Decimal
    sales_qty: Decimal
    stock_on_hand: Decimal
    stock_value: Decimal


@dataclass(frozen=True)
class HpMhMtExtract:
    code: str
    data_date: date
    rows: tuple[HpMhRow, ...]
    summary: HpMhSummary
    sale_skus: frozenset[str]
    inventory_skus: frozenset[str]
    inventory_branches: frozenset[str]


@dataclass(frozen=True)
class HpMhPairExtract:
    data_date: date
    inventory_path: str
    sales_path: str
    inventory_filename: str
    sales_filename: str
    inventory_checksum: str
    sales_checksum: str
    business_fingerprint: str
    hp: HpMhMtExtract
    mh: HpMhMtExtract
    ignored_branch_codes: tuple[str, ...]
    reconciliation_errors: tuple[str, ...]


@dataclass
class _Values:
    branch_name: str = ""
    description: str | None = None
    source_amount: Decimal = Decimal("0")
    sales_qty: Decimal = Decimal("0")
    stock_on_hand: Decimal = Decimal("0")
    stock_value: Decimal = Decimal("0")


def extract_hp_mh_pair(
    inventory_path: str | Path,
    sales_path: str | Path,
) -> HpMhPairExtract:
    inventory = Path(inventory_path)
    sales = Path(sales_path)
    inventory_rows = _read_zip_csv(inventory, expected_kind="inventory")
    sales_rows = _read_zip_csv(sales, expected_kind="sales")

    inventory_date, inventory_values, inventory_meta = _parse_inventory(inventory_rows)
    sales_date, sales_values, sales_meta = _parse_sales(sales_rows)
    if inventory_date != sales_date:
        raise HpMhFormatError(
            "วันที่ข้อมูล Inventory และ Sale Out ไม่ตรงกัน: "
            f"{inventory_date:%d/%m/%Y} != {sales_date:%d/%m/%Y}"
        )

    combined: dict[tuple[str, str, str], _Values] = defaultdict(_Values)
    ignored = set(inventory_meta["ignored_branches"]) | set(sales_meta["ignored_branches"])
    for key, value in inventory_values.items():
        target = combined[key]
        target.branch_name = value.branch_name
        target.description = value.description
        target.stock_on_hand += value.stock_on_hand
        target.stock_value += value.stock_value
    for key, value in sales_values.items():
        target = combined[key]
        target.branch_name = value.branch_name or target.branch_name
        target.description = value.description or target.description
        target.source_amount += value.source_amount
        target.sales_qty += value.sales_qty

    extracts = {
        code: _build_mt_extract(
            code,
            inventory_date,
            combined,
            sale_skus=sales_meta["sale_skus"][code],
            inventory_skus=inventory_meta["inventory_skus"][code],
            inventory_branches=inventory_meta["inventory_branches"][code],
        )
        for code in ("HP", "MH")
    }
    fingerprint = _business_fingerprint(inventory_date, combined)
    return HpMhPairExtract(
        data_date=inventory_date,
        inventory_path=str(inventory),
        sales_path=str(sales),
        inventory_filename=inventory.name,
        sales_filename=sales.name,
        inventory_checksum=sha256_file(inventory),
        sales_checksum=sha256_file(sales),
        business_fingerprint=fingerprint,
        hp=extracts["HP"],
        mh=extracts["MH"],
        ignored_branch_codes=tuple(sorted(ignored)),
        reconciliation_errors=tuple(inventory_meta["errors"]),
    )


def _read_zip_csv(path: Path, *, expected_kind: str) -> list[list[str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size == 0:
        raise HpMhFormatError(f"ไฟล์ {path.name} มีขนาด 0 bytes")
    try:
        with ZipFile(path) as archive:
            members = [
                name
                for name in archive.namelist()
                if not name.endswith("/") and Path(name).suffix.lower() == ".csv"
            ]
            if len(members) != 1:
                raise HpMhFormatError(
                    f"ZIP {path.name} ต้องมี CSV หนึ่งไฟล์ แต่พบ {len(members)} ไฟล์"
                )
            member = members[0]
            lower = member.lower()
            if expected_kind == "inventory" and "inventorydata" not in lower:
                raise HpMhFormatError(f"ZIP {path.name} ไม่ใช่ InventoryData")
            if expected_kind == "sales" and "salesdata" not in lower:
                raise HpMhFormatError(f"ZIP {path.name} ไม่ใช่ SalesData")
            with archive.open(member) as stream:
                text = (line.decode("utf-8-sig") for line in stream)
                return [[_clean(cell) for cell in row] for row in csv.reader(text)]
    except (BadZipFile, UnicodeDecodeError, OSError) as exc:
        raise HpMhFormatError(f"เปิด ZIP {path.name} ไม่สำเร็จ: {exc}") from exc


def _clean(value: object) -> str:
    text = str(value or "").strip()
    if text.startswith('="') and text.endswith('"'):
        return text[2:-1].strip()
    return text


def _normalized(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _decimal(value: str, *, field: str, row_number: int) -> Decimal:
    text = _clean(value).replace(",", "")
    if not text:
        return Decimal("0")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise HpMhFormatError(
            f"{field} แถว {row_number} ไม่ใช่ตัวเลข: {value!r}"
        ) from exc


def _date(value: str) -> date:
    text = _clean(value)
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            pass
    raise HpMhFormatError(f"วันที่ข้อมูลไม่ถูกต้อง: {value!r}")


def _find_header(rows: list[list[str]], required: set[str]) -> int:
    for index, row in enumerate(rows):
        names = {_normalized(cell) for cell in row}
        if required.issubset(names):
            return index
    raise HpMhFormatError("ไม่พบ Header ที่จำเป็น: " + ", ".join(sorted(required)))


def _header_index(row: list[str], *names: str) -> int | None:
    expected = {_normalized(name) for name in names}
    return next(
        (index for index, value in enumerate(row) if _normalized(value) in expected),
        None,
    )


def _branch_owner(branch_code: str) -> str | None:
    code = branch_code.upper()
    if code.startswith("S"):
        return "HP"
    if code.startswith("M"):
        return "MH"
    return None


def _parse_sales(
    rows: list[list[str]],
) -> tuple[
    date,
    dict[tuple[str, str, str], _Values],
    dict[str, object],
]:
    header_index = _find_header(rows, {"PERIODDATE", "SITENO", "ARTNO", "QTY", "VALUE"})
    header = rows[header_index]
    columns = {
        "date": _header_index(header, "PERIODDATE"),
        "branch": _header_index(header, "SITENO", "SITE"),
        "sku": _header_index(header, "ARTNO", "SKU"),
        "qty": _header_index(header, "QTY"),
        "value": _header_index(header, "VALUE", "AMOUNT"),
        "description": _header_index(header, "ARTNAME", "DESCRIPTION", "DESC"),
        "branch_name": _header_index(header, "SITENAME", "BRANCHNAME"),
    }
    assert all(columns[name] is not None for name in ("date", "branch", "sku", "qty", "value"))
    values: dict[tuple[str, str, str], _Values] = defaultdict(_Values)
    dates: set[date] = set()
    ignored: set[str] = set()
    sale_skus = {"HP": set(), "MH": set()}
    for row_number, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        branch = _cell(row, columns["branch"]).upper()
        sku = _cell(row, columns["sku"])
        if not branch and not sku:
            continue
        if not branch or not sku:
            raise HpMhFormatError(f"Sale Out แถว {row_number} ขาด SITENO หรือ ARTNO")
        owner = _branch_owner(branch)
        if owner is None:
            ignored.add(branch)
            continue
        row_date = _date(_cell(row, columns["date"]))
        dates.add(row_date)
        key = (owner, branch, sku)
        target = values[key]
        target.branch_name = _cell(row, columns["branch_name"]) or branch
        target.description = _cell(row, columns["description"]) or target.description
        target.sales_qty += _decimal(_cell(row, columns["qty"]), field="QTY", row_number=row_number)
        target.source_amount += _decimal(
            _cell(row, columns["value"]), field="VALUE", row_number=row_number
        )
        sale_skus[owner].add(sku)
    if len(dates) != 1:
        raise HpMhFormatError(
            f"Sale Out ต้องมี Data Date เดียว แต่พบ {len(dates)} วัน"
        )
    return dates.pop(), values, {
        "ignored_branches": ignored,
        "sale_skus": sale_skus,
    }


def _parse_inventory(
    rows: list[list[str]],
) -> tuple[
    date,
    dict[tuple[str, str, str], _Values],
    dict[str, object],
]:
    art_row = _find_header(rows, {"ARTNO"})
    first_header = rows[art_row]
    sku_column = _header_index(first_header, "ARTNO", "SKU")
    if sku_column is None:
        raise HpMhFormatError("Inventory ไม่พบ column ARTNO")
    band_end = art_row + 1
    while (
        band_end < min(len(rows), art_row + 3)
        and not _cell(rows[band_end], sku_column)
    ):
        band_end += 1
    header_band = rows[art_row:band_end]
    width = max((len(row) for row in header_band), default=0)
    combined_headers = [
        " ".join(_cell(row, column) for row in header_band if _cell(row, column))
        for column in range(width)
    ]
    description_column = _header_index(first_header, "ARTNAME", "DESCRIPTION", "DESC")

    site_columns: list[tuple[int, str, str, str]] = []
    previous_branch = ""
    for column, title in enumerate(combined_headers):
        match = BRANCH_PATTERN.search(title.upper())
        if match:
            previous_branch = match.group(1).upper()
        normalized = _normalized(title)
        metric = (
            "qty"
            if "QTY" in normalized
            else "amount"
            if any(token in normalized for token in ("AMT", "AMOUNT", "VALUE"))
            else None
        )
        if metric and previous_branch:
            branch_name = re.sub(BRANCH_PATTERN, "", title)
            branch_name = re.sub(
                r"\b(QTY|AMT|AMOUNT|VALUE)\b",
                "",
                branch_name,
                flags=re.I,
            ).strip(" -_/|") or previous_branch
            site_columns.append((column, previous_branch, branch_name, metric))
    if not site_columns:
        raise HpMhFormatError("Inventory ไม่พบ column สาขา QTY/AMT")

    data_start = art_row + 1
    while data_start < len(rows) and not _cell(rows[data_start], sku_column):
        data_start += 1
    values: dict[tuple[str, str, str], _Values] = defaultdict(_Values)
    ignored: set[str] = set()
    inventory_skus = {"HP": set(), "MH": set()}
    inventory_branches = {"HP": set(), "MH": set()}
    all_site_qty = Decimal("0")
    all_site_amount = Decimal("0")
    for row_number, row in enumerate(rows[data_start:], start=data_start + 1):
        sku = _cell(row, sku_column)
        if not sku:
            continue
        normalized_sku = _normalized(sku)
        if normalized_sku.startswith("TOTAL") or normalized_sku.startswith("GRANDTOTAL"):
            continue
        description = _cell(row, description_column) or None
        for column, branch, branch_name, metric in site_columns:
            amount = _decimal(
                _cell(row, column),
                field=f"Inventory {branch} {metric}",
                row_number=row_number,
            )
            if metric == "qty":
                all_site_qty += amount
            else:
                all_site_amount += amount
            owner = _branch_owner(branch)
            if owner is None:
                ignored.add(branch)
                continue
            inventory_skus[owner].add(sku)
            inventory_branches[owner].add(branch)
            if amount == 0:
                continue
            target = values[(owner, branch, sku)]
            target.branch_name = branch_name
            target.description = description
            if metric == "qty":
                target.stock_on_hand += amount
            else:
                target.stock_value += amount

    data_date = _inventory_date(rows[: max(art_row, 1)])
    errors = _inventory_reconciliation(
        rows,
        combined_headers,
        data_start,
        sku_column,
        all_site_qty,
        all_site_amount,
    )
    return data_date, values, {
        "ignored_branches": ignored,
        "inventory_skus": inventory_skus,
        "inventory_branches": inventory_branches,
        "errors": errors,
    }


def _inventory_date(rows: list[list[str]]) -> date:
    for row in rows:
        for cell in row:
            match = DATE_PATTERN.search(cell)
            if match:
                return _date(match.group(1))
    raise HpMhFormatError("Inventory ไม่พบ Last Update/Data Date ภายในไฟล์")


def _inventory_reconciliation(
    rows: list[list[str]],
    headers: list[str],
    data_start: int,
    sku_column: int,
    calculated_qty: Decimal,
    calculated_amount: Decimal,
) -> list[str]:
    # GRAND totals include DC/other sites too. Validation therefore uses every
    # branch-coded site column, while storage still keeps only S* and M* rows.
    qty_column = next(
        (
            index
            for index, title in enumerate(headers)
            if "GRAND" in title.upper() and "QTY" in title.upper()
        ),
        None,
    )
    amount_column = next(
        (
            index
            for index, title in enumerate(headers)
            if "GRAND" in title.upper()
            and any(token in title.upper() for token in ("AMT", "AMOUNT", "VALUE"))
        ),
        None,
    )
    if qty_column is None and amount_column is None:
        return []
    errors: list[str] = []
    if qty_column is not None:
        reported_qty = sum(
            (
                _decimal(_cell(row, qty_column), field="GRAND QTY", row_number=index + 1)
                for index, row in enumerate(rows[data_start:], start=data_start)
                if _cell(row, sku_column)
            ),
            Decimal("0"),
        )
        if reported_qty != calculated_qty:
            errors.append(
                f"Inventory QTY: calculated={calculated_qty}, source={reported_qty}"
            )
    if amount_column is not None:
        reported_amount = sum(
            (
                _decimal(_cell(row, amount_column), field="GRAND AMT", row_number=index + 1)
                for index, row in enumerate(rows[data_start:], start=data_start)
                if _cell(row, sku_column)
            ),
            Decimal("0"),
        )
        if reported_amount != calculated_amount:
            errors.append(
                f"Inventory AMT: calculated={calculated_amount}, source={reported_amount}"
            )
    return errors


def _cell(row: list[str], index: int | None) -> str:
    return row[index] if index is not None and index < len(row) else ""


def _build_mt_extract(
    code: str,
    data_date: date,
    combined: dict[tuple[str, str, str], _Values],
    *,
    sale_skus: set[str],
    inventory_skus: set[str],
    inventory_branches: set[str],
) -> HpMhMtExtract:
    rows = tuple(
        HpMhRow(
            branch_code=branch,
            branch_name=value.branch_name or branch,
            sku=sku,
            description=value.description,
            source_amount=value.source_amount,
            amount=calculate_amount(value.source_amount),
            sales_qty=value.sales_qty,
            stock_on_hand=value.stock_on_hand,
            stock_value=value.stock_value,
        )
        for (owner, branch, sku), value in sorted(combined.items())
        if owner == code
    )
    summary = HpMhSummary(
        row_count=len(rows),
        store_count=len({row.branch_code for row in rows}),
        sku_count=len({row.sku for row in rows}),
        negative_row_count=sum(
            row.source_amount < 0 or row.sales_qty < 0 for row in rows
        ),
        source_amount=sum((row.source_amount for row in rows), Decimal("0")),
        amount=sum((row.amount for row in rows), Decimal("0")).quantize(STORAGE_SCALE),
        sales_qty=sum((row.sales_qty for row in rows), Decimal("0")),
        stock_on_hand=sum((row.stock_on_hand for row in rows), Decimal("0")),
        stock_value=sum((row.stock_value for row in rows), Decimal("0")),
    )
    return HpMhMtExtract(
        code=code,
        data_date=data_date,
        rows=rows,
        summary=summary,
        sale_skus=frozenset(sale_skus),
        inventory_skus=frozenset(inventory_skus),
        inventory_branches=frozenset(inventory_branches),
    )


def _business_fingerprint(
    data_date: date,
    combined: dict[tuple[str, str, str], _Values],
) -> str:
    payload = [
        [
            owner,
            branch,
            sku,
            str(value.source_amount),
            str(value.sales_qty),
            str(value.stock_on_hand),
            str(value.stock_value),
        ]
        for (owner, branch, sku), value in sorted(combined.items())
    ]
    canonical = json.dumps(
        {"dataDate": data_date.isoformat(), "rows": payload},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

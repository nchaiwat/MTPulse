from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.importers.dh import STORAGE_SCALE, DhPairExtract

RECONCILIATION_TOLERANCE = Decimal("0.02")


class DhPricingError(ValueError):
    pass


@dataclass(frozen=True)
class DhPrice:
    source_sku: str
    unit_price_ex_vat: Decimal
    effective_from: date
    effective_to: date | None = None

    def __post_init__(self) -> None:
        source_sku = str(self.source_sku).strip()
        unit_price = Decimal(str(self.unit_price_ex_vat))
        if not source_sku:
            raise DhPricingError("DH Price ต้องระบุ SKU")
        if unit_price <= 0:
            raise DhPricingError(f"ราคาขาย Ex VAT ของ SKU {source_sku} ต้องมากกว่า 0")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise DhPricingError(f"ช่วงวันที่ราคาของ SKU {source_sku} ไม่ถูกต้อง")
        object.__setattr__(self, "source_sku", source_sku)
        object.__setattr__(self, "unit_price_ex_vat", unit_price.quantize(STORAGE_SCALE))


@dataclass(frozen=True)
class DhPricedFactRow:
    branch_code: str
    branch_name: str
    sku: str
    description: str | None
    unit_price_ex_vat: Decimal | None
    source_amount: Decimal
    amount: Decimal
    sales_qty: Decimal
    stock_on_hand: Decimal


@dataclass(frozen=True)
class DhPricedSummary:
    row_count: int
    store_count: int
    sku_count: int
    negative_row_count: int
    source_footer_amount: Decimal
    derived_amount: Decimal
    sales_qty: Decimal
    stock_on_hand: Decimal


@dataclass(frozen=True)
class DhPricedPair:
    source: DhPairExtract
    business_fingerprint: str
    rows: tuple[DhPricedFactRow, ...]
    summary: DhPricedSummary
    reconciliation_errors: tuple[str, ...]


def price_dh_pair(
    pair: DhPairExtract,
    prices: tuple[DhPrice, ...],
) -> DhPricedPair:
    selected_prices = _select_prices(pair, prices)
    sales_by_key = defaultdict(Decimal)
    stock_by_key = defaultdict(Decimal)
    identity_by_key: dict[tuple[str, str], tuple[str, str | None]] = {}

    for row in pair.sales_rows:
        key = (row.branch_code, row.sku)
        sales_by_key[key] += row.sales_qty
        identity_by_key[key] = (row.branch_name, row.description)
    for row in pair.stock_rows:
        key = (row.branch_code, row.sku)
        stock_by_key[key] += row.stock_on_hand
        existing = identity_by_key.get(key)
        identity_by_key[key] = (
            row.branch_name,
            (existing[1] if existing and existing[1] else row.description),
        )

    rows = []
    derived_by_branch = defaultdict(Decimal)
    for branch_code, sku in sorted(sales_by_key.keys() | stock_by_key.keys()):
        branch_name, description = identity_by_key[(branch_code, sku)]
        sales_qty = sales_by_key[(branch_code, sku)]
        unit_price = selected_prices.get(sku)
        amount = (
            (sales_qty * unit_price).quantize(STORAGE_SCALE)
            if unit_price is not None
            else Decimal("0").quantize(STORAGE_SCALE)
        )
        derived_by_branch[branch_code] += amount
        rows.append(
            DhPricedFactRow(
                branch_code=branch_code,
                branch_name=branch_name,
                sku=sku,
                description=description,
                unit_price_ex_vat=unit_price,
                source_amount=amount,
                amount=amount,
                sales_qty=sales_qty,
                stock_on_hand=stock_by_key[(branch_code, sku)],
            )
        )

    source_footer_amount = sum(
        (row.amount for row in pair.branch_amounts), Decimal("0")
    ).quantize(STORAGE_SCALE)
    derived_amount = sum((row.amount for row in rows), Decimal("0")).quantize(
        STORAGE_SCALE
    )
    reconciliation_errors = [*pair.reconciliation_errors]
    footer_by_branch = {row.branch_code: row for row in pair.branch_amounts}
    for branch_code in sorted(set(derived_by_branch) | set(footer_by_branch)):
        derived = derived_by_branch[branch_code].quantize(STORAGE_SCALE)
        footer_row = footer_by_branch.get(branch_code)
        footer = (
            footer_row.amount.quantize(STORAGE_SCALE)
            if footer_row is not None
            else Decimal("0").quantize(STORAGE_SCALE)
        )
        if (derived - footer).copy_abs() > RECONCILIATION_TOLERANCE:
            branch_name = (
                footer_row.branch_name
                if footer_row is not None
                else next(
                    row.branch_name for row in rows if row.branch_code == branch_code
                )
            )
            reconciliation_errors.append(
                f"Amount สาขา {branch_name} จาก Qty × ราคา {derived} "
                f"ไม่ตรงกับ Footer {footer}"
            )
    if (derived_amount - source_footer_amount).copy_abs() > RECONCILIATION_TOLERANCE:
        reconciliation_errors.append(
            f"Amount รวมจาก Qty × ราคา {derived_amount} "
            f"ไม่ตรงกับ Footer {source_footer_amount}"
        )

    summary = DhPricedSummary(
        row_count=len(rows),
        store_count=len({row.branch_code for row in rows}),
        sku_count=len({row.sku for row in rows}),
        negative_row_count=sum(
            row.amount < 0 or row.sales_qty < 0 or row.stock_on_hand < 0
            for row in rows
        ),
        source_footer_amount=source_footer_amount,
        derived_amount=derived_amount,
        sales_qty=sum((row.sales_qty for row in rows), Decimal("0")),
        stock_on_hand=sum((row.stock_on_hand for row in rows), Decimal("0")),
    )
    fingerprint_payload = {
        "source": pair.business_fingerprint,
        "prices": [
            [sku, str(unit_price)]
            for sku, unit_price in sorted(selected_prices.items())
        ],
    }
    business_fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return DhPricedPair(
        source=pair,
        business_fingerprint=business_fingerprint,
        rows=tuple(rows),
        summary=summary,
        reconciliation_errors=tuple(reconciliation_errors),
    )


def _select_prices(
    pair: DhPairExtract,
    prices: tuple[DhPrice, ...],
) -> dict[str, Decimal]:
    prices_by_sku: dict[str, list[DhPrice]] = defaultdict(list)
    for price in prices:
        prices_by_sku[price.source_sku].append(price)

    sold_skus = {row.sku for row in pair.sales_rows if row.sales_qty != 0}
    selected: dict[str, Decimal] = {}
    missing = []
    overlapping = []
    for sku in sorted(sold_skus):
        candidates = [
            price
            for price in prices_by_sku.get(sku, [])
            if price.effective_from <= pair.sales_date
            and (price.effective_to is None or pair.sales_date <= price.effective_to)
        ]
        if not candidates:
            missing.append(sku)
            continue
        if len(candidates) > 1:
            overlapping.append(sku)
            continue
        selected[sku] = candidates[0].unit_price_ex_vat

    if missing:
        raise DhPricingError(f"ไม่พบราคาขาย Ex VAT ณ วันที่ Sale สำหรับ SKU: {', '.join(missing)}")
    if overlapping:
        raise DhPricingError(
            "พบมากกว่าหนึ่งราคาที่ใช้ได้ในวันเดียวกันสำหรับ SKU: "
            + ", ".join(overlapping)
        )
    return selected

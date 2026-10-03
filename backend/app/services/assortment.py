"""Confirmed WA memberships; reuse Performance semantics rather than duplicate MT rules."""

import calendar
import json
from datetime import date
from decimal import Decimal
from difflib import SequenceMatcher

from sqlalchemy import select

from app.api.performance import performance
from app.models import (
    AssortmentBase,
    AssortmentForecast,
    AssortmentMember,
    AssortmentPlan,
    ImportBatch,
    ItemMapping,
    ModernTrade,
)
from app.modern_trade_registry import active_modern_trade_codes
from app.services.telegram import setting_value

ATTRS = ["กลุ่ม", "รุ่น", "สินค้า", "ประเภท", "มุ้ง", "สี", "ขนาด"]


def base_dict(row, members):
    return {
        "id": row.id,
        "description": row.description,
        "attributes": json.loads(row.attributes),
        "version": row.version,
        "members": sorted(members),
    }


def catalog(db):
    memberships = list(db.scalars(select(AssortmentMember)))
    bases = [
        base_dict(b, [m.wa_item_code for m in memberships if m.base_id == b.id])
        for b in db.scalars(select(AssortmentBase).order_by(AssortmentBase.description))
    ]
    plans = [
        {
            "id": p.id,
            "name": p.name,
            "year": p.year,
            "version": p.version,
            "primary": p.primary_year is not None,
        }
        for p in db.scalars(
            select(AssortmentPlan).order_by(AssortmentPlan.year.desc(), AssortmentPlan.name)
        )
    ]
    return {
        "bases": bases,
        "plans": plans,
        "mts": list(active_modern_trade_codes("performance")),
        "pageSize": page_size(db),
    }


def page_size(db):
    value = int(setting_value(db, "assortment_page_size") or 25)
    return value if value in (0, 25, 50, 100) else 25


def candidates(db, search="", page=1):
    members = {m.wa_item_code: m.base_id for m in db.scalars(select(AssortmentMember))}
    bases = list(db.scalars(select(AssortmentBase)))
    items = {}
    for m, code in db.execute(
        select(ItemMapping, ModernTrade.code)
        .join(ModernTrade, ItemMapping.modern_trade_id == ModernTrade.id)
        .where(
            ModernTrade.code.in_(active_modern_trade_codes("performance")),
            ItemMapping.status == "confirmed",
            ItemMapping.report_status == "active",
        )
        .order_by(ItemMapping.effective_from)
    ):
        row = items.setdefault(
            m.wa_item_code,
            {
                "waItem": m.wa_item_code,
                "description": "",
                "sources": [],
                "baseId": members.get(m.wa_item_code),
            },
        )
        if m.wa_item_description:
            row["description"] = m.wa_item_description
        source = {"mt": code, "sku": m.source_sku}
        if source not in row["sources"]:
            row["sources"].append(source)
    result = []
    for row in items.values():
        if search.casefold() not in (row["waItem"] + " " + row["description"]).casefold():
            continue
        proposed = sorted(
            (
                (
                    SequenceMatcher(
                        None, row["description"].casefold(), b.description.casefold()
                    ).ratio(),
                    b,
                )
                for b in bases
            ),
            key=lambda pair: pair[0],
            reverse=True,
        )
        row["suggestedBaseId"] = (
            proposed[0][1].id
            if proposed and proposed[0][0] >= 0.65 and row["description"]
            else None
        )
        result.append(row)
    result.sort(key=lambda row: row["waItem"])
    return {"items": result[(page - 1) * 50 : page * 50], "total": len(result)}


def sum_present(values):
    present = [Decimal(str(v)) for v in values if v is not None]
    return float(sum(present)) if present else None


def report(
    db,
    year,
    plan_id=None,
    mt=None,
    search="",
    mode="sales",
    basis="net",
    page=1,
    all_rows=False,
    group="",
    model="",
):
    cat = catalog(db)
    bases = [
        b
        for b in cat["bases"]
        if search.casefold()
        in (
            b["description"] + " " + " ".join(b["members"]) + " " + " ".join(b["attributes"])
        ).casefold()
        and (not group or b["attributes"][0] == group)
        and (not model or b["attributes"][1] == model)
    ]
    total = len(bases)
    size = page_size(db) or max(total, 1)
    if not all_rows:
        bases = bases[(page - 1) * size : page * size]
    selected = [mt] if mt else cat["mts"]
    membership = {wa: b["id"] for b in bases for wa in b["members"]}
    plan = db.get(AssortmentPlan, plan_id) if plan_id else None
    forecasts = (
        {
            (f.base_id, f.mt_code): json.loads(f.months)
            for f in db.scalars(
                select(AssortmentForecast).where(AssortmentForecast.plan_id == plan_id)
            )
        }
        if plan
        else {}
    )
    cells = {
        b["id"]: {
            code: {"years": {}, "forecast": forecasts.get((b["id"], code), [None] * 12)}
            for code in selected
        }
        for b in bases
    }
    coverage = {}
    trades = {
        m.code: m for m in db.scalars(select(ModernTrade).where(ModernTrade.code.in_(selected)))
    }
    for code, trade in trades.items():
        coverage[code] = {}
        skus = sorted(
            set(
                db.scalars(
                    select(ItemMapping.source_sku).where(
                        ItemMapping.modern_trade_id == trade.id,
                        ItemMapping.wa_item_code.in_(membership),
                        ItemMapping.status == "confirmed",
                        ItemMapping.report_status == "active",
                    )
                )
            )
        )
        for yr in (year - 2, year - 1):
            start, end = date(yr, 1, 1), date(yr, 12, 31)
            days = set(
                db.scalars(
                    select(ImportBatch.data_date).where(
                        ImportBatch.modern_trade_id == trade.id,
                        ImportBatch.status.in_(("imported", "imported_with_warnings")),
                        ImportBatch.sales_grain == "daily",
                        ImportBatch.data_date.between(start, end),
                    )
                )
            )
            expected = 366 if calendar.isleap(yr) else 365
            coverage[code][str(yr)] = {
                "days": len(days),
                "expected": expected,
                "months": [
                    {
                        "days": sum(d.month == m for d in days),
                        "expected": calendar.monthrange(yr, m)[1],
                    }
                    for m in range(1, 13)
                ],
            }
            for base in bases:
                cells[base["id"]][code]["years"][str(yr)] = {
                    "months": [None] * 12,
                    "total": None,
                    "snapshot": None,
                }
            # Report enforces current mapping and branch scope for requested SKUs.
            for offset in range(0, len(skus), 150):
                result = performance(
                    db,
                    mt_code=code,
                    date_from=start,
                    date_to=end,
                    page_size=1_000_000,
                    sku_ids=",".join(skus[offset : offset + 150]),
                    mapping_status="confirmed",
                    hide_unmapped=True,
                    sales_basis=basis,
                    grain="month" if mode == "sales" else "day_total",
                    report_mode="sales" if mode == "sales" else "inventory",
                    latest_only=mode == "inventory",
                )
                for item in result["items"]:
                    base_id = membership.get(item["waItem"])
                    if not base_id or item["mappingStatus"] != "confirmed":
                        continue
                    cell = cells[base_id][code]["years"][str(yr)]
                    for point in item["points"]:
                        if mode == "inventory":
                            cell["snapshot"] = point["date"]
                            cell["total"] = sum_present([cell["total"], point["stockOh"]])
                        else:
                            month = int(point["date"][5:7]) - 1
                            cell["months"][month] = sum_present(
                                [cell["months"][month], point["qty"]]
                            )
            if mode == "sales":
                for base in bases:
                    cell = cells[base["id"]][code]["years"][str(yr)]
                    cell["total"] = sum_present(cell["months"])
    for base in bases:
        base["cells"] = cells[base["id"]]
        for code, cell in base["cells"].items():
            values = cell["forecast"]
            cell["forecast"] = [float(v) if v is not None else None for v in values]
            cell["forecastTotal"] = sum_present(values)
            cell["filled"] = sum(v is not None for v in values)
            prior = cell["years"].get(str(year - 1), {}).get("total")
            c = coverage.get(code, {}).get(str(year - 1), {})
            cell["growth"] = (
                (cell["forecastTotal"] / prior - 1) * 100
                if mode == "sales"
                and cell["filled"] == 12
                and prior
                and prior > 0
                and c.get("days") == c.get("expected")
                else None
            )
    return {
        "items": bases,
        "total": total,
        "page": page,
        "pageSize": size,
        "mts": selected,
        "year": year,
        "coverage": coverage,
        "planVersion": plan.version if plan else None,
        "basis": basis,
        "mode": mode,
    }

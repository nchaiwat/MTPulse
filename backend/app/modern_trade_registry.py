from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ModernTradeCode = Literal["TWD", "HP", "MH", "HH", "GH", "SCG", "TA", "DH"]
ActiveReportingModernTradeCode = Literal[
    "TWD",
    "HP",
    "MH",
    "HH",
    "GH",
    "TA",
    "DH",
]
ModernTradeCapability = Literal[
    "dashboard",
    "performance",
    "manual_import",
    "folder_import",
    "automatic_import",
    "corrective_import",
    "mapping",
    "sku_backfill",
    "sho_pro",
    "monitoring",
    "settings",
    "excel",
]

ALL_CAPABILITIES: frozenset[ModernTradeCapability] = frozenset(
    {
        "dashboard",
        "performance",
        "manual_import",
        "folder_import",
        "automatic_import",
        "corrective_import",
        "mapping",
        "sku_backfill",
        "sho_pro",
        "monitoring",
        "settings",
        "excel",
    }
)


@dataclass(frozen=True)
class ModernTradeDefinition:
    code: ModernTradeCode
    name: str
    display_name: str
    source_group_code: str
    source_owner_code: ModernTradeCode
    vat_mode: Literal["include", "exclude"] | None
    inventory_metrics: tuple[str, ...]
    active_capabilities: frozenset[ModernTradeCapability]
    planned_capabilities: frozenset[ModernTradeCapability]

    def supports(self, capability: ModernTradeCapability) -> bool:
        return capability in self.active_capabilities

    def plans(self, capability: ModernTradeCapability) -> bool:
        return capability in self.planned_capabilities


_COMPLETE_TWD = ALL_CAPABILITIES
_ACTIVE_HP_MH = frozenset(
    {
        "dashboard",
        "performance",
        "manual_import",
        "folder_import",
        "automatic_import",
        "mapping",
        "sku_backfill",
        "sho_pro",
        "monitoring",
        "settings",
        "excel",
    }
)
_ACTIVE_HH = frozenset(
    {
        "dashboard",
        "performance",
        "manual_import",
        "folder_import",
        "automatic_import",
        "corrective_import",
        "mapping",
        "sku_backfill",
        "sho_pro",
        "monitoring",
        "settings",
        "excel",
    }
)
_ACTIVE_GH = ALL_CAPABILITIES
_ACTIVE_TA = ALL_CAPABILITIES

MODERN_TRADES: dict[ModernTradeCode, ModernTradeDefinition] = {
    "TWD": ModernTradeDefinition(
        code="TWD",
        name="Thai Watsadu",
        display_name="TWD",
        source_group_code="TWD",
        source_owner_code="TWD",
        vat_mode="include",
        inventory_metrics=("stockOh", "stockOnOrder"),
        active_capabilities=_COMPLETE_TWD,
        planned_capabilities=frozenset(),
    ),
    "HP": ModernTradeDefinition(
        code="HP",
        name="HomePro",
        display_name="HomePro (HP)",
        source_group_code="HP_MH",
        source_owner_code="HP",
        vat_mode="exclude",
        inventory_metrics=("stockOh", "stockValue"),
        active_capabilities=_ACTIVE_HP_MH,
        planned_capabilities=frozenset({"corrective_import"}),
    ),
    "MH": ModernTradeDefinition(
        code="MH",
        name="MegaHome",
        display_name="MegaHome (MH)",
        source_group_code="HP_MH",
        source_owner_code="HP",
        vat_mode="exclude",
        inventory_metrics=("stockOh", "stockValue"),
        active_capabilities=_ACTIVE_HP_MH,
        planned_capabilities=frozenset({"corrective_import"}),
    ),
    "HH": ModernTradeDefinition(
        code="HH",
        name="HomeHub",
        display_name="HomeHub (HH)",
        source_group_code="HH",
        source_owner_code="HH",
        vat_mode="exclude",
        inventory_metrics=("stockOh", "stockValue"),
        active_capabilities=_ACTIVE_HH,
        planned_capabilities=frozenset(),
    ),
    "GH": ModernTradeDefinition(
        code="GH",
        name="Global House",
        display_name="Global House (GH)",
        source_group_code="GH",
        source_owner_code="GH",
        vat_mode="include",
        inventory_metrics=("stockOh", "stockValue"),
        active_capabilities=_ACTIVE_GH,
        planned_capabilities=frozenset(),
    ),
    "SCG": ModernTradeDefinition(
        code="SCG",
        name="Modern Trade SCG",
        display_name="Modern Trade SCG (SCG)",
        source_group_code="SCG",
        source_owner_code="SCG",
        vat_mode=None,
        inventory_metrics=(),
        active_capabilities=frozenset(),
        planned_capabilities=ALL_CAPABILITIES,
    ),
    "TA": ModernTradeDefinition(
        code="TA",
        name="Thai-Aust",
        display_name="Thai-Aust (TA)",
        source_group_code="TA",
        source_owner_code="TA",
        vat_mode="include",
        inventory_metrics=("stockOh", "stockValue"),
        active_capabilities=_ACTIVE_TA,
        planned_capabilities=frozenset(),
    ),
    "DH": ModernTradeDefinition(
        code="DH",
        name="DoHome",
        display_name="DoHome (DH)",
        source_group_code="DH",
        source_owner_code="DH",
        vat_mode="exclude",
        inventory_metrics=("stockOh",),
        active_capabilities=ALL_CAPABILITIES,
        planned_capabilities=frozenset(),
    ),
}


def modern_trade_definition(code: str) -> ModernTradeDefinition | None:
    return MODERN_TRADES.get(code.strip().upper())  # type: ignore[arg-type]


def active_modern_trade_codes(
    capability: ModernTradeCapability,
) -> frozenset[ModernTradeCode]:
    return frozenset(
        definition.code
        for definition in MODERN_TRADES.values()
        if definition.supports(capability)
    )


def active_source_owner_codes(
    capability: ModernTradeCapability,
) -> frozenset[ModernTradeCode]:
    return frozenset(
        definition.source_owner_code
        for definition in MODERN_TRADES.values()
        if definition.supports(capability)
    )


def source_group_member_codes(source_group_code: str) -> tuple[ModernTradeCode, ...]:
    normalized = source_group_code.strip().upper()
    return tuple(
        definition.code
        for definition in MODERN_TRADES.values()
        if definition.source_group_code == normalized
    )


def active_capability_label(capability: ModernTradeCapability) -> str:
    codes = [
        definition.code
        for definition in MODERN_TRADES.values()
        if definition.supports(capability)
    ]
    if len(codes) < 2:
        return ", ".join(codes)
    return f"{', '.join(codes[:-1])} และ {codes[-1]}"

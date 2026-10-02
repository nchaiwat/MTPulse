from app.modern_trade_registry import (
    ALL_CAPABILITIES,
    MODERN_TRADES,
    active_modern_trade_codes,
    active_source_owner_codes,
)


def test_registry_contains_current_and_future_modern_trades() -> None:
    assert set(MODERN_TRADES) == {
        "TWD",
        "HP",
        "MH",
        "HH",
        "GH",
        "SCG",
        "TA",
        "DH",
    }
    assert MODERN_TRADES["GH"].vat_mode == "include"
    assert MODERN_TRADES["TA"].vat_mode == "include"
    assert MODERN_TRADES["SCG"].vat_mode is None


def test_every_capability_has_one_explicit_state() -> None:
    for definition in MODERN_TRADES.values():
        assert not definition.active_capabilities & definition.planned_capabilities
        assert definition.active_capabilities | definition.planned_capabilities == ALL_CAPABILITIES


def test_active_reporting_package_isolated_per_modern_trade() -> None:
    reporting_codes = {"TWD", "HP", "MH", "HH", "GH", "TA", "DH"}
    for capability in (
        "dashboard",
        "performance",
        "mapping",
        "sho_pro",
        "monitoring",
        "settings",
        "excel",
    ):
        assert active_modern_trade_codes(capability) == reporting_codes


def test_source_owners_preserve_shared_hp_mh_and_independent_packages() -> None:
    assert MODERN_TRADES["HP"].source_owner_code == "HP"
    assert MODERN_TRADES["MH"].source_owner_code == "HP"
    assert MODERN_TRADES["HH"].source_owner_code == "HH"
    assert MODERN_TRADES["TA"].source_owner_code == "TA"
    assert active_source_owner_codes("automatic_import") == {
        "TWD",
        "HP",
        "HH",
        "GH",
        "TA",
        "DH",
    }


def test_hh_package_has_no_unimplemented_capability_gap() -> None:
    hh = MODERN_TRADES["HH"]
    assert hh.active_capabilities == {
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
    assert hh.planned_capabilities == set()


def test_ta_package_is_complete_and_isolated_from_gh() -> None:
    ta = MODERN_TRADES["TA"]
    assert ta.name == "Thai-Aust"
    assert ta.source_group_code == "TA"
    assert ta.source_owner_code == "TA"
    assert ta.inventory_metrics == ("stockOh", "stockValue")
    assert ta.active_capabilities == ALL_CAPABILITIES
    assert ta.planned_capabilities == set()


def test_dh_package_is_complete_and_uses_ex_vat_pricing() -> None:
    dh = MODERN_TRADES["DH"]
    assert dh.name == "DoHome"
    assert dh.source_group_code == "DH"
    assert dh.source_owner_code == "DH"
    assert dh.vat_mode == "exclude"
    assert dh.inventory_metrics == ("stockOh",)
    assert dh.active_capabilities == ALL_CAPABILITIES
    assert dh.planned_capabilities == set()

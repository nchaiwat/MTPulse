from app.modern_trade_registry import (
    ALL_CAPABILITIES,
    MODERN_TRADES,
    active_modern_trade_codes,
    active_source_owner_codes,
)


def test_registry_contains_current_and_future_modern_trades() -> None:
    assert set(MODERN_TRADES) == {"TWD", "HP", "MH", "HH", "GH", "SCG", "TA"}
    assert all(MODERN_TRADES[code].vat_mode is None for code in ("GH", "SCG", "TA"))


def test_every_capability_has_one_explicit_state() -> None:
    for definition in MODERN_TRADES.values():
        assert not definition.active_capabilities & definition.planned_capabilities
        assert definition.active_capabilities | definition.planned_capabilities == ALL_CAPABILITIES


def test_active_reporting_package_isolated_per_modern_trade() -> None:
    reporting_codes = {"TWD", "HP", "MH", "HH"}
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


def test_source_owners_preserve_shared_hp_mh_and_independent_hh() -> None:
    assert MODERN_TRADES["HP"].source_owner_code == "HP"
    assert MODERN_TRADES["MH"].source_owner_code == "HP"
    assert MODERN_TRADES["HH"].source_owner_code == "HH"
    assert active_source_owner_codes("automatic_import") == {"TWD", "HP", "HH"}


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

from types import SimpleNamespace

from app.services.monitoring import _overall_status, _warning_count, _warning_details


def test_overall_status_uses_highest_severity() -> None:
    notices = [
        {"level": "warning", "title": "warning", "detail": "detail"},
        {"level": "critical", "title": "critical", "detail": "detail"},
    ]

    assert _overall_status(notices) == "critical"
    assert _overall_status([]) == "healthy"


def test_warning_count_ignores_blank_reconciliation_lines() -> None:
    batch = SimpleNamespace(reconciliation_errors="first\n\nsecond\n")

    assert _warning_count(batch) == 2
    assert _warning_count(None) == 0


def test_warning_details_returns_actionable_reconciliation_text() -> None:
    batch = SimpleNamespace(
        reconciliation_errors="Stock On Hand: calculated=77904.0, source=77379\n\nsecond warning"
    )

    assert _warning_details(batch) == (
        "Stock On Hand: calculated=77904.0, source=77379 · second warning"
    )

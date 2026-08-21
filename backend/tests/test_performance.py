from datetime import date

import pytest

from app.api.performance import _month_bounds


def test_month_bounds_supports_leap_year() -> None:
    assert _month_bounds("2024-02") == (date(2024, 2, 1), date(2024, 2, 29))


def test_month_bounds_rejects_invalid_month() -> None:
    with pytest.raises(ValueError):
        _month_bounds("2026-13")

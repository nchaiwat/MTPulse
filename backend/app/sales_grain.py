from datetime import date

SALES_GRAIN_DAILY = "daily"
SALES_GRAIN_ROLLING_30D = "rolling_30d"
ROLLING_30D_WINDOW_DAYS = 30
ROLLING_30D_EFFECTIVE_DATA_DATE = date(2026, 8, 4)


def flat_sales_grain(data_date: date) -> tuple[str, int | None]:
    if data_date >= ROLLING_30D_EFFECTIVE_DATA_DATE:
        return SALES_GRAIN_ROLLING_30D, ROLLING_30D_WINDOW_DAYS
    return SALES_GRAIN_DAILY, None

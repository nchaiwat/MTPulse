from datetime import date, datetime
from zoneinfo import ZoneInfo

BANGKOK_TIMEZONE = ZoneInfo("Asia/Bangkok")


def bangkok_now() -> datetime:
    return datetime.now(BANGKOK_TIMEZONE)


def bangkok_today() -> date:
    return bangkok_now().date()


def as_bangkok(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(BANGKOK_TIMEZONE)


def as_bangkok_excel(value: datetime) -> datetime:
    return as_bangkok(value).replace(tzinfo=None)

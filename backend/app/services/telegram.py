from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import SystemSetting

TOKEN_KEY = "telegram_bot_token"
GROUP_KEY = "telegram_group_id"
NOTIFY_MANUAL_KEY = "telegram_notify_manual_import"
BANGKOK_TIMEZONE = ZoneInfo("Asia/Bangkok")


class SettingsCryptoError(ValueError):
    pass


@dataclass(frozen=True)
class TelegramDelivery:
    status: str
    message: str


def format_thai_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def format_telegram_message(
    title: str,
    details: Sequence[str] = (),
    *,
    occurred_at: datetime | None = None,
) -> str:
    timestamp = occurred_at or datetime.now(BANGKOK_TIMEZONE)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=BANGKOK_TIMEZONE)
    else:
        timestamp = timestamp.astimezone(BANGKOK_TIMEZONE)
    header = f"📦 MT Pulse · {format_thai_date(timestamp.date())} {timestamp:%H:%M} น."
    return "\n".join([header, "────────────", title, *details])


def _fernet() -> Fernet:
    key = get_settings().settings_encryption_key
    if not key:
        raise SettingsCryptoError("ยังไม่ได้ตั้งค่า Settings Encryption Key บน Server")
    try:
        return Fernet(key.encode())
    except ValueError as exc:
        raise SettingsCryptoError("Settings Encryption Key ไม่ถูกต้อง") from exc


def _row(session: Session, key: str) -> SystemSetting | None:
    return session.get(SystemSetting, key)


def setting_value(session: Session, key: str) -> str | None:
    row = _row(session, key)
    return row.value if row else None


def set_setting(
    session: Session, key: str, value: str | None, *, secret: bool, actor: str
) -> None:
    row = _row(session, key)
    if row is None:
        row = SystemSetting(key=key, value=value, is_secret=secret, updated_by=actor)
        session.add(row)
    else:
        row.value = value
        row.is_secret = secret
        row.updated_by = actor


def set_bot_token(session: Session, token: str, actor: str) -> None:
    encrypted = _fernet().encrypt(token.encode()).decode()
    set_setting(session, TOKEN_KEY, encrypted, secret=True, actor=actor)


def bot_token(session: Session) -> str | None:
    encrypted = setting_value(session, TOKEN_KEY)
    if not encrypted:
        return None
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken as exc:
        raise SettingsCryptoError("ไม่สามารถถอดรหัส Telegram Bot Token ได้") from exc


def telegram_config(session: Session) -> dict:
    configured = bool(setting_value(session, TOKEN_KEY))
    return {
        "telegramConfigured": configured,
        "botTokenMasked": "••••••••" if configured else "",
        "groupId": setting_value(session, GROUP_KEY) or "",
        "notifyManualImport": setting_value(session, NOTIFY_MANUAL_KEY) != "false",
    }


def _rejected_delivery(response: httpx.Response, payload: dict) -> TelegramDelivery:
    error_code = payload.get("error_code") or response.status_code
    description = str(payload.get("description") or "").lower()
    if error_code == 401:
        return TelegramDelivery(
            "failed",
            "Telegram ปฏิเสธ Bot Token กรุณาตรวจสอบ Token ที่บันทึกไว้",
        )
    if error_code == 400 and "chat not found" in description:
        return TelegramDelivery(
            "failed",
            "ไม่พบ Group / Chat ID หรือยังไม่ได้เพิ่ม Bot เข้า Group",
        )
    if error_code == 403:
        return TelegramDelivery(
            "failed",
            "Bot ไม่มีสิทธิ์ส่งข้อความใน Group หรือถูกนำออกจาก Group",
        )
    return TelegramDelivery("failed", f"Telegram ปฏิเสธคำขอ (รหัส {error_code})")


def send_telegram(
    session: Session,
    title: str,
    details: Sequence[str] = (),
    *,
    force: bool = False,
) -> TelegramDelivery:
    if not force and setting_value(session, NOTIFY_MANUAL_KEY) == "false":
        return TelegramDelivery("skipped", "ปิดการแจ้งเตือน Manual Import")
    group_id = setting_value(session, GROUP_KEY)
    try:
        token = bot_token(session)
    except SettingsCryptoError as exc:
        return TelegramDelivery("failed", str(exc))
    if not token or not group_id:
        return TelegramDelivery("skipped", "ยังไม่ได้ตั้งค่า Telegram Bot Token หรือ Group ID")
    try:
        response = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": group_id,
                "text": format_telegram_message(title, details),
            },
            timeout=10,
        )
    except httpx.HTTPError:
        return TelegramDelivery("failed", "เชื่อมต่อ Telegram ไม่สำเร็จ กรุณาตรวจสอบ Internet")
    try:
        payload = response.json()
    except ValueError:
        return TelegramDelivery(
            "failed",
            f"Telegram ตอบกลับข้อมูลที่อ่านไม่ได้ (HTTP {response.status_code})",
        )
    if not payload.get("ok"):
        return _rejected_delivery(response, payload)
    return TelegramDelivery("sent", "ส่ง Telegram สำเร็จ")
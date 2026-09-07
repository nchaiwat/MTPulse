import json
from datetime import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_session
from app.models import AuditEvent
from app.services.technical_health import (
    DEFAULT_THRESHOLDS,
    TechnicalNotificationConfig,
    save_technical_notification_config,
    send_manual_technical_health,
    technical_notification_config,
)
from app.services.telegram import (
    GROUP_KEY,
    NOTIFY_MANUAL_KEY,
    SettingsCryptoError,
    bot_token,
    send_telegram,
    set_bot_token,
    set_setting,
    setting_value,
    telegram_config,
)

router = APIRouter(prefix="/api/settings/system", tags=["system settings"])


class TelegramSettingsUpdate(BaseModel):
    bot_token: str | None = Field(default=None, max_length=300)
    group_id: str = Field(max_length=100)
    notify_manual_import: bool = True


class TechnicalThresholdUpdate(BaseModel):
    warning: float = Field(ge=0, le=100)
    critical: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_threshold_order(self) -> "TechnicalThresholdUpdate":
        if self.warning >= self.critical:
            raise ValueError("Warning ต้องน้อยกว่า Critical")
        return self


class TechnicalNotificationSettingsUpdate(BaseModel):
    daily_enabled: bool = True
    daily_time: time = time(7)
    critical_enabled: bool = True
    recovery_enabled: bool = True
    cooldown_minutes: int = Field(default=60, ge=5, le=1440)
    thresholds: dict[str, TechnicalThresholdUpdate]

    @model_validator(mode="after")
    def validate_threshold_codes(self) -> "TechnicalNotificationSettingsUpdate":
        expected = set(DEFAULT_THRESHOLDS)
        received = set(self.thresholds)
        if received != expected:
            raise ValueError(
                "Threshold ต้องมี cpu, memory, disk, connections และ deadTuples"
            )
        return self


@router.get("/telegram")
def get_telegram_settings(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    return telegram_config(session)


@router.get("/telegram/token")
def get_telegram_token(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    if not get_settings().allow_secret_reveal:
        raise HTTPException(status_code=403, detail="ปิดการเปิดดู Token บน Environment นี้")
    try:
        token = bot_token(session)
    except SettingsCryptoError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not token:
        raise HTTPException(status_code=404, detail="ยังไม่มี Bot Token ที่บันทึกไว้")
    return {"botToken": token}


@router.patch("/telegram")
def update_telegram_settings(
    update: TelegramSettingsUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    actor = "system-settings"
    try:
        if update.bot_token and update.bot_token.strip():
            set_bot_token(session, update.bot_token.strip(), actor)
    except SettingsCryptoError as exc:
        session.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    set_setting(session, GROUP_KEY, update.group_id.strip() or None, secret=False, actor=actor)
    set_setting(
        session,
        NOTIFY_MANUAL_KEY,
        "true" if update.notify_manual_import else "false",
        secret=False,
        actor=actor,
    )
    session.add(
        AuditEvent(
            entity_type="system_setting",
            entity_id="telegram",
            action="update",
            actor=actor,
            before_json=None,
            after_json=json.dumps(
                {
                    "group_id": update.group_id.strip(),
                    "notify_manual_import": update.notify_manual_import,
                    "bot_token_updated": bool(update.bot_token and update.bot_token.strip()),
                },
                ensure_ascii=False,
            ),
        )
    )
    session.commit()
    return telegram_config(session)


@router.post("/telegram/test")
def test_telegram_settings(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    group_id = setting_value(session, GROUP_KEY) or "ยังไม่ได้ตั้งค่า"
    delivery = send_telegram(
        session,
        "📣 ทดสอบการส่งข้อความเข้า Telegram",
        [
            "👥 กลุ่มเป้าหมาย: MT Pulse Notification Group",
            f"🆔 Telegram Group ID: {group_id}",
            "👤 ผู้ทดสอบ: System Settings",
            "✅ สถานะ: ระบบส่งข้อความทดสอบสำเร็จ",
        ],
        force=True,
    )
    session.add(
        AuditEvent(
            entity_type="system_setting",
            entity_id="telegram",
            action="test_notification",
            actor="system-settings",
            before_json=None,
            after_json=json.dumps(
                {"status": delivery.status, "message": delivery.message},
                ensure_ascii=False,
            ),
        )
    )
    session.commit()
    if delivery.status != "sent":
        raise HTTPException(status_code=502, detail=delivery.message)
    return {
        "status": delivery.status,
        "message": "ส่งข้อความทดสอบสำเร็จ",
    }


@router.get("/technical-notifications")
def get_technical_notification_settings(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    return technical_notification_config(session).as_dict()


@router.post("/technical-notifications/check")
def check_technical_health(
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    result = send_manual_technical_health(session, actor="system-settings")
    if result["status"] != "sent":
        raise HTTPException(status_code=502, detail=result["message"])
    return result


@router.patch("/technical-notifications")
def update_technical_notification_settings(
    update: TechnicalNotificationSettingsUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    actor = "system-settings"
    before = technical_notification_config(session).as_dict()
    config = TechnicalNotificationConfig(
        daily_enabled=update.daily_enabled,
        daily_time=update.daily_time,
        critical_enabled=update.critical_enabled,
        recovery_enabled=update.recovery_enabled,
        cooldown_minutes=update.cooldown_minutes,
        thresholds={
            code: (threshold.warning, threshold.critical)
            for code, threshold in update.thresholds.items()
        },
    )
    save_technical_notification_config(session, config, actor=actor)
    after = config.as_dict()
    session.add(
        AuditEvent(
            entity_type="system_setting",
            entity_id="technical_notifications",
            action="update",
            actor=actor,
            before_json=json.dumps(before, ensure_ascii=False),
            after_json=json.dumps(after, ensure_ascii=False),
        )
    )
    session.commit()
    return after
